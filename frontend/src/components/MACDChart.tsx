import React from 'react';
import { ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

interface MACDChartProps {
    data: any[];
}

const MACDChart: React.FC<MACDChartProps> = ({ data }) => {
    if (!data || data.length === 0) return <div className="text-gray-500">No MACD Data</div>;

    // Filter data to only include points with MACD values
    const macdData = data.filter(item =>
        item.macd !== undefined || item.MACD !== undefined ||
        item.macd_histogram !== undefined || item.MACD_Histogram !== undefined
    );

    if (macdData.length === 0) return <div className="text-gray-500">No MACD Data Available</div>;

    // Determine keys
    const macdKey = macdData[0]?.macd !== undefined ? 'macd' : 'MACD';
    const signalKey = macdData[0]?.macd_signal !== undefined ? 'macd_signal' : 'MACD_Signal';
    const histogramKey = macdData[0]?.macd_histogram !== undefined ? 'macd_histogram' : 'MACD_Histogram';
    const dateKey = macdData[0]?.Date !== undefined ? 'Date' :
        macdData[0]?.dates !== undefined ? 'dates' : 'Date';

    return (
        <div className="chart-container">
            <h3>MACD (Moving Average Convergence Divergence)</h3>
            <ResponsiveContainer width="100%" height={350}>
                <ComposedChart data={macdData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey={dateKey} stroke="#9ca3af" tick={{ fontSize: 12 }} />
                    <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} />
                    <Tooltip
                        contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', color: '#e5e7eb' }}
                        itemStyle={{ color: '#93c5fd' }}
                    />
                    {/* Zero line */}
                    <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
                    {/* MACD Histogram */}
                    <Bar dataKey={histogramKey} fill="#3b82f6" opacity={0.6} />
                    {/* MACD Line */}
                    <Line
                        type="monotone"
                        dataKey={macdKey}
                        stroke="#22c55e"
                        strokeWidth={2}
                        dot={false}
                    />
                    {/* Signal Line */}
                    <Line
                        type="monotone"
                        dataKey={signalKey}
                        stroke="#ef4444"
                        strokeWidth={2}
                        dot={false}
                    />
                </ComposedChart>
            </ResponsiveContainer>
        </div>
    );
};

export default MACDChart;
