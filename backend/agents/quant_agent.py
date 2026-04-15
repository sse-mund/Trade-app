
from typing import Dict, Any, List
import pandas as pd
import numpy as np
from .base_agent import BaseAgent
from indicators.ichimoku import analyze_ichimoku

class QuantAgent(BaseAgent):
    """
    Agent responsible for quantitative analysis of market data.
    Key responsibilities:
    - Volume analysis (Relative Volume, Trends)
    - Volatility metrics (ATR, Bollinger Band Width)
    - Momentum indicators (RSI, MACD interpretation)
    """
    
    def analyze(self, ticker: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the data using quantitative metrics.
        """
        if 'historical_df' not in data or data['historical_df'].empty:
             return {
                "signal": 0,
                "confidence": 0.0,
                "reasoning": "No historical data available for quant analysis",
                "metrics": {}
            }
            
        df = data['historical_df']
        
        # Default weights (can be overridden by user)
        DEFAULT_WEIGHTS = {
            "momentum": 0.30,
            "ichimoku": 0.25,
            "volume": 0.25,
            "volatility": 0.20,
        }
        user_weights = data.get('quant_weights') or {}
        weights = {**DEFAULT_WEIGHTS, **{k: v for k, v in user_weights.items() if k in DEFAULT_WEIGHTS}}
        
        # Normalize weights to sum to 1.0
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        # 1. Volume Analysis
        volume_signal, volume_metrics = self._analyze_volume(df)
        
        # 2. Volatility Analysis
        volatility_signal, volatility_metrics = self._analyze_volatility(df)
        
        # 3. Momentum Analysis (RSI/MACD)
        momentum_signal, momentum_metrics = self._analyze_momentum(df)
        
        # 4. Ichimoku Cloud Analysis
        ichimoku_signal, ichimoku_metrics = self._analyze_ichimoku(df)
        
        # Combined Signal (Weighted — user-configurable)
        raw_signal = (
            momentum_signal   * weights["momentum"] +
            ichimoku_signal   * weights["ichimoku"] +
            volume_signal     * weights["volume"] +
            volatility_signal * weights["volatility"]
        )
        
        # Determine final signal integer
        final_signal = 0
        if raw_signal > 0.2:
            final_signal = 1
        elif raw_signal < -0.2:
            final_signal = -1
            
        # Reasoning generation
        reasoning_parts = []
        if abs(momentum_signal) > 0.5:
            direction = "Bullish" if momentum_signal > 0 else "Bearish"
            reasoning_parts.append(f"{direction} momentum (RSI/MACD)")
            
        if abs(ichimoku_signal) > 0.3:
            ichi_dir = "Bullish" if ichimoku_signal > 0 else "Bearish"
            reasoning_parts.append(f"{ichi_dir} Ichimoku Cloud signal")

        if abs(volume_signal) > 0.5:
             reasoning_parts.append(f"High relative volume ({volume_metrics['relative_volume']:.1f}x)")
             
        if volatility_metrics.get('is_squeezing'):
            reasoning_parts.append("Volatility squeeze detected")
            
        # Round weights for clean display
        display_weights = {k: round(v * 100) for k, v in weights.items()}
            
        return {
            "signal": final_signal,
            "confidence": self._normalize_confidence(abs(raw_signal) + 0.2),
            "reasoning": "; ".join(reasoning_parts) if reasoning_parts else "Neutral quantitative metrics",
            "metrics": {
                **volume_metrics,
                **volatility_metrics,
                **momentum_metrics,
                **ichimoku_metrics,
            },
            "weights": display_weights,
        }


    def _analyze_volume(self, df: pd.DataFrame) -> tuple[float, Dict]:
        """
        Analyze volume trends and relative volume.
        Migrations from ChartGenerator.calculate_volume_analysis
        """
        if len(df) < 20:
            return 0.0, {}
            
        current_volume = df['Volume'].iloc[-1]
        avg_volume = df['Volume'].rolling(window=20).mean().iloc[-1]
        
        rel_vol = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        signal = 0.0
        # High relative volume confirms trends
        if rel_vol > 1.5:
            # Check price direction
            price_change = df['Close'].iloc[-1] - df['Open'].iloc[-1]
            if price_change > 0:
                signal = 0.5 # Bullish volume
            else:
                signal = -0.5 # Bearish volume
                
        return signal, {"relative_volume": rel_vol, "volume_ma": avg_volume}

    def _analyze_volatility(self, df: pd.DataFrame) -> tuple[float, Dict]:
        """
        Analyze volatility using ATR and Bollinger Bands.
        """
        if len(df) < 20:
             return 0.0, {}
             
        # Bollinger Band Width
        sma = df['Close'].rolling(window=20).mean()
        std = df['Close'].rolling(window=20).std()
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        
        bb_width = (upper - lower) / sma
        current_width = bb_width.iloc[-1]
        avg_width = bb_width.rolling(window=20).mean().iloc[-1]
        
        is_squeezing = current_width < (avg_width * 0.8)
        
        signal = 0.0
        # Squeeze often creates explosive moves, but direction is unknown until breakout
        # Low volatility = 0 signal but useful context
        
        return signal, {"bb_width": current_width, "is_squeezing": is_squeezing}

    def _analyze_momentum(self, df: pd.DataFrame) -> tuple[float, Dict]:
        """
        Analyze RSI and MACD for momentum.
        """
        if len(df) < 26:
             return 0.0, {}
             
        # RSI (Assuming already calculated or calculate here)
        # Using simple calculation for self-containment
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]
        
        signal = 0.0
        if current_rsi < 30:
            signal = 0.8 # Oversold -> Buy
        elif current_rsi > 70:
            signal = -0.8 # Overbought -> Sell
            
        return signal, {"rsi": current_rsi}

    def _analyze_ichimoku(self, df: pd.DataFrame) -> tuple[float, Dict]:
        """
        Analyze Ichimoku Cloud for trend direction, momentum, and S/R.
        """
        result = analyze_ichimoku(df)
        
        metrics = {
            "ichimoku_trend": result["trend"],
            "ichimoku_momentum": result["momentum"],
            "ichimoku_signal": result["signal"],
            "ichimoku_cloud_support": result["cloud_support"],
            "ichimoku_cloud_resistance": result["cloud_resistance"],
        }
        
        # Pass through the detailed metrics too
        if result.get("metrics"):
            metrics.update({f"ichimoku_{k}": v for k, v in result["metrics"].items()})
        
        return result["signal"], metrics
