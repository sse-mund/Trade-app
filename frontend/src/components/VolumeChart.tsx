import React from 'react';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Bar, ComposedChart } from 'recharts';

interface VolumeChartProps {
    data: any[];
}

const VolumeChart: React.FC<VolumeChartProps> = ({ data }) => {
    if (!data || data.length === 0) return <div className="text-gray-500">No Volume Data</div>;

    // Determine volume key
    const volumeKey = data[0]?.volume !== undefined ? 'volume' :
        data[0]?.Volume !== undefined ? 'Volume' : 'volume';

    // Determine date key
    const dateKey = data[0]?.Date !== undefined ? 'Date' :
        data[0]?.dates !== undefined ? 'dates' : 'Date';

    // Calculate average volume for color coding
    const avgVolume = data.reduce((sum, item) => sum + (item[volumeKey] || 0), 0) / data.length;

    // Add color based on volume comparison to average
    const chartData = data.map(item => ({
        ...item,
        volumeColor: (item[volumeKey] || 0) > avgVolume ? '#22c55e' : '#ef4444'
    }));

    return (
        <div className="chart-container">
            <h3>Volume</h3>
            <ResponsiveContainer width="100%" height={350}>
                <ComposedChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey={dateKey} stroke="#9ca3af" tick={{ fontSize: 12 }} />
                    <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} />
                    <Tooltip
                        contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', color: '#e5e7eb' }}
                        itemStyle={{ color: '#93c5fd' }}
                    />
                    <Bar dataKey={volumeKey} fill="#3b82f6" />
                </ComposedChart>
            </ResponsiveContainer>
        </div>
    );
};

export default VolumeChart;
