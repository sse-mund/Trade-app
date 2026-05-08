
from typing import Dict, Any
import logging
import json
import os
from .pattern_agent import PatternAgent
from .quant_agent import QuantAgent
from .sentiment_agent import SentimentAgent
from .analyst_brain import AnalystBrain
from .langgraph_brain import LangGraphBrain

logger = logging.getLogger(__name__)

_TUNED_PARAMS_PATH = os.path.join(os.path.dirname(__file__), "tuned_params.json")


def _load_tuned_params() -> Dict[str, Any]:
    """Load saved optimizer params if present, else return empty dict (defaults)."""
    if os.path.exists(_TUNED_PARAMS_PATH):
        try:
            with open(_TUNED_PARAMS_PATH) as f:
                params = json.load(f)
            logger.info(f"AnalystOrchestrator: loaded tuned params from file: {params}")
            return params
        except Exception as e:
            logger.warning(f"AnalystOrchestrator: could not load tuned_params.json: {e}")
    return {}

class AnalystOrchestrator:
    """
    Coordinator for all trading agents.
    Runs Pattern, Quant, and Sentiment agents, then passes their raw
    outputs to the LangGraph Brain (Ollama LLM) for intelligent synthesis.
    Falls back to the rule-based AnalystBrain if Ollama is unavailable.
    """
    
    def __init__(self):
        self.pattern_agent = PatternAgent("Pattern")
        self.quant_agent = QuantAgent("Quant")
        self.sentiment_agent = SentimentAgent()
        self.langgraph_brain = LangGraphBrain()
        self.expert_brain = AnalystBrain()
        # Load tuned params from optimizer (if available)
        self.tuned_params = _load_tuned_params()

    def analyze(self, ticker: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run all agents, then pass results to the Brain for synthesis.
        Tries LangGraph (Ollama LLM) first, falls back to expert system.

        data must contain:
            'historical_df'  — pandas DataFrame of OHLCV data
            'news_articles'  — list of news article dicts
        """
        logger.info(f"Orchestrating analysis for {ticker}")
        
        # 1. Run individual agents (they crunch the numbers)
        pattern_result   = self.pattern_agent.analyze(ticker, data)
        quant_result     = self.quant_agent.analyze(ticker, data)
        sentiment_result = self.sentiment_agent.analyze(ticker, data)
        
        agent_results = {
            "pattern":   pattern_result,
            "quant":     quant_result,
            "sentiment": sentiment_result,
        }
        
        # 2. Get current price for context
        current_price = None
        df = data.get('historical_df')
        if df is not None and not df.empty:
            current_price = float(df['Close'].iloc[-1])
        
        # 3. Try LangGraph Brain (Ollama LLM) first
        brain_output = self.langgraph_brain.synthesize(
            ticker=ticker,
            agent_results=agent_results,
            current_price=current_price,
            news_articles=data.get('news_articles', []),
        )
        
        strategy_name = "Multi-Agent Consensus (v3 — LangGraph + Ollama)"
        
        # 4. Fall back to expert system if LLM unavailable
        llm_used = brain_output is not None
        if brain_output is None:
            logger.info("LangGraph Brain unavailable, falling back to expert system")
            brain_output = self.expert_brain.synthesize(
                ticker=ticker,
                agent_results=agent_results,
                current_price=current_price,
                news_articles=data.get('news_articles', []),
            )
            strategy_name = "Multi-Agent Consensus (v3 — Expert System)"
        
        logger.info(
            f"Brain synthesis complete for {ticker}: "
            f"{brain_output['recommendation']} "
            f"(confidence={brain_output['confidence']}, "
            f"regime={brain_output.get('market_regime', 'N/A')})"
        )
        
        # 5. Build response
        # Get confluence from expert brain (always available)
        expert_data = self.expert_brain.synthesize(
            ticker=ticker,
            agent_results=agent_results,
            current_price=current_price,
        ) if "confluence" not in brain_output else brain_output

        result = {
            "ticker": ticker,
            "recommendation": brain_output["recommendation"],
            "confidence": brain_output["confidence"],
            "risk_level": brain_output.get("risk_level", "Medium"),
            "target_price": brain_output.get("target_price"),
            "stop_loss": brain_output.get("stop_loss"),
            "time_horizon": brain_output.get("time_horizon", ""),
            "trade_reasoning": brain_output.get("trade_reasoning", ""),
            "agent_results": agent_results,
            "reasoning": brain_output.get("brain_reasoning", ""),
            "brain_reasoning": brain_output.get("brain_reasoning", ""),
            "risk_factors": brain_output.get("risk_factors", []),
            "market_regime": brain_output.get("market_regime", ""),
            "key_insight": brain_output.get("key_insight", ""),
            "confluence": expert_data.get("confluence", {}),
            "strategyName": strategy_name,
            "llm_used": llm_used,  # False when Ollama unavailable and expert system was used
        }
        
        return self._sanitize_results(result)

    def _sanitize_results(self, data: Any) -> Any:
        """Recursively replace NaN/Inf with None and convert numpy types for JSON compatibility."""
        import math
        import numpy as np
        
        if isinstance(data, (float, np.floating)):
            if math.isnan(data) or math.isinf(data):
                return None
            return float(data)
        elif isinstance(data, (int, np.integer)):
            return int(data)
        elif isinstance(data, (bool, np.bool_)):
            return bool(data)
        elif isinstance(data, dict):
            return {k: self._sanitize_results(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_results(i) for i in data]
        return data
