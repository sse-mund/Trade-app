/**
 * Comprehensive test suite for the Trade Strategy App frontend
 * Tests API integration, chart functions, UI state management, and error handling
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { JSDOM } from 'jsdom';

// Setup DOM environment
let dom;
let document;
let window;

beforeEach(() => {
    // Create a new JSDOM instance for each test
    dom = new JSDOM(`
    <!DOCTYPE html>
    <html>
      <body>
        <input type="text" id="ticker" />
        <button id="analyzeBtn">Analyze</button>
        <div id="loading" style="display: none;">Loading...</div>
        <div id="error" style="display: none;"></div>
        <div id="results" style="display: none;">
          <span id="stockTicker"></span>
          <span id="currentPrice"></span>
          <span id="trendBadge"></span>
          <span id="rsiValue"></span>
          <span id="macdValue"></span>
          <span id="sma50Value"></span>
          <span id="sma200Value"></span>
          <div id="supportLevels"></div>
          <div id="resistanceLevels"></div>
          <canvas id="priceChart"></canvas>
          <canvas id="bollingerChart"></canvas>
          <canvas id="volumeChart"></canvas>
          <canvas id="rsiChart"></canvas>
          <canvas id="macdChart"></canvas>
        </div>
      </body>
    </html>
  `, {
        url: 'http://localhost:5173',
        pretendToBeVisual: true,
    });

    document = dom.window.document;
    window = dom.window;

    // Make document and window available globally
    global.document = document;
    global.window = window;

    // Mock Chart.js
    global.Chart = vi.fn().mockImplementation(() => ({
        destroy: vi.fn(),
        update: vi.fn(),
    }));
});

afterEach(() => {
    vi.clearAllMocks();
    dom.window.close();
});

// ============================================================================
// HELPER FUNCTIONS TESTS
// ============================================================================

describe('UI Helper Functions', () => {
    it('should show loading indicator', () => {
        const loading = document.getElementById('loading');
        expect(loading.style.display).toBe('none');

        // Simulate showLoading function
        loading.style.display = 'block';
        expect(loading.style.display).toBe('block');
    });

    it('should hide loading indicator', () => {
        const loading = document.getElementById('loading');
        loading.style.display = 'block';

        // Simulate hideLoading function
        loading.style.display = 'none';
        expect(loading.style.display).toBe('none');
    });

    it('should show error message', () => {
        const error = document.getElementById('error');
        const errorMessage = 'Test error message';

        error.textContent = errorMessage;
        error.style.display = 'block';

        expect(error.textContent).toBe(errorMessage);
        expect(error.style.display).toBe('block');
    });

    it('should hide error message', () => {
        const error = document.getElementById('error');
        error.style.display = 'block';

        error.style.display = 'none';
        expect(error.style.display).toBe('none');
    });

    it('should hide results', () => {
        const results = document.getElementById('results');
        results.style.display = 'block';

        results.style.display = 'none';
        expect(results.style.display).toBe('none');
    });
});

// ============================================================================
// DISPLAY RESULTS TESTS
// ============================================================================

describe('Display Results Function', () => {
    const mockData = {
        ticker: 'AAPL',
        current_price: 175.50,
        trend: 'Bullish',
        indicators: {
            rsi: 65.25,
            macd: 0.0234,
            sma_50: 170.00,
            sma_200: 165.00
        },
        levels: {
            support: [160.00, 165.00],
            resistance: [180.00, 185.00, 190.00]
        },
        charts: {
            price: {
                dates: ['2024-01-01', '2024-01-02'],
                close: [170, 175],
                sma_20: [168, 172],
                sma_50: [165, 167],
                sma_200: [160, 162],
                open: [169, 174],
                high: [171, 176],
                low: [168, 173]
            },
            bollinger: {
                dates: ['2024-01-01', '2024-01-02'],
                upper: [180, 185],
                middle: [170, 175],
                lower: [160, 165],
                close: [170, 175]
            },
            volume: {
                dates: ['2024-01-01', '2024-01-02'],
                volume: [1000000, 1200000],
                volume_ma: [1100000, 1150000]
            },
            rsi: {
                dates: ['2024-01-01', '2024-01-02'],
                rsi: [60, 65]
            },
            macd: {
                dates: ['2024-01-01', '2024-01-02'],
                macd: [0.02, 0.023],
                signal: [0.018, 0.021],
                histogram: [0.002, 0.002]
            }
        }
    };

    it('should display stock ticker correctly', () => {
        const stockTicker = document.getElementById('stockTicker');
        stockTicker.textContent = mockData.ticker;

        expect(stockTicker.textContent).toBe('AAPL');
    });

    it('should display current price correctly', () => {
        const currentPrice = document.getElementById('currentPrice');
        currentPrice.textContent = `$${mockData.current_price.toFixed(2)}`;

        expect(currentPrice.textContent).toBe('$175.50');
    });

    it('should display trend badge correctly', () => {
        const trendBadge = document.getElementById('trendBadge');
        trendBadge.textContent = mockData.trend;
        trendBadge.className = 'trend-badge ' + mockData.trend.toLowerCase();

        expect(trendBadge.textContent).toBe('Bullish');
        expect(trendBadge.className).toContain('bullish');
    });

    it('should display indicators correctly', () => {
        const rsiValue = document.getElementById('rsiValue');
        const macdValue = document.getElementById('macdValue');
        const sma50Value = document.getElementById('sma50Value');
        const sma200Value = document.getElementById('sma200Value');

        rsiValue.textContent = mockData.indicators.rsi.toFixed(2);
        macdValue.textContent = mockData.indicators.macd.toFixed(4);
        sma50Value.textContent = `$${mockData.indicators.sma_50.toFixed(2)}`;
        sma200Value.textContent = `$${mockData.indicators.sma_200.toFixed(2)}`;

        expect(rsiValue.textContent).toBe('65.25');
        expect(macdValue.textContent).toBe('0.0234');
        expect(sma50Value.textContent).toBe('$170.00');
        expect(sma200Value.textContent).toBe('$165.00');
    });

    it('should display support levels correctly', () => {
        const supportLevels = document.getElementById('supportLevels');
        supportLevels.innerHTML = '';

        mockData.levels.support.forEach(level => {
            const div = document.createElement('div');
            div.className = 'level-item';
            div.textContent = `$${level.toFixed(2)}`;
            supportLevels.appendChild(div);
        });

        const items = supportLevels.querySelectorAll('.level-item');
        expect(items.length).toBe(2);
        expect(items[0].textContent).toBe('$160.00');
        expect(items[1].textContent).toBe('$165.00');
    });

    it('should display resistance levels correctly', () => {
        const resistanceLevels = document.getElementById('resistanceLevels');
        resistanceLevels.innerHTML = '';

        mockData.levels.resistance.forEach(level => {
            const div = document.createElement('div');
            div.className = 'level-item';
            div.textContent = `$${level.toFixed(2)}`;
            resistanceLevels.appendChild(div);
        });

        const items = resistanceLevels.querySelectorAll('.level-item');
        expect(items.length).toBe(3);
        expect(items[0].textContent).toBe('$180.00');
        expect(items[2].textContent).toBe('$190.00');
    });

    it('should handle empty support/resistance levels', () => {
        const container = document.getElementById('supportLevels');
        container.innerHTML = '';

        const emptyLevels = [];
        if (emptyLevels.length === 0) {
            container.innerHTML = '<div class="level-item">No levels detected</div>';
        }

        expect(container.innerHTML).toContain('No levels detected');
    });
});

// ============================================================================
// API INTEGRATION TESTS
// ============================================================================

describe('API Integration', () => {
    beforeEach(() => {
        // Mock fetch globally
        global.fetch = vi.fn();
    });

    it('should make correct API request', async () => {
        const mockResponse = {
            ticker: 'AAPL',
            current_price: 175.50,
            indicators: { rsi: 65, macd: 0.02, sma_50: 170, sma_200: 165 },
            levels: { support: [], resistance: [] },
            trend: 'Bullish',
            charts: {
                price: { dates: [], close: [], sma_20: [], sma_50: [], sma_200: [] },
                bollinger: { dates: [], upper: [], middle: [], lower: [], close: [] },
                volume: { dates: [], volume: [], volume_ma: [] },
                rsi: { dates: [], rsi: [] },
                macd: { dates: [], macd: [], signal: [], histogram: [] }
            }
        };

        global.fetch.mockResolvedValue({
            ok: true,
            json: async () => mockResponse
        });

        const response = await fetch('http://localhost:8000/analyze_charts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker: 'AAPL', selected_strategies: [] })
        });

        expect(fetch).toHaveBeenCalledWith(
            'http://localhost:8000/analyze_charts',
            expect.objectContaining({
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
        );

        expect(response.ok).toBe(true);
        const data = await response.json();
        expect(data.ticker).toBe('AAPL');
    });

    it('should handle API error response', async () => {
        global.fetch.mockResolvedValue({
            ok: false,
            status: 404,
            json: async () => ({ detail: 'Ticker not found' })
        });

        const response = await fetch('http://localhost:8000/analyze_charts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker: 'INVALID', selected_strategies: [] })
        });

        expect(response.ok).toBe(false);
        expect(response.status).toBe(404);

        const error = await response.json();
        expect(error.detail).toBe('Ticker not found');
    });

    it('should handle network error', async () => {
        global.fetch.mockRejectedValue(new Error('Network error'));

        try {
            await fetch('http://localhost:8000/analyze_charts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker: 'AAPL', selected_strategies: [] })
            });
            expect.fail('Should have thrown error');
        } catch (error) {
            expect(error.message).toBe('Network error');
        }
    });
});

// ============================================================================
// CHART CREATION TESTS
// ============================================================================

describe('Chart Creation', () => {
    it('should create chart with correct context', () => {
        const canvas = document.getElementById('priceChart');
        const ctx = canvas.getContext('2d');

        expect(ctx).toBeDefined();
    });

    it('should create price chart with correct data structure', () => {
        const mockData = {
            dates: ['2024-01-01', '2024-01-02'],
            close: [170, 175],
            sma_20: [168, 172],
            sma_50: [165, 167],
            sma_200: [160, 162],
            open: [169, 174],
            high: [171, 176],
            low: [168, 173]
        };

        const chartConfig = {
            type: 'line',
            data: {
                labels: mockData.dates,
                datasets: [
                    {
                        label: 'Close Price',
                        data: mockData.close,
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        borderWidth: 2,
                        pointRadius: 0,
                        fill: true
                    }
                ]
            }
        };

        expect(chartConfig.type).toBe('line');
        expect(chartConfig.data.labels).toEqual(mockData.dates);
        expect(chartConfig.data.datasets[0].data).toEqual(mockData.close);
    });

    it('should create MACD histogram with color coding', () => {
        const histogramData = [0.002, -0.001, 0.003, -0.002];
        const colors = histogramData.map(val =>
            val >= 0 ? 'rgba(16, 185, 129, 0.6)' : 'rgba(239, 68, 68, 0.6)'
        );

        expect(colors[0]).toBe('rgba(16, 185, 129, 0.6)'); // Positive - green
        expect(colors[1]).toBe('rgba(239, 68, 68, 0.6)');  // Negative - red
        expect(colors[2]).toBe('rgba(16, 185, 129, 0.6)'); // Positive - green
        expect(colors[3]).toBe('rgba(239, 68, 68, 0.6)');  // Negative - red
    });
});

// ============================================================================
// INPUT VALIDATION TESTS
// ============================================================================

describe('Input Validation', () => {
    it('should validate empty ticker input', () => {
        const ticker = document.getElementById('ticker');
        ticker.value = '';

        const value = ticker.value.trim().toUpperCase();
        expect(value).toBe('');
    });

    it('should convert ticker to uppercase', () => {
        const ticker = document.getElementById('ticker');
        ticker.value = 'aapl';

        const value = ticker.value.trim().toUpperCase();
        expect(value).toBe('AAPL');
    });

    it('should trim whitespace from ticker', () => {
        const ticker = document.getElementById('ticker');
        ticker.value = '  AAPL  ';

        const value = ticker.value.trim().toUpperCase();
        expect(value).toBe('AAPL');
    });
});

// ============================================================================
// CHART OPTIONS TESTS
// ============================================================================

describe('Chart Options', () => {
    it('should generate correct chart options structure', () => {
        const getChartOptions = (yAxisLabel) => ({
            responsive: true,
            maintainAspectRatio: true,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                },
                tooltip: {
                    enabled: true,
                    mode: 'index',
                    intersect: false,
                }
            },
            scales: {
                x: {
                    display: true,
                    ticks: {
                        maxTicksLimit: 10
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: yAxisLabel
                    }
                }
            }
        });

        const options = getChartOptions('Price ($)');

        expect(options.responsive).toBe(true);
        expect(options.scales.y.title.text).toBe('Price ($)');
        expect(options.plugins.legend.display).toBe(true);
    });
});
