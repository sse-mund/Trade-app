import React, { useState } from 'react';

interface Trade {
    entry_date: string;
    exit_date: string;
    entry_price: number;
    exit_price: number;
    pnl_pct: number;
    days_held: number;
    note?: string;
}

interface Metrics {
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    win_rate: number;
    avg_win_pct: number;
    avg_loss_pct: number;
    avg_return_pct: number;
    profit_factor: number;
    total_return_pct: number;
    buy_hold_return_pct: number;
    alpha: number;
    max_drawdown_pct: number;
    sharpe_ratio: number;
    avg_days_held: number;
    agent_accuracy: { pattern: number; quant: number };
}

interface BacktestResult {
    ticker: string;
    start_date: string;
    end_date: string;
    bar_count: number;
    metrics: Metrics;
    trade_log: Trade[];
}

interface OptimizeResult {
    ticker: string;
    combinations_tried: number;
    best_params: Record<string, number>;
    baseline_metrics: Metrics;
    best_metrics: Metrics;
    improvement: { sharpe: number; win_rate: number; total_return: number };
    top_10_combos: any[];
}

interface WFTickerReport {
    ticker: string;
    train: { sharpe: number; win_rate: number; total_return: number; trades: number; max_drawdown: number };
    test:  { sharpe: number; win_rate: number; total_return: number; trades: number; max_drawdown: number };
    dates: { train_start: string; train_end: string; test_start: string; test_end: string };
}

interface WFResult {
    method: string;
    tickers: string[];
    train_ratio: number;
    combinations_tried: number;
    elapsed_seconds: number;
    best_params: Record<string, number>;
    train_avg_sharpe: number;
    test_avg_sharpe: number;
    overfitting: { score_pct: number; verdict: string; emoji: string };
    per_ticker: WFTickerReport[];
    top_10_combos: any[];
    saved_to: string | null;
}

interface BacktestPanelProps {
    ticker: string;
}

const MetricCard = ({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) => (
    <div style={{
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 12,
        padding: '1rem 1.25rem',
        minWidth: 130,
        flex: 1,
    }}>
        <div style={{ fontSize: 11, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>{label}</div>
        <div style={{ fontSize: 22, fontWeight: 700, color: color || '#f1f5f9' }}>{value}</div>
        {sub && <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>{sub}</div>}
    </div>
);

const verdictColor = (verdict: string) => {
    if (verdict === 'robust') return '#22c55e';
    if (verdict === 'moderate') return '#f59e0b';
    return '#ef4444';
};

const BacktestPanel: React.FC<BacktestPanelProps> = ({ ticker }) => {
    const [result, setResult] = useState<BacktestResult | null>(null);
    const [optimizeResult, setOptimizeResult] = useState<OptimizeResult | null>(null);
    const [wfResult, setWfResult] = useState<WFResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [optimizing, setOptimizing] = useState(false);
    const [wfOptimizing, setWfOptimizing] = useState(false);
    const [error, setError] = useState('');
    const [showAllTrades, setShowAllTrades] = useState(false);

    const runBacktest = async () => {
        setLoading(true);
        setError('');
        setResult(null);
        setOptimizeResult(null);
        setWfResult(null);
        try {
            const res = await fetch('http://localhost:8000/backtest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker }),
            });
            if (!res.ok) throw new Error(await res.text());
            setResult(await res.json());
        } catch (e: any) {
            setError(e.message || 'Backtest failed');
        } finally {
            setLoading(false);
        }
    };

    const runOptimize = async () => {
        setOptimizing(true);
        setError('');
        try {
            const res = await fetch('http://localhost:8000/optimize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker }),
            });
            if (!res.ok) throw new Error(await res.text());
            setOptimizeResult(await res.json());
        } catch (e: any) {
            setError(e.message || 'Optimization failed');
        } finally {
            setOptimizing(false);
        }
    };

    const runWalkForward = async () => {
        setWfOptimizing(true);
        setError('');
        setWfResult(null);
        try {
            // Fetch default tickers from config
            let tickers: string[] = [];
            try {
                const tickerRes = await fetch('http://localhost:8000/optimizer_tickers');
                if (tickerRes.ok) {
                    const data = await tickerRes.json();
                    tickers = data.tickers || [];
                }
            } catch { /* fall back to letting backend use its defaults */ }

            const res = await fetch('http://localhost:8000/optimize_wf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...(tickers.length > 0 ? { tickers } : {}),
                    train_ratio: 0.6,
                }),
            });
            if (!res.ok) throw new Error(await res.text());
            setWfResult(await res.json());
        } catch (e: any) {
            setError(e.message || 'Walk-forward optimization failed');
        } finally {
            setWfOptimizing(false);
        }
    };

    const busy = loading || optimizing || wfOptimizing;
    const m = result?.metrics;
    const trades = result?.trade_log || [];
    const displayedTrades = showAllTrades ? trades : trades.slice(0, 15);

    return (
        <div style={{
            marginTop: '2rem',
            background: 'linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(30,41,59,0.95) 100%)',
            border: '1px solid rgba(99,102,241,0.25)',
            borderRadius: 16,
            padding: '1.5rem',
            boxShadow: '0 4px 32px rgba(0,0,0,0.4)',
        }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                <div>
                    <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#a78bfa' }}>
                        🧪 Backtest — {ticker}
                    </h3>
                    {result && (
                        <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>
                            {result.start_date} → {result.end_date} · {result.bar_count} trading days
                        </div>
                    )}
                </div>
                <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                    <button
                        onClick={runBacktest}
                        disabled={busy}
                        style={{
                            padding: '0.5rem 1.25rem',
                            background: loading ? '#374151' : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                            color: 'white',
                            border: 'none',
                            borderRadius: 8,
                            fontWeight: 600,
                            cursor: busy ? 'not-allowed' : 'pointer',
                            fontSize: 13,
                            transition: 'all 0.2s',
                        }}
                    >
                        {loading ? '⏳ Running…' : '▶ Run Backtest'}
                    </button>
                    {result && (
                        <button
                            onClick={runOptimize}
                            disabled={busy}
                            style={{
                                padding: '0.5rem 1.25rem',
                                background: optimizing ? '#374151' : 'linear-gradient(135deg, #059669, #10b981)',
                                color: 'white',
                                border: 'none',
                                borderRadius: 8,
                                fontWeight: 600,
                                cursor: busy ? 'not-allowed' : 'pointer',
                                fontSize: 13,
                                transition: 'all 0.2s',
                            }}
                        >
                            {optimizing ? '⚙️ Optimizing…' : '⚡ Optimize Model'}
                        </button>
                    )}
                    <button
                        onClick={runWalkForward}
                        disabled={busy}
                        style={{
                            padding: '0.5rem 1.25rem',
                            background: wfOptimizing ? '#374151' : 'linear-gradient(135deg, #d97706, #f59e0b)',
                            color: 'white',
                            border: 'none',
                            borderRadius: 8,
                            fontWeight: 600,
                            cursor: busy ? 'not-allowed' : 'pointer',
                            fontSize: 13,
                            transition: 'all 0.2s',
                        }}
                    >
                        {wfOptimizing ? '🔄 Walk-Forward…' : '🎯 Walk-Forward Optimize'}
                    </button>
                </div>
            </div>

            {error && (
                <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444', borderRadius: 8, padding: '0.75rem 1rem', color: '#f87171', marginBottom: '1rem', fontSize: 13 }}>
                    {error}
                </div>
            )}

            {/* Metrics Grid */}
            {m && (
                <>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1rem' }}>
                        <MetricCard label="Win Rate" value={`${m.win_rate}%`} sub={`${m.winning_trades}W / ${m.losing_trades}L`} color={m.win_rate >= 50 ? '#22c55e' : '#f87171'} />
                        <MetricCard label="Model Return" value={`${m.total_return_pct > 0 ? '+' : ''}${m.total_return_pct}%`} color={m.total_return_pct >= 0 ? '#22c55e' : '#f87171'} />
                        <MetricCard label="Buy & Hold" value={`${m.buy_hold_return_pct > 0 ? '+' : ''}${m.buy_hold_return_pct}%`} color="#94a3b8" />
                        <MetricCard label="Alpha" value={`${m.alpha > 0 ? '+' : ''}${m.alpha}%`} sub="vs buy & hold" color={m.alpha >= 0 ? '#34d399' : '#f87171'} />
                        <MetricCard label="Sharpe Ratio" value={`${m.sharpe_ratio}`} color={m.sharpe_ratio >= 1 ? '#34d399' : m.sharpe_ratio >= 0 ? '#fbbf24' : '#f87171'} />
                        <MetricCard label="Max Drawdown" value={`-${m.max_drawdown_pct}%`} color="#f87171" />
                        <MetricCard label="Profit Factor" value={`${m.profit_factor}x`} color={m.profit_factor >= 1.5 ? '#22c55e' : '#fbbf24'} />
                        <MetricCard label="Avg Days Held" value={`${m.avg_days_held}d`} />
                    </div>

                    {/* Agent Accuracy */}
                    <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.25rem' }}>
                        {[
                            { label: 'Pattern Agent Accuracy', val: m.agent_accuracy.pattern },
                            { label: 'Quant Agent Accuracy', val: m.agent_accuracy.quant },
                        ].map(({ label, val }) => (
                            <div key={label} style={{ flex: 1, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 10, padding: '0.75rem 1rem' }}>
                                <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 6 }}>{label}</div>
                                <div style={{ height: 6, background: '#1f2937', borderRadius: 99, overflow: 'hidden' }}>
                                    <div style={{ height: '100%', width: `${val}%`, background: val >= 55 ? '#22c55e' : '#f59e0b', borderRadius: 99, transition: 'width 0.6s ease' }} />
                                </div>
                                <div style={{ fontSize: 13, fontWeight: 700, color: '#f1f5f9', marginTop: 4 }}>{val}%</div>
                            </div>
                        ))}
                    </div>
                </>
            )}

            {/* Single-Ticker Optimize Result */}
            {optimizeResult && (
                <div style={{ background: 'rgba(16,185,129,0.07)', border: '1px solid rgba(16,185,129,0.25)', borderRadius: 12, padding: '1rem 1.25rem', marginBottom: '1.25rem' }}>
                    <div style={{ fontWeight: 700, color: '#34d399', marginBottom: '0.75rem', fontSize: 14 }}>
                        ✅ Optimization Complete — {optimizeResult.combinations_tried} combinations tried
                    </div>
                    <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
                        {[
                            { label: 'Sharpe improvement', val: optimizeResult.improvement.sharpe, sign: true },
                            { label: 'Win rate improvement', val: optimizeResult.improvement.win_rate, sign: true, suffix: '%' },
                            { label: 'Return improvement', val: optimizeResult.improvement.total_return, sign: true, suffix: '%' },
                        ].map(({ label, val, sign, suffix }) => (
                            <div key={label}>
                                <div style={{ fontSize: 11, color: '#6b7280' }}>{label}</div>
                                <div style={{ fontSize: 16, fontWeight: 700, color: val >= 0 ? '#34d399' : '#f87171' }}>
                                    {sign && val >= 0 ? '+' : ''}{val}{suffix || ''}
                                </div>
                            </div>
                        ))}
                    </div>
                    <div style={{ fontSize: 12, color: '#6b7280' }}>
                        Best params: {Object.entries(optimizeResult.best_params).map(([k, v]) => `${k}=${v}`).join(' · ')}
                    </div>
                    <div style={{ fontSize: 12, color: '#34d399', marginTop: 4 }}>
                        ✓ Model updated — next analysis will use optimized parameters
                    </div>
                </div>
            )}

            {/* ═══════════════ Walk-Forward Optimization Results ═══════════════ */}
            {wfResult && (
                <div style={{
                    background: 'linear-gradient(135deg, rgba(217,119,6,0.08) 0%, rgba(245,158,11,0.04) 100%)',
                    border: '1px solid rgba(245,158,11,0.3)',
                    borderRadius: 14,
                    padding: '1.25rem 1.5rem',
                    marginBottom: '1.25rem',
                }}>
                    {/* WF Header */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1rem' }}>
                        <div>
                            <div style={{ fontWeight: 700, color: '#fbbf24', fontSize: 15 }}>
                                🎯 Walk-Forward Optimization Complete
                            </div>
                            <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>
                                {wfResult.tickers.length} tickers · {wfResult.combinations_tried} combos · {wfResult.elapsed_seconds}s
                                · Train {Math.round(wfResult.train_ratio * 100)}% / Test {Math.round((1 - wfResult.train_ratio) * 100)}%
                            </div>
                        </div>
                        {/* Overfitting badge */}
                        <div style={{
                            display: 'flex', alignItems: 'center', gap: '0.5rem',
                            padding: '0.5rem 1rem',
                            background: `${verdictColor(wfResult.overfitting.verdict)}15`,
                            border: `1px solid ${verdictColor(wfResult.overfitting.verdict)}40`,
                            borderRadius: 10,
                        }}>
                            <span style={{ fontSize: 20 }}>{wfResult.overfitting.emoji}</span>
                            <div>
                                <div style={{ fontSize: 11, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Overfitting</div>
                                <div style={{ fontSize: 16, fontWeight: 700, color: verdictColor(wfResult.overfitting.verdict) }}>
                                    {wfResult.overfitting.score_pct}% — {wfResult.overfitting.verdict}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Summary metrics row */}
                    <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                        <MetricCard label="Train Avg Sharpe" value={`${wfResult.train_avg_sharpe}`} color="#fbbf24" />
                        <MetricCard label="Test Avg Sharpe" value={`${wfResult.test_avg_sharpe}`} color={wfResult.test_avg_sharpe > 0 ? '#22c55e' : '#f87171'} />
                        <MetricCard label="Tickers" value={`${wfResult.tickers.length}`} sub={wfResult.tickers.join(', ')} />
                    </div>

                    {/* Per-ticker train vs test table */}
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#94a3b8', marginBottom: '0.5rem' }}>
                        Per-Ticker Train vs Test Performance
                    </div>
                    <div style={{ overflowX: 'auto', marginBottom: '1rem' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                            <thead>
                                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                                    <th style={{ padding: '0.4rem 0.75rem', textAlign: 'left', color: '#6b7280', fontWeight: 600 }}>Ticker</th>
                                    <th style={{ padding: '0.4rem 0.75rem', textAlign: 'right', color: '#fbbf24', fontWeight: 600 }}>Train Sharpe</th>
                                    <th style={{ padding: '0.4rem 0.75rem', textAlign: 'right', color: '#38bdf8', fontWeight: 600 }}>Test Sharpe</th>
                                    <th style={{ padding: '0.4rem 0.75rem', textAlign: 'right', color: '#fbbf24', fontWeight: 600 }}>Train Win%</th>
                                    <th style={{ padding: '0.4rem 0.75rem', textAlign: 'right', color: '#38bdf8', fontWeight: 600 }}>Test Win%</th>
                                    <th style={{ padding: '0.4rem 0.75rem', textAlign: 'right', color: '#fbbf24', fontWeight: 600 }}>Train Return</th>
                                    <th style={{ padding: '0.4rem 0.75rem', textAlign: 'right', color: '#38bdf8', fontWeight: 600 }}>Test Return</th>
                                    <th style={{ padding: '0.4rem 0.75rem', textAlign: 'right', color: '#6b7280', fontWeight: 600 }}>Trades</th>
                                </tr>
                            </thead>
                            <tbody>
                                {wfResult.per_ticker.map((pt) => (
                                    <tr key={pt.ticker} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                        <td style={{ padding: '0.4rem 0.75rem', color: '#e2e8f0', fontWeight: 600 }}>{pt.ticker}</td>
                                        <td style={{ padding: '0.4rem 0.75rem', textAlign: 'right', color: '#fbbf24' }}>{pt.train.sharpe}</td>
                                        <td style={{ padding: '0.4rem 0.75rem', textAlign: 'right', color: pt.test.sharpe >= 0 ? '#38bdf8' : '#f87171' }}>{pt.test.sharpe}</td>
                                        <td style={{ padding: '0.4rem 0.75rem', textAlign: 'right', color: '#fbbf24' }}>{pt.train.win_rate}%</td>
                                        <td style={{ padding: '0.4rem 0.75rem', textAlign: 'right', color: pt.test.win_rate >= 50 ? '#38bdf8' : '#f87171' }}>{pt.test.win_rate}%</td>
                                        <td style={{ padding: '0.4rem 0.75rem', textAlign: 'right', color: pt.train.total_return >= 0 ? '#fbbf24' : '#f87171' }}>
                                            {pt.train.total_return > 0 ? '+' : ''}{pt.train.total_return}%
                                        </td>
                                        <td style={{ padding: '0.4rem 0.75rem', textAlign: 'right', color: pt.test.total_return >= 0 ? '#38bdf8' : '#f87171' }}>
                                            {pt.test.total_return > 0 ? '+' : ''}{pt.test.total_return}%
                                        </td>
                                        <td style={{ padding: '0.4rem 0.75rem', textAlign: 'right', color: '#6b7280' }}>
                                            {pt.train.trades} / {pt.test.trades}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {/* Best params */}
                    <div style={{ fontSize: 12, color: '#6b7280' }}>
                        Best params: {Object.entries(wfResult.best_params)
                            .filter(([k]) => !k.startsWith('_'))
                            .map(([k, v]) => `${k}=${v}`).join(' · ')}
                    </div>
                    <div style={{ fontSize: 12, color: '#fbbf24', marginTop: 4 }}>
                        ✓ Model updated with cross-validated parameters
                    </div>
                </div>
            )}

            {/* Walk-Forward loading indicator */}
            {wfOptimizing && (
                <div style={{
                    background: 'rgba(245,158,11,0.07)',
                    border: '1px solid rgba(245,158,11,0.2)',
                    borderRadius: 12,
                    padding: '1.5rem',
                    marginBottom: '1.25rem',
                    textAlign: 'center',
                }}>
                    <div style={{ fontSize: 28, marginBottom: '0.5rem' }}>🔄</div>
                    <div style={{ fontWeight: 700, color: '#fbbf24', fontSize: 14, marginBottom: '0.25rem' }}>
                        Walk-Forward Optimization Running…
                    </div>
                    <div style={{ fontSize: 12, color: '#6b7280' }}>
                        Training across 8 tickers × 108 param combos. This may take 30–90 seconds.
                    </div>
                    <div style={{
                        marginTop: '0.75rem',
                        height: 4,
                        background: '#1f2937',
                        borderRadius: 99,
                        overflow: 'hidden',
                    }}>
                        <div style={{
                            height: '100%',
                            width: '100%',
                            background: 'linear-gradient(90deg, #d97706, #fbbf24, #d97706)',
                            borderRadius: 99,
                            animation: 'wf-pulse 1.5s ease-in-out infinite',
                        }} />
                    </div>
                    <style>{`
                        @keyframes wf-pulse {
                            0%, 100% { opacity: 0.4; transform: scaleX(0.3); }
                            50% { opacity: 1; transform: scaleX(1); }
                        }
                    `}</style>
                </div>
            )}

            {/* Trade Log */}
            {trades.length > 0 && (
                <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#94a3b8', marginBottom: '0.5rem' }}>
                        Trade Log ({trades.length} trades)
                    </div>
                    <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                            <thead>
                                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                                    {['Entry Date', 'Exit Date', 'Entry $', 'Exit $', 'P&L %', 'Days'].map(h => (
                                        <th key={h} style={{ padding: '0.4rem 0.75rem', textAlign: 'left', color: '#6b7280', fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {displayedTrades.map((t, i) => (
                                    <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', transition: 'background 0.15s' }}
                                        onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
                                        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                                    >
                                        <td style={{ padding: '0.4rem 0.75rem', color: '#94a3b8' }}>{t.entry_date}</td>
                                        <td style={{ padding: '0.4rem 0.75rem', color: '#94a3b8' }}>{t.exit_date}{t.note === 'open_at_end' ? ' ⏳' : ''}</td>
                                        <td style={{ padding: '0.4rem 0.75rem', color: '#e2e8f0' }}>${t.entry_price}</td>
                                        <td style={{ padding: '0.4rem 0.75rem', color: '#e2e8f0' }}>${t.exit_price}</td>
                                        <td style={{ padding: '0.4rem 0.75rem', fontWeight: 700, color: t.pnl_pct >= 0 ? '#22c55e' : '#f87171' }}>
                                            {t.pnl_pct >= 0 ? '+' : ''}{t.pnl_pct}%
                                        </td>
                                        <td style={{ padding: '0.4rem 0.75rem', color: '#6b7280' }}>{t.days_held}d</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    {trades.length > 15 && (
                        <button
                            onClick={() => setShowAllTrades(v => !v)}
                            style={{ marginTop: '0.5rem', background: 'none', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, padding: '0.35rem 0.75rem', color: '#6b7280', cursor: 'pointer', fontSize: 12 }}
                        >
                            {showAllTrades ? `▲ Show less` : `▼ Show all ${trades.length} trades`}
                        </button>
                    )}
                </div>
            )}

            {!result && !loading && !wfOptimizing && !wfResult && (
                <div style={{ textAlign: 'center', color: '#4b5563', padding: '2rem', fontSize: 14 }}>
                    Click <strong style={{ color: '#8b5cf6' }}>Run Backtest</strong> to simulate 5 years of {ticker} trading,
                    or <strong style={{ color: '#fbbf24' }}>Walk-Forward Optimize</strong> to tune across 8 tickers
                </div>
            )}
        </div>
    );
};

export default BacktestPanel;
