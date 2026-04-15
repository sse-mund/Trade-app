import pandas as pd
import numpy as np
import math
import yfinance as yf
import logger_config
from database import StockDatabase
from typing import Dict, List, Tuple, Optional

logger = logger_config.get_logger(__name__)

# Intraday interval → (yfinance fetch period string, window for support/resistance)
INTRADAY_CONFIG = {
    '5m':  {'period': '5d',  'sr_window': 10},
    '15m': {'period': '5d',  'sr_window': 8},
    '1h':  {'period': '30d', 'sr_window': 6},
}

def _sv(v):
    """Safe value: convert NaN / Inf to None so JSON serialisation never fails."""
    if v is None:
        return None
    try:
        if math.isnan(v) or math.isinf(v):
            return None
    except (TypeError, ValueError):
        pass
    return v

class ChartGenerator:
    """Generates comprehensive chart data with technical indicators."""
    
    def __init__(self):
        """Initialize chart generator with database connection."""
        self.db = StockDatabase()
        logger.info("ChartGenerator initialized")
    
    def calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> pd.DataFrame:
        """Calculate Bollinger Bands."""
        logger.info(f"Calculating Bollinger Bands with period={period}, std_dev={std_dev}")
        
        df = df.copy()
        df['BB_Middle'] = df['Close'].rolling(window=period).mean()
        rolling_std = df['Close'].rolling(window=period).std()
        df['BB_Upper'] = df['BB_Middle'] + (rolling_std * std_dev)
        df['BB_Lower'] = df['BB_Middle'] - (rolling_std * std_dev)
        df['BB_Width'] = df['BB_Upper'] - df['BB_Lower']
        
        return df
    
    def calculate_volume_analysis(self, df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """Calculate volume analysis metrics."""
        logger.info(f"Calculating volume analysis with period={period}")
        
        df = df.copy()
        df['Volume_MA'] = df['Volume'].rolling(window=period).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']
        
        return df
    
    def detect_support_resistance(self, df: pd.DataFrame, window: int = 20) -> Tuple[List[float], List[float]]:
        """Detect support and resistance levels."""
        logger.info(f"Detecting support and resistance levels with window={window}")
        
        # Get recent data for analysis
        recent_df = df.tail(100)
        
        # Find local minima (support) and maxima (resistance)
        support_levels = []
        resistance_levels = []
        
        for i in range(window, len(recent_df) - window):
            # Check for local minimum (support)
            if recent_df['Low'].iloc[i] == recent_df['Low'].iloc[i-window:i+window].min():
                support_levels.append(float(recent_df['Low'].iloc[i]))
            
            # Check for local maximum (resistance)
            if recent_df['High'].iloc[i] == recent_df['High'].iloc[i-window:i+window].max():
                resistance_levels.append(float(recent_df['High'].iloc[i]))
        
        # Remove duplicates, handle NaNs, and sort
        support_levels = [s for s in support_levels if not (np.isnan(s) or np.isinf(s))]
        resistance_levels = [r for r in resistance_levels if not (np.isnan(r) or np.isinf(r))]
        
        support_levels = sorted(list(set([round(s, 2) for s in support_levels])))
        resistance_levels = sorted(list(set([round(r, 2) for r in resistance_levels])))
        
        # Keep only the most significant levels (top 3 of each)
        support_levels = support_levels[:3] if len(support_levels) > 3 else support_levels
        resistance_levels = resistance_levels[-3:] if len(resistance_levels) > 3 else resistance_levels
        
        logger.info(f"Found {len(support_levels)} support and {len(resistance_levels)} resistance levels")
        return support_levels, resistance_levels
    
    def calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators."""
        logger.info("Calculating all technical indicators")
        
        df = df.copy()
        
        # Moving Averages
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['SMA_200'] = df['Close'].rolling(window=200).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
        
        # Bollinger Bands
        df = self.calculate_bollinger_bands(df)
        
        # Volume Analysis
        df = self.calculate_volume_analysis(df)
        
        logger.info("All indicators calculated successfully")
        return df
    
    def generate_chart_data(self, ticker: str, period_days: int = 365) -> Dict:
        """Generate comprehensive chart data for a ticker."""
        logger.info(f"Generating chart data for {ticker}, period={period_days} days")
        
        try:
            # Fetch data from database
            df = self.db.get_historical_data(ticker)
            
            if df.empty:
                logger.warning(f"No data found for {ticker}")
                return {"error": f"No data found for {ticker}"}
            
            # Rename columns to match expected format
            df = df.rename(columns={
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            })
            
            # Ensure index is datetime and handle timezones
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            # Standardize to naive UTC for calculations
            if df.index.tz is not None:
                df.index = df.index.tz_convert('UTC').tz_localize(None)
            
            # Filter by period
            # We use naive UTC for index, so cutoff must be naive UTC too
            cutoff_date = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=period_days)
            today = pd.Timestamp.utcnow().tz_localize(None)
            df = df[(df.index >= cutoff_date) & (df.index <= today)]
            
            if df.empty:
                logger.warning(f"No data in requested period for {ticker}")
                return {"error": f"No data in requested period for {ticker}"}
            
            logger.info(f"Processing {len(df)} records for {ticker}")
            
            # Calculate all indicators
            df = self.calculate_all_indicators(df)
            
            # Detect support and resistance
            support_levels, resistance_levels = self.detect_support_resistance(df)
            
            # Prepare data for charts (use full requested period)
            chart_df = df.copy()
            
            # Round data before replacing NaNs to ensure cleaner output
            cols_to_round_2 = ['Open', 'High', 'Low', 'Close', 'SMA_20', 'SMA_50', 'SMA_200', 
                              'BB_Upper', 'BB_Middle', 'BB_Lower', 'RSI']
            cols_to_round_4 = ['MACD', 'MACD_Signal', 'MACD_Histogram']
            
            for col in cols_to_round_2:
                if col in chart_df.columns:
                    chart_df[col] = chart_df[col].round(2)
            
            for col in cols_to_round_4:
                if col in chart_df.columns:
                    chart_df[col] = chart_df[col].round(4)

            # Replace NaN/Infinity with None for valid JSON serialization
            chart_df = chart_df.replace([np.inf, -np.inf], np.nan)
            chart_df = chart_df.astype(object).where(pd.notnull(chart_df), None)
            
            # Convert dates to strings
            dates = chart_df.index.strftime('%Y-%m-%d').tolist()
            
            # Price chart data - convert to array of objects for Recharts
            price_data = [
                {
                    'Date': date,
                    'Close':   _sv(close),
                    'Open':    _sv(open_val),
                    'High':    _sv(high),
                    'Low':     _sv(low),
                    'SMA_20':  _sv(sma20),
                    'SMA_50':  _sv(sma50),
                    'SMA_200': _sv(sma200),
                }
                for date, close, open_val, high, low, sma20, sma50, sma200 in zip(
                    dates,
                    chart_df['Close'].tolist(),
                    chart_df['Open'].tolist(),
                    chart_df['High'].tolist(),
                    chart_df['Low'].tolist(),
                    chart_df['SMA_20'].tolist(),
                    chart_df['SMA_50'].tolist(),
                    chart_df['SMA_200'].tolist(),
                )
            ]
            
            # Bollinger Bands data
            bollinger_data = [
                {
                    'Date': date,
                    'Upper':  _sv(upper),
                    'Middle': _sv(middle),
                    'Lower':  _sv(lower),
                    'Close':  _sv(close),
                }
                for date, upper, middle, lower, close in zip(
                    dates,
                    chart_df['BB_Upper'].tolist(),
                    chart_df['BB_Middle'].tolist(),
                    chart_df['BB_Lower'].tolist(),
                    chart_df['Close'].tolist(),
                )
            ]
            
            # Volume data
            volume_data = [
                {
                    'Date': date,
                    'Volume':    _sv(volume),
                    'Volume_MA': _sv(vol_ma),
                }
                for date, volume, vol_ma in zip(
                    dates,
                    chart_df['Volume'].tolist(),
                    chart_df['Volume_MA'].tolist(),
                )
            ]
            
            
            # RSI data
            rsi_data = [
                {
                    'Date': date,
                    'RSI': _sv(rsi),
                }
                for date, rsi in zip(
                    dates,
                    chart_df['RSI'].tolist(),
                )
            ]
            
            # MACD data
            macd_data = [
                {
                    'Date':      date,
                    'MACD':      _sv(macd),
                    'Signal':    _sv(signal),
                    'Histogram': _sv(histogram),
                }
                for date, macd, signal, histogram in zip(
                    dates,
                    chart_df['MACD'].tolist(),
                    chart_df['MACD_Signal'].tolist(),
                    chart_df['MACD_Histogram'].tolist(),
                )
            ]
            
            # Helper for safe scalar access
            def get_safe_scalar(series, decimals=2):
                val = series.iloc[-1]
                if pd.isna(val) or np.isinf(val):
                    return None
                return round(float(val), decimals)

            # Current values
            current_price = get_safe_scalar(df['Close'])
            current_rsi = get_safe_scalar(df['RSI'])
            current_macd = get_safe_scalar(df['MACD'], 4)
            current_macd_signal = get_safe_scalar(df['MACD_Signal'], 4)
            
            # Trend analysis
            sma_20_current = get_safe_scalar(df['SMA_20'])
            sma_50_current = get_safe_scalar(df['SMA_50'])
            sma_200_current = get_safe_scalar(df['SMA_200'])
            
            trend = "Neutral"
            if current_price is not None and sma_50_current is not None and sma_200_current is not None:
                if current_price > sma_50_current > sma_200_current:
                    trend = "Bullish"
                elif current_price < sma_50_current < sma_200_current:
                    trend = "Bearish"
            
            # Compile response
            response = {
                'ticker': ticker,
                'current_price': current_price,
                'data_points': len(chart_df),
                'date_range': {
                    'start': dates[0],
                    'end': dates[-1]
                },
                'charts': {
                    'price': price_data,
                    'bollinger': bollinger_data,
                    'volume': volume_data,
                    'rsi': rsi_data,
                    'macd': macd_data,
                },
                'indicators': {
                    'rsi': current_rsi,
                    'macd': current_macd,
                    'macd_signal': current_macd_signal,
                    'sma_20': sma_20_current,
                    'sma_50': sma_50_current,
                    'sma_200': sma_200_current,
                },
                'levels': {
                    'support': support_levels,
                    'resistance': resistance_levels,
                },
                'trend': trend
            }
            
            logger.info(f"Chart data generated successfully for {ticker}")
            return response
            
        except Exception as e:
            logger.error(f"Error generating chart data for {ticker}: {str(e)}", exc_info=True)
            return {"error": str(e)}
    def generate_intraday_chart_data(self, ticker: str, interval: str) -> Dict:
        """
        Generate chart data for intraday intervals (5m, 15m, 1h).
        Fetches directly from yfinance — no DB involved.
        Returns the same response shape as generate_chart_data().
        """
        if interval not in INTRADAY_CONFIG:
            return {"error": f"Unsupported interval '{interval}'. Use: {list(INTRADAY_CONFIG.keys())}"}

        cfg = INTRADAY_CONFIG[interval]
        logger.info(f"Fetching intraday data for {ticker} @ {interval} (period={cfg['period']})")

        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=cfg['period'], interval=interval)

            if df is None or df.empty:
                return {"error": f"No intraday data available for {ticker} at {interval}"}

            # Normalise column names
            df = df.rename(columns={
                'Open': 'Open', 'High': 'High', 'Low': 'Low',
                'Close': 'Close', 'Volume': 'Volume'
            })

            # Strip timezone from index so downstream code stays simple
            if df.index.tz is not None:
                df.index = df.index.tz_convert('UTC').tz_localize(None)

            # Keep only the most recent 100 candles for intraday charts
            if len(df) > 100:
                df = df.tail(100)

            logger.info(f"Fetched {len(df)} intraday bars for {ticker} (capped at 100)")

            # Calculate indicators
            df = self.calculate_all_indicators(df)

            # Support/resistance (smaller window for intraday)
            support_levels, resistance_levels = self.detect_support_resistance(
                df, window=cfg['sr_window']
            )

            # Clean NaN/Inf
            chart_df = df.copy()
            chart_df = chart_df.replace([np.inf, -np.inf], np.nan)
            chart_df = chart_df.astype(object).where(pd.notnull(chart_df), None)

            for col in ['Open', 'High', 'Low', 'Close', 'SMA_20', 'SMA_50', 'BB_Upper', 'BB_Middle', 'BB_Lower', 'RSI']:
                if col in chart_df.columns:
                    chart_df[col] = chart_df[col].apply(
                        lambda x: round(x, 2) if (_sv(x) is not None) else None
                    )

            for col in ['MACD', 'MACD_Signal', 'MACD_Histogram']:
                if col in chart_df.columns:
                    chart_df[col] = chart_df[col].apply(
                        lambda x: round(x, 4) if (_sv(x) is not None) else None
                    )

            # Format timestamps (include time for intraday)
            dates = chart_df.index.strftime('%Y-%m-%d %H:%M').tolist()

            price_data = [
                {
                    'Date': date, 'Close': _sv(c), 'Open': _sv(o), 'High': _sv(h), 'Low': _sv(l),
                    'SMA_20': _sv(s20), 'SMA_50': _sv(s50), 'SMA_200': None,
                }
                for date, c, o, h, l, s20, s50 in zip(
                    dates,
                    chart_df['Close'].tolist(), chart_df['Open'].tolist(),
                    chart_df['High'].tolist(), chart_df['Low'].tolist(),
                    chart_df['SMA_20'].tolist(), chart_df['SMA_50'].tolist(),
                )
            ]

            bollinger_data = [
                {'Date': date, 'Upper': _sv(u), 'Middle': _sv(m), 'Lower': _sv(l), 'Close': _sv(c)}
                for date, u, m, l, c in zip(
                    dates,
                    chart_df['BB_Upper'].tolist(), chart_df['BB_Middle'].tolist(),
                    chart_df['BB_Lower'].tolist(), chart_df['Close'].tolist(),
                )
            ]

            volume_data = [
                {'Date': date, 'Volume': _sv(v), 'Volume_MA': _sv(vm)}
                for date, v, vm in zip(
                    dates, chart_df['Volume'].tolist(), chart_df['Volume_MA'].tolist(),
                )
            ]

            rsi_data = [
                {'Date': date, 'RSI': _sv(rsi)}
                for date, rsi in zip(dates, chart_df['RSI'].tolist())

            ]

            macd_data = [
                {'Date': date, 'MACD': macd, 'Signal': sig, 'Histogram': hist}
                for date, macd, sig, hist in zip(
                    dates,
                    chart_df['MACD'].tolist(), chart_df['MACD_Signal'].tolist(),
                    chart_df['MACD_Histogram'].tolist(),
                )
            ]

            def safe(series, decimals=2):
                val = series.iloc[-1]
                return round(float(val), decimals) if pd.notna(val) and not np.isinf(val) else None

            current_price = safe(df['Close'])

            return {
                'ticker':       ticker,
                'interval':     interval,
                'current_price': current_price,
                'data_points':  len(chart_df),
                'date_range':   {'start': dates[0], 'end': dates[-1]},
                'charts': {
                    'price':     price_data,
                    'bollinger': bollinger_data,
                    'volume':    volume_data,
                    'rsi':       rsi_data,
                    'macd':      macd_data,
                },
                'indicators': {
                    'rsi':          safe(df['RSI']),
                    'macd':         safe(df['MACD'], 4),
                    'macd_signal':  safe(df['MACD_Signal'], 4),
                    'sma_20':       safe(df['SMA_20']),
                    'sma_50':       safe(df['SMA_50']),
                    'sma_200':      None,
                },
                'levels': {
                    'support':    support_levels,
                    'resistance': resistance_levels,
                },
                'trend': 'N/A (intraday)',
            }

        except Exception as e:
            logger.error(f"Error generating intraday chart for {ticker} @ {interval}: {e}", exc_info=True)
            return {"error": str(e)}
