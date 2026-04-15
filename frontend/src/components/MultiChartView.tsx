import React from 'react';
import CandlestickChart from './CandlestickChart';
import VolumeChart from './VolumeChart';
import RSIChart from './RSIChart';
import MACDChart from './MACDChart';
import BollingerChart from './BollingerChart';

interface MultiChartViewProps {
    data: any;
}

const MultiChartView: React.FC<MultiChartViewProps> = ({ data }) => {
    if (!data) return <div>No data available</div>;

    // Extract chart data from different possible structures, capped to last 100 candles
    const CANDLE_LIMIT = 100;
    const priceData = (data.charts?.price || data.price_data || data.history || []).slice(-CANDLE_LIMIT);
    const volumeData = (data.charts?.volume || data.volume_data || data.history || []).slice(-CANDLE_LIMIT);
    const rsiData = (data.charts?.rsi || data.rsi_data || data.chart_data || []).slice(-CANDLE_LIMIT);
    const macdData = (data.charts?.macd || data.macd_data || data.chart_data || []).slice(-CANDLE_LIMIT);
    const bollingerData = (data.charts?.bollinger || data.bollinger_data || []).slice(-CANDLE_LIMIT);

    return (
        <div className="multi-chart-container">
            {/* Main Price Chart — always candlestick */}
            {priceData.length > 0 && (
                <CandlestickChart data={priceData} />
            )}

            {/* Bollinger Bands Chart */}
            {bollingerData.length > 0 && <BollingerChart data={bollingerData} />}

            {/* Volume Chart */}
            {volumeData.length > 0 && <VolumeChart data={volumeData} />}

            <div className="indicators-row">
                {/* RSI Chart */}
                {rsiData.length > 0 && (
                    <div className="indicator-chart">
                        <RSIChart data={rsiData} />
                    </div>
                )}

                {/* MACD Chart */}
                {macdData.length > 0 && (
                    <div className="indicator-chart">
                        <MACDChart data={macdData} />
                    </div>
                )}
            </div>
        </div>
    );
};

export default MultiChartView;
