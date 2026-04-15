import React, { useState } from 'react';

interface AgentInsightCardProps {
    agentName: string;
    signal: number;        // -1, -0.5, 0, 0.5, 1
    confidence: number;    // 0–1
    reasoning: string;
    metrics?: Record<string, any>;
}

const AgentInsightCard: React.FC<AgentInsightCardProps> = ({
    agentName,
    signal,
    confidence,
    reasoning,
    metrics,
}) => {
    const [expanded, setExpanded] = useState(false);

    const confidencePercent = Math.round(confidence * 100);

    /** Derive a human label from the raw signal number */
    const getSignalLabel = () => {
        if (signal > 0.2) return 'Bullish';
        if (signal < -0.2) return 'Bearish';
        return 'Neutral';
    };

    const signalLabel = getSignalLabel();

    const accentColor =
        signalLabel === 'Bullish' ? '#22c55e'
            : signalLabel === 'Bearish' ? '#ef4444'
                : '#f59e0b';

    /** Build a short one-liner that explains *why* this matters to the trade. */
    const getImpactSummary = () => {
        if (signalLabel === 'Bullish') {
            return `${agentName} sees bullish conditions — supports a BUY bias.`;
        }
        if (signalLabel === 'Bearish') {
            return `${agentName} sees bearish conditions — supports a SELL/avoid bias.`;
        }
        return `${agentName} is neutral — no directional edge detected.`;
    };

    /** Format selected metrics for display */
    const renderMetrics = () => {
        if (!metrics) return null;
        const items: React.ReactNode[] = [];

        if (metrics.rsi !== undefined) {
            const rsiVal = parseFloat(metrics.rsi.toFixed(1));
            const rsiNote = rsiVal < 30 ? ' (Oversold)' : rsiVal > 70 ? ' (Overbought)' : '';
            items.push(<span key="rsi" className="agent-metric">RSI: {rsiVal}{rsiNote}</span>);
        }
        if (metrics.relative_volume !== undefined) {
            items.push(<span key="rv" className="agent-metric">Rel. Vol: {parseFloat(metrics.relative_volume.toFixed(2))}x</span>);
        }
        if (metrics.is_squeezing !== undefined && metrics.is_squeezing) {
            items.push(<span key="sq" className="agent-metric squeeze">BB Squeeze ⚡</span>);
        }
        if (metrics.trend) {
            items.push(<span key="tr" className="agent-metric">Trend: {metrics.trend}</span>);
        }
        if (metrics.breakout && metrics.breakout.type !== 'none') {
            items.push(
                <span key="bk" className="agent-metric">
                    Breakout: {metrics.breakout.type} @ ${parseFloat(metrics.breakout.level.toFixed(2))}
                </span>
            );
        }
        return items.length > 0 ? <div className="agent-metrics-row">{items}</div> : null;
    };

    return (
        <div
            className="agent-insight-card"
            style={{ borderLeftColor: accentColor }}
        >
            {/* Card header row */}
            <div className="agent-card-header">
                <div className="agent-card-left">
                    <span className="agent-name">{agentName}</span>
                    <span
                        className="agent-signal-badge"
                        style={{ backgroundColor: accentColor }}
                    >
                        {signalLabel}
                    </span>
                </div>

                <div className="agent-card-right">
                    {/* Confidence mini-bar */}
                    <div className="agent-confidence-wrap">
                        <div className="agent-confidence-bar">
                            <div
                                className="agent-confidence-fill"
                                style={{
                                    width: `${confidencePercent}%`,
                                    backgroundColor: accentColor,
                                }}
                            />
                        </div>
                        <span className="agent-confidence-pct">{confidencePercent}%</span>
                    </div>

                    {/* Expand / Collapse button */}
                    <button
                        className="agent-expand-btn"
                        style={{ borderColor: accentColor, color: accentColor }}
                        onClick={() => setExpanded(prev => !prev)}
                        aria-label={expanded ? 'Collapse reasoning' : 'Expand reasoning'}
                        title={expanded ? 'Hide reasoning' : 'Show reasoning'}
                    >
                        {expanded ? '−' : '+'}
                    </button>
                </div>
            </div>

            {/* Impact one-liner always visible */}
            <p className="agent-impact-summary">{getImpactSummary()}</p>

            {/* Expanded reasoning + metrics */}
            {expanded && (
                <div className="agent-reasoning-box">
                    <p className="agent-reasoning-text">💡 {reasoning}</p>
                    {renderMetrics()}
                </div>
            )}
        </div>
    );
};

export default AgentInsightCard;
