"""
Walk-Forward Optimizer — Multi-ticker grid search with train/test validation.

Prevents overfitting by:
  1. Training across multiple tickers (generalization)
  2. Splitting each ticker's data into train/test windows
  3. Reporting overfitting score = (train_sharpe - test_sharpe) / train_sharpe

Default ticker universe:
  NVDA, AAPL, MSFT, AMZN, GOOGL, META, TSLA, AMD
"""

import json
import logging
import os
import time
from itertools import product
from typing import Dict, Any, List, Optional, Tuple

from .backtester import Backtester
from .metrics import compute_metrics

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import OPTIMIZER_TICKERS

logger = logging.getLogger(__name__)

TUNED_PARAMS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "agents", "tuned_params.json"
)

DEFAULT_TICKERS = OPTIMIZER_TICKERS

# ── Parameter grid (same as single-ticker optimizer) ──────────────────────────

_GRID = {
    "pattern_weight":   [0.35, 0.45, 0.55, 0.65],
    "rsi_oversold":     [25, 30, 35],
    "rsi_overbought":   [65, 70, 75],
    "signal_threshold": [0.10, 0.15, 0.20],
}


def _expand_grid(grid: Dict[str, List]) -> List[Dict[str, Any]]:
    keys = list(grid.keys())
    combos = list(product(*grid.values()))
    result = []
    for combo in combos:
        params = dict(zip(keys, combo))
        params["quant_weight"] = round(1.0 - params["pattern_weight"], 2)
        result.append(params)
    return result


def _split_dates(df_index, train_ratio: float) -> Tuple[str, str, str, str]:
    """Compute train/test split dates from a DatetimeIndex."""
    n = len(df_index)
    split_idx = int(n * train_ratio)
    train_start = str(df_index[0].date())
    train_end   = str(df_index[split_idx - 1].date())
    test_start  = str(df_index[split_idx].date())
    test_end    = str(df_index[-1].date())
    return train_start, train_end, test_start, test_end


# ── Walk-Forward Optimizer ────────────────────────────────────────────────────

class WalkForwardOptimizer:
    """
    Multi-ticker walk-forward optimizer with overfitting detection.

    Usage:
        wfo = WalkForwardOptimizer(db, data_collector)
        result = wfo.optimize(["NVDA", "AAPL", "MSFT"])
    """

    def __init__(self, db, data_collector=None):
        self.db = db
        self.data_collector = data_collector
        self.backtester = Backtester(db)

    def optimize(
        self,
        tickers: Optional[List[str]] = None,
        train_ratio: float = 0.6,
    ) -> Dict[str, Any]:
        """
        Run multi-ticker walk-forward optimization.

        Args:
            tickers:      list of tickers to optimize across (default: 8-stock universe)
            train_ratio:  fraction of data for training (default: 0.6 = first 60%)

        Returns:
            dict with train/test metrics per ticker, best params, overfitting score
        """
        tickers = tickers or DEFAULT_TICKERS
        start_time = time.time()

        logger.info(f"WF-Optimizer: starting for {len(tickers)} tickers, train_ratio={train_ratio}")

        # ── 1. Ensure data is fresh ──────────────────────────────────────────
        if self.data_collector:
            for t in tickers:
                try:
                    self.data_collector.update_stock_data(t)
                except Exception as e:
                    logger.warning(f"WF-Optimizer: data update failed for {t}: {e}")

        # ── 2. Compute train/test split dates per ticker ──────────────────────
        splits: Dict[str, Dict[str, str]] = {}
        valid_tickers: List[str] = []

        for t in tickers:
            try:
                df = self.backtester._load_and_prepare(t)
                if len(df) < 100:
                    logger.warning(f"WF-Optimizer: skipping {t}, only {len(df)} bars")
                    continue
                train_start, train_end, test_start, test_end = _split_dates(df.index, train_ratio)
                splits[t] = {
                    "train_start": train_start, "train_end": train_end,
                    "test_start": test_start,   "test_end": test_end,
                    "total_bars": len(df),
                }
                valid_tickers.append(t)
            except Exception as e:
                logger.warning(f"WF-Optimizer: failed to load {t}: {e}")

        if not valid_tickers:
            return {"error": "No valid tickers with enough data"}

        logger.info(f"WF-Optimizer: {len(valid_tickers)} valid tickers: {valid_tickers}")

        # ── 3. Grid search on TRAIN data ──────────────────────────────────────
        param_grid = _expand_grid(_GRID)
        total_combos = len(param_grid)
        logger.info(f"WF-Optimizer: searching {total_combos} combos × {len(valid_tickers)} tickers")

        search_results: List[Tuple[float, Dict, Dict]] = []  # (avg_sharpe, params, per_ticker_metrics)

        for i, params in enumerate(param_grid):
            ticker_sharpes = []
            ticker_metrics = {}

            for t in valid_tickers:
                try:
                    result = self.backtester.run_on_range(
                        t, splits[t]["train_start"], splits[t]["train_end"], params
                    )
                    metrics = compute_metrics(
                        result["trade_log"], result["equity_curve"], result["buy_hold_curve"]
                    )
                    sharpe = metrics.get("sharpe_ratio", 0) or 0
                    ticker_sharpes.append(sharpe)
                    ticker_metrics[t] = metrics
                except Exception as e:
                    logger.debug(f"WF-Optimizer: {t} failed with params {params}: {e}")
                    ticker_sharpes.append(0)

            if ticker_sharpes:
                avg_sharpe = sum(ticker_sharpes) / len(ticker_sharpes)
                search_results.append((avg_sharpe, params, ticker_metrics))

            if (i + 1) % 20 == 0:
                logger.info(f"WF-Optimizer: progress {i+1}/{total_combos}")

        if not search_results:
            return {"error": "All parameter combinations failed"}

        # ── 4. Pick best by average train Sharpe ──────────────────────────────
        search_results.sort(key=lambda x: x[0], reverse=True)
        best_train_sharpe, best_params, best_train_metrics = search_results[0]

        logger.info(f"WF-Optimizer: best train avg Sharpe = {best_train_sharpe:.3f}")

        # ── 5. Validate on TEST data ──────────────────────────────────────────
        test_metrics_per_ticker: Dict[str, Any] = {}
        test_sharpes = []

        for t in valid_tickers:
            try:
                result = self.backtester.run_on_range(
                    t, splits[t]["test_start"], splits[t]["test_end"], best_params
                )
                metrics = compute_metrics(
                    result["trade_log"], result["equity_curve"], result["buy_hold_curve"]
                )
                test_metrics_per_ticker[t] = metrics
                test_sharpes.append(metrics.get("sharpe_ratio", 0) or 0)
            except Exception as e:
                logger.warning(f"WF-Optimizer: test validation failed for {t}: {e}")
                test_metrics_per_ticker[t] = {"error": str(e)}
                test_sharpes.append(0)

        avg_test_sharpe = sum(test_sharpes) / len(test_sharpes) if test_sharpes else 0

        # ── 6. Compute overfitting score ──────────────────────────────────────
        if best_train_sharpe > 0:
            overfit_score = (best_train_sharpe - avg_test_sharpe) / best_train_sharpe
        else:
            overfit_score = 0.0

        overfit_pct = round(overfit_score * 100, 1)

        if overfit_pct < 30:
            overfit_verdict = "robust"
            overfit_emoji = "✅"
        elif overfit_pct < 60:
            overfit_verdict = "moderate"
            overfit_emoji = "⚠️"
        else:
            overfit_verdict = "severe"
            overfit_emoji = "🚨"

        logger.info(
            f"WF-Optimizer: overfitting score = {overfit_pct}% ({overfit_verdict}) "
            f"— train Sharpe {best_train_sharpe:.3f}, test Sharpe {avg_test_sharpe:.3f}"
        )

        # ── 7. Save tuned params with validation metadata ─────────────────────
        save_payload = {
            **best_params,
            "_validation": {
                "method": "walk_forward",
                "tickers": valid_tickers,
                "train_ratio": train_ratio,
                "train_sharpe": round(best_train_sharpe, 3),
                "test_sharpe": round(avg_test_sharpe, 3),
                "overfit_pct": overfit_pct,
                "overfit_verdict": overfit_verdict,
            }
        }

        save_path = os.path.abspath(TUNED_PARAMS_PATH)
        try:
            with open(save_path, "w") as f:
                json.dump(save_payload, f, indent=2)
            logger.info(f"WF-Optimizer: saved best params to {save_path}")
        except Exception as e:
            logger.error(f"WF-Optimizer: could not save params: {e}")
            save_path = None

        # ── 8. Build per-ticker comparison table ──────────────────────────────
        per_ticker_report = []
        for t in valid_tickers:
            train_m = best_train_metrics.get(t, {})
            test_m  = test_metrics_per_ticker.get(t, {})
            per_ticker_report.append({
                "ticker": t,
                "train": {
                    "sharpe":       train_m.get("sharpe_ratio", 0),
                    "win_rate":     train_m.get("win_rate", 0),
                    "total_return": train_m.get("total_return_pct", 0),
                    "trades":       train_m.get("total_trades", 0),
                    "max_drawdown": train_m.get("max_drawdown_pct", 0),
                },
                "test": {
                    "sharpe":       test_m.get("sharpe_ratio", 0),
                    "win_rate":     test_m.get("win_rate", 0),
                    "total_return": test_m.get("total_return_pct", 0),
                    "trades":       test_m.get("total_trades", 0),
                    "max_drawdown": test_m.get("max_drawdown_pct", 0),
                },
                "dates": splits.get(t, {}),
            })

        # Top-10 param combos
        top_10 = [
            {**p, "avg_sharpe": round(s, 3)}
            for s, p, _ in search_results[:10]
        ]

        elapsed = round(time.time() - start_time, 1)

        return {
            "method":              "walk_forward",
            "tickers":             valid_tickers,
            "train_ratio":         train_ratio,
            "combinations_tried":  len(search_results),
            "elapsed_seconds":     elapsed,
            "best_params":         best_params,
            "train_avg_sharpe":    round(best_train_sharpe, 3),
            "test_avg_sharpe":     round(avg_test_sharpe, 3),
            "overfitting": {
                "score_pct":  overfit_pct,
                "verdict":    overfit_verdict,
                "emoji":      overfit_emoji,
            },
            "per_ticker":          per_ticker_report,
            "top_10_combos":       top_10,
            "saved_to":            save_path,
        }
