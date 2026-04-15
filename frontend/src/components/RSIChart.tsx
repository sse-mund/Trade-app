import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceArea } from 'recharts';

interface RSIChartProps {
    data: any[];
}

const RSIChart: React.FC<RSIChartProps> = ({ data }) => {
    if (!data || data.length === 0) return <div className="text-gray-500">No RSI Data</div>;

    // Filter data to only include points with RSI values
    const rsiData = data.filter(item => item.rsi !== undefined || item.RSI !== undefined);

    if (rsiData.length === 0) return <div className="text-gray-500">No RSI Data Available</div>;

    // Determine keys
    const rsiKey = rsiData[0]?.rsi !== undefined ? 'rsi' : 'RSI';
    const dateKey = rsiData[0]?.Date !== undefined ? 'Date' :
        rsiData[0]?.dates !== undefined ? 'dates' : 'Date';

    return (
        <div className="chart-container">
            <h3>RSI (Relative Strength Index)</h3>
            <ResponsiveContainer width="100%" height={350}>
                <LineChart data={rsiData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey={dateKey} stroke="#9ca3af" tick={{ fontSize: 12 }} />
                    <YAxis domain={[0, 100]} stroke="#9ca3af" tick={{ fontSize: 12 }} />
                    <Tooltip
                        contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', color: '#e5e7eb' }}
                        itemStyle={{ color: '#93c5fd' }}
                    />
                    {/* Overbought zone (70-100) */}
                    <ReferenceArea y1={70} y2={100} fill="#ef4444" fillOpacity={0.1} />
                    {/* Oversold zone (0-30) */}
                    <ReferenceArea y1={0} y2={30} fill="#22c55e" fillOpacity={0.1} />
                    {/* RSI line */}
                    <Line
                        type="monotone"
                        dataKey={rsiKey}
                        stroke="#a855f7"
                        strokeWidth={2}
                        dot={false}
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
};

export default RSIChart;
