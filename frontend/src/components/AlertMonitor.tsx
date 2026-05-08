import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Shield, ShieldOff, Activity, Zap } from 'lucide-react';
import AlertToast from './AlertToast';
import type { AlertData } from './AlertToast';

interface AlertMonitorProps {
    tickers: string[];
    onSelectTicker: (ticker: string) => void;
    enabled: boolean;
    onToggle: () => void;
    onAlertsFound?: (count: number) => void;  // called after scan produces alerts
}

interface SignalSnapshot {
    recommendation: string;
    signal: number;
    rsi: number | null;
    sentiment_score: number | null;
    confidence: number;
    current_price?: number;
    market_regime?: string;
    key_insight?: string;
    target_price?: number | null;
    stop_loss?: number | null;
    risk_level?: string;
}

// ─── LocalStorage helpers for persisting monitor baseline signals ───────
const MONITOR_STORAGE_KEY = 'trade_app_monitor_signals';

function loadStoredSignals(): Record<string, SignalSnapshot> {
    try {
        const raw = localStorage.getItem(MONITOR_STORAGE_KEY);
        if (raw) {
            const parsed = JSON.parse(raw);
            if (parsed && typeof parsed === 'object') return parsed;
        }
    } catch { /* corrupted data, start fresh */ }
    return {};
}

function saveStoredSignals(signals: Record<string, SignalSnapshot>) {
    try {
        localStorage.setItem(MONITOR_STORAGE_KEY, JSON.stringify(signals));
    } catch { /* quota exceeded, silently skip */ }
}

const AlertMonitor: React.FC<AlertMonitorProps> = ({
    tickers,
    onSelectTicker,
    enabled,
    onToggle,
    onAlertsFound,
}) => {
    const [intervalMinutes, setIntervalMinutes] = useState(10);
    const [previousSignals, setPreviousSignals] = useState<Record<string, SignalSnapshot>>(loadStoredSignals);
    const [activeAlerts, setActiveAlerts] = useState<AlertData[]>([]);
    const [totalAlertCount, setTotalAlertCount] = useState(0);
    const [scanning, setScanning] = useState(false);
    const [lastScanTime, setLastScanTime] = useState<string | null>(null);
    const [countdown, setCountdown] = useState(0);
    const [scanProgress, setScanProgress] = useState('');
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
    // isFirstScan = true only if we have NO stored baseline signals
    const isFirstScan = useRef(Object.keys(loadStoredSignals()).length === 0);

    // Fetch monitor config on mount
    useEffect(() => {
        fetch('http://localhost:8000/monitor/config')
            .then(r => r.json())
            .then(config => {
                if (config.interval_minutes) {
                    setIntervalMinutes(config.interval_minutes);
                }
            })
            .catch(() => { /* use default */ });
    }, []);

    // Run a monitor scan
    const runMonitorScan = useCallback(async () => {
        if (tickers.length === 0 || scanning) return;

        setScanning(true);
        setScanProgress(`Scanning 0/${tickers.length}...`);

        try {
            const body: any = {
                tickers,
                previous_signals: isFirstScan.current ? {} : previousSignals,
            };

            const res = await fetch('http://localhost:8000/monitor_scan_stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!res.ok) throw new Error(await res.text());

            const reader = res.body?.getReader();
            if (!reader) throw new Error('No stream reader');

            const decoder = new TextDecoder();
            let buffer = '';
            let completed = 0;
            let totalNewAlerts = 0;
            const newSignals: Record<string, SignalSnapshot> = { ...previousSignals };

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

                        if (payload.type === 'alert') {
                            const alertData: AlertData = {
                                ...payload,
                                timestamp: Date.now(),
                            };
                            setActiveAlerts(prev => [alertData, ...prev]);
                            setTotalAlertCount(prev => prev + 1);
                            totalNewAlerts++;

                            // Auto-analyze for critical alerts
                            if (payload.severity === 'critical') {
                                onSelectTicker(payload.ticker);
                            }
                        } else if (payload.type === 'status') {
                            completed++;
                            setScanProgress(`Scanning ${completed}/${tickers.length}...`);
                            // Update stored signals
                            if (payload.current) {
                                newSignals[payload.ticker] = payload.current;
                            }
                        } else if (payload.type === 'done') {
                            setScanProgress('');
                        }
                    } catch { /* skip malformed SSE lines */ }
                }
            }

            setPreviousSignals(newSignals);
            saveStoredSignals(newSignals);  // persist baseline across page refreshes
            isFirstScan.current = false;
            setLastScanTime(new Date().toLocaleTimeString());
            setCountdown(intervalMinutes * 60);

            // Notify parent so AlertHistory can refresh
            if (totalNewAlerts > 0) onAlertsFound?.(totalNewAlerts);

        } catch (e: any) {
            console.error('Monitor scan failed:', e);
        } finally {
            setScanning(false);
            setScanProgress('');
        }
    }, [tickers, previousSignals, scanning, intervalMinutes, onSelectTicker, onAlertsFound]);

    // Always keep a ref to the latest runMonitorScan so intervals never use a stale closure
    const runMonitorScanRef = useRef(runMonitorScan);
    useEffect(() => {
        runMonitorScanRef.current = runMonitorScan;
    }, [runMonitorScan]);

    // Timer management
    useEffect(() => {
        if (!enabled || tickers.length === 0) {
            if (timerRef.current) clearInterval(timerRef.current);
            if (countdownRef.current) clearInterval(countdownRef.current);
            return;
        }

        // Run initial scan after a short delay (let the first watchlist scan finish)
        const initialDelay = setTimeout(() => {
            runMonitorScanRef.current();
        }, 3000);

        // Set up recurring timer — always calls the latest runMonitorScan via ref
        timerRef.current = setInterval(() => {
            runMonitorScanRef.current();
        }, intervalMinutes * 60 * 1000);

        // Countdown timer (updates every second)
        countdownRef.current = setInterval(() => {
            setCountdown(prev => Math.max(0, prev - 1));
        }, 1000);

        return () => {
            clearTimeout(initialDelay);
            if (timerRef.current) clearInterval(timerRef.current);
            if (countdownRef.current) clearInterval(countdownRef.current);
        };
    }, [enabled, tickers.length, intervalMinutes]); // eslint-disable-line react-hooks/exhaustive-deps

    const dismissAlert = (index: number) => {
        setActiveAlerts(prev => prev.filter((_, i) => i !== index));
    };

    const formatCountdown = (seconds: number): string => {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m}:${s.toString().padStart(2, '0')}`;
    };

    return (
        <>
            {/* Monitor Status Pill in header */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
            }}>
                <button
                    onClick={onToggle}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.4rem',
                        padding: '0.4rem 0.85rem',
                        background: enabled
                            ? 'linear-gradient(135deg, rgba(34,197,94,0.15), rgba(16,185,129,0.1))'
                            : 'rgba(255,255,255,0.04)',
                        border: enabled
                            ? '1px solid rgba(34,197,94,0.3)'
                            : '1px solid rgba(255,255,255,0.1)',
                        borderRadius: 20,
                        color: enabled ? '#4ade80' : '#6b7280',
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: 'pointer',
                        transition: 'all 0.3s ease',
                    }}
                    title={enabled ? 'Monitoring active — click to pause' : 'Click to start monitoring'}
                >
                    {enabled ? (
                        <>
                            <Shield size={13} style={{
                                animation: scanning ? 'pulse-monitor 1.5s ease-in-out infinite' : 'none',
                            }} />
                            <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                                {scanning ? (
                                    <>
                                        <Activity size={11} style={{ animation: 'spin 1s linear infinite' }} />
                                        <span style={{ fontSize: 11 }}>{scanProgress || 'Scanning…'}</span>
                                    </>
                                ) : (
                                    <>
                                        <span
                                            style={{
                                                width: 6, height: 6,
                                                borderRadius: '50%',
                                                background: '#22c55e',
                                                boxShadow: '0 0 8px rgba(34,197,94,0.6)',
                                                animation: 'pulse-dot 2s ease-in-out infinite',
                                            }}
                                        />
                                        Monitor
                                    </>
                                )}
                            </span>
                            {!scanning && countdown > 0 && (
                                <span style={{ fontSize: 10, color: '#6b7280', fontWeight: 500 }}>
                                    {formatCountdown(countdown)}
                                </span>
                            )}
                        </>
                    ) : (
                        <>
                            <ShieldOff size={13} />
                            Monitor Off
                        </>
                    )}
                </button>

                {/* Alert count badge */}
                {totalAlertCount > 0 && (
                    <span style={{
                        fontSize: 10,
                        fontWeight: 700,
                        color: '#fbbf24',
                        background: 'rgba(251,191,36,0.12)',
                        border: '1px solid rgba(251,191,36,0.3)',
                        borderRadius: 10,
                        padding: '0.1rem 0.45rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.2rem',
                    }}>
                        <Zap size={9} />
                        {totalAlertCount}
                    </span>
                )}

                {lastScanTime && !scanning && (
                    <span style={{ fontSize: 10, color: '#4b5563' }}>
                        Last: {lastScanTime}
                    </span>
                )}
            </div>

            {/* Floating toast container */}
            <div style={{
                position: 'fixed',
                top: '1rem',
                right: '1rem',
                zIndex: 10000,
                display: 'flex',
                flexDirection: 'column',
                gap: 0,
                maxHeight: '80vh',
                overflowY: 'auto',
                pointerEvents: 'none',
            }}>
                <div style={{ pointerEvents: 'auto' }}>
                    {activeAlerts.slice(0, 5).map((alert, i) => (
                        <AlertToast
                            key={`${alert.ticker}-${alert.alert_type}-${alert.timestamp}-${i}`}
                            alert={alert}
                            index={i}
                            onDismiss={() => dismissAlert(i)}
                            onClickTicker={onSelectTicker}
                        />
                    ))}
                </div>
            </div>

            <style>{`
                @keyframes pulse-monitor {
                    0%, 100% { opacity: 1; transform: scale(1); }
                    50% { opacity: 0.7; transform: scale(1.1); }
                }
                @keyframes pulse-dot {
                    0%, 100% { opacity: 1; box-shadow: 0 0 8px rgba(34,197,94,0.6); }
                    50% { opacity: 0.6; box-shadow: 0 0 16px rgba(34,197,94,0.8); }
                }
            `}</style>
        </>
    );
};

export default AlertMonitor;
