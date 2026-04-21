import React, { useState, useEffect, useCallback } from 'react';
import { Plus, X, Star, TrendingUp, RefreshCw } from 'lucide-react';

interface WatchlistProps {
    onSelectTicker: (ticker: string) => void;
    activeTicker?: string;
}

interface ScanResult {
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
}

const STORAGE_KEY = 'trade_strategy_watchlist';

const loadWatchlist = (): string[] => {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch {
        return [];
    }
};

const saveWatchlist = (list: string[]) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
};

const recColor = (rec: string) => {
    if (rec === 'BUY') return '#22c55e';
    if (rec === 'SELL') return '#ef4444';
    if (rec === 'HOLD') return '#f59e0b';
    return '#6b7280';
};

const recBg = (rec: string) => {
    if (rec === 'BUY') return 'rgba(34,197,94,0.12)';
    if (rec === 'SELL') return 'rgba(239,68,68,0.12)';
    if (rec === 'HOLD') return 'rgba(245,158,11,0.12)';
    return 'rgba(107,114,128,0.12)';
};

const riskColor = (risk: string) => {
    if (risk === 'Low') return '#22c55e';
    if (risk === 'Medium') return '#f59e0b';
    if (risk === 'High') return '#ef4444';
    return '#6b7280';
};

const Watchlist: React.FC<WatchlistProps> = ({ onSelectTicker, activeTicker }) => {
    const [tickers, setTickers] = useState<string[]>(loadWatchlist);
    const [input, setInput] = useState('');
    const [isAdding, setIsAdding] = useState(false);
    const [collapsed, setCollapsed] = useState(false);
    const [scanResults, setScanResults] = useState<ScanResult[]>([]);
    const [scanning, setScanning] = useState(false);
    const [lastScanTime, setLastScanTime] = useState<string | null>(null);

    useEffect(() => {
        saveWatchlist(tickers);
    }, [tickers]);

    const addTicker = () => {
        const t = input.trim().toUpperCase();
        if (!t || tickers.includes(t)) {
            setInput('');
            setIsAdding(false);
            return;
        }
        setTickers(prev => [...prev, t]);
        setInput('');
        setIsAdding(false);
    };

    const removeTicker = (t: string, e: React.MouseEvent) => {
        e.stopPropagation();
        setTickers(prev => prev.filter(x => x !== t));
        setScanResults(prev => prev.filter(r => r.ticker !== t));
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            addTicker();
        }
        if (e.key === 'Escape') {
            setIsAdding(false);
            setInput('');
        }
    };

    const [scanProgress, setScanProgress] = useState('');

    const runScan = useCallback(async () => {
        if (tickers.length === 0) return;
        setScanning(true);
        setScanResults([]);
        setScanProgress(`0/${tickers.length} scanned`);

        try {
            const res = await fetch('http://localhost:8000/batch_scan_stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tickers }),
            });
            if (!res.ok) throw new Error(await res.text());

            const reader = res.body?.getReader();
            if (!reader) throw new Error('No stream reader');

            const decoder = new TextDecoder();
            let buffer = '';
            let completed = 0;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const payload = JSON.parse(line.slice(6));
                        if (payload.type === 'result') {
                            completed++;
                            setScanProgress(`${completed}/${tickers.length} scanned`);
                            setScanResults(prev => {
                                const filtered = prev.filter(r => r.ticker !== payload.ticker);
                                return [...filtered, payload];
                            });
                        } else if (payload.type === 'done') {
                            setScanProgress('');
                        }
                    } catch { /* skip malformed SSE lines */ }
                }
            }

            setLastScanTime(new Date().toLocaleTimeString());
        } catch (e: any) {
            console.error('Batch scan stream failed:', e);
        } finally {
            setScanning(false);
            setScanProgress('');
        }
    }, [tickers]);

    // Auto-scan when tickers change
    const prevTickersLen = React.useRef(tickers.length);
    useEffect(() => {
        // Scan on initial load if we have tickers, OR if a new ticker was added
        if (tickers.length > 0 && (scanResults.length === 0 || tickers.length > prevTickersLen.current)) {
            runScan();
        }
        prevTickersLen.current = tickers.length;
    }, [tickers.length]); // eslint-disable-line react-hooks/exhaustive-deps

    return (
        <div style={{
            background: 'linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(30,41,59,0.9) 100%)',
            border: '1px solid rgba(99,102,241,0.2)',
            borderRadius: 14,
            padding: collapsed ? '0.75rem 1.25rem' : '1rem 1.25rem 1.25rem',
            marginBottom: '1.5rem',
            boxShadow: '0 2px 20px rgba(0,0,0,0.3)',
            transition: 'all 0.3s ease',
        }}>
            {/* Header */}
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    userSelect: 'none',
                }}
                onClick={() => setCollapsed(c => !c)}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Star size={16} style={{ color: '#fbbf24' }} />
                    <span style={{
                        fontSize: 14,
                        fontWeight: 700,
                        color: '#f1f5f9',
                        letterSpacing: '0.02em',
                    }}>
                        Watchlist
                    </span>
                    <span style={{
                        fontSize: 11,
                        color: '#6b7280',
                        fontWeight: 500,
                    }}>
                        {tickers.length} {tickers.length === 1 ? 'ticker' : 'tickers'}
                    </span>
                    {lastScanTime && (
                        <span style={{ fontSize: 10, color: '#4b5563', marginLeft: '0.25rem' }}>
                            · scanned {lastScanTime}
                        </span>
                    )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {!collapsed && tickers.length > 0 && (
                        <button
                            onClick={(e) => { e.stopPropagation(); runScan(); }}
                            disabled={scanning}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.35rem',
                                padding: '0.3rem 0.75rem',
                                background: scanning ? '#374151' : 'linear-gradient(135deg, #059669, #10b981)',
                                color: 'white',
                                border: 'none',
                                borderRadius: 6,
                                fontSize: 12,
                                fontWeight: 600,
                                cursor: scanning ? 'not-allowed' : 'pointer',
                                transition: 'all 0.2s',
                            }}
                            title="Scan all tickers for recommendations"
                        >
                            <RefreshCw size={12} style={{ animation: scanning ? 'spin 1s linear infinite' : 'none' }} />
                            {scanning ? (scanProgress || 'Scanning…') : 'Scan All'}
                        </button>
                    )}
                    {!collapsed && (
                        <button
                            onClick={(e) => { e.stopPropagation(); setIsAdding(true); }}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.35rem',
                                padding: '0.3rem 0.75rem',
                                background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                                color: 'white',
                                border: 'none',
                                borderRadius: 6,
                                fontSize: 12,
                                fontWeight: 600,
                                cursor: 'pointer',
                                transition: 'all 0.2s',
                            }}
                            title="Add ticker"
                        >
                            <Plus size={13} />
                            Add
                        </button>
                    )}
                    <span style={{
                        color: '#6b7280',
                        fontSize: 14,
                        transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
                        transition: 'transform 0.2s',
                        display: 'inline-block',
                    }}>
                        ▾
                    </span>
                </div>
            </div>

            {/* Body */}
            {!collapsed && (
                <div style={{ marginTop: '0.75rem' }}>
                    {/* Add ticker input */}
                    {isAdding && (
                        <div style={{
                            display: 'flex',
                            gap: '0.5rem',
                            marginBottom: '0.75rem',
                            animation: 'fadeIn 0.2s ease',
                        }}>
                            <input
                                autoFocus
                                type="text"
                                placeholder="e.g. AAPL"
                                value={input}
                                onChange={e => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                style={{
                                    flex: 1,
                                    padding: '0.4rem 0.75rem',
                                    background: 'rgba(255,255,255,0.05)',
                                    border: '1px solid rgba(99,102,241,0.3)',
                                    borderRadius: 6,
                                    color: '#f1f5f9',
                                    fontSize: 13,
                                    outline: 'none',
                                    fontFamily: 'inherit',
                                    textTransform: 'uppercase',
                                }}
                            />
                            <button
                                onClick={addTicker}
                                style={{
                                    padding: '0.4rem 0.75rem',
                                    background: '#22c55e',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: 6,
                                    fontSize: 12,
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                }}
                            >
                                Add
                            </button>
                            <button
                                onClick={() => { setIsAdding(false); setInput(''); }}
                                style={{
                                    padding: '0.4rem 0.6rem',
                                    background: 'transparent',
                                    color: '#6b7280',
                                    border: '1px solid rgba(255,255,255,0.1)',
                                    borderRadius: 6,
                                    fontSize: 12,
                                    cursor: 'pointer',
                                }}
                            >
                                Cancel
                            </button>
                        </div>
                    )}

                    {/* ═══ Summary Table ═══ */}
                    {scanResults.length > 0 ? (
                        <div style={{ overflowX: 'auto', marginBottom: '0.75rem' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                                <thead>
                                    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                                        <th style={thStyle}>Ticker</th>
                                        <th style={thStyle}>Price</th>
                                        <th style={thStyle}>Change</th>
                                        <th style={thStyle}>Signal</th>
                                        <th style={thStyle}>Confidence</th>
                                        <th style={thStyle}>Regime</th>
                                        <th style={thStyle}>Risk</th>
                                        <th style={{ ...thStyle, minWidth: 180 }}>Insight</th>
                                        <th style={thStyle}></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {scanResults.map(r => {
                                        const isActive = activeTicker?.toUpperCase() === r.ticker;
                                        return (
                                            <tr
                                                key={r.ticker}
                                                onClick={() => onSelectTicker(r.ticker)}
                                                style={{
                                                    borderBottom: '1px solid rgba(255,255,255,0.04)',
                                                    cursor: 'pointer',
                                                    transition: 'background 0.15s',
                                                    background: isActive ? 'rgba(99,102,241,0.08)' : 'transparent',
                                                }}
                                                onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
                                                onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
                                            >
                                                <td style={{ ...tdStyle, fontWeight: 700, color: '#e2e8f0' }}>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                                                        <TrendingUp size={12} style={{ opacity: 0.5 }} />
                                                        {r.ticker}
                                                    </div>
                                                </td>
                                                <td style={{ ...tdStyle, color: '#f1f5f9', fontWeight: 600 }}>
                                                    {r.current_price != null ? `$${r.current_price}` : '—'}
                                                </td>
                                                <td style={{
                                                    ...tdStyle,
                                                    fontWeight: 600,
                                                    color: r.change_pct != null ? (r.change_pct >= 0 ? '#22c55e' : '#ef4444') : '#6b7280',
                                                }}>
                                                    {r.change_pct != null ? `${r.change_pct >= 0 ? '+' : ''}${r.change_pct}%` : '—'}
                                                </td>
                                                <td style={tdStyle}>
                                                    <span style={{
                                                        display: 'inline-block',
                                                        padding: '0.2rem 0.6rem',
                                                        borderRadius: 6,
                                                        fontSize: 11,
                                                        fontWeight: 700,
                                                        color: recColor(r.recommendation),
                                                        background: recBg(r.recommendation),
                                                        letterSpacing: '0.03em',
                                                    }}>
                                                        {r.recommendation}
                                                    </span>
                                                </td>
                                                <td style={tdStyle}>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                                        <div style={{
                                                            width: 40,
                                                            height: 5,
                                                            background: '#1f2937',
                                                            borderRadius: 99,
                                                            overflow: 'hidden',
                                                        }}>
                                                            <div style={{
                                                                height: '100%',
                                                                width: `${(r.confidence || 0) * 100}%`,
                                                                background: r.confidence > 0.6 ? '#22c55e' : r.confidence > 0.3 ? '#f59e0b' : '#ef4444',
                                                                borderRadius: 99,
                                                                transition: 'width 0.3s',
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
                                                <td style={{
                                                    ...tdStyle,
                                                    color: '#6b7280',
                                                    fontSize: 11,
                                                    maxWidth: 220,
                                                    overflow: 'hidden',
                                                    textOverflow: 'ellipsis',
                                                    whiteSpace: 'nowrap',
                                                }}
                                                    title={r.key_insight}
                                                >
                                                    {r.key_insight}
                                                </td>
                                                <td style={tdStyle}>
                                                    <span
                                                        onClick={(e) => removeTicker(r.ticker, e)}
                                                        style={{
                                                            opacity: 0.3,
                                                            cursor: 'pointer',
                                                            transition: 'opacity 0.15s',
                                                        }}
                                                        onMouseEnter={e => (e.currentTarget.style.opacity = '1')}
                                                        onMouseLeave={e => (e.currentTarget.style.opacity = '0.3')}
                                                        title={`Remove ${r.ticker}`}
                                                    >
                                                        <X size={13} />
                                                    </span>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                    {/* Render pending tickers that were just added but not yet scanned */}
                                    {tickers.filter(t => !scanResults.find(r => r.ticker === t)).map(t => {
                                        const isActive = activeTicker?.toUpperCase() === t;
                                        return (
                                            <tr
                                                key={`pending-${t}`}
                                                style={{
                                                    borderBottom: '1px solid rgba(255,255,255,0.04)',
                                                    background: isActive ? 'rgba(99,102,241,0.08)' : 'transparent',
                                                }}
                                            >
                                                <td style={{ ...tdStyle, fontWeight: 700, color: '#e2e8f0', opacity: 0.6 }}>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                                                        <TrendingUp size={12} style={{ opacity: 0.5 }} />
                                                        {t}
                                                    </div>
                                                </td>
                                                <td colSpan={7} style={{ ...tdStyle, color: '#6b7280', fontStyle: 'italic', fontSize: 11 }}>
                                                    Scanning...
                                                </td>
                                                <td style={tdStyle}>
                                                    <span
                                                        onClick={(e) => removeTicker(t, e)}
                                                        style={{ opacity: 0.3, cursor: 'pointer', transition: 'opacity 0.15s' }}
                                                        onMouseEnter={e => (e.currentTarget.style.opacity = '1')}
                                                        onMouseLeave={e => (e.currentTarget.style.opacity = '0.3')}
                                                    >
                                                        <X size={13} />
                                                    </span>
                                                </td>
                                            </tr>
                                        )
                                    })}
                                </tbody>
                            </table>
                        </div>
                    ) : tickers.length > 0 ? (
                        <div style={{
                            display: 'flex',
                            flexWrap: 'wrap',
                            gap: '0.5rem',
                            marginBottom: '0.5rem',
                        }}>
                            {tickers.map(t => {
                                const isActive = activeTicker?.toUpperCase() === t;
                                return (
                                    <button
                                        key={t}
                                        onClick={() => onSelectTicker(t)}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '0.4rem',
                                            padding: '0.4rem 0.75rem',
                                            background: isActive
                                                ? 'linear-gradient(135deg, rgba(99,102,241,0.3), rgba(139,92,246,0.2))'
                                                : 'rgba(255,255,255,0.04)',
                                            border: isActive
                                                ? '1px solid rgba(139,92,246,0.5)'
                                                : '1px solid rgba(255,255,255,0.08)',
                                            borderRadius: 8,
                                            color: isActive ? '#c4b5fd' : '#e2e8f0',
                                            fontSize: 13,
                                            fontWeight: 600,
                                            cursor: 'pointer',
                                            transition: 'all 0.2s',
                                        }}
                                    >
                                        <TrendingUp size={12} style={{ opacity: 0.6 }} />
                                        {t}
                                        <span
                                            onClick={(e) => removeTicker(t, e)}
                                            style={{ opacity: 0.4, cursor: 'pointer' }}
                                        >
                                            <X size={13} />
                                        </span>
                                    </button>
                                );
                            })}
                        </div>
                    ) : (
                        <div style={{
                            textAlign: 'center',
                            padding: '1rem',
                            color: '#4b5563',
                            fontSize: 13,
                        }}>
                            No tickers yet — click <strong style={{ color: '#8b5cf6' }}>+ Add</strong> to start building your watchlist
                        </div>
                    )}
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
            `}</style>
        </div>
    );
};

const thStyle: React.CSSProperties = {
    padding: '0.4rem 0.6rem',
    textAlign: 'left',
    color: '#6b7280',
    fontWeight: 600,
    whiteSpace: 'nowrap',
    fontSize: 11,
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
};

const tdStyle: React.CSSProperties = {
    padding: '0.5rem 0.6rem',
    whiteSpace: 'nowrap',
};

export default Watchlist;
