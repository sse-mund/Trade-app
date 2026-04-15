"""
LangGraph Brain — LLM-powered agent graph using Ollama.

A LangGraph state machine that:
1. Collects agent results (Pattern, Quant, Sentiment)
2. Sends a structured prompt to Ollama's local LLM
3. Returns intelligent, context-aware reasoning

Falls back gracefully to the rule-based AnalystBrain if Ollama is unavailable.
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional, TypedDict, Annotated

from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# LangGraph State
# ────────────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    """State that flows through the LangGraph nodes."""
    ticker: str
    current_price: Optional[float]
    pattern_result: Dict[str, Any]
    quant_result: Dict[str, Any]
    sentiment_result: Dict[str, Any]
    news_headlines: List[str]
    # Output from LLM
    llm_output: Optional[Dict[str, Any]]
    error: Optional[str]


# ────────────────────────────────────────────────────────────────────────────
# LLM Prompt
# ────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert stock market analyst. You synthesize data from three analysis agents:
- Pattern Agent: identifies chart patterns, support/resistance, breakouts, trend, Ichimoku Cloud
- Quant Agent: analyzes RSI, volume, volatility, Bollinger Bands, Ichimoku Cloud momentum
- Sentiment Agent: scores news sentiment from articles

Analyze the data provided and respond with a JSON object (no markdown, no code fences) containing EXACTLY these keys:
{
  "recommendation": "BUY" or "SELL" or "HOLD" (REQUIRED - must be one of these three exact strings),
  "confidence": 0.0 to 1.0,
  "target_price": a realistic target price number,
  "stop_loss": a stop loss price number,
  "time_horizon": "1-3 days" or "1-2 weeks" or "2-4 weeks" or "1-3 months",
  "trade_reasoning": explain exactly WHY you chose these specific target and stop loss prices — which support/resistance level, technical indicator, or pattern justifies each price,
  "risk_level": "Low" or "Medium" or "High",
  "market_regime": one of "Trending Up", "Trending Down", "Ranging", "Volatile", "Breakout", "Squeeze",
  "key_insight": a single sentence — the most important takeaway for the trader,
  "brain_reasoning": a 3-5 sentence narrative explaining your analysis with specific numbers,
  "risk_factors": an array of 1-4 specific risk strings
}

IMPORTANT: The "recommendation" field is MANDATORY. You MUST set it to exactly "BUY", "SELL", or "HOLD". Never omit it.

CRITICAL RULES for target_price and stop_loss:
- target_price MUST be based on a specific support or resistance level from the data. For BUY, use the nearest resistance above current price. For SELL, use the nearest support below.
- stop_loss MUST be based on a specific support or resistance level. For BUY, place below the nearest support with a small buffer. For SELL, place above the nearest resistance.
- If no levels are available, use a conservative 3-5% from current price and state this in trade_reasoning.
- NEVER invent arbitrary round numbers. Every price must be justified by actual data.
- trade_reasoning must explicitly state which level or indicator determined each price.

Be specific — reference actual numbers (RSI values, price levels, volume ratios) in your reasoning.
Do NOT include any text outside the JSON object."""


def _build_analysis_prompt(state: AgentState) -> str:
    """Build the user prompt from agent results."""
    pattern = state["pattern_result"]
    quant = state["quant_result"]
    sentiment = state["sentiment_result"]

    p_metrics = pattern.get("metrics", {})
    q_metrics = quant.get("metrics", {})
    s_metrics = sentiment.get("metrics", {})

    sections = [
        f"## Stock: {state['ticker']}",
    ]

    if state.get("current_price"):
        sections.append(f"Current Price: ${state['current_price']:.2f}")

    sections.append(f"""
## Pattern Agent (Signal: {pattern.get('signal', 0)}, Confidence: {pattern.get('confidence', 0):.2f})
- Trend: {p_metrics.get('trend', 'unknown')}
- Ichimoku Trend: {p_metrics.get('ichimoku_trend', 'N/A')}
- Ichimoku Momentum: {p_metrics.get('ichimoku_momentum', 'N/A')}
- Cloud Support: {p_metrics.get('cloud_support', 'N/A')}
- Cloud Resistance: {p_metrics.get('cloud_resistance', 'N/A')}
- Breakout: {p_metrics.get('breakout', {}).get('type', 'none')}
- Support levels: {p_metrics.get('support_levels', [])}
- Resistance levels: {p_metrics.get('resistance_levels', [])}
- Reasoning: {pattern.get('reasoning', 'N/A')}

## Quant Agent (Signal: {quant.get('signal', 0)}, Confidence: {quant.get('confidence', 0):.2f})
- RSI: {q_metrics.get('rsi', 'N/A')}
- Relative Volume: {q_metrics.get('relative_volume', 'N/A')}
- BB Width: {q_metrics.get('bb_width', 'N/A')}
- Squeeze: {q_metrics.get('is_squeezing', False)}
- Ichimoku Signal: {q_metrics.get('ichimoku_signal', 'N/A')}
- Ichimoku Trend: {q_metrics.get('ichimoku_trend', 'N/A')}
- Ichimoku TK Cross: {q_metrics.get('ichimoku_tk_cross', 'N/A')}
- Reasoning: {quant.get('reasoning', 'N/A')}

## Sentiment Agent (Signal: {sentiment.get('signal', 0)}, Confidence: {sentiment.get('confidence', 0):.2f})
- Article count: {s_metrics.get('article_count', 0)}
- Avg sentiment: {s_metrics.get('avg_sentiment', 'N/A')}
- Positive: {s_metrics.get('positive_count', 0)}, Negative: {s_metrics.get('negative_count', 0)}, Neutral: {s_metrics.get('neutral_count', 0)}
- Reasoning: {sentiment.get('reasoning', 'N/A')}""")

    if state.get("news_headlines"):
        sections.append(f"\n## Recent Headlines:\n" + "\n".join(
            f"- {h}" for h in state["news_headlines"][:5]
        ))

    return "\n".join(sections)


# ────────────────────────────────────────────────────────────────────────────
# LangGraph Nodes
# ────────────────────────────────────────────────────────────────────────────

def _safe_json_parse(content: str) -> Optional[dict]:
    """
    Try to parse JSON content. If it fails (e.g. truncated response),
    attempt to close the JSON object and try again before giving up.
    """
    # Attempt 1: direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Attempt 2: close unclosed JSON object (handle LLM token cutoff)
    try:
        # Count open braces to determine how many closing braces needed
        opens = content.count("{")
        closes = content.count("}")
        if opens > closes:
            # Close any open string first (look for unclosed quote in last segment)
            repaired = content.rstrip().rstrip(",")
            # If the last char is in the middle of a string value, close it
            if repaired.count('"') % 2 != 0:
                repaired += '"'
            repaired += "}" * (opens - closes)
            return json.loads(repaired)
    except (json.JSONDecodeError, Exception):
        pass

    return None


def synthesize_with_llm(state: AgentState) -> dict:
    """
    Node: Send agent metrics to Ollama LLM for synthesis.
    Returns updated state with llm_output or error.
    """
    try:
        from langchain_ollama import ChatOllama

        model_name = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        llm = ChatOllama(
            model=model_name,
            temperature=0.3,
            num_predict=2048,  # Increased: 600 was causing truncated JSON responses
            format="json",
        )

        prompt = _build_analysis_prompt(state)

        messages = [
            ("system", SYSTEM_PROMPT),
            ("human", prompt),
        ]

        logger.info(f"LangGraph Brain: Sending analysis to Ollama ({model_name})...")
        response = llm.invoke(messages)

        # Parse JSON from response
        content = response.content.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        parsed = _safe_json_parse(content)
        if parsed is None:
            logger.warning(f"LangGraph Brain: Raw LLM content (unparseable): {content[:500]}")
            raise json.JSONDecodeError("Could not parse or repair LLM JSON", content, 0)

        rec = parsed.get('recommendation')
        logger.info(f"LangGraph Brain: LLM returned recommendation={rec}")

        # Validate the parsed output has required fields
        if rec is None:
            logger.warning(f"LangGraph Brain: LLM JSON keys: {list(parsed.keys())}")
            logger.warning(f"LangGraph Brain: Raw LLM content: {content[:500]}")
            # Try common alternative keys the model might use
            for alt_key in ['Recommendation', 'action', 'Action', 'signal', 'Signal', 'decision', 'Decision']:
                if alt_key in parsed:
                    parsed['recommendation'] = parsed[alt_key]
                    logger.info(f"LangGraph Brain: Found recommendation under alt key '{alt_key}': {parsed[alt_key]}")
                    break

        return {"llm_output": parsed, "error": None}

    except json.JSONDecodeError as e:
        logger.warning(f"LangGraph Brain: Failed to parse LLM JSON: {e}")
        return {"llm_output": None, "error": f"JSON parse error: {e}"}
    except Exception as e:
        logger.warning(f"LangGraph Brain: Ollama error: {e}")
        return {"llm_output": None, "error": str(e)}


def format_output(state: AgentState) -> dict:
    """
    Node: Format the final output. If LLM failed, error is set
    and the caller (orchestrator) falls back to expert system.
    """
    return state


# ────────────────────────────────────────────────────────────────────────────
# Build the Graph
# ────────────────────────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    """Build the LangGraph agent graph."""
    graph = StateGraph(AgentState)

    graph.add_node("synthesize", synthesize_with_llm)
    graph.add_node("output", format_output)

    graph.set_entry_point("synthesize")
    graph.add_edge("synthesize", "output")
    graph.add_edge("output", END)

    return graph.compile()


# Module-level compiled graph (singleton)
_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────

class LangGraphBrain:
    """
    LangGraph-powered brain that uses Ollama for LLM reasoning.
    Falls back gracefully if Ollama is unavailable.
    """

    def __init__(self):
        self.available = True
        try:
            from langchain_ollama import ChatOllama
            logger.info("LangGraphBrain: langchain-ollama available")
        except ImportError:
            self.available = False
            logger.warning("LangGraphBrain: langchain-ollama not installed")

    def synthesize(
        self,
        ticker: str,
        agent_results: Dict[str, Dict[str, Any]],
        current_price: Optional[float] = None,
        news_articles: Optional[List[Dict]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Run the LangGraph brain.

        Returns a dict with brain fields, or None if LLM is unavailable
        (so the orchestrator can fall back to expert system).
        """
        if not self.available:
            return None

        # Extract news headlines for context
        headlines = []
        if news_articles:
            headlines = [
                a.get("headline", "")
                for a in news_articles[:5]
                if a.get("headline")
            ]

        # Build initial state
        initial_state: AgentState = {
            "ticker": ticker,
            "current_price": current_price,
            "pattern_result": agent_results.get("pattern", {}),
            "quant_result": agent_results.get("quant", {}),
            "sentiment_result": agent_results.get("sentiment", {}),
            "news_headlines": headlines,
            "llm_output": None,
            "error": None,
        }

        try:
            graph = get_graph()
            result = graph.invoke(initial_state)

            llm_output = result.get("llm_output")
            err = result.get("error")

            if err:
                logger.warning(f"LangGraphBrain: LLM error: {err}, falling back to expert system")
                return None

            if llm_output is None:
                logger.warning("LangGraphBrain: LLM returned no output, falling back to expert system")
                return None

            llm = llm_output

            # If LLM returned empty JSON, fall back to expert system
            if not llm or len(llm) == 0:
                logger.warning("LangGraphBrain: LLM returned empty JSON '{}', falling back to expert system")
                return None

            # Normalize and validate the LLM output — search multiple possible keys
            recommendation = None
            for key in ['recommendation', 'Recommendation', 'action', 'Action', 'signal_type', 'decision', 'Decision', 'trade_action', 'position']:
                val = llm.get(key)
                if val is not None:
                    recommendation = str(val).upper().strip()
                    break

            # If still None, search inside any nested dicts (some models nest the output)
            if recommendation is None:
                for key, val in llm.items():
                    if isinstance(val, dict):
                        for sub_key in ['recommendation', 'action', 'decision']:
                            if sub_key in val:
                                recommendation = str(val[sub_key]).upper().strip()
                                logger.info(f"LangGraphBrain: Found recommendation in nested '{key}.{sub_key}': {recommendation}")
                                break
                    if recommendation is not None:
                        break

            # Last resort: derive from agent signals if LLM completely failed to provide recommendation
            if recommendation is None or recommendation not in ("BUY", "SELL", "HOLD"):
                # Derive from the actual agent signals passed to this method
                p_signal = agent_results.get("pattern", {}).get("signal", 0)
                q_signal = agent_results.get("quant", {}).get("signal", 0)
                s_signal = agent_results.get("sentiment", {}).get("signal", 0)
                avg_signal = (p_signal + q_signal + s_signal) / 3
                if avg_signal > 0.15:
                    recommendation = "BUY"
                elif avg_signal < -0.15:
                    recommendation = "SELL"
                else:
                    recommendation = "HOLD"
                logger.warning(f"LangGraphBrain: Recommendation missing from LLM, derived '{recommendation}' from agent signals (avg={avg_signal:.2f})")


            confidence = float(llm.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            risk_level = str(llm.get("risk_level", "Medium"))
            if risk_level not in ("Low", "Medium", "High"):
                risk_level = "Medium"

            # Parse trade parameters
            target_price = llm.get("target_price")
            stop_loss = llm.get("stop_loss")
            if target_price is not None:
                try:
                    target_price = round(float(target_price), 2)
                except (ValueError, TypeError):
                    target_price = None
            if stop_loss is not None:
                try:
                    stop_loss = round(float(stop_loss), 2)
                except (ValueError, TypeError):
                    stop_loss = None

            time_horizon = str(llm.get("time_horizon", ""))
            trade_reasoning = str(llm.get("trade_reasoning", ""))

            return {
                "recommendation": recommendation,
                "confidence": round(confidence, 2),
                "risk_level": risk_level,
                "target_price": target_price,
                "stop_loss": stop_loss,
                "time_horizon": time_horizon,
                "trade_reasoning": trade_reasoning,
                "brain_reasoning": str(llm.get("brain_reasoning", "")),
                "risk_factors": list(llm.get("risk_factors", [])),
                "market_regime": str(llm.get("market_regime", "")),
                "key_insight": str(llm.get("key_insight", "")),
            }

        except Exception as e:
            logger.warning(f"LangGraphBrain error: {e}")
            return None
