"""
Log Analyzer Agent — Daily Error/Warning Analysis & Suggestions

Reads the application log files, extracts all ERROR and WARNING entries,
groups them by pattern, analyzes root causes, and writes a daily
markdown report with actionable suggestions.

Can be triggered:
  - On app startup (analyzes previous day's logs)
  - Via API endpoint (/analyze_logs)
  - Manually: python -m agents.log_analyzer
"""

import os
import re
import logging
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Known error signatures → root cause & suggested fix
# ─────────────────────────────────────────────────────────────────────────────

ERROR_SIGNATURES = [
    {
        "id": "newsapi_rate_limit",
        "pattern": r"News API rate limit exceeded",
        "category": "API",
        "root_cause": "NewsAPI free tier (100 req/day) exhausted during batch scans",
        "suggestion": (
            "1. Reduce scan frequency or batch size\n"
            "2. Cache news results per ticker for 1-2 hours\n"
            "3. Upgrade to a paid NewsAPI plan ($449/mo for 250K req)\n"
            "4. Add a request counter that stops calling NewsAPI after 80 requests/day"
        ),
        "severity": "warning",
    },
    {
        "id": "newsapi_timeout",
        "pattern": r"News API request timed out",
        "category": "API",
        "root_cause": "NewsAPI server didn't respond within the timeout window",
        "suggestion": (
            "1. Increase timeout from 10s to 15s in newsapi_connector.py\n"
            "2. Add retry logic with exponential backoff (max 2 retries)\n"
            "3. This is often transient — check if it correlates with high API load times"
        ),
        "severity": "warning",
    },
    {
        "id": "newsapi_no_articles",
        "pattern": r"No articles returned for (\w+)",
        "category": "Data",
        "root_cause": "No news coverage found for the ticker (often follows rate limit)",
        "suggestion": (
            "1. Check if this follows a rate limit error (if so, fix the rate limit first)\n"
            "2. For low-coverage tickers, fall back to Finnhub company news\n"
            "3. Consider expanding search terms beyond just the ticker symbol"
        ),
        "severity": "info",
    },
    {
        "id": "finnhub_connection_reset",
        "pattern": r"Error fetching Finnhub.*(Connection.*aborted|ConnectionResetError|forcibly closed)",
        "category": "API",
        "root_cause": "Finnhub server dropped the TCP connection (rate limiting or server overload)",
        "suggestion": (
            "1. Add connection retry with 1-2s backoff in finnhub_connector.py\n"
            "2. Implement connection pooling with `requests.Session()`\n"
            "3. Check if this correlates with rapid sequential API calls during batch scans\n"
            "4. Add `time.sleep(0.5)` between Finnhub API calls in batch operations"
        ),
        "severity": "high",
    },
    {
        "id": "finnhub_timeout",
        "pattern": r"Error fetching Finnhub.*(Read timed out|ConnectTimeoutError|timeout)",
        "category": "API",
        "root_cause": "Finnhub API didn't respond within the timeout window",
        "suggestion": (
            "1. Increase read timeout from 10s to 15s\n"
            "2. Add retry logic (max 2 retries with 2s backoff)\n"
            "3. If frequent, check network stability or switch to a closer Finnhub endpoint"
        ),
        "severity": "warning",
    },
    {
        "id": "finnhub_rate_limit",
        "pattern": r"(429|rate.?limit|too many requests).*finnhub|finnhub.*(429|rate.?limit)",
        "category": "API",
        "root_cause": "Exceeded Finnhub free tier limit (60 calls/min)",
        "suggestion": (
            "1. Add a rate limiter: max 55 calls/min with token bucket\n"
            "2. Batch scan should throttle: `time.sleep(1.1)` between tickers\n"
            "3. Cache Finnhub quote data for 60 seconds\n"
            "4. Consider upgrading Finnhub plan for production use"
        ),
        "severity": "high",
    },
    {
        "id": "llm_empty_json",
        "pattern": r"(returned no extractable JSON|returned empty JSON|All models returned empty JSON)",
        "category": "LLM",
        "root_cause": "Ollama LLM produced prose instead of valid JSON structure",
        "suggestion": (
            "1. Verify Ollama is running: `ollama list`\n"
            "2. Check if model is overloaded (GPU memory)\n"
            "3. Inspect raw LLM response in logs for truncation patterns\n"
            "4. Increase `num_predict` parameter or simplify the JSON schema\n"
            "5. The expert system fallback handles this gracefully"
        ),
        "severity": "high",
    },
    {
        "id": "llm_fallback",
        "pattern": r"falling back to expert system",
        "category": "LLM",
        "root_cause": "LangGraph Brain failed to synthesize — rule-based AnalystBrain used instead",
        "suggestion": (
            "1. This is expected fallback behavior, not a failure\n"
            "2. If too frequent (>50% of analyses), investigate LLM stability\n"
            "3. Check Ollama memory usage and model loading status\n"
            "4. Consider restarting Ollama if it's been running for days"
        ),
        "severity": "medium",
    },
    {
        "id": "ollama_connection",
        "pattern": r"(Connection refused.*ollama|Ollama.*unavailable|connect.*11434|Could not connect.*Ollama)",
        "category": "LLM",
        "root_cause": "Ollama server is not running or not reachable on port 11434",
        "suggestion": (
            "1. Start Ollama: `ollama serve`\n"
            "2. Verify it's listening: `curl http://localhost:11434/api/tags`\n"
            "3. Check if another process is using port 11434\n"
            "4. The app will use the expert system fallback until Ollama is restored"
        ),
        "severity": "critical",
    },
    {
        "id": "json_parse_error",
        "pattern": r"(JSONDecodeError|json\.loads.*error|Expecting.*delimiter|Expecting value)",
        "category": "LLM",
        "root_cause": "LLM output contained malformed JSON that the repair logic couldn't fix",
        "suggestion": (
            "1. Check _fix_unquoted_values() in langgraph_brain.py for edge cases\n"
            "2. Add more robust JSON repair patterns\n"
            "3. Log the raw malformed JSON for manual inspection\n"
            "4. Consider using a constrained generation mode if model supports it"
        ),
        "severity": "medium",
    },
    {
        "id": "yfinance_error",
        "pattern": r"(yfinance|Yahoo Finance).*(error|failed|exception|no data|No data found)",
        "category": "Data",
        "root_cause": "Yahoo Finance data download failed (rate limit, network, or invalid ticker)",
        "suggestion": (
            "1. Add retry logic with exponential backoff to data_collector.py\n"
            "2. Check if the ticker symbol is valid\n"
            "3. Yahoo Finance may be rate-limiting — add 0.5s delay between requests\n"
            "4. If persistent, check internet connectivity"
        ),
        "severity": "medium",
    },
    {
        "id": "database_error",
        "pattern": r"(sqlite3|database|OperationalError|IntegrityError).*(locked|error|failed)",
        "category": "Database",
        "root_cause": "SQLite database access issue (likely concurrent write contention)",
        "suggestion": (
            "1. Ensure only one writer at a time (add write locking)\n"
            "2. Increase SQLite busy_timeout: `conn.execute('PRAGMA busy_timeout = 5000')`\n"
            "3. Check disk space and file permissions on stock_data.db\n"
            "4. Consider WAL mode: `conn.execute('PRAGMA journal_mode=WAL')`"
        ),
        "severity": "high",
    },
    {
        "id": "memory_warning",
        "pattern": r"(MemoryError|out of memory|memory.*exhausted|killed.*OOM)",
        "category": "System",
        "root_cause": "Process ran out of available memory",
        "suggestion": (
            "1. Switch to a smaller LLM model (llama3.2:1b)\n"
            "2. Reduce batch scan size\n"
            "3. Check for memory leaks in long-running processes\n"
            "4. Add memory monitoring and restart policy"
        ),
        "severity": "critical",
    },
    {
        "id": "monitor_scan_error",
        "pattern": r"Monitor scan error for (\w+)",
        "category": "Monitor",
        "root_cause": "Watchlist monitor scan failed for a ticker",
        "suggestion": (
            "1. Check if the ticker data is available in the database\n"
            "2. Verify data_collector can fetch data for this symbol\n"
            "3. Check the full traceback in the log for the specific error\n"
            "4. The monitor will retry on the next scan cycle"
        ),
        "severity": "warning",
    },
    {
        "id": "data_refresh_failed",
        "pattern": r"(data refresh failed|update_stock_data.*failed|initial data fetch failed)",
        "category": "Data",
        "root_cause": "Could not refresh historical price data from yfinance",
        "suggestion": (
            "1. Check internet connectivity\n"
            "2. Verify yfinance is not being rate-limited\n"
            "3. The ticker may be delisted or have a naming change\n"
            "4. Check yfinance version: `pip install --upgrade yfinance`"
        ),
        "severity": "warning",
    },
    {
        "id": "unhandled_exception",
        "pattern": r"(Traceback|Unhandled exception|Internal Server Error|500)",
        "category": "Application",
        "root_cause": "Unhandled exception in the application code",
        "suggestion": (
            "1. Check the full traceback in the log for the specific error\n"
            "2. Add try/except handling around the failing code path\n"
            "3. Report the issue if it's reproducible"
        ),
        "severity": "high",
    },
]

# Severity ordering for sorting
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "warning": 3, "info": 4}
SEVERITY_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "warning": "⚠️", "info": "ℹ️"}


class LogAnalyzerAgent:
    """
    Analyzes application log files for errors and warnings,
    groups them by pattern, and writes a daily markdown report
    with root cause analysis and actionable suggestions.
    """

    def __init__(self, log_dir: str = None, report_dir: str = None):
        base = os.path.dirname(os.path.dirname(__file__))
        self.log_dir = log_dir or os.path.join(base, "logs")
        self.report_dir = report_dir or os.path.join(base, "logs", "reports")
        os.makedirs(self.report_dir, exist_ok=True)

    def _find_log_files(self, date: str) -> List[str]:
        """Find all log files for a given date (YYYY-MM-DD)."""
        files = []
        if not os.path.isdir(self.log_dir):
            return files
        for fname in os.listdir(self.log_dir):
            if fname.startswith("trade_app_") and date in fname and fname.endswith(".log"):
                files.append(os.path.join(self.log_dir, fname))
            # Also match rotated files like trade_app_2026-04-24.log.2026-04-28
            elif fname.endswith(f".{date}"):
                files.append(os.path.join(self.log_dir, fname))
        return sorted(files)

    def _read_lines(self, path: str) -> List[str]:
        """Read all lines from a log file."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.readlines()
        except Exception as e:
            logger.warning(f"LogAnalyzer: could not read {path}: {e}")
            return []

    def _parse_line(self, line: str) -> Optional[Dict]:
        """Parse a structured log line."""
        line = line.strip()
        if not line:
            return None
        m = re.match(
            r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - ([\w.]+) - (\w+) - (.+)$",
            line,
        )
        if m:
            return {
                "timestamp": m.group(1),
                "source": m.group(2),
                "level": m.group(3),
                "message": m.group(4),
                "raw": line,
            }
        return None

    def _extract_errors_warnings(self, lines: List[str]) -> Tuple[List[Dict], Dict]:
        """Extract ERROR and WARNING entries, plus overall stats."""
        entries = []
        stats = Counter()
        for line in lines:
            parsed = self._parse_line(line)
            if not parsed:
                continue
            stats[parsed["level"]] += 1
            if parsed["level"] in ("ERROR", "WARNING"):
                entries.append(parsed)
        return entries, dict(stats)

    def _match_patterns(self, entries: List[Dict]) -> List[Dict]:
        """Match error/warning entries against known signatures."""
        matched = defaultdict(lambda: {
            "count": 0,
            "first_seen": None,
            "last_seen": None,
            "samples": [],
            "affected_tickers": set(),
        })

        for entry in entries:
            text = f"{entry['source']} - {entry['level']} - {entry['message']}"
            for sig in ERROR_SIGNATURES:
                m = re.search(sig["pattern"], text, re.IGNORECASE)
                if m:
                    pid = sig["id"]
                    rec = matched[pid]
                    rec["count"] += 1
                    if rec["first_seen"] is None:
                        rec["first_seen"] = entry["timestamp"]
                    rec["last_seen"] = entry["timestamp"]
                    if len(rec["samples"]) < 3:
                        rec["samples"].append(entry["message"][:250])
                    # Extract ticker if captured in the regex
                    if m.lastindex and m.lastindex >= 1:
                        rec["affected_tickers"].add(m.group(1))
                    # Also try to extract ticker from message
                    ticker_m = re.search(r"\b([A-Z]{1,5})\b", entry["message"])
                    if ticker_m:
                        candidate = ticker_m.group(1)
                        if candidate not in ("ERROR", "WARNING", "INFO", "DEBUG",
                                             "API", "HTTP", "GET", "POST", "PUT",
                                             "SSL", "TCP", "DNS", "URL", "JSON",
                                             "LLM", "WAL", "OOM", "N", "A"):
                            rec["affected_tickers"].add(candidate)
                    break  # Only match first pattern per entry

        # Build results
        results = []
        for sig in ERROR_SIGNATURES:
            pid = sig["id"]
            if pid in matched:
                rec = matched[pid]
                results.append({
                    **sig,
                    "count": rec["count"],
                    "first_seen": rec["first_seen"],
                    "last_seen": rec["last_seen"],
                    "samples": rec["samples"],
                    "affected_tickers": sorted(rec["affected_tickers"]),
                })

        results.sort(key=lambda x: (SEVERITY_ORDER.get(x["severity"], 5), -x["count"]))
        return results

    def _find_unmatched(self, entries: List[Dict], matched_ids: set) -> List[Dict]:
        """Find errors/warnings that didn't match any known signature."""
        unmatched = []
        for entry in entries:
            text = f"{entry['source']} - {entry['level']} - {entry['message']}"
            is_matched = False
            for sig in ERROR_SIGNATURES:
                if re.search(sig["pattern"], text, re.IGNORECASE):
                    is_matched = True
                    break
            if not is_matched and entry["level"] == "ERROR":
                unmatched.append(entry)
        # Deduplicate by message similarity
        seen_prefixes = set()
        deduped = []
        for entry in unmatched:
            prefix = entry["message"][:80]
            if prefix not in seen_prefixes:
                seen_prefixes.add(prefix)
                deduped.append(entry)
        return deduped[:10]  # Cap at 10 unique unmatched errors

    def _compute_health_score(self, issues: List[Dict], total_lines: int) -> int:
        """Compute a 0-100 health score."""
        score = 100
        for issue in issues:
            sev = issue["severity"]
            count = issue["count"]
            if sev == "critical":
                score -= 30 * min(count, 3)
            elif sev == "high":
                score -= min(20, count * 4)
            elif sev == "medium":
                score -= min(10, count * 2)
            elif sev == "warning":
                score -= min(8, count)
        return max(0, score)

    def _hourly_distribution(self, entries: List[Dict]) -> Dict[str, int]:
        """Count errors/warnings per hour."""
        buckets = defaultdict(int)
        for entry in entries:
            hour = entry["timestamp"][:13]  # YYYY-MM-DD HH
            buckets[hour] += 1
        return dict(sorted(buckets.items()))

    def analyze_date(self, date: str = None) -> Dict:
        """
        Analyze logs for a specific date.

        Args:
            date: YYYY-MM-DD string. Defaults to yesterday.

        Returns:
            Full analysis dict with issues, stats, health score, etc.
        """
        if date is None:
            date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        log_files = self._find_log_files(date)
        if not log_files:
            logger.info(f"LogAnalyzer: no log files found for {date}")
            return {
                "date": date,
                "log_files": [],
                "total_lines": 0,
                "stats": {},
                "issues": [],
                "unmatched_errors": [],
                "health_score": 100,
                "hourly_distribution": {},
            }

        # Read all lines from all log files for this date
        all_lines = []
        for lf in log_files:
            all_lines.extend(self._read_lines(lf))

        entries, stats = self._extract_errors_warnings(all_lines)
        issues = self._match_patterns(entries)
        unmatched = self._find_unmatched(entries, {i["id"] for i in issues})
        total_lines = sum(stats.values())
        health = self._compute_health_score(issues, total_lines)
        hourly = self._hourly_distribution(entries)

        return {
            "date": date,
            "log_files": [os.path.basename(f) for f in log_files],
            "total_lines": total_lines,
            "stats": stats,
            "error_count": stats.get("ERROR", 0),
            "warning_count": stats.get("WARNING", 0),
            "issues": issues,
            "unmatched_errors": unmatched,
            "health_score": health,
            "hourly_distribution": hourly,
        }

    def generate_report(self, date: str = None) -> str:
        """
        Analyze logs and write a markdown report file.

        Args:
            date: YYYY-MM-DD. Defaults to yesterday.

        Returns:
            Path to the generated report file.
        """
        analysis = self.analyze_date(date)
        date_str = analysis["date"]
        report_path = os.path.join(self.report_dir, f"log_report_{date_str}.md")

        md = self._render_markdown(analysis)

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md)

        logger.info(
            f"LogAnalyzer: report written to {report_path} "
            f"(health={analysis['health_score']}, "
            f"issues={len(analysis['issues'])}, "
            f"errors={analysis.get('error_count', 0)}, "
            f"warnings={analysis.get('warning_count', 0)})"
        )
        return report_path

    def _render_markdown(self, analysis: Dict) -> str:
        """Render the analysis dict as a markdown report."""
        date = analysis["date"]
        health = analysis["health_score"]
        stats = analysis["stats"]
        issues = analysis["issues"]
        unmatched = analysis.get("unmatched_errors", [])
        hourly = analysis.get("hourly_distribution", {})

        # Health bar visual
        if health >= 80:
            health_icon = "🟢"
            health_label = "Healthy"
        elif health >= 50:
            health_icon = "🟡"
            health_label = "Degraded"
        elif health >= 20:
            health_icon = "🟠"
            health_label = "Unhealthy"
        else:
            health_icon = "🔴"
            health_label = "Critical"

        lines = []
        lines.append(f"# 📋 Log Analysis Report — {date}")
        lines.append("")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Log files:** {', '.join(analysis.get('log_files', ['none']))}")
        lines.append("")

        # ─── Health Score ─────────────────────────────────────────────
        lines.append("## Health Score")
        lines.append("")
        health_bar = "█" * (health // 5) + "░" * (20 - health // 5)
        lines.append(f"{health_icon} **{health}/100** — {health_label}")
        lines.append(f"```")
        lines.append(f"[{health_bar}] {health}%")
        lines.append(f"```")
        lines.append("")

        # ─── Summary ─────────────────────────────────────────────────
        lines.append("## Summary")
        lines.append("")
        lines.append(f"| Metric | Count |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Total log lines | {analysis.get('total_lines', 0):,} |")
        lines.append(f"| 🔴 Errors | {stats.get('ERROR', 0):,} |")
        lines.append(f"| ⚠️ Warnings | {stats.get('WARNING', 0):,} |")
        lines.append(f"| ℹ️ Info | {stats.get('INFO', 0):,} |")
        lines.append(f"| Identified issues | {len(issues)} |")
        lines.append(f"| Unmatched errors | {len(unmatched)} |")
        lines.append("")

        # ─── Hourly Distribution ──────────────────────────────────────
        if hourly:
            lines.append("## Error/Warning Distribution by Hour")
            lines.append("")
            max_count = max(hourly.values()) if hourly else 1
            for hour, count in hourly.items():
                bar_len = int((count / max_count) * 30)
                bar = "█" * bar_len
                time_label = hour.split(" ")[1] if " " in hour else hour
                lines.append(f"  {time_label}:00  {bar} {count}")
            lines.append("")

        # ─── Issues ──────────────────────────────────────────────────
        if issues:
            lines.append("## Identified Issues")
            lines.append("")

            for i, issue in enumerate(issues, 1):
                emoji = SEVERITY_EMOJI.get(issue["severity"], "❓")
                lines.append(f"### {i}. {emoji} {issue['category']}: {issue.get('title', issue['id'])}")
                lines.append("")
                lines.append(f"- **Severity:** {issue['severity'].upper()}")
                lines.append(f"- **Occurrences:** {issue['count']}")
                lines.append(f"- **First seen:** {issue.get('first_seen', 'N/A')}")
                lines.append(f"- **Last seen:** {issue.get('last_seen', 'N/A')}")
                if issue.get("affected_tickers"):
                    lines.append(f"- **Affected tickers:** {', '.join(issue['affected_tickers'][:10])}")
                lines.append("")

                lines.append("**Root Cause:**")
                lines.append(f"> {issue['root_cause']}")
                lines.append("")

                lines.append("**Suggested Fix:**")
                for fix_line in issue["suggestion"].split("\n"):
                    lines.append(f"  {fix_line.strip()}")
                lines.append("")

                if issue.get("samples"):
                    lines.append("<details>")
                    lines.append(f"<summary>Sample log entries ({min(len(issue['samples']), 3)})</summary>")
                    lines.append("")
                    lines.append("```")
                    for sample in issue["samples"][:3]:
                        lines.append(sample)
                    lines.append("```")
                    lines.append("</details>")
                    lines.append("")

                lines.append("---")
                lines.append("")

        # ─── Unmatched Errors ─────────────────────────────────────────
        if unmatched:
            lines.append("## Unmatched Errors (Unknown Patterns)")
            lines.append("")
            lines.append("These errors did not match any known signature and may need manual investigation:")
            lines.append("")
            for entry in unmatched:
                lines.append(f"- **[{entry['timestamp']}]** `{entry['source']}`: {entry['message'][:200]}")
            lines.append("")
            lines.append("> 💡 **Tip:** If these errors recur, add a new signature to `ERROR_SIGNATURES` in `log_analyzer.py`")
            lines.append("")

        # ─── Action Items ─────────────────────────────────────────────
        action_items = [i for i in issues if i["severity"] in ("critical", "high")]
        if action_items:
            lines.append("## 🚨 Priority Action Items")
            lines.append("")
            for i, item in enumerate(action_items, 1):
                emoji = SEVERITY_EMOJI.get(item["severity"], "❓")
                lines.append(f"{i}. {emoji} **{item.get('title', item['id'])}** "
                             f"({item['count']}x) — {item['root_cause']}")
            lines.append("")

        # ─── Footer ──────────────────────────────────────────────────
        lines.append("---")
        lines.append(f"*Report generated by LogAnalyzerAgent at "
                     f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        lines.append("")

        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    agent = LogAnalyzerAgent()

    # Accept optional date argument
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    else:
        target_date = None  # defaults to yesterday

    report_path = agent.generate_report(target_date)
    print(f"\n[OK] Report written to: {report_path}")

    # Also print a quick summary
    analysis = agent.analyze_date(target_date)
    print(f"   Health Score: {analysis['health_score']}/100")
    print(f"   Errors: {analysis.get('error_count', 0)}, Warnings: {analysis.get('warning_count', 0)}")
    print(f"   Issues found: {len(analysis['issues'])}")
