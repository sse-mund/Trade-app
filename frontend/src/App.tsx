import { useState } from 'react'
import './App.css'
import StrategyCard from './components/StrategyCard'
import NewsFeed from './components/NewsFeed'
import StockChart from './components/StockChart'
import MultiChartView from './components/MultiChartView'
import AgentInsightsPanel from './components/AgentInsightsPanel'
import FinalRecommendation from './components/FinalRecommendation'
import CompanyFundamentals from './components/CompanyFundamentals'
import BacktestPanel from './components/BacktestPanel'
import Watchlist from './components/Watchlist'
import BuyRecommendations from './components/BuyRecommendations'
import TickerAutocomplete from './components/TickerAutocomplete'
import QuantWeights, { DEFAULT_QUANT_WEIGHTS } from './components/QuantWeights'

// All strategies are always analyzed
const ALL_STRATEGIES = ['SMA', 'RSI', 'MACD'];

// Daily period options
const DAILY_PERIODS = [
  { label: '3M', days: 90 },
  { label: '1Y', days: 365 },
  { label: '5Y', days: 1825 },
];

// Intraday interval options
const INTRADAY_INTERVALS = [
  { label: '5M', interval: '5m', desc: '5-min bars · last 5 days' },
  { label: '15M', interval: '15m', desc: '15-min bars · last 5 days' },
  { label: '1H', interval: '1h', desc: '1-hr bars · last 30 days' },
];

function App() {
  const [ticker, setTicker] = useState('')
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [period, setPeriod] = useState(90)  // Default to 3M
  const [interval, setInterval] = useState<string | null>(null)  // null = daily mode
  const [quantWeights, setQuantWeights] = useState<Record<string, number> | null>(null)

  const handleAnalyze = async (
    e: React.FormEvent | null,
    overridePeriod?: number,
    overrideInterval?: string | null,
    overrideTicker?: string,
    overrideWeights?: Record<string, number> | null,
  ) => {
    if (e) e.preventDefault();
    const tickerToUse = overrideTicker || ticker;
    if (!tickerToUse) return;

    const periodToUse = overridePeriod !== undefined ? overridePeriod : period;
    const intervalToUse = overrideInterval !== undefined ? overrideInterval : interval;

    setLoading(true);
    setError('');
    if (!data) setData(null);

    try {
      const body: any = {
        ticker: tickerToUse.toUpperCase(),
        selected_strategies: ALL_STRATEGIES,
        period_days: periodToUse,
      };
      if (intervalToUse) body.interval = intervalToUse;
      const weightsToUse = overrideWeights !== undefined ? overrideWeights : quantWeights;
      if (weightsToUse) body.quant_weights = weightsToUse;

      const response = await fetch('http://localhost:8000/analyze_charts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) throw new Error('Failed to fetch data');

      const result = await response.json();
      setData(result);
    } catch (err) {
      console.error('Error in handleAnalyze:', err);
      setError('Error analyzing ticker. Please check the symbol.');
    } finally {
      setLoading(false);
    }
  }

  const switchToDaily = (days: number) => {
    setPeriod(days);
    setInterval(null);
    if (ticker) handleAnalyze(null, days, null);
  };

  const switchToIntraday = (iv: string) => {
    setInterval(iv);
    if (ticker) handleAnalyze(null, period, iv);
  };

  const selectWatchlistTicker = (t: string) => {
    setTicker(t);
    // Trigger analysis with current period settings
    setTimeout(() => {
      const body: any = {
        ticker: t.toUpperCase(),
        selected_strategies: ALL_STRATEGIES,
        period_days: period,
      };
      if (interval) body.interval = interval;

      setLoading(true);
      setError('');
      fetch('http://localhost:8000/analyze_charts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
        .then(r => { if (!r.ok) throw new Error('Failed'); return r.json(); })
        .then(result => setData(result))
        .catch(() => setError('Error analyzing ticker.'))
        .finally(() => setLoading(false));
    }, 0);
  };

  const isIntraday = !!data?.is_intraday;

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Trade Strategy AI</h1>
        <p>Advanced Market Analysis</p>
      </header>

      <main className="app-main">
        <Watchlist onSelectTicker={selectWatchlistTicker} activeTicker={ticker} />
        <BuyRecommendations onSelectTicker={selectWatchlistTicker} />
        <form onSubmit={handleAnalyze} className="search-form">
          <TickerAutocomplete 
            value={ticker}
            onChange={(val) => setTicker(val)}
            onSelect={(val) => {
              setTicker(val);
              handleAnalyze(null, undefined, undefined, val);
            }}
            disabled={loading}
          />
          <button type="submit" disabled={loading} className="analyze-btn">
            {loading ? 'Analyzing...' : 'Analyze'}
          </button>

          {/* Daily period pills */}
          <div className="chart-timeline-btns" style={{ marginLeft: '0.75rem' }}>
            {DAILY_PERIODS.map(({ label, days }) => (
              <button
                key={label}
                type="button"
                disabled={loading}
                onClick={() => switchToDaily(days)}
                className={`chart-period-btn${!interval && period === days ? ' chart-period-btn--active' : ''}`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Intraday interval pills */}
          <div className="chart-timeline-btns chart-timeline-btns--intraday" style={{ marginLeft: '0.5rem' }}>
            {INTRADAY_INTERVALS.map(({ label, interval: iv }) => (
              <button
                key={label}
                type="button"
                disabled={loading}
                onClick={() => switchToIntraday(iv)}
                className={`chart-period-btn chart-period-btn--intraday${interval === iv ? ' chart-period-btn--active' : ''}`}
                title={INTRADAY_INTERVALS.find(i => i.interval === iv)?.desc}
              >
                {label}
              </button>
            ))}
          </div>
        </form>

        {/* Quant Weight Configuration */}
        <QuantWeights
          weights={data?.analysis?.agent_results?.quant?.weights
            ? data.analysis.agent_results.quant.weights
            : DEFAULT_QUANT_WEIGHTS
          }
          onChange={(newWeights) => {
            setQuantWeights(newWeights);
            // Re-analyze with new weights if we have a ticker
            if (ticker) {
              handleAnalyze(null, undefined, undefined, ticker, newWeights);
            }
          }}
          disabled={loading}
        />

        {error && <div className="error-message">{error}</div>}

        {data && (
          <div className="results-container">
            <div className="ticker-info">
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <h2>{data.ticker}</h2>
                <span className="current-price">${data.current_price?.toFixed(2) || 'N/A'}</span>
                {data.trend && !isIntraday && <span className="trend-badge">{data.trend}</span>}
                {isIntraday && (
                  <span className="intraday-badge">
                    ⚡ Intraday · {interval?.toUpperCase()}
                  </span>
                )}
              </div>
            </div>

            {/* Support/resistance levels (daily only) */}
            {!isIntraday && data.levels && (data.levels.support?.length > 0 || data.levels.resistance?.length > 0) && (
              <div className="levels-info">
                {data.levels.support?.length > 0 && (
                  <div className="support-levels">
                    <strong>Support:</strong> {data.levels.support.map((s: number) => `$${s.toFixed(2)}`).join(', ')}
                  </div>
                )}
                {data.levels.resistance?.length > 0 && (
                  <div className="resistance-levels">
                    <strong>Resistance:</strong> {data.levels.resistance.map((r: number) => `$${r.toFixed(2)}`).join(', ')}
                  </div>
                )}
              </div>
            )}

            {/* Intraday S/R levels */}
            {isIntraday && data.levels && (data.levels.support?.length > 0 || data.levels.resistance?.length > 0) && (
              <div className="levels-info">
                {data.levels.support?.length > 0 && (
                  <div className="support-levels">
                    <strong>Intraday Support:</strong> {data.levels.support.map((s: number) => `$${s.toFixed(2)}`).join(', ')}
                  </div>
                )}
                {data.levels.resistance?.length > 0 && (
                  <div className="resistance-levels">
                    <strong>Intraday Resistance:</strong> {data.levels.resistance.map((r: number) => `$${r.toFixed(2)}`).join(', ')}
                  </div>
                )}
              </div>
            )}

            {/* Brain Recommendation (daily only) */}
            {!isIntraday && data.analysis?.recommendation && (
              <FinalRecommendation
                recommendation={data.analysis.recommendation}
                confidence={data.analysis.confidence ?? 0}
                riskLevel={data.analysis.risk_level}
                reasoning={data.analysis.reasoning}
                strategyName={data.analysis.strategyName}
                currentPrice={data.current_price}
                targetPrice={data.analysis.target_price}
                stopLoss={data.analysis.stop_loss}
                timeframe={data.analysis.time_horizon}
                tradeReasoning={data.analysis.trade_reasoning}
                agentCount={Object.keys(data.analysis.agent_results ?? {}).length}
                resistanceLevels={data.levels?.resistance}
                supportLevels={data.levels?.support}
                brainReasoning={data.analysis.brain_reasoning}
                riskFactors={data.analysis.risk_factors}
                marketRegime={data.analysis.market_regime}
                keyInsight={data.analysis.key_insight}
              />
            )}

            {/* Agent Insights Panel (daily only) */}
            {!isIntraday && data.analysis?.agent_results && (
              <AgentInsightsPanel analysis={data.analysis} />
            )}

            {/* Company Fundamentals (daily only) */}
            {!isIntraday && data.fundamentals && (
              <CompanyFundamentals data={data.fundamentals} ticker={data.ticker || ticker} />
            )}

            {/* Intraday note */}
            {isIntraday && (
              <div className="intraday-note">
                ⚡ Showing <strong>{interval?.toUpperCase()}</strong> intraday chart with live S/R levels and indicators.
                Switch to <strong>3M · 1Y · 5Y</strong> for full agent analysis and company fundamentals.
              </div>
            )}

            {/* Timeline toggle above charts */}
            <div className="chart-timeline-bar">
              <span className="chart-timeline-label">Chart Period</span>
              <div className="chart-timeline-btns">
                {DAILY_PERIODS.map(({ label, days }) => (
                  <button
                    key={label}
                    type="button"
                    disabled={loading}
                    onClick={() => switchToDaily(days)}
                    className={`chart-period-btn${!interval && period === days ? ' chart-period-btn--active' : ''}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="chart-timeline-btns chart-timeline-btns--intraday">
                {INTRADAY_INTERVALS.map(({ label, interval: iv, desc }) => (
                  <button
                    key={label}
                    type="button"
                    disabled={loading}
                    onClick={() => switchToIntraday(iv)}
                    title={desc}
                    className={`chart-period-btn chart-period-btn--intraday${interval === iv ? ' chart-period-btn--active' : ''}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {loading && <span className="chart-timeline-loading">Updating…</span>}
            </div>

            {/* Charts */}
            {data.chart_data || data.charts ? (
              <MultiChartView key={`charts-${interval ?? period}-${data.ticker}`} data={data} />
            ) : (
              <StockChart key={`stock-${interval ?? period}-${data.ticker}`} data={data.history} />
            )}



            {/* Strategy cards (legacy) */}
            {data.strategies && (
              <div className="strategies-grid">
                {Object.entries(data.strategies).map(([name, result]: [string, any]) => (
                  <StrategyCard
                    key={name}
                    strategyName={name}
                    signal={result.signal}
                    details={result}
                  />
                ))}
              </div>
            )}

            {/* News Feed (daily only) */}
            {!isIntraday && data.news && data.news.length > 0 && (
              <div style={{ marginTop: '2rem' }}>
                <NewsFeed articles={data.news} />
              </div>
            )}

            {/* Backtest & Optimizer Panel (daily only) */}
            {!isIntraday && (
              <BacktestPanel ticker={data.ticker || ticker.toUpperCase()} />
            )}

            {/* Technical Indicators */}
            {data.indicators && (
              <div className="indicators-summary">
                <h3>Technical Indicators</h3>
                <div className="indicators-grid">
                  {data.indicators.rsi !== undefined && <div className="indicator-item">RSI: {data.indicators.rsi?.toFixed(2) ?? 'N/A'}</div>}
                  {data.indicators.macd !== undefined && <div className="indicator-item">MACD: {data.indicators.macd?.toFixed(4) ?? 'N/A'}</div>}
                  {data.indicators.sma_20 !== undefined && <div className="indicator-item">SMA(20): ${data.indicators.sma_20?.toFixed(2) ?? 'N/A'}</div>}
                  {!isIntraday && data.indicators.sma_50 !== undefined && <div className="indicator-item">SMA(50): ${data.indicators.sma_50?.toFixed(2) ?? 'N/A'}</div>}
                </div>

              </div>
            )}

          </div>
        )}
      </main>
    </div>
  )
}

export default App
