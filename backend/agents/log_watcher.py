"""
Log Watcher Agent — monitors log files for errors and suggests fixes.

Scans today's log file, categorizes issues by severity, groups recurring
patterns, and maps known error signatures to actionable suggestions.
"""

import re
import os
from datetime import datetime
from collections import Counter, defaultdict
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Known error patterns → suggested fixes
# ─────────────────────────────────────────────────────────────────────────────

ERROR_PATTERNS = [
    {
        "id": "llm_empty_json",
        "pattern": r"(returned no extractable JSON|returned empty JSON|All models returned empty JSON|Model returned empty JSON)",
        "severity": "high",
        "category": "LLM",
        "title": "LLM returning no parseable JSON",
        "suggestion": "The LLM model (llama3.2:3b) is producing malformed output. "
                      "Check if Ollama is running (`ollama list`). "
                      "If the model is loaded, inspect the raw response for unquoted strings or truncation. "
                      "Consider increasing `num_predict` or adding stricter JSON prompting.",
    },
    {
        "id": "llm_fallback",
        "pattern": r"falling back to expert system",
        "severity": "medium",
        "category": "LLM",
        "title": "LLM synthesis failed — using expert system fallback",
        "suggestion": "The LangGraph Brain failed to produce a valid recommendation, so the rule-based "
                      "AnalystBrain was used instead. This is expected behavior but indicates the LLM "
                      "is unreliable. Check Ollama status and LLM logs for root cause.",
    },
    {
        "id": "praw_missing",
        "pattern": r"praw package not installed",
        "severity": "low",
        "category": "Dependencies",
        "title": "Reddit connector disabled — praw not installed",
        "suggestion": "Install praw: `pip install praw`. "
                      "Or suppress this warning by setting REDDIT_ENABLED=false in .env. "
                      "The app works fine without Reddit data.",
    },
    {
        "id": "finnhub_rate_limit",
        "pattern": r"(429|rate.?limit|too many requests)",
        "severity": "high",
        "category": "API",
        "title": "Finnhub API rate limit exceeded (429)",
        "suggestion": "The free Finnhub tier allows 60 calls/minute. "
                      "Add throttling between batch scan tickers (time.sleep) or "
                      "implement request queuing. Consider upgrading the Finnhub plan for production.",
    },
    {
        "id": "finnhub_404",
        "pattern": r"finnhub.*404|symbol not found",
        "severity": "low",
        "category": "API",
        "title": "Finnhub returned 404 for a ticker",
        "suggestion": "The ticker may be delisted or not covered by Finnhub. "
                      "Verify the ticker exists on Finnhub's symbol lookup.",
    },
    {
        "id": "yfinance_error",
        "pattern": r"(yfinance|Yahoo Finance).*(error|failed|exception|no data)",
        "severity": "medium",
        "category": "Data",
        "title": "yfinance data fetch failed",
        "suggestion": "Yahoo Finance may be rate-limiting or down. "
                      "Check internet connectivity. If persistent, add retry logic with exponential backoff.",
    },
    {
        "id": "ollama_connection",
        "pattern": r"(Connection refused|Ollama.*unavailable|connect.*ollama|Could not connect)",
        "severity": "critical",
        "category": "LLM",
        "title": "Cannot connect to Ollama server",
        "suggestion": "Ollama is not running. Start it with `ollama serve` in a separate terminal. "
                      "Verify it's listening on port 11434: `curl http://localhost:11434/api/tags`",
    },
    {
        "id": "json_parse_error",
        "pattern": r"(JSONDecodeError|json\.loads|Expecting.*delimiter|Expecting value)",
        "severity": "medium",
        "category": "LLM",
        "title": "JSON parsing error from LLM output",
        "suggestion": "The LLM response contained malformed JSON that couldn't be repaired. "
                      "This is usually caused by unquoted string values or truncated responses. "
                      "The _fix_unquoted_values() repair logic should handle most cases.",
    },
    {
        "id": "stale_data",
        "pattern": r"data.*is stale|Refreshing|stale or missing",
        "severity": "info",
        "category": "Data",
        "title": "Historical data refresh triggered",
        "suggestion": "This is normal — data is being incrementally updated from yfinance. "
                      "If this happens too frequently, check market_hours.py freshness logic.",
    },
    {
        "id": "newsapi_error",
        "pattern": r"(newsapi|News API).*(error|failed|exception|rate.?limit)",
        "severity": "medium",
        "category": "API",
        "title": "NewsAPI request failed",
        "suggestion": "Check your NEWSAPI_KEY in .env. Free tier allows 100 requests/day. "
                      "If exhausted, the app will fall back to Finnhub for news.",
    },
    {
        "id": "twitter_disabled",
        "pattern": r"Twitter.*DISABLED|TWITTER_ENABLED.*false",
        "severity": "info",
        "category": "Config",
        "title": "Twitter integration is disabled",
        "suggestion": "Set TWITTER_ENABLED=true in .env and provide a valid TWITTER_BEARER_TOKEN to enable.",
    },
    {
        "id": "memory_warning",
        "pattern": r"(MemoryError|out of memory|memory.*exhausted)",
        "severity": "critical",
        "category": "System",
        "title": "Memory exhaustion detected",
        "suggestion": "The system is running out of memory. This may be caused by the LLM model. "
                      "Try using a smaller model (llama3.2:1b) or reducing batch scan size.",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Log Watcher Agent
# ─────────────────────────────────────────────────────────────────────────────

class LogWatcherAgent:
    """Analyzes log files for errors, patterns, and suggests fixes."""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir

    def _get_today_log_path(self) -> str:
        today = datetime.now().strftime('%Y-%m-%d')
        return os.path.join(self.log_dir, f"trade_app_{today}.log")

    def _read_log_lines(self, path: str, max_lines: int = 5000) -> list:
        """Read log file lines, handling file locks."""
        if not os.path.exists(path):
            return []
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            return lines[-max_lines:] if len(lines) > max_lines else lines
        except Exception as e:
            logger.warning(f"LogWatcher: Could not read {path}: {e}")
            return []

    def _parse_line(self, line: str) -> dict:
        """Parse a single log line."""
        line = line.strip()
        if not line:
            return None
        match = re.match(
            r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - ([\w.]+) - (\w+) - (.+)$',
            line
        )
        if match:
            timestamp, source, level, message = match.groups()
            return {
                "timestamp": timestamp,
                "source": source,
                "level": level,
                "message": message,
                "raw": line,
            }
        return None

    def analyze(self, max_lines: int = 5000) -> dict:
        """
        Analyze today's log file and return a structured report.
        
        Returns:
            {
                "summary": {...},
                "issues": [...],
                "error_timeline": [...],
                "health_score": int,
                "recommendations": [...]
            }
        """
        path = self._get_today_log_path()
        raw_lines = self._read_log_lines(path, max_lines)

        if not raw_lines:
            return {
                "summary": {"total": 0, "errors": 0, "warnings": 0, "info": 0},
                "issues": [],
                "error_timeline": [],
                "health_score": 100,
                "recommendations": [],
                "log_file": os.path.basename(path),
                "analyzed_at": datetime.now().isoformat(),
            }

        # Parse all lines
        entries = []
        for line in raw_lines:
            parsed = self._parse_line(line)
            if parsed:
                entries.append(parsed)

        # Count levels
        level_counts = Counter(e["level"] for e in entries)
        total = len(entries)
        errors = level_counts.get("ERROR", 0)
        warnings = level_counts.get("WARNING", 0)

        # Match error patterns
        issues = []
        pattern_counts = defaultdict(lambda: {"count": 0, "first_seen": None, "last_seen": None, "samples": []})

        for entry in entries:
            full_text = f"{entry['source']} - {entry['level']} - {entry['message']}"
            for pat in ERROR_PATTERNS:
                if re.search(pat["pattern"], full_text, re.IGNORECASE):
                    pid = pat["id"]
                    pc = pattern_counts[pid]
                    pc["count"] += 1
                    if pc["first_seen"] is None:
                        pc["first_seen"] = entry["timestamp"]
                    pc["last_seen"] = entry["timestamp"]
                    if len(pc["samples"]) < 3:
                        pc["samples"].append(entry["message"][:200])

        # Build issues list sorted by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        for pat in ERROR_PATTERNS:
            pid = pat["id"]
            if pid in pattern_counts:
                pc = pattern_counts[pid]
                issues.append({
                    "id": pid,
                    "severity": pat["severity"],
                    "category": pat["category"],
                    "title": pat["title"],
                    "suggestion": pat["suggestion"],
                    "count": pc["count"],
                    "first_seen": pc["first_seen"],
                    "last_seen": pc["last_seen"],
                    "samples": pc["samples"],
                })

        issues.sort(key=lambda x: severity_order.get(x["severity"], 5))

        # Build error timeline (errors per 10-min bucket)
        error_timeline = []
        time_buckets = defaultdict(int)
        for entry in entries:
            if entry["level"] in ("ERROR", "WARNING"):
                ts = entry["timestamp"][:15] + "0"  # Round to 10-min
                time_buckets[ts] += 1
        for ts, count in sorted(time_buckets.items()):
            error_timeline.append({"time": ts, "count": count})

        # Compute health score (0-100)
        health = 100
        for issue in issues:
            if issue["severity"] == "critical":
                health -= 30
            elif issue["severity"] == "high":
                health -= min(15, issue["count"] * 3)
            elif issue["severity"] == "medium":
                health -= min(10, issue["count"] * 2)
            elif issue["severity"] == "low":
                health -= min(5, issue["count"])
        health = max(0, health)

        # Top recommendations (actionable items only)
        recommendations = []
        for issue in issues:
            if issue["severity"] in ("critical", "high", "medium") and issue["count"] > 0:
                recommendations.append({
                    "priority": issue["severity"],
                    "action": issue["suggestion"],
                    "related_issue": issue["title"],
                    "occurrences": issue["count"],
                })

        return {
            "summary": {
                "total": total,
                "errors": errors,
                "warnings": warnings,
                "info": level_counts.get("INFO", 0),
            },
            "issues": issues,
            "error_timeline": error_timeline,
            "health_score": health,
            "recommendations": recommendations,
            "log_file": os.path.basename(path),
            "analyzed_at": datetime.now().isoformat(),
        }
