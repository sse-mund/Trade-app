import React from 'react';
import {
    ComposedChart,
    Bar,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell,
} from 'recharts';

interface CandlestickChartProps {
    data: any[]; // each: { Date, Open, High, Low, Close, SMA_20, SMA_50 }
}

/* ── Custom tooltip ───────────────────────────────────────────────────── */
const CandleTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const d = payload[0]?.payload;
    if (!d) return null;
    const bull = (d.Close ?? 0) >= (d.Open ?? 0);
    const col = bull ? '#22c55e' : '#ef4444';
    return (
        <div style={{
            background: '#1f2937', border: '1px solid #374151', borderRadius: 8,
            padding: '10px 14px', fontSize: 13, color: '#e5e7eb', minWidth: 190,
        }}>
            <div style={{ marginBottom: 6, color: '#9ca3af' }}>{d.Date}</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 16px' }}>
                <span style={{ color: '#9ca3af' }}>Open</span>  <span style={{ color: col }}>${d.Open?.toFixed(2) ?? '-'}</span>
                <span style={{ color: '#9ca3af' }}>High</span>  <span style={{ color: '#34d399' }}>${d.High?.toFixed(2) ?? '-'}</span>
                <span style={{ color: '#9ca3af' }}>Low</span>   <span style={{ color: '#f87171' }}>${d.Low?.toFixed(2) ?? '-'}</span>
                <span style={{ color: '#9ca3af' }}>Close</span> <span style={{ color: col, fontWeight: 600 }}>${d.Close?.toFixed(2) ?? '-'}</span>
            </div>
            {d.SMA_20 != null && <div style={{ marginTop: 6, color: '#f59e0b' }}>SMA20: ${d.SMA_20.toFixed(2)}</div>}
            {d.SMA_50 != null && <div style={{ color: '#a78bfa' }}>SMA50: ${d.SMA_50.toFixed(2)}</div>}
        </div>
    );
};

/* ── Custom candle shape ──────────────────────────────────────────────── */
/**
 * Recharts passes x, y, width, height to Bar shapes.
 * We use a stacked bar trick:
 *   - "shadow" bar  = transparent offset from yAxis=0 up to Math.min(open,close)
 *   - "body" bar    = colored from Math.min to Math.max(open,close)
 * The custom shape then adds the high/low wicks using the provided y/height.
 *
 * Here we handle the full candle in ONE custom shape drawing everything
 * by referencing the raw OHLC from the datum in `props.formattedGraphicalItems`
 * — but simpler: we just read `props.background` coords to know chart area
 * and recalculate everything from the domain stored in parent.
 *
 * SIMPLEST approach: store a ref to {yScale} and use it inside the shape.
 */

/** We'll pass yScale via a closure */
const makeCandleShape = (
    yScale: (v: number) => number,
) => {
    const Shape = (props: any) => {
        const { x, width, index, payload } = props;
        if (!payload) return null;
        const { Open, High, Low, Close } = payload;
        if (Open == null || High == null || Low == null || Close == null) return null;

        const bull = Close >= Open;
        const bodyColor = bull ? '#22c55e' : '#ef4444';
        const wickColor = bull ? '#16a34a' : '#dc2626';

        const yHigh = yScale(High);
        const yLow = yScale(Low);
        const yBodyTop = yScale(Math.max(Open, Close));
        const yBodyBot = yScale(Math.min(Open, Close));
        const cx = x + width / 2;
        const bodyW = Math.max(width - 4, 2);
        const bodyX = cx - bodyW / 2;
        const bodyH = Math.max(yBodyBot - yBodyTop, 1);

        return (
            <g key={index}>
                {/* Upper wick */}
                <line x1={cx} y1={yHigh} x2={cx} y2={yBodyTop} stroke={wickColor} strokeWidth={1.5} />
                {/* Body */}
                <rect x={bodyX} y={yBodyTop} width={bodyW} height={bodyH} fill={bodyColor} rx={1} />
                {/* Lower wick */}
                <line x1={cx} y1={yBodyBot} x2={cx} y2={yLow} stroke={wickColor} strokeWidth={1.5} />
            </g>
        );
    };
    Shape.displayName = 'CandleShape';
    return Shape;
};

/* ── Main component ───────────────────────────────────────────────────── */
const CandlestickChart: React.FC<CandlestickChartProps> = ({ data: rawData }) => {
    if (!rawData || rawData.length === 0) {
        return <div style={{ color: '#9ca3af' }}>No candlestick data</div>;
    }

    // Limit to last 100 candles
    const data = rawData.slice(-100);

    const highs = data.map(d => d.High).filter(v => v != null) as number[];
    const lows = data.map(d => d.Low).filter(v => v != null) as number[];
    const yMin = Math.min(...lows);
    const yMax = Math.max(...highs);
    const pad = (yMax - yMin) * 0.02;
    const domainMin = yMin - pad;
    const domainMax = yMax + pad;

    /** We'll capture the yScale from the rendered chart axis via a custom tick/ref hack.
     *  Cleanest: use a CustomizedAxisTick to grab d3Scale, but that's fragile.
     *  Instead, compute a linear scale ourselves and keep it in sync with chart domain. */
    const CHART_HEIGHT = 380;
    const MARGIN_TOP = 10;
    const MARGIN_BOTTOM = 35; // approx x-axis area
    const plotH = CHART_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM;

    const yScale = (value: number): number => {
        const ratio = (domainMax - value) / (domainMax - domainMin);
        return MARGIN_TOP + ratio * plotH;
    };

    const CandleShape = makeCandleShape(yScale);

    /**
     * Recharts Bar needs a numeric dataKey.
     * We set dataKey="Close" so it has something to compute bar positions with,
     * but our custom shape ignores those coords and uses yScale directly.
     * We hide the bar fill (fillOpacity=0) so only our custom SVG shows.
     */
    return (
        <div className="chart-container">
            <h3>Candlestick Chart</h3>
            <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
                <ComposedChart
                    data={data}
                    margin={{ top: MARGIN_TOP, right: 20, left: 10, bottom: 5 }}
                >
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis
                        dataKey="Date"
                        stroke="#9ca3af"
                        tick={{ fontSize: 10 }}
                        interval="preserveStartEnd"
                    />
                    <YAxis
                        domain={[domainMin, domainMax]}
                        stroke="#9ca3af"
                        tick={{ fontSize: 11 }}
                        tickFormatter={(v: number) => `$${v.toFixed(2)}`}
                        width={75}
                    />
                    <Tooltip content={<CandleTooltip />} cursor={{ stroke: '#4b5563', strokeWidth: 1 }} />

                    {/* Bar — provides x/width per candle; custom shape draws the full candle */}
                    <Bar
                        dataKey="Close"
                        shape={<CandleShape />}
                        isAnimationActive={false}
                        fillOpacity={0}
                    >
                        {data.map((_: any, i: number) => (
                            <Cell key={`cell-${i}`} />
                        ))}
                    </Bar>

                    {/* SMA overlays */}
                    <Line type="monotone" dataKey="SMA_20" stroke="#f59e0b" dot={false}
                        strokeWidth={1.5} strokeDasharray="4 2" connectNulls name="SMA 20" />
                    <Line type="monotone" dataKey="SMA_50" stroke="#a78bfa" dot={false}
                        strokeWidth={1.5} strokeDasharray="4 2" connectNulls name="SMA 50" />
                </ComposedChart>
            </ResponsiveContainer>

            {/* Legend */}
            <div style={{ display: 'flex', gap: 16, justifyContent: 'center', marginTop: 8, fontSize: 12 }}>
                <span style={{ color: '#22c55e' }}>▮ Bullish</span>
                <span style={{ color: '#ef4444' }}>▮ Bearish</span>
                <span style={{ color: '#f59e0b' }}>— SMA 20</span>
                <span style={{ color: '#a78bfa' }}>— SMA 50</span>
            </div>
        </div>
    );
};

export default CandlestickChart;
