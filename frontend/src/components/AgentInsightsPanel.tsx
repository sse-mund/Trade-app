import React from 'react';
import AgentInsightCard from './AgentInsightCard';

interface AgentResult {
    signal: number;
    confidence: number;
    reasoning: string;
    metrics?: Record<string, any>;
}

interface AgentInsightsPanelProps {
    analysis: {
        recommendation: string;
        confidence: number;
        risk_level: string;
        reasoning: string;
        agent_results: Record<string, AgentResult>;
        confluence?: {
            agreement: string;
            description: string;
            bullish_count: number;
            bearish_count: number;
            neutral_count: number;
        };
    };
}

/** Human-readable display names for each agent key */
const AGENT_DISPLAY_NAMES: Record<string, string> = {
    pattern: '📐 Pattern Analysis',
    quant: '📊 Quant Analysis',
    sentiment: '📰 Sentiment Analysis',
};

/** Get confluence badge color */
const getConfluenceColor = (agreement: string) => {
    if (agreement.includes('strong')) return '#22c55e';
    if (agreement.includes('moderate')) return '#3b82f6';
    if (agreement === 'mixed') return '#f59e0b';
    return '#94a3b8';
};

const AgentInsightsPanel: React.FC<AgentInsightsPanelProps> = ({ analysis }) => {
    if (!analysis?.agent_results) return null;

    const entries = Object.entries(analysis.agent_results);
    if (entries.length === 0) return null;

    const confluence = analysis.confluence;

    return (
        <div className="agent-insights-panel">
            <div className="agent-insights-header">
                <span className="agent-insights-title">🧠 Agent Analysis</span>
                <span className="agent-insights-subtitle">
                    {entries.length} agent{entries.length !== 1 ? 's' : ''} · click&nbsp;<strong>+</strong>&nbsp;for details
                </span>
                {confluence && (
                    <span
                        className="confluence-badge"
                        style={{
                            backgroundColor: `${getConfluenceColor(confluence.agreement)}22`,
                            color: getConfluenceColor(confluence.agreement),
                            borderColor: getConfluenceColor(confluence.agreement),
                        }}
                    >
                        {confluence.agreement === 'mixed' ? '⚠️' : '✓'} {confluence.description}
                    </span>
                )}
            </div>

            <div className="agent-insights-grid">
                {entries.map(([key, result]) => (
                    <AgentInsightCard
                        key={key}
                        agentName={AGENT_DISPLAY_NAMES[key] ?? key}
                        signal={result.signal}
                        confidence={result.confidence}
                        reasoning={result.reasoning}
                        metrics={result.metrics}
                    />
                ))}
            </div>
        </div>
    );
};

export default AgentInsightsPanel;
