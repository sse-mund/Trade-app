import pandas as pd
import logger_config

logger = logger_config.get_logger(__name__)

def calculate_sma(df: pd.DataFrame, short_window: int = 20, long_window: int = 50) -> pd.DataFrame:
    """
    Calculates Simple Moving Averages and generates signals.
    """
    logger.info(f"Calculating SMA with windows: short={short_window}, long={long_window}")
    
    df = df.copy()
    df[f'SMA_{short_window}'] = df['Close'].rolling(window=short_window).mean()
    df[f'SMA_{long_window}'] = df['Close'].rolling(window=long_window).mean()
    
    # Signal: 1 (Buy) if Short > Long, -1 (Sell) if Short < Long, else 0
    df['SMA_Signal'] = 0
    df.loc[df[f'SMA_{short_window}'] > df[f'SMA_{long_window}'], 'SMA_Signal'] = 1
    df.loc[df[f'SMA_{short_window}'] < df[f'SMA_{long_window}'], 'SMA_Signal'] = -1
    
    latest_signal = df['SMA_Signal'].iloc[-1]
    signal_text = "BUY" if latest_signal == 1 else "SELL" if latest_signal == -1 else "HOLD"
    logger.info(f"SMA calculation complete. Latest signal: {signal_text} ({latest_signal})")
    
    return df

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculates RSI and generates signals.
    """
    logger.info(f"Calculating RSI with period: {period}")
    
    df = df.copy()
    # Manual RSI calculation to avoid pandas_ta dependency if not installed, or use simple formula
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Signal: Buy < 30, Sell > 70
    df['RSI_Signal'] = 0
    df.loc[df['RSI'] < 30, 'RSI_Signal'] = 1
    df.loc[df['RSI'] > 70, 'RSI_Signal'] = -1
    
    latest_rsi = df['RSI'].iloc[-1]
    latest_signal = df['RSI_Signal'].iloc[-1]
    signal_text = "BUY" if latest_signal == 1 else "SELL" if latest_signal == -1 else "HOLD"
    logger.info(f"RSI calculation complete. Latest RSI: {latest_rsi:.2f}, Signal: {signal_text} ({latest_signal})")
    
    return df

def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    Calculates MACD and generates signals.
    """
    logger.info(f"Calculating MACD with parameters: fast={fast}, slow={slow}, signal={signal}")
    
    df = df.copy()
    df['EMA_12'] = df['Close'].ewm(span=fast, adjust=False).mean()
    df['EMA_26'] = df['Close'].ewm(span=slow, adjust=False).mean()
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['Signal_Line'] = df['MACD'].ewm(span=signal, adjust=False).mean()
    
    # Signal: Buy if MACD > Signal Line, Sell if MACD < Signal Line
    df['MACD_Signal'] = 0
    df.loc[df['MACD'] > df['Signal_Line'], 'MACD_Signal'] = 1
    df.loc[df['MACD'] < df['Signal_Line'], 'MACD_Signal'] = -1
    
    latest_macd = df['MACD'].iloc[-1]
    latest_signal_line = df['Signal_Line'].iloc[-1]
    latest_signal = df['MACD_Signal'].iloc[-1]
    signal_text = "BUY" if latest_signal == 1 else "SELL" if latest_signal == -1 else "HOLD"
    logger.info(f"MACD calculation complete. MACD: {latest_macd:.4f}, Signal Line: {latest_signal_line:.4f}, Signal: {signal_text} ({latest_signal})")
    
    return df

def apply_strategies(df: pd.DataFrame, strategies: list) -> dict:
    logger.info(f"Applying strategies: {strategies}")
    
    results = {}
    if 'SMA' in strategies:
        logger.info("Processing SMA strategy")
        sma_df = calculate_sma(df)
        # Sanitize data for JSON serialization
        chart_data = sma_df[[f'SMA_20', f'SMA_50']].tail(100).copy()
        chart_data = chart_data.replace([float('inf'), float('-inf')], float('nan'))
        chart_data = chart_data.where(pd.notnull(chart_data), None)
        
        results['SMA'] = {
            'signal': int(sma_df['SMA_Signal'].iloc[-1]),
            'data': chart_data.to_dict(orient='records')
        }
    if 'RSI' in strategies:
        logger.info("Processing RSI strategy")
        rsi_df = calculate_rsi(df)
        results['RSI'] = {
            'value': float(rsi_df['RSI'].iloc[-1]),
            'signal': int(rsi_df['RSI_Signal'].iloc[-1])
        }
    if 'MACD' in strategies:
        logger.info("Processing MACD strategy")
        macd_df = calculate_macd(df)
        results['MACD'] = {
            'macd_line': float(macd_df['MACD'].iloc[-1]),
            'signal_line': float(macd_df['Signal_Line'].iloc[-1]),
            'signal': int(macd_df['MACD_Signal'].iloc[-1])
        }
    
    logger.info(f"Strategy application complete. Processed {len(results)} strategies")
    return results
