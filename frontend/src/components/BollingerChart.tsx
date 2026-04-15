import React from 'react';
import { ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

interface BollingerChartProps {
    data: any[];
}

const BollingerChart: React.FC<BollingerChartProps> = ({ data }) => {
    if (!data || data.length === 0) return <div className="text-gray-500">No Bollinger Data</div>;

    // Determine date key
    const dateKey: string = data[0]?.Date !== undefined ? 'Date' :
        data[0]?.dates !== undefined ? 'dates' : 'Date';

    return (
        <div className="chart-container">
            <h3>Bollinger Bands</h3>
            <ResponsiveContainer width="100%" height={350}>
                <ComposedChart data={data}>
                    <defs>
                        <linearGradient id="colorPriceBollinger" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.1} />
                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey={dateKey} stroke="#9ca3af" tick={{ fontSize: 12 }} />
                    <YAxis domain={['auto', 'auto']} stroke="#9ca3af" tick={{ fontSize: 12 }} />
                    <Tooltip
                        contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', color: '#e5e7eb' }}
                        itemStyle={{ color: '#93c5fd' }}
                    />
                    <Legend />

                    {/* Upper Band */}
                    <Line
                        type="monotone"
                        dataKey="Upper"
                        stroke="#ef4444"
                        strokeWidth={1}
                        strokeDasharray="5 5"
                        dot={false}
                    />

                    {/* Middle Band (SMA 20) */}
                    <Line
                        type="monotone"
                        dataKey="Middle"
                        stroke="#f59e0b"
                        strokeWidth={2}
                        dot={false}
                    />

                    {/* Lower Band */}
                    <Line
                        type="monotone"
                        dataKey="Lower"
                        stroke="#10b981"
                        strokeWidth={1}
                        strokeDasharray="5 5"
                        dot={false}
                    />

                    {/* Close Price */}
                    <Area
                        type="monotone"
                        dataKey="Close"
                        stroke="#3b82f6"
                        fillOpacity={1}
                        fill="url(#colorPriceBollinger)"
                        strokeWidth={2}
                    />
                </ComposedChart>
            </ResponsiveContainer>
        </div>
    );
};

export default BollingerChart;
