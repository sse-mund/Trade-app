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
- Pattern Agent: identifies chart patterns, support/resistance, breakouts, trend
- Quant Agent: analyzes RSI, volume, volatility, Bollinger Bands
- Sentiment Agent: scores news sentiment from articles

Analyze the data provided and respond with ONLY a JSON object containing:
{
  "recommendation": "BUY" or "SELL" or "HOLD",
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

Rules:
- "recommendation" MUST be exactly "BUY", "SELL", or "HOLD". Never omit it.
- target_price and stop_loss should be based on support/resistance levels from the data.
- Be specific — reference actual numbers (RSI values, price levels, volume ratios).
- Do NOT include any text outside the JSON object."""


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
- Breakout: {p_metrics.get('breakout', {}).get('type', 'none')}
- Support levels: {p_metrics.get('support_levels', [])}
- Resistance levels: {p_metrics.get('resistance_levels', [])}
- Reasoning: {pattern.get('reasoning', 'N/A')}

## Quant Agent (Signal: {quant.get('signal', 0)}, Confidence: {quant.get('confidence', 0):.2f})
- RSI: {q_metrics.get('rsi', 'N/A')}
- Relative Volume: {q_metrics.get('relative_volume', 'N/A')}
- BB Width: {q_metrics.get('bb_width', 'N/A')}
- Squeeze: {q_metrics.get('is_squeezing', False)}
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

def _fix_unquoted_values(text):
    """Fix unquoted string values and missing commas in malformed LLM JSON."""
    import re
    lines = text.split('\n')
    fixed_lines = []
    for line in lines:
        stripped = line.strip()
        m = re.match(r'^(\s*"(\w+)":\s*)(.+)$', stripped)
        if m:
            prefix = m.group(1)
            value_part = m.group(3).strip()
            if (value_part.startswith('"') or
                value_part.startswith('{') or
                value_part.startswith('[') or
                value_part in ('true', 'true,', 'false', 'false,', 'null', 'null,') or
                re.match(r'^-?\d', value_part)):
                fixed_lines.append(line)
            else:
                has_comma = value_part.endswith(',')
                if has_comma:
                    value_part = value_part[:-1].strip()
                value_part = value_part.replace('\\', '\\\\').replace('"', '\\"')
                leading_ws = line[:len(line) - len(line.lstrip())]
                new_line = f'{leading_ws}{prefix}"{value_part}"{"," if has_comma else ""}'
                fixed_lines.append(new_line)
        else:
            fixed_lines.append(line)
    result_lines = []
    for i, line in enumerate(fixed_lines):
        stripped = line.rstrip()
        if (stripped and
            not stripped.endswith(',') and
            not stripped.endswith('{') and
            not stripped.endswith('[') and
            stripped != '}' and
            stripped != ']'):
            for j in range(i + 1, len(fixed_lines)):
                next_stripped = fixed_lines[j].strip()
                if next_stripped:
                    if re.match(r'^"(\w+)":', next_stripped):
                        line = line.rstrip() + ','
                    break
        result_lines.append(line)
    return '\n'.join(result_lines)
    """
    Fix unquoted string values in malformed JSON from LLMs.
    
    Handles patterns like:
        "trade_reasoning": Target price at $260...
    Converts to:
        "trade_reasoning": "Target price at $260..."
    """
    import re

    # Pattern: "key": followed by a value that is NOT:
    #   - a quote (already a string)
    #   - a digit/minus (number)
    #   - true/false/null (boolean/null)
    #   - { or [ (object/array)
    # Capture everything until the next "key": or end of object
    def fix_match(m):
        key = m.group(1)
        value = m.group(2).strip()
        # Remove trailing comma if present
        value = value.rstrip(',')
        # Escape any quotes inside the value
        value = value.replace('"', '\\"')
        return f'"{key}": "{value}"'

    # Match: "key": <unquoted text> up to the next "key": or closing brace
    pattern = r'"(\w+)":\s*(?!["{\[\dtfn-])(.+?)(?=\s*"\w+":|\s*[}])'
    fixed = re.sub(pattern, fix_match, text, flags=re.DOTALL)
    
    return fixed


def _safe_json_parse(content: str) -> Optional[dict]:
    """
    Try to parse JSON content. If it fails (e.g. truncated response),
    attempt multiple repair strategies before giving up.
    """
    # Attempt 1: direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Attempt 2: fix unquoted string values
    try:
        fixed = _fix_unquoted_values(content)
        return json.loads(fixed)
    except (json.JSONDecodeError, Exception):
        pass

    # Attempt 3: close unclosed JSON object (handle LLM token cutoff)
    try:
        repaired = content.rstrip().rstrip(",")
        # Fix unquoted values first
        repaired = _fix_unquoted_values(repaired)
        opens = repaired.count("{")
        closes = repaired.count("}")
        if opens > closes:
            if repaired.count('"') % 2 != 0:
                repaired += '"'
            repaired += "}" * (opens - closes)
            return json.loads(repaired)
    except (json.JSONDecodeError, Exception):
        pass

    # Attempt 4: fix unquoted values + close truncated braces
    try:
        repaired = _fix_unquoted_values(content)
        repaired = repaired.rstrip().rstrip(",")
        opens = repaired.count("{")
        closes = repaired.count("}")
        if opens > closes:
            if repaired.count('"') % 2 != 0:
                repaired += '"'
            repaired += "}" * (opens - closes)
            return json.loads(repaired)
    except (json.JSONDecodeError, Exception):
        pass

    return None


def _extract_json_from_text(text: str) -> Optional[dict]:
    """
    Extract a JSON object from raw LLM text that may contain
    surrounding prose, markdown fences, unquoted values, etc.
    """
    import re

    text = text.strip()

    # Strip markdown code fences — check ```json BEFORE bare ```
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Try direct parse first
    result = _safe_json_parse(text)
    if result and len(result) > 0:
        return result

    # Try to find a JSON object in the text using regex
    json_match = re.search(r'\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}', text, re.DOTALL)
    if json_match:
        result = _safe_json_parse(json_match.group())
        if result and len(result) > 0:
            return result

    return None


def synthesize_with_llm(state: AgentState) -> dict:
    """
    Node: Send agent metrics to Ollama LLM for synthesis.

    Strategy:
    1. Use the base model (llama3.2:3b) WITHOUT format="json"
       to avoid empty {} responses.
    2. Extract JSON from raw text ourselves.
    """
    try:
        from langchain_ollama import ChatOllama

        model_name = "llama3.2:3b"

        prompt = _build_analysis_prompt(state)
        messages = [
            ("system", SYSTEM_PROMPT),
            ("human", prompt),
        ]

        parsed = None
        try:
            llm = ChatOllama(
                model=model_name,
                temperature=0.3,
                num_predict=4096,
            )

            logger.info(f"LangGraph Brain: Sending analysis to Ollama ({model_name})...")
            response = llm.invoke(messages)
            content = response.content.strip()

            logger.info(f"LangGraph Brain: Raw response from {model_name} ({len(content)} chars): {content[:500]}")

            parsed = _extract_json_from_text(content)

            if parsed and len(parsed) > 0:
                logger.info(f"LangGraph Brain: Got {len(parsed)} keys from {model_name}")
            else:
                logger.warning(f"LangGraph Brain: {model_name} returned no extractable JSON")
                parsed = None

        except Exception as model_err:
            logger.warning(f"LangGraph Brain: {model_name} failed: {model_err}")
            parsed = None

        if parsed is None or len(parsed) == 0:
            return {"llm_output": None, "error": "Model returned empty JSON"}


        rec = parsed.get('recommendation')
        logger.info(f"LangGraph Brain: LLM returned recommendation={rec}")

        # Validate the parsed output has required fields
        if rec is None:
            logger.warning(f"LangGraph Brain: LLM JSON keys: {list(parsed.keys())}")
            for alt_key in ['Recommendation', 'action', 'Action', 'signal', 'Signal', 'decision', 'Decision']:
                if alt_key in parsed:
                    parsed['recommendation'] = parsed[alt_key]
                    logger.info(f"LangGraph Brain: Found recommendation under alt key '{alt_key}': {parsed[alt_key]}")
                    break

        return {"llm_output": parsed, "error": None}

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
            import traceback
            logger.warning(f"LangGraphBrain error: {e}\n{traceback.format_exc()}")
            return None
