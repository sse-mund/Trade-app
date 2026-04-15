import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface StockChartProps {
    data: any[];
}

const StockChart: React.FC<StockChartProps> = ({ data }) => {
    console.log('StockChart rendered with data length:', data?.length);
    if (data && data.length > 0) {
        console.log('First data point:', data[0]);
        console.log('Last data point:', data[data.length - 1]);
    }

    if (!data || data.length === 0) return <div className="text-gray-500">No Chart Data</div>;

    // Determine data key for Close price: could be 'Close' or 'close'
    const priceKey: string = data[0]?.Close !== undefined ? 'Close' :
        data[0]?.close !== undefined ? 'close' : 'Close';

    // Determine date key
    const dateKey: string = data[0]?.Date !== undefined ? 'Date' :
        data[0]?.dates !== undefined ? 'dates' : 'Date';

    return (
        <div className="chart-container">
            <h3>Price History</h3>
            <ResponsiveContainer width="100%" height={350}>
                <AreaChart data={data}>
                    <defs>
                        <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8} />
                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey={dateKey} stroke="#9ca3af" tick={{ fontSize: 12 }} />
                    <YAxis stroke="#9ca3af" domain={['auto', 'auto']} tick={{ fontSize: 12 }} />
                    <Tooltip
                        contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', color: '#e5e7eb' }}
                        itemStyle={{ color: '#93c5fd' }}
                    />
                    <Area type="monotone" dataKey={priceKey} stroke="#3b82f6" fillOpacity={1} fill="url(#colorPrice)" />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    );
};

export default StockChart;
