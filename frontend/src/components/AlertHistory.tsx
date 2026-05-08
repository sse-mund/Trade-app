import React, { useState, useEffect } from 'react';
import { Clock, AlertTriangle, TrendingUp, TrendingDown, Activity, BarChart3, Newspaper, Bell, ChevronDown, Trash2, RefreshCw } from 'lucide-react';

interface HistoryAlert {
    id: number;
    ticker: string;
    alert_type: string;
    severity: string;
    message: string;
    previous_recommendation: string | null;
    current_recommendation: string | null;
    previous_signal: number | null;
    current_signal: number | null;
    details: string | null;
    created_at: string;
}

interface AlertHistoryProps {
    onSelectTicker: (ticker: string) => void;
    refreshTrigger?: number; // increment to trigger refresh
}

const severityColors: Record<string, { accent: string; bg: string; border: string }> = {
    info:     { accent: '#3b82f6', bg: 'rgba(59,130,246,0.08)',  border: 'rgba(59,130,246,0.2)' },
    warning:  { accent: '#f59e0b', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.2)' },
    critical: { accent: '#ef4444', bg: 'rgba(239,68,68,0.08)',   border: 'rgba(239,68,68,0.2)' },
};

const alertTypeIcons: Record<string, React.ReactNode> = {
    trend_reversal: <TrendingDown size={12} />,
    rsi_oversold:   <TrendingUp size={12} />,
    rsi_overbought: <TrendingDown size={12} />,
    breakout:       <Activity size={12} />,
    volume_spike:   <BarChart3 size={12} />,
    sentiment_flip: <Newspaper size={12} />,
    buzz_spike:     <Bell size={12} />,
};

const alertTypeLabels: Record<string, string> = {
    trend_reversal: 'Trend Reversal',
    rsi_oversold:   'RSI Oversold',
    rsi_overbought: 'RSI Overbought',
    breakout:       'Breakout',
    volume_spike:   'Volume Spike',
    sentiment_flip: 'Sentiment Flip',
    buzz_spike:     'News Buzz',
};

const recColor = (rec: string | null) => {
    if (rec === 'BUY') return '#22c55e';
    if (rec === 'SELL') return '#ef4444';
    if (rec === 'HOLD') return '#f59e0b';
    return '#6b7280';
};

const AlertHistory: React.FC<AlertHistoryProps> = ({ onSelectTicker, refreshTrigger }) => {
    const [alerts, setAlerts] = useState<HistoryAlert[]>([]);
    const [collapsed, setCollapsed] = useState(true);
    const [loading, setLoading] = useState(false);
    const [filterSeverity, setFilterSeverity] = useState<string | null>(null);
    const [filterType, setFilterType] = useState<string | null>(null);

    const HOURS_WINDOW = 8;

    const fetchHistory = async () => {
        setLoading(true);
        try {
            const res = await fetch(`http://localhost:8000/alerts/history?limit=200&hours=${HOURS_WINDOW}`);
            if (!res.ok) throw new Error('Failed');
            const data = await res.json();
            // Client-side guard: drop anything older than HOURS_WINDOW regardless of backend response
            const cutoff = Date.now() - HOURS_WINDOW * 60 * 60 * 1000;
            const fresh = (data.alerts || []).filter((a: HistoryAlert) => {
                const ts = a.created_at.includes('T') || a.created_at.endsWith('Z')
                    ? a.created_at
                    : a.created_at + ' UTC';
                return new Date(ts).getTime() >= cutoff;
            });
            setAlerts(fresh);
        } catch (e) {
            console.error('Failed to fetch alert history:', e);
        } finally {
            setLoading(false);
        }
    };

    // Fetch on mount and when trigger changes
    useEffect(() => {
        fetchHistory();
    }, [refreshTrigger]);

    const filteredAlerts = alerts.filter(a => {
        if (filterSeverity && a.severity !== filterSeverity) return false;
        if (filterType && a.alert_type !== filterType) return false;
        return true;
    });

    const severityCounts = {
        critical: alerts.filter(a => a.severity === 'critical').length,
        warning:  alerts.filter(a => a.severity === 'warning').length,
        info:     alerts.filter(a => a.severity === 'info').length,
    };

    const hasAlerts = alerts.length > 0;

    const formatTime = (ts: string) => {
        try {
            // SQLite stores created_at without timezone info — append ' UTC'
            // so the browser correctly converts to the user's local timezone (e.g. CDT)
            const d = new Date(ts.includes('T') || ts.endsWith('Z') ? ts : ts + ' UTC');
            if (isNaN(d.getTime())) return ts;
            return d.toLocaleString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                hour12: true,
            });
        } catch {
            return ts;
        }
    };

    return (
        <div style={{
            background: 'linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(30,41,59,0.9) 100%)',
            border: '1px solid rgba(251,191,36,0.15)',
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
                    <Clock size={15} style={{ color: '#fbbf24' }} />
                    <span style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', letterSpacing: '0.02em' }}>
                        Alert History
                    </span>
                    <span style={{ fontSize: 11, color: '#6b7280', fontWeight: 500 }}>
                        {hasAlerts
                            ? `${alerts.length} in last 8h`
                            : 'Last 8 hours'
                        }
                    </span>
                    {/* Severity summary badges */}
                    {severityCounts.critical > 0 && (
                        <span style={{
                            fontSize: 10, fontWeight: 700, color: '#ef4444',
                            background: 'rgba(239,68,68,0.12)', borderRadius: 8,
                            padding: '0.05rem 0.4rem',
                        }}>
                            {severityCounts.critical} critical
                        </span>
                    )}
                    {severityCounts.warning > 0 && (
                        <span style={{
                            fontSize: 10, fontWeight: 700, color: '#f59e0b',
                            background: 'rgba(245,158,11,0.12)', borderRadius: 8,
                            padding: '0.05rem 0.4rem',
                        }}>
                            {severityCounts.warning} warning
                        </span>
                    )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {!collapsed && (
                        <button
                            onClick={(e) => { e.stopPropagation(); fetchHistory(); }}
                            style={{
                                display: 'flex', alignItems: 'center', gap: '0.25rem',
                                padding: '0.25rem 0.5rem', background: 'rgba(255,255,255,0.04)',
                                border: '1px solid rgba(255,255,255,0.08)', borderRadius: 6,
                                color: '#6b7280', fontSize: 11, cursor: 'pointer',
                                transition: 'all 0.15s',
                            }}
                            title="Refresh"
                        >
                            <RefreshCw size={11} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
                        </button>
                    )}
                    <ChevronDown
                        size={16}
                        style={{
                            color: '#6b7280',
                            transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
                            transition: 'transform 0.2s',
                        }}
                    />
                </div>
            </div>

            {/* Body */}
            {!collapsed && (
                <div style={{ marginTop: '0.75rem' }}>
                    {!hasAlerts ? (
                        <div style={{
                            textAlign: 'center',
                            padding: '1.25rem 1rem',
                            color: '#4b5563',
                            fontSize: 12,
                            lineHeight: 1.6,
                        }}>
                            <div style={{ fontSize: 20, marginBottom: '0.5rem' }}>🔔</div>
                            <div style={{ color: '#6b7280', fontWeight: 600, marginBottom: '0.25rem' }}>
                                No alerts in the last 8 hours
                            </div>
                            <div>
                                The monitor scans your watchlist every 10 minutes. Alerts appear here when trend reversals, RSI crossings, breakouts, volume spikes, or sentiment shifts are detected.
                            </div>
                        </div>
                    ) : (
                    <>
                    {/* Filters */}
                    <div style={{ display: 'flex', gap: '0.35rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
                        {/* Severity filters */}
                        {(['critical', 'warning', 'info'] as const).map(sev => {
                            const active = filterSeverity === sev;
                            const colors = severityColors[sev];
                            return (
                                <button
                                    key={sev}
                                    onClick={() => setFilterSeverity(active ? null : sev)}
                                    style={{
                                        fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
                                        letterSpacing: '0.04em',
                                        padding: '0.2rem 0.55rem', borderRadius: 6,
                                        border: `1px solid ${active ? colors.accent : 'rgba(255,255,255,0.08)'}`,
                                        background: active ? colors.bg : 'transparent',
                                        color: active ? colors.accent : '#6b7280',
                                        cursor: 'pointer', transition: 'all 0.15s',
                                    }}
                                >
                                    {sev}
                                </button>
                            );
                        })}
                        <span style={{ width: 1, background: 'rgba(255,255,255,0.08)', margin: '0 0.15rem' }} />
                        {/* Type filters */}
                        {Object.entries(alertTypeLabels).map(([type, label]) => {
                            const active = filterType === type;
                            return (
                                <button
                                    key={type}
                                    onClick={() => setFilterType(active ? null : type)}
                                    style={{
                                        fontSize: 10, fontWeight: 500,
                                        padding: '0.2rem 0.55rem', borderRadius: 6,
                                        border: `1px solid ${active ? '#818cf8' : 'rgba(255,255,255,0.06)'}`,
                                        background: active ? 'rgba(129,140,248,0.1)' : 'transparent',
                                        color: active ? '#818cf8' : '#4b5563',
                                        cursor: 'pointer', transition: 'all 0.15s',
                                        display: 'flex', alignItems: 'center', gap: '0.25rem',
                                    }}
                                >
                                    {alertTypeIcons[type]}
                                    {label}
                                </button>
                            );
                        })}
                    </div>

                    {/* Alert timeline */}
                    <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                        {filteredAlerts.length === 0 ? (
                            <div style={{ textAlign: 'center', padding: '1rem', color: '#4b5563', fontSize: 12 }}>
                                No alerts match the current filter
                            </div>
                        ) : (
                            filteredAlerts.map((alert) => {
                                const colors = severityColors[alert.severity] || severityColors.info;
                                return (
                                    <div
                                        key={alert.id}
                                        onClick={() => onSelectTicker(alert.ticker)}
                                        style={{
                                            display: 'flex',
                                            gap: '0.6rem',
                                            padding: '0.55rem 0.6rem',
                                            borderBottom: '1px solid rgba(255,255,255,0.03)',
                                            cursor: 'pointer',
                                            transition: 'background 0.15s',
                                            borderRadius: 6,
                                        }}
                                        onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
                                        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                                    >
                                        {/* Timeline dot */}
                                        <div style={{
                                            display: 'flex',
                                            flexDirection: 'column',
                                            alignItems: 'center',
                                            paddingTop: '0.15rem',
                                        }}>
                                            <div style={{
                                                width: 8, height: 8, borderRadius: '50%',
                                                background: colors.accent,
                                                boxShadow: `0 0 6px ${colors.accent}60`,
                                                flexShrink: 0,
                                            }} />
                                            <div style={{
                                                width: 1, flex: 1,
                                                background: 'rgba(255,255,255,0.06)',
                                                marginTop: '0.2rem',
                                            }} />
                                        </div>

                                        {/* Content */}
                                        <div style={{ flex: 1, minWidth: 0 }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', marginBottom: '0.2rem' }}>
                                                <span style={{
                                                    fontSize: 12, fontWeight: 700, color: '#e2e8f0',
                                                }}>
                                                    {alert.ticker}
                                                </span>
                                                <span style={{
                                                    fontSize: 9, fontWeight: 600, textTransform: 'uppercase',
                                                    letterSpacing: '0.04em',
                                                    color: colors.accent,
                                                    background: `${colors.accent}18`,
                                                    padding: '0.05rem 0.35rem',
                                                    borderRadius: 3,
                                                }}>
                                                    {alert.severity}
                                                </span>
                                                <span style={{
                                                    fontSize: 9, color: '#4b5563',
                                                    display: 'flex', alignItems: 'center', gap: '0.2rem',
                                                }}>
                                                    {alertTypeIcons[alert.alert_type]}
                                                    {alertTypeLabels[alert.alert_type] || alert.alert_type}
                                                </span>
                                                {/* Recommendation badges */}
                                                {alert.previous_recommendation && alert.current_recommendation &&
                                                 alert.previous_recommendation !== alert.current_recommendation && (
                                                    <span style={{ fontSize: 10, display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                                                        <span style={{ color: recColor(alert.previous_recommendation), fontWeight: 600, textDecoration: 'line-through', opacity: 0.6 }}>
                                                            {alert.previous_recommendation}
                                                        </span>
                                                        <span style={{ color: '#4b5563' }}>→</span>
                                                        <span style={{ color: recColor(alert.current_recommendation), fontWeight: 700 }}>
                                                            {alert.current_recommendation}
                                                        </span>
                                                    </span>
                                                )}
                                            </div>
                                            <div style={{
                                                fontSize: 11, color: '#94a3b8', lineHeight: 1.4,
                                                overflow: 'hidden', textOverflow: 'ellipsis',
                                                whiteSpace: 'nowrap',
                                            }}>
                                                {alert.message}
                                            </div>
                                        </div>

                                        {/* Timestamp */}
                                        <div style={{
                                            fontSize: 10, color: '#4b5563',
                                            whiteSpace: 'nowrap', flexShrink: 0,
                                            paddingTop: '0.15rem',
                                        }}>
                                            {formatTime(alert.created_at)}
                                        </div>
                                    </div>
                                );
                            })
                        )}
                    </div>
                    </>
                    )}
                </div>
            )}

            <style>{`
                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    );
};

export default AlertHistory;
