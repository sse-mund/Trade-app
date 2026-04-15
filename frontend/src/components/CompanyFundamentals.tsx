import React from 'react';

interface FundamentalsData {
    market_cap?: number | null;
    pe_ratio?: number | null;
    forward_pe?: number | null;
    price_to_book?: number | null;
    revenue_ttm?: number | null;
    gross_profit?: number | null;
    net_income?: number | null;
    eps?: number | null;
    free_cash_flow?: number | null;
    return_on_equity?: number | null;
    total_debt?: number | null;
    debt_to_equity?: number | null;
    current_ratio?: number | null;
    next_earnings_date?: string | null;
    earnings_growth?: number | null;
    revenue_growth?: number | null;
}

interface CompanyFundamentalsProps {
    data: FundamentalsData;
    ticker: string;
}

// ─── Formatting helpers ────────────────────────────────────── //

/** Format large dollar numbers as $12.5B / $340.2M / $4.1K */
function fmtLargeNum(val: number | null | undefined): string {
    if (val == null || isNaN(val)) return 'N/A';
    const abs = Math.abs(val);
    const sign = val < 0 ? '-' : '';
    if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(2)}T`;
    if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
    if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(2)}M`;
    if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(2)}K`;
    return `${sign}$${abs.toFixed(2)}`;
}

/** Format a ratio / multiple */
function fmtRatio(val: number | null | undefined, decimals = 2): string {
    if (val == null || isNaN(val)) return 'N/A';
    return val.toFixed(decimals) + 'x';
}

/** Format a percentage growth figure (e.g. 0.12 → "+12.0%") */
function fmtGrowth(val: number | null | undefined): string {
    if (val == null || isNaN(val)) return 'N/A';
    const pct = (val * 100).toFixed(1);
    return val >= 0 ? `+${pct}%` : `${pct}%`;
}

/** Color for growth: green positive, red negative */
function growthColor(val: number | null | undefined): string {
    if (val == null) return 'var(--text-secondary)';
    return val >= 0 ? '#22c55e' : '#ef4444';
}

// ─── Sub-components ────────────────────────────────────────── //

interface MetricRowProps {
    label: string;
    value: string;
    valueColor?: string;
}
const MetricRow: React.FC<MetricRowProps> = ({ label, value, valueColor }) => (
    <div className="fund-metric-row">
        <span className="fund-metric-label">{label}</span>
        <span className="fund-metric-value" style={valueColor ? { color: valueColor } : {}}>
            {value}
        </span>
    </div>
);

interface FundCardProps {
    icon: string;
    title: string;
    children: React.ReactNode;
}
const FundCard: React.FC<FundCardProps> = ({ icon, title, children }) => (
    <div className="fund-card">
        <div className="fund-card-header">
            <span className="fund-card-icon">{icon}</span>
            <span className="fund-card-title">{title}</span>
        </div>
        <div className="fund-card-body">{children}</div>
    </div>
);

// ─── Summary Generator ─────────────────────────────────────── //

interface SummaryPoint { icon: string; text: string; tone: 'positive' | 'negative' | 'neutral'; }

function generateFundamentalsSummary(data: FundamentalsData): SummaryPoint[] {
    const points: SummaryPoint[] = [];

    // --- Valuation ---
    if (data.pe_ratio != null) {
        if (data.pe_ratio > 40) {
            points.push({
                icon: '📊', tone: 'negative',
                text: `P/E of ${data.pe_ratio.toFixed(1)}x is elevated — the market prices in high growth expectations. Downside risk if growth disappoints.`
            });
        } else if (data.pe_ratio > 25) {
            points.push({
                icon: '📊', tone: 'neutral',
                text: `P/E of ${data.pe_ratio.toFixed(1)}x is moderately above the market average (~20x), reflecting growth premium.`
            });
        } else if (data.pe_ratio > 0) {
            points.push({
                icon: '📊', tone: 'positive',
                text: `P/E of ${data.pe_ratio.toFixed(1)}x is near or below the market average (~20x), suggesting reasonable valuation.`
            });
        }
    }

    // --- Revenue Growth ---
    if (data.revenue_growth != null) {
        const pct = (data.revenue_growth * 100).toFixed(1);
        if (data.revenue_growth >= 0.20) {
            points.push({
                icon: '💰', tone: 'positive',
                text: `Revenue is growing at +${pct}% — strong top-line momentum, indicating healthy demand.`
            });
        } else if (data.revenue_growth >= 0.05) {
            points.push({
                icon: '💰', tone: 'neutral',
                text: `Revenue growth of +${pct}% is moderate. Solid but not exceptional expansion.`
            });
        } else if (data.revenue_growth >= 0) {
            points.push({
                icon: '💰', tone: 'neutral',
                text: `Revenue growth of +${pct}% is below 5% — top-line expansion is slowing.`
            });
        } else {
            points.push({
                icon: '💰', tone: 'negative',
                text: `Revenue declined ${pct}% — shrinking top line is a concern and warrants close monitoring.`
            });
        }
    }

    // --- Free Cash Flow ---
    if (data.free_cash_flow != null) {
        if (data.free_cash_flow > 0) {
            const fcfStr = Math.abs(data.free_cash_flow) >= 1e9
                ? `$${(data.free_cash_flow / 1e9).toFixed(1)}B`
                : `$${(data.free_cash_flow / 1e6).toFixed(0)}M`;
            points.push({
                icon: '✅', tone: 'positive',
                text: `Positive free cash flow of ${fcfStr} — the company generates real cash and has flexibility for dividends, buybacks, or investment.`
            });
        } else {
            points.push({
                icon: '⚠️', tone: 'negative',
                text: `Negative free cash flow — the company is spending more cash than it generates. Watch for financing needs.`
            });
        }
    }

    // --- ROE ---
    if (data.return_on_equity != null) {
        const roePct = (data.return_on_equity * 100).toFixed(1);
        if (data.return_on_equity >= 0.20) {
            points.push({
                icon: '⭐', tone: 'positive',
                text: `Return on Equity of ${roePct}% is strong — management is generating excellent returns from shareholder capital.`
            });
        } else if (data.return_on_equity >= 0.10) {
            points.push({
                icon: '📈', tone: 'neutral',
                text: `Return on Equity of ${roePct}% is decent, roughly in line with a healthy business benchmark (>10%).`
            });
        } else if (data.return_on_equity >= 0) {
            points.push({
                icon: '📉', tone: 'neutral',
                text: `Return on Equity of ${roePct}% is below 10% — capital efficiency has room for improvement.`
            });
        } else {
            points.push({
                icon: '🔴', tone: 'negative',
                text: `Negative Return on Equity — the company is not generating profit from shareholder equity.`
            });
        }
    }

    // --- Debt ---
    if (data.debt_to_equity != null) {
        if (data.debt_to_equity > 150) {
            points.push({
                icon: '🔴', tone: 'negative',
                text: `Debt/Equity of ${data.debt_to_equity.toFixed(0)} is very high — significant leverage increases financial risk, especially in rising-rate environments.`
            });
        } else if (data.debt_to_equity > 80) {
            points.push({
                icon: '⚠️', tone: 'neutral',
                text: `Debt/Equity of ${data.debt_to_equity.toFixed(0)} indicates moderate-to-high leverage. Manageable, but worth watching.`
            });
        }
        // Low debt is implicitly positive — no need to add noise
    }

    // --- Liquidity ---
    if (data.current_ratio != null && data.current_ratio < 1.0) {
        points.push({
            icon: '⚠️', tone: 'negative',
            text: `Current ratio of ${data.current_ratio.toFixed(2)} is below 1.0 — the company may struggle to cover short-term obligations with liquid assets.`
        });
    }

    return points;
}

// ─── Main Component ────────────────────────────────────────── //

const CompanyFundamentals: React.FC<CompanyFundamentalsProps> = ({ data, ticker }) => {
    const hasAnyData = Object.values(data).some(v => v != null);
    const summaryPoints = generateFundamentalsSummary(data);

    if (!hasAnyData) {
        return (
            <div className="fundamentals-panel">
                <div className="fundamentals-header">
                    <span className="fundamentals-title">🏦 Company Fundamentals</span>
                    <span className="fundamentals-ticker">{ticker}</span>
                </div>
                <p className="fund-no-data">Fundamental data not available for this ticker.</p>
            </div>
        );
    }

    return (
        <div className="fundamentals-panel">
            <div className="fundamentals-header">
                <span className="fundamentals-title">🏦 Company Fundamentals</span>
                <span className="fundamentals-ticker">{ticker}</span>
            </div>

            {/* ── Fundamental Summary ── */}
            {summaryPoints.length > 0 && (
                <div className="fund-summary-block">
                    <span className="fund-summary-label">📋 Fundamental Analysis Summary</span>
                    <ul className="fund-summary-list">
                        {summaryPoints.map((pt, i) => (
                            <li key={i} className={`fund-summary-item fund-summary-${pt.tone}`}>
                                <span className="fund-summary-icon">{pt.icon}</span>
                                <span className="fund-summary-text">{pt.text}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* ── Metric Cards Grid ── */}
            <div className="fundamentals-grid">
                {/* ── Revenue & Earnings ── */}
                <FundCard icon="💰" title="Revenue & Earnings">
                    <MetricRow label="Revenue (TTM)" value={fmtLargeNum(data.revenue_ttm)} />
                    <MetricRow label="Gross Profit" value={fmtLargeNum(data.gross_profit)} />
                    <MetricRow label="Net Income" value={fmtLargeNum(data.net_income)} />
                    <MetricRow label="Free Cash Flow" value={fmtLargeNum(data.free_cash_flow)} />
                    <MetricRow
                        label="Revenue Growth"
                        value={fmtGrowth(data.revenue_growth)}
                        valueColor={growthColor(data.revenue_growth)}
                    />
                </FundCard>

                {/* ── Valuation ── */}
                <FundCard icon="📊" title="Valuation">
                    <MetricRow label="Market Cap" value={fmtLargeNum(data.market_cap)} />
                    <MetricRow label="P/E (Trailing)" value={data.pe_ratio != null ? data.pe_ratio.toFixed(2) : 'N/A'} />
                    <MetricRow label="Forward P/E" value={data.forward_pe != null ? data.forward_pe.toFixed(2) : 'N/A'} />
                    <MetricRow label="Price / Book" value={fmtRatio(data.price_to_book)} />
                    <MetricRow
                        label="Return on Equity"
                        value={data.return_on_equity != null ? `${(data.return_on_equity * 100).toFixed(1)}%` : 'N/A'}
                        valueColor={
                            data.return_on_equity != null
                                ? data.return_on_equity >= 0.15 ? '#22c55e'
                                    : data.return_on_equity >= 0 ? '#f59e0b'
                                        : '#ef4444'
                                : undefined
                        }
                    />
                </FundCard>

                {/* ── Debt & Liquidity ── */}
                <FundCard icon="🔴" title="Debt & Liquidity">
                    <MetricRow label="Total Debt" value={fmtLargeNum(data.total_debt)} />
                    <MetricRow
                        label="Debt / Equity"
                        value={data.debt_to_equity != null ? data.debt_to_equity.toFixed(2) : 'N/A'}
                        valueColor={
                            data.debt_to_equity != null
                                ? data.debt_to_equity > 100 ? '#ef4444'
                                    : data.debt_to_equity > 50 ? '#f59e0b'
                                        : '#22c55e'
                                : undefined
                        }
                    />
                    <MetricRow
                        label="Current Ratio"
                        value={data.current_ratio != null ? data.current_ratio.toFixed(2) : 'N/A'}
                        valueColor={
                            data.current_ratio != null
                                ? data.current_ratio >= 1.5 ? '#22c55e'
                                    : data.current_ratio >= 1 ? '#f59e0b'
                                        : '#ef4444'
                                : undefined
                        }
                    />
                </FundCard>

                {/* ── Earnings ── */}
                <FundCard icon="📅" title="Earnings">
                    <MetricRow label="EPS (Trailing)" value={data.eps != null ? `$${data.eps.toFixed(2)}` : 'N/A'} />
                    <MetricRow
                        label="Earnings Growth"
                        value={fmtGrowth(data.earnings_growth)}
                        valueColor={growthColor(data.earnings_growth)}
                    />
                    <MetricRow
                        label="Next Earnings Date"
                        value={data.next_earnings_date ?? 'N/A'}
                    />
                </FundCard>
            </div>
        </div>
    );
};

export default CompanyFundamentals;

