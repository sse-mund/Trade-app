"""
Metrics — Compute performance statistics from a backtester trade log.
"""

import math
from typing import Dict, Any, List


def compute_metrics(
    trade_log: List[Dict],
    equity_curve: List[Dict],
    buy_hold_curve: List[Dict],
) -> Dict[str, Any]:
    """
    Compute performance metrics from a completed backtest.

    Args:
        trade_log:     list of trade dicts from Backtester.run()
        equity_curve:  list of {date, equity} dicts
        buy_hold_curve: list of {date, value} dicts

    Returns:
        dict with all performance metrics
    """
    if not trade_log:
        return {"error": "No trades executed"}

    pnls = [t["pnl_pct"] for t in trade_log]
    winners = [p for p in pnls if p > 0]
    losers  = [p for p in pnls if p <= 0]

    win_rate = len(winners) / len(pnls) * 100 if pnls else 0
    avg_win  = sum(winners) / len(winners) if winners else 0
    avg_loss = sum(losers)  / len(losers)  if losers  else 0
    avg_return = sum(pnls) / len(pnls)

    # Profit factor (gross profit / gross loss)
    gross_profit = sum(winners) if winners else 0
    gross_loss   = abs(sum(losers)) if losers else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Total model return (from equity curve)
    start_eq = equity_curve[0]["equity"]  if equity_curve else 100
    end_eq   = equity_curve[-1]["equity"] if equity_curve else 100
    total_return = (end_eq - start_eq) / start_eq * 100

    # Buy-and-hold return over same period
    start_bh = buy_hold_curve[0]["value"]  if buy_hold_curve else 100
    end_bh   = buy_hold_curve[-1]["value"] if buy_hold_curve else 100
    buy_hold_return = end_bh - start_bh  # already normalised to 100

    # Max drawdown (on equity curve)
    max_drawdown = _max_drawdown([e["equity"] for e in equity_curve])

    # Sharpe ratio (annualised, using per-trade returns as a proxy)
    sharpe = _sharpe(pnls)

    # Days held stats
    days_held_list = [t["days_held"] for t in trade_log]
    avg_days_held  = sum(days_held_list) / len(days_held_list) if days_held_list else 0

    # Per-agent win analysis
    # A pattern/quant signal was "correct" if it pointed the same direction as the trade outcome
    pattern_correct = _agent_accuracy(trade_log, "entry_pattern_signal")
    quant_correct   = _agent_accuracy(trade_log, "entry_quant_signal")

    return {
        "total_trades":     len(trade_log),
        "winning_trades":   len(winners),
        "losing_trades":    len(losers),
        "win_rate":         round(win_rate, 1),
        "avg_win_pct":      round(avg_win, 2),
        "avg_loss_pct":     round(avg_loss, 2),
        "avg_return_pct":   round(avg_return, 2),
        "profit_factor":    round(profit_factor, 2) if profit_factor != float("inf") else 999,
        "total_return_pct": round(total_return, 2),
        "buy_hold_return_pct": round(buy_hold_return, 2),
        "alpha":            round(total_return - buy_hold_return, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "sharpe_ratio":     round(sharpe, 3),
        "avg_days_held":    round(avg_days_held, 1),
        "agent_accuracy": {
            "pattern": round(pattern_correct * 100, 1),
            "quant":   round(quant_correct   * 100, 1),
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _max_drawdown(equity: List[float]) -> float:
    """Peak-to-trough max drawdown as a % of peak equity."""
    if not equity:
        return 0.0
    peak = equity[0]
    max_dd = 0.0
    for val in equity:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _sharpe(returns: List[float], risk_free: float = 0.05) -> float:
    """
    Annualised Sharpe ratio from per-trade return % list.
    Assumes ~252 trades per year (rough, since trades are irregular).
    """
    if len(returns) < 2:
        return 0.0
    n = len(returns)
    avg = sum(returns) / n
    variance = sum((r - avg) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(variance) if variance > 0 else 0
    if std == 0:
        return 0.0
    # Annualise: assume average 20 trading days per trade, 252 days/yr → ~12 trades/yr
    trades_per_year = 252 / 20
    return (avg - risk_free / trades_per_year) / std * math.sqrt(trades_per_year)


def _agent_accuracy(trade_log: List[Dict], signal_key: str) -> float:
    """Fraction of trades where an agent's entry signal direction matched the outcome."""
    if not trade_log:
        return 0.0
    correct = 0
    for t in trade_log:
        sig = t.get(signal_key, 0)
        pnl = t.get("pnl_pct", 0)
        # Signal positive + trade profitable = correct
        # Signal negative + trade unprofitable = would also be "correct" if we shorted,
        # but we only go long, so a negative entry signal that generated a long = INCORRECT
        if sig > 0 and pnl > 0:
            correct += 1
        elif sig < 0 and pnl <= 0:
            correct += 1  # agent was right that the trade should not have been entered
    return correct / len(trade_log)
