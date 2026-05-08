import React, { useEffect, useState } from 'react';
import { AlertTriangle, TrendingUp, TrendingDown, Activity, BarChart3, Newspaper, Bell, X } from 'lucide-react';

export interface AlertData {
    id?: number;
    ticker: string;
    alert_type: string;
    severity: 'info' | 'warning' | 'critical';
    message: string;
    previous_recommendation?: string;
    current_recommendation?: string;
    previous_signal?: number;
    current_signal?: number;
    details?: Record<string, any>;
    created_at?: string;
    timestamp?: number; // client-side timestamp
}

interface AlertToastProps {
    alert: AlertData;
    index: number;
    onDismiss: () => void;
    onClickTicker: (ticker: string) => void;
    autoDismissMs?: number;
}

const severityConfig = {
    info: {
        bg: 'rgba(59, 130, 246, 0.12)',
        border: 'rgba(59, 130, 246, 0.4)',
        glow: 'rgba(59, 130, 246, 0.15)',
        text: '#93c5fd',
        accent: '#3b82f6',
        icon: <Bell size={16} />,
    },
    warning: {
        bg: 'rgba(245, 158, 11, 0.12)',
        border: 'rgba(245, 158, 11, 0.4)',
        glow: 'rgba(245, 158, 11, 0.15)',
        text: '#fcd34d',
        accent: '#f59e0b',
        icon: <AlertTriangle size={16} />,
    },
    critical: {
        bg: 'rgba(239, 68, 68, 0.15)',
        border: 'rgba(239, 68, 68, 0.5)',
        glow: 'rgba(239, 68, 68, 0.2)',
        text: '#fca5a5',
        accent: '#ef4444',
        icon: <AlertTriangle size={16} />,
    },
};

const alertTypeIcons: Record<string, React.ReactNode> = {
    trend_reversal: <TrendingDown size={14} />,
    rsi_oversold: <TrendingUp size={14} />,
    rsi_overbought: <TrendingDown size={14} />,
    breakout: <Activity size={14} />,
    volume_spike: <BarChart3 size={14} />,
    sentiment_flip: <Newspaper size={14} />,
    buzz_spike: <Bell size={14} />,
};

const AlertToast: React.FC<AlertToastProps> = ({
    alert,
    index,
    onDismiss,
    onClickTicker,
    autoDismissMs = 12000,
}) => {
    const [isExiting, setIsExiting] = useState(false);
    const [progress, setProgress] = useState(100);
    const config = severityConfig[alert.severity] || severityConfig.info;

    useEffect(() => {
        const startTime = Date.now();
        const interval = setInterval(() => {
            const elapsed = Date.now() - startTime;
            const remaining = Math.max(0, 100 - (elapsed / autoDismissMs) * 100);
            setProgress(remaining);
            if (remaining <= 0) {
                clearInterval(interval);
                handleDismiss();
            }
        }, 50);
        return () => clearInterval(interval);
    }, [autoDismissMs]);

    const handleDismiss = () => {
        setIsExiting(true);
        setTimeout(onDismiss, 300);
    };

    return (
        <div
            className={`alert-toast ${isExiting ? 'alert-toast--exit' : 'alert-toast--enter'}`}
            style={{
                position: 'relative',
                background: config.bg,
                border: `1px solid ${config.border}`,
                borderRadius: 12,
                padding: '0.85rem 1rem',
                marginBottom: '0.5rem',
                boxShadow: `0 4px 24px ${config.glow}, 0 2px 8px rgba(0,0,0,0.3)`,
                backdropFilter: 'blur(12px)',
                cursor: 'pointer',
                transition: 'all 0.3s ease',
                maxWidth: 420,
                overflow: 'hidden',
                animationDelay: `${index * 0.08}s`,
            }}
            onClick={() => onClickTicker(alert.ticker)}
        >
            {/* Progress bar */}
            <div style={{
                position: 'absolute',
                bottom: 0,
                left: 0,
                height: 2,
                width: `${progress}%`,
                background: config.accent,
                borderRadius: '0 0 12px 12px',
                transition: 'width 0.05s linear',
                opacity: 0.6,
            }} />

            {/* Header row */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <span style={{ color: config.accent, display: 'flex' }}>{config.icon}</span>
                    <span style={{
                        fontSize: 10,
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                        color: config.accent,
                        padding: '0.1rem 0.4rem',
                        background: `${config.accent}22`,
                        borderRadius: 4,
                    }}>
                        {alert.severity}
                    </span>
                    <span style={{
                        fontSize: 13,
                        fontWeight: 700,
                        color: '#f1f5f9',
                        marginLeft: '0.2rem',
                    }}>
                        {alert.ticker}
                    </span>
                </div>
                <button
                    onClick={(e) => { e.stopPropagation(); handleDismiss(); }}
                    style={{
                        background: 'none',
                        border: 'none',
                        color: '#6b7280',
                        cursor: 'pointer',
                        padding: '0.15rem',
                        display: 'flex',
                        transition: 'color 0.15s',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.color = '#e2e8f0')}
                    onMouseLeave={e => (e.currentTarget.style.color = '#6b7280')}
                >
                    <X size={14} />
                </button>
            </div>

            {/* Message */}
            <div style={{
                fontSize: 12,
                color: config.text,
                lineHeight: 1.5,
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.4rem',
            }}>
                <span style={{ color: config.accent, marginTop: '0.1rem', flexShrink: 0, display: 'flex' }}>
                    {alertTypeIcons[alert.alert_type] || <Activity size={14} />}
                </span>
                <span>{alert.message}</span>
            </div>

            {/* Recommendation change badge */}
            {alert.previous_recommendation && alert.current_recommendation &&
             alert.previous_recommendation !== alert.current_recommendation && (
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    marginTop: '0.4rem',
                    fontSize: 11,
                }}>
                    <span style={{
                        padding: '0.15rem 0.5rem',
                        borderRadius: 4,
                        background: recBg(alert.previous_recommendation),
                        color: recColor(alert.previous_recommendation),
                        fontWeight: 700,
                        textDecoration: 'line-through',
                        opacity: 0.7,
                    }}>
                        {alert.previous_recommendation}
                    </span>
                    <span style={{ color: '#6b7280' }}>→</span>
                    <span style={{
                        padding: '0.15rem 0.5rem',
                        borderRadius: 4,
                        background: recBg(alert.current_recommendation),
                        color: recColor(alert.current_recommendation),
                        fontWeight: 700,
                    }}>
                        {alert.current_recommendation}
                    </span>
                </div>
            )}

            {/* Click hint */}
            <div style={{
                fontSize: 10,
                color: '#4b5563',
                marginTop: '0.35rem',
                textAlign: 'right',
            }}>
                Click for full analysis →
            </div>
        </div>
    );
};

const recColor = (rec: string) => {
    if (rec === 'BUY') return '#22c55e';
    if (rec === 'SELL') return '#ef4444';
    if (rec === 'HOLD') return '#f59e0b';
    return '#6b7280';
};

const recBg = (rec: string) => {
    if (rec === 'BUY') return 'rgba(34,197,94,0.15)';
    if (rec === 'SELL') return 'rgba(239,68,68,0.15)';
    if (rec === 'HOLD') return 'rgba(245,158,11,0.15)';
    return 'rgba(107,114,128,0.15)';
};

export default AlertToast;
