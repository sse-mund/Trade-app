import React, { useState } from 'react';
import { TrendingUp, ShieldCheck, Target, Clock, AlertTriangle } from 'lucide-react';

interface BuyRec {
    ticker: string;
    recommendation: string;
    confidence: number;
    current_price: number | null;
    change_pct: number | null;
    market_regime: string;
    risk_level: string;
    key_insight: string;
    target_price?: number | null;
    stop_loss?: number | null;
    time_horizon?: string;
    trade_reasoning?: string;
    signal_strength?: number;
}

interface BuyRecommendationsProps {
    onSelectTicker: (ticker: string) => void;
}

const riskColor = (r: string) => {
    if (r === 'Low') return '#22c55e';
    if (r === 'Medium') return '#f59e0b';
    return '#ef4444';
};

const BuyRecommendations: React.FC<BuyRecommendationsProps> = ({ onSelectTicker }) => {
    const [results, setResults] = useState<BuyRec[]>([]);
    const [scanning, setScanning] = useState(false);
    const [progress, setProgress] = useState('');
    const [scanTime, setScanTime] = useState<string | null>(null);
    const [error, setError] = useState('');
    const [expanded, setExpanded] = useState<string | null>(null);

    const runScan = async () => {
        setScanning(true);
        setError('');
        setResults([]);
        setProgress('Fetching stock universe…');

        try {
            // 1. Get the full TOP_50 stock list
            const tickerRes = await fetch('http://localhost:8000/top_stocks');
            if (!tickerRes.ok) throw new Error('Failed to fetch stock list');
            const { tickers } = await tickerRes.json();

            setProgress(`Scanning ${tickers.length} stocks for BUY signals…`);

            // 2. Run batch scan
            const scanRes = await fetch('http://localhost:8000/batch_scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tickers }),
            });
            if (!scanRes.ok) throw new Error(await scanRes.text());
            const data = await scanRes.json();

            // 3. Filter to BUY only, sorted by confidence desc
            const buys = (data.results || [])
                .filter((r: BuyRec) => r.recommendation === 'BUY')
                .sort((a: BuyRec, b: BuyRec) => (b.confidence || 0) - (a.confidence || 0));

            setResults(buys);
            setScanTime(new Date().toLocaleTimeString());
            setProgress('');
        } catch (e: any) {
            setError(e.message || 'Scan failed');
            setProgress('');
        } finally {
            setScanning(false);
        }
    };

    const calcUpside = (current: number | null, target: number | null | undefined) => {
        if (!current || !target) return null;
        return ((target - current) / current * 100).toFixed(1);
    };

    const calcRisk = (current: number | null, stop: number | null | undefined) => {
        if (!current || !stop) return null;
        return ((current - stop) / current * 100).toFixed(1);
    };

    return (
        <div style={{
            background: 'linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(30,41,59,0.9) 100%)',
            border: '1px solid rgba(34,197,94,0.2)',
            borderRadius: 14,
            padding: '1.25rem 1.5rem',
            marginBottom: '1.5rem',
            boxShadow: '0 2px 20px rgba(0,0,0,0.3)',
        }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <TrendingUp size={18} style={{ color: '#22c55e' }} />
                    <span style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9' }}>
                        Buy Recommendations
                    </span>
                    {scanTime && (
                        <span style={{ fontSize: 11, color: '#4b5563' }}>
                            · {results.length} found · {scanTime}
                        </span>
                    )}
                </div>
                <button
                    onClick={runScan}
                    disabled={scanning}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.4rem',
                        padding: '0.5rem 1.25rem',
                        background: scanning ? '#374151' : 'linear-gradient(135deg, #059669, #22c55e)',
                        color: 'white',
                        border: 'none',
                        borderRadius: 8,
                        fontWeight: 600,
                        cursor: scanning ? 'not-allowed' : 'pointer',
                        fontSize: 13,
                        transition: 'all 0.2s',
                        boxShadow: scanning ? 'none' : '0 2px 12px rgba(34,197,94,0.3)',
                    }}
                >
                    {scanning ? (
                        <>
                            <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⏳</span>
                            Scanning…
                        </>
                    ) : (
                        <>
                            🔍 Scan for Buy Signals
                        </>
                    )}
                </button>
            </div>

            {error && (
                <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444', borderRadius: 8, padding: '0.75rem', color: '#f87171', fontSize: 13, marginBottom: '1rem' }}>
                    {error}
                </div>
            )}

            {/* Progress */}
            {scanning && progress && (
                <div style={{
                    background: 'rgba(34,197,94,0.06)',
                    border: '1px solid rgba(34,197,94,0.15)',
                    borderRadius: 10,
                    padding: '1rem',
                    textAlign: 'center',
                    marginBottom: '1rem',
                }}>
                    <div style={{ fontSize: 13, color: '#6b7280', marginBottom: '0.5rem' }}>{progress}</div>
                    <div style={{ height: 4, background: '#1f2937', borderRadius: 99, overflow: 'hidden' }}>
                        <div style={{
                            height: '100%',
                            width: '100%',
                            background: 'linear-gradient(90deg, #059669, #22c55e, #059669)',
                            borderRadius: 99,
                            animation: 'wf-pulse 1.5s ease-in-out infinite',
                        }} />
                    </div>
                </div>
            )}

            {/* Results Table */}
            {results.length > 0 && (
                <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                        <thead>
                            <tr style={{ borderBottom: '2px solid rgba(34,197,94,0.2)' }}>
                                <th style={thStyle}>Ticker</th>
                                <th style={thStyle}>Price</th>
                                <th style={thStyle}>Change</th>
                                <th style={thStyle}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                                        <Target size={11} /> Target
                                    </div>
                                </th>
                                <th style={thStyle}>Upside</th>
                                <th style={thStyle}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                                        <ShieldCheck size={11} /> Stop Loss
                                    </div>
                                </th>
                                <th style={thStyle}>Risk %</th>
                                <th style={thStyle}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                                        <Clock size={11} /> Horizon
                                    </div>
                                </th>
                                <th style={thStyle}>Confidence</th>
                                <th style={thStyle}>Regime</th>
                                <th style={thStyle}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                                        <AlertTriangle size={11} /> Risk
                                    </div>
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {results.map(r => {
                                const upside = calcUpside(r.current_price, r.target_price);
                                const riskPct = calcRisk(r.current_price, r.stop_loss);
                                const isExpanded = expanded === r.ticker;

                                return (
                                    <React.Fragment key={r.ticker}>
                                        <tr
                                            style={{
                                                borderBottom: '1px solid rgba(255,255,255,0.04)',
                                                cursor: 'pointer',
                                                transition: 'background 0.15s',
                                            }}
                                            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(34,197,94,0.04)')}
                                            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                                            onClick={() => setExpanded(isExpanded ? null : r.ticker)}
                                        >
                                            <td style={{ ...tdStyle, fontWeight: 700, color: '#e2e8f0' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                                                    <span style={{
                                                        display: 'inline-block',
                                                        width: 6, height: 6,
                                                        borderRadius: '50%',
                                                        background: '#22c55e',
                                                        boxShadow: '0 0 6px rgba(34,197,94,0.5)',
                                                    }} />
                                                    {r.ticker}
                                                </div>
                                            </td>
                                            <td style={{ ...tdStyle, color: '#f1f5f9', fontWeight: 600 }}>
                                                {r.current_price ? `$${r.current_price}` : '—'}
                                            </td>
                                            <td style={{
                                                ...tdStyle, fontWeight: 600,
                                                color: r.change_pct != null ? (r.change_pct >= 0 ? '#22c55e' : '#ef4444') : '#6b7280',
                                            }}>
                                                {r.change_pct != null ? `${r.change_pct >= 0 ? '+' : ''}${r.change_pct}%` : '—'}
                                            </td>
                                            <td style={{ ...tdStyle, color: '#34d399', fontWeight: 700 }}>
                                                {r.target_price ? `$${r.target_price}` : '—'}
                                            </td>
                                            <td style={{ ...tdStyle, fontWeight: 700, color: '#22c55e' }}>
                                                {upside ? `+${upside}%` : '—'}
                                            </td>
                                            <td style={{ ...tdStyle, color: '#f87171', fontWeight: 600 }}>
                                                {r.stop_loss ? `$${r.stop_loss}` : '—'}
                                            </td>
                                            <td style={{ ...tdStyle, color: '#f87171', fontSize: 11 }}>
                                                {riskPct ? `-${riskPct}%` : '—'}
                                            </td>
                                            <td style={{ ...tdStyle, color: '#94a3b8', fontSize: 11 }}>
                                                {r.time_horizon || '—'}
                                            </td>
                                            <td style={tdStyle}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                                    <div style={{
                                                        width: 36, height: 5,
                                                        background: '#1f2937', borderRadius: 99, overflow: 'hidden',
                                                    }}>
                                                        <div style={{
                                                            height: '100%',
                                                            width: `${(r.confidence || 0) * 100}%`,
                                                            background: r.confidence > 0.6 ? '#22c55e' : r.confidence > 0.3 ? '#f59e0b' : '#ef4444',
                                                            borderRadius: 99,
                                                        }} />
                                                    </div>
                                                    <span style={{ color: '#94a3b8', fontSize: 11 }}>
                                                        {Math.round((r.confidence || 0) * 100)}%
                                                    </span>
                                                </div>
                                            </td>
                                            <td style={{ ...tdStyle, color: '#94a3b8', fontSize: 11 }}>
                                                {r.market_regime || '—'}
                                            </td>
                                            <td style={{ ...tdStyle, color: riskColor(r.risk_level), fontWeight: 600, fontSize: 11 }}>
                                                {r.risk_level}
                                            </td>
                                        </tr>
                                        {/* Expanded detail row */}
                                        {isExpanded && (
                                            <tr>
                                                <td colSpan={11} style={{ padding: 0 }}>
                                                    <div style={{
                                                        background: 'rgba(34,197,94,0.04)',
                                                        borderBottom: '1px solid rgba(34,197,94,0.15)',
                                                        padding: '0.75rem 1rem',
                                                        animation: 'fadeIn 0.2s ease',
                                                    }}>
                                                        <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
                                                            <div>
                                                                <div style={{ fontSize: 10, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Risk/Reward</div>
                                                                <div style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9' }}>
                                                                    {upside && riskPct ? `${(parseFloat(upside) / parseFloat(riskPct)).toFixed(1)}:1` : '—'}
                                                                </div>
                                                            </div>
                                                            <div>
                                                                <div style={{ fontSize: 10, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Signal Strength</div>
                                                                <div style={{ fontSize: 14, fontWeight: 700, color: '#34d399' }}>
                                                                    {r.signal_strength != null ? r.signal_strength.toFixed(3) : '—'}
                                                                </div>
                                                            </div>
                                                        </div>
                                                        <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.5 }}>
                                                            <strong style={{ color: '#6b7280' }}>Insight:</strong> {r.key_insight}
                                                        </div>
                                                        {r.trade_reasoning && (
                                                            <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.5, marginTop: '0.35rem' }}>
                                                                <strong style={{ color: '#6b7280' }}>Trade Reasoning:</strong> {r.trade_reasoning}
                                                            </div>
                                                        )}
                                                        <button
                                                            onClick={(e) => { e.stopPropagation(); onSelectTicker(r.ticker); }}
                                                            style={{
                                                                marginTop: '0.5rem',
                                                                padding: '0.35rem 0.75rem',
                                                                background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                                                                color: 'white',
                                                                border: 'none',
                                                                borderRadius: 6,
                                                                fontSize: 12,
                                                                fontWeight: 600,
                                                                cursor: 'pointer',
                                                            }}
                                                        >
                                                            📊 Full Analysis → {r.ticker}
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        )}
                                    </React.Fragment>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}

            {/* No results state */}
            {!scanning && results.length === 0 && scanTime && (
                <div style={{ textAlign: 'center', padding: '1rem', color: '#6b7280', fontSize: 13 }}>
                    No BUY signals found across the index. All stocks are HOLD or SELL right now.
                </div>
            )}

            {!scanning && !scanTime && (
                <div style={{ textAlign: 'center', padding: '1rem', color: '#4b5563', fontSize: 13 }}>
                    Click <strong style={{ color: '#22c55e' }}>Scan for Buy Signals</strong> to analyze all 50 index stocks and surface the best opportunities
                </div>
            )}

            <style>{`
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(-4px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
                @keyframes wf-pulse {
                    0%, 100% { opacity: 0.4; transform: scaleX(0.3); }
                    50% { opacity: 1; transform: scaleX(1); }
                }
            `}</style>
        </div>
    );
};

const thStyle: React.CSSProperties = {
    padding: '0.5rem 0.6rem',
    textAlign: 'left',
    color: '#6b7280',
    fontWeight: 600,
    whiteSpace: 'nowrap',
    fontSize: 11,
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
    borderBottom: '2px solid rgba(34,197,94,0.2)',
};

const tdStyle: React.CSSProperties = {
    padding: '0.55rem 0.6rem',
    whiteSpace: 'nowrap',
};

export default BuyRecommendations;
