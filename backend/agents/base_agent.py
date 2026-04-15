
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseAgent(ABC):
    """
    Abstract base class for all trading strategy agents.
    Ensures consistent interface for the Orchestrator.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.confidence = 0.0
        
    @abstractmethod
    def analyze(self, ticker: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the given data and return agent's recommendation.
        
        Args:
            ticker: Stock symbol
            data: Dictionary containing all necessary data (price history, news, etc.)
            
        Returns:
            Dict containing:
            - signal: int (-1 for sell, 0 for hold, 1 for buy)
            - confidence: float (0.0 to 1.0)
            - reasoning: str (explanation of the decision)
            - metrics: dict (agent-specific metrics)
        """
        pass
        
    def _normalize_confidence(self, raw_score: float) -> float:
        """Utility to clip confidence between 0.0 and 1.0"""
        return max(0.0, min(1.0, raw_score))
