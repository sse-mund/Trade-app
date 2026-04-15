// TypeScript interfaces for API responses
export interface ChartDataPoint {
    Date?: string;
    dates?: string;
    Close?: number;
    close?: number;
    Open?: number;
    High?: number;
    Low?: number;
    Volume?: number;
    volume?: number;
}

export interface RSIDataPoint extends ChartDataPoint {
    RSI?: number;
    rsi?: number;
}

export interface MACDDataPoint extends ChartDataPoint {
    MACD?: number;
    macd?: number;
    MACD_Signal?: number;
    macd_signal?: number;
    MACD_Histogram?: number;
    macd_histogram?: number;
}

export interface SupportResistance {
    support: number[];
    resistance: number[];
}

export interface TechnicalIndicators {
    rsi?: number;
    macd?: number;
    macd_signal?: number;
    sma_20?: number;
    sma_50?: number;
    sma_200?: number;
    bollinger_upper?: number;
    bollinger_lower?: number;
    volume_ma?: number;
}

export interface ChartCollection {
    price?: ChartDataPoint[];
    volume?: ChartDataPoint[];
    rsi?: RSIDataPoint[];
    macd?: MACDDataPoint[];
}

export interface StrategyResult {
    signal: number;  // -1 (sell), 0 (hold), 1 (buy)
    data?: any;
}

export interface AnalyzeChartsResponse {
    ticker: string;
    current_price: number;
    data_points?: number;
    trend?: string;
    levels?: SupportResistance;
    indicators?: TechnicalIndicators;
    chart_data?: ChartDataPoint[];
    charts?: ChartCollection;
    history?: ChartDataPoint[];
    strategies?: {
        [key: string]: StrategyResult;
    };
}

export interface NewsArticle {
    headline: string;
    summary: string;
    source: string;
    datetime: number;  // Unix timestamp
    url: string;
    related: string;  // Ticker symbol
    sentiment_score?: number | null;
    upvotes?: number;  // For Reddit
    engagement?: number;  // For Twitter
}

export interface AgentResult {
    signal: number;  // -1 (sell), 0 (hold), 1 (buy)
    confidence: number;  // 0.0 to 1.0
    reasoning: string;
    metrics: {
        [key: string]: any;
    };
    strategyName?: string;
    currentPrice?: number;
    targetPrice?: number;
    timeframe?: string;
}

export interface MultiAgentAnalysisResponse {
    ticker: string;
    recommendation: 'BUY' | 'SELL' | 'HOLD';
    confidence: number;
    agent_results: {
        pattern?: AgentResult;
        sentiment?: AgentResult;
        quant?: AgentResult;
    };
    reasoning: string;
    strategyName?: string;
    currentPrice?: number;
    targetPrice?: number;
    timeframe?: string;
    resistanceLevels?: number[];
    supportLevels?: number[];
    risk_level?: 'Low' | 'Medium' | 'High';
    news?: NewsArticle[];

    // Brain fields
    brain_reasoning?: string;
    risk_factors?: string[];
    market_regime?: string;
    key_insight?: string;
    confluence?: {
        agreement: string;
        description: string;
        bullish_count: number;
        bearish_count: number;
        neutral_count: number;
    };
}
