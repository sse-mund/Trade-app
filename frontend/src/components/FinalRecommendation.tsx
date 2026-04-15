import React from 'react';

interface FinalRecommendationProps {
    recommendation: 'BUY' | 'SELL' | 'HOLD';
    confidence: number;  // 0-1
    agentCount?: number;
    riskLevel?: 'Low' | 'Medium' | 'High';
    reasoning?: string;

    // Trading details
    strategyName?: string;
    currentPrice?: number;
    targetPrice?: number;
    stopLoss?: number;
    timeframe?: string;  // e.g., "2-3 weeks", "1 month"
    tradeReasoning?: string;
    resistanceLevels?: number[];
    supportLevels?: number[];

    // Brain fields
    brainReasoning?: string;
    riskFactors?: string[];
    marketRegime?: string;
    keyInsight?: string;
}

const FinalRecommendation: React.FC<FinalRecommendationProps> = ({
    recommendation,
    confidence,
    agentCount = 3,
    riskLevel = 'Medium',
    reasoning,
    strategyName,
    currentPrice,
    targetPrice,
    stopLoss,
    timeframe,
    tradeReasoning,
    resistanceLevels,
    supportLevels,
    brainReasoning,
    riskFactors,
    marketRegime,
    keyInsight,
}) => {
    const confidencePercent = Math.round(confidence * 100);

    // Calculate potential gain/loss percentage
    const potentialChange = currentPrice && targetPrice
        ? ((targetPrice - currentPrice) / currentPrice * 100).toFixed(2)
        : null;

    // Color scheme based on recommendation
    const getRecommendationColor = () => {
        switch (recommendation) {
            case 'BUY': return '#22c55e';
            case 'SELL': return '#ef4444';
            case 'HOLD': return '#f59e0b';
            default: return '#94a3b8';
        }
    };

    const getRiskColor = () => {
        switch (riskLevel) {
            case 'Low': return '#22c55e';
            case 'Medium': return '#f59e0b';
            case 'High': return '#ef4444';
            default: return '#94a3b8';
        }
    };

    // Display reasoning: prefer brain reasoning, fallback to legacy
    const displayReasoning = brainReasoning || reasoning;

    return (
        <div className="final-recommendation-card">
            <div className="recommendation-header">
                <div className="recommendation-main">
                    <div className="recommendation-title-row">
                        <span
                            className="recommendation-badge"
                            style={{ backgroundColor: getRecommendationColor() }}
                        >
                            {recommendation}
                        </span>
                        {strategyName && (
                            <span className="strategy-name">{strategyName}</span>
                        )}
                        {brainReasoning && (
                            <span className="brain-badge">🧠 AI Brain</span>
                        )}
                    </div>

                    {/* Key Insight — the single most important takeaway */}
                    {keyInsight && (
                        <div className="key-insight-box">
                            <span className="key-insight-icon">💡</span>
                            <p className="key-insight-text">{keyInsight}</p>
                        </div>
                    )}

                    <div className="confidence-section">
                        <span className="confidence-label">Confidence</span>
                        <div className="confidence-bar-container">
                            <div
                                className="confidence-bar-fill"
                                style={{
                                    width: `${confidencePercent}%`,
                                    backgroundColor: getRecommendationColor()
                                }}
                            />
                        </div>
                        <span className="confidence-value">{confidencePercent}%</span>
                    </div>
                </div>

                <div className="recommendation-meta">
                    <div className="meta-item">
                        <span className="meta-label">Based on</span>
                        <span className="meta-value">{agentCount} Agents</span>
                    </div>
                    <div className="meta-item">
                        <span className="meta-label">Risk Level</span>
                        <span
                            className="meta-value"
                            style={{ color: getRiskColor() }}
                        >
                            {riskLevel}
                        </span>
                    </div>
                    {marketRegime && (
                        <div className="meta-item">
                            <span className="meta-label">Market Regime</span>
                            <span className="meta-value regime-badge">{marketRegime}</span>
                        </div>
                    )}
                </div>
            </div>

            {/* Trading Details Section - Only show for BUY/SELL */}
            {(recommendation === 'BUY' || recommendation === 'SELL') && (currentPrice || targetPrice) && (
                <div className="trading-details">
                    <div className="trading-details-grid">
                        {currentPrice && (
                            <div className="detail-item">
                                <span className="detail-label">Current Price</span>
                                <span className="detail-value price-current">${currentPrice.toFixed(2)}</span>
                            </div>
                        )}

                        {targetPrice && (
                            <div className="detail-item">
                                <span className="detail-label">🎯 Target Price</span>
                                <span className="detail-value price-target">${targetPrice.toFixed(2)}</span>
                            </div>
                        )}

                        {stopLoss && (
                            <div className="detail-item">
                                <span className="detail-label">🛑 Stop Loss</span>
                                <span className="detail-value" style={{ color: '#ef4444' }}>${stopLoss.toFixed(2)}</span>
                            </div>
                        )}

                        {potentialChange && (
                            <div className="detail-item">
                                <span className="detail-label">Potential {recommendation === 'BUY' ? 'Gain' : 'Loss'}</span>
                                <span
                                    className="detail-value potential-change"
                                    style={{
                                        color: parseFloat(potentialChange) >= 0 ? '#22c55e' : '#ef4444'
                                    }}
                                >
                                    {parseFloat(potentialChange) >= 0 ? '+' : ''}{potentialChange}%
                                </span>
                            </div>
                        )}

                        {timeframe && (
                            <div className="detail-item">
                                <span className="detail-label">⏱️ Time Horizon</span>
                                <span className="detail-value">{timeframe}</span>
                            </div>
                        )}
                    </div>

                    {/* Key Levels */}
                    {(resistanceLevels || supportLevels) && (
                        <div className="key-levels">
                            {resistanceLevels && resistanceLevels.length > 0 && (
                                <div className="levels-group">
                                    <span className="levels-label resistance">Resistance:</span>
                                    <span className="levels-values">
                                        {resistanceLevels.map((level, idx) => (
                                            <span key={idx} className="level-value">
                                                ${level.toFixed(2)}
                                            </span>
                                        ))}
                                    </span>
                                </div>
                            )}

                            {supportLevels && supportLevels.length > 0 && (
                                <div className="levels-group">
                                    <span className="levels-label support">Support:</span>
                                    <span className="levels-values">
                                        {supportLevels.map((level, idx) => (
                                            <span key={idx} className="level-value">
                                                ${level.toFixed(2)}
                                            </span>
                                        ))}
                                    </span>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Trade Reasoning */}
                    {tradeReasoning && (
                        <div className="trade-reasoning">
                            <p style={{ margin: 0, fontSize: '0.85rem', color: '#94a3b8', lineHeight: 1.5 }}>
                                📐 <strong>Price Justification:</strong> {tradeReasoning}
                            </p>
                        </div>
                    )}
                </div>
            )}

            {/* Risk Factors */}
            {riskFactors && riskFactors.length > 0 && (
                <div className="risk-factors-section">
                    <h4>⚠️ Risk Factors</h4>
                    <ul className="risk-factors-list">
                        {riskFactors.map((risk, idx) => (
                            <li key={idx} className="risk-factor-item">{risk}</li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Recommendation Reasoning */}
            {displayReasoning && (
                <div className="recommendation-reasoning">
                    <h4>Recommendation Rationale</h4>
                    <p>{displayReasoning}</p>
                </div>
            )}
        </div>
    );
};

export default FinalRecommendation;
