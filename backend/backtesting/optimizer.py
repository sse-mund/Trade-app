"""
Optimizer — Grid search over agent parameters to maximise risk-adjusted returns.

Parameters tuned:
  - pattern_weight / quant_weight  (must sum to 1)
  - rsi_oversold  threshold (25 / 30 / 35)
  - rsi_overbought threshold (65 / 70 / 75)
  - signal_threshold (0.10 / 0.15 / 0.20)

Optimisation objective: maximise Sharpe ratio
  (avoids overfitting to lucky high-return but high-risk params)

Results saved to backend/agents/tuned_params.json so the orchestrator
can load them automatically on next startup.
"""

import json
import logging
import os
from itertools import product
from typing import Dict, Any, List, Tuple, Optional

from .backtester import Backtester
from .metrics import compute_metrics

logger = logging.getLogger(__name__)

TUNED_PARAMS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "agents", "tuned_params.json"
)

# ── Parameter grid ─────────────────────────────────────────────────────────────

_GRID = {
    "pattern_weight":  [0.35, 0.45, 0.55, 0.65],
    "rsi_oversold":    [25, 30, 35],
    "rsi_overbought":  [65, 70, 75],
    "signal_threshold":[0.10, 0.15, 0.20],
}


def _expand_grid(grid: Dict[str, List]) -> List[Dict[str, Any]]:
    keys = list(grid.keys())
    combos = list(product(*grid.values()))
    result = []
    for combo in combos:
        params = dict(zip(keys, combo))
        # quant_weight is complement of pattern_weight
        params["quant_weight"] = round(1.0 - params["pattern_weight"], 2)
        result.append(params)
    return result


# ── Optimizer class ────────────────────────────────────────────────────────────

class Optimizer:
    """
    Grid-search optimizer.

    Usage:
        opt = Optimizer(db)
        result = opt.optimize("NVDA")
        # result contains best_params, before/after metrics, full search log
    """

    def __init__(self, db):
        self.db = db
        self.backtester = Backtester(db)

    def optimize(self, ticker: str) -> Dict[str, Any]:
        """
        Run grid search over parameter space, return best params and comparison.

        Args:
            ticker: Stock ticker to optimise on (e.g. "NVDA")

        Returns:
            dict with keys:
              ticker, best_params, baseline_metrics, best_metrics,
              improvement, search_results (top 10), saved_to
        """
        # ── Baseline (default params) ──────────────────────────────────────
        logger.info(f"Optimizer: computing baseline for {ticker}")
        baseline_result = self.backtester.run(ticker, params={})
        baseline_metrics = compute_metrics(
            baseline_result["trade_log"],
            baseline_result["equity_curve"],
            baseline_result["buy_hold_curve"],
        )

        # ── Grid search ────────────────────────────────────────────────────
        param_grid = _expand_grid(_GRID)
        logger.info(f"Optimizer: searching {len(param_grid)} parameter combinations for {ticker}")

        search_results: List[Tuple[float, Dict, Dict]] = []

        for params in param_grid:
            try:
                result = self.backtester.run(ticker, params=params)
                metrics = compute_metrics(
                    result["trade_log"],
                    result["equity_curve"],
                    result["buy_hold_curve"],
                )
                score = metrics.get("sharpe_ratio", 0)
                search_results.append((score, params, metrics))
            except Exception as e:
                logger.warning(f"Optimizer: param combo failed: {params} — {e}")

        if not search_results:
            return {"error": "All parameter combinations failed"}

        # ── Pick best by Sharpe ────────────────────────────────────────────
        search_results.sort(key=lambda x: x[0], reverse=True)
        best_score, best_params, best_metrics = search_results[0]

        # ── Save tuned params ──────────────────────────────────────────────
        save_path = os.path.abspath(TUNED_PARAMS_PATH)
        try:
            with open(save_path, "w") as f:
                json.dump(best_params, f, indent=2)
            logger.info(f"Optimizer: saved best params to {save_path}")
        except Exception as e:
            logger.error(f"Optimizer: could not save params: {e}")
            save_path = None

        # Top-10 results for display
        top_10 = [
            {**p, "sharpe": round(s, 3), "win_rate": m.get("win_rate"), "total_return": m.get("total_return_pct")}
            for s, p, m in search_results[:10]
        ]

        improvement = {
            "sharpe":       round(best_metrics.get("sharpe_ratio", 0) - baseline_metrics.get("sharpe_ratio", 0), 3),
            "win_rate":     round((best_metrics.get("win_rate", 0) or 0) - (baseline_metrics.get("win_rate", 0) or 0), 1),
            "total_return": round((best_metrics.get("total_return_pct", 0) or 0) - (baseline_metrics.get("total_return_pct", 0) or 0), 2),
        }

        return {
            "ticker":           ticker,
            "combinations_tried": len(search_results),
            "best_params":      best_params,
            "baseline_metrics": baseline_metrics,
            "best_metrics":     best_metrics,
            "improvement":      improvement,
            "top_10_combos":    top_10,
            "saved_to":         save_path,
        }


# ── Helper: load saved params ──────────────────────────────────────────────────

def load_tuned_params() -> Optional[Dict[str, Any]]:
    """Load tuned_params.json if it exists. Returns None otherwise."""
    path = os.path.abspath(TUNED_PARAMS_PATH)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            params = json.load(f)
        logger.info(f"Loaded tuned params from {path}: {params}")
        return params
    except Exception as e:
        logger.warning(f"Could not load tuned_params.json: {e}")
        return None
