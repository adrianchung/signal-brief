"""Run logging and history persistence.

Each pipeline run appends a JSON record to a .jsonl file.  Old records
are pruned on write based on the configured retention period.

Record schema
─────────────
{
    "timestamp":          str   ISO-8601 UTC
    "provider":           str   "gemini" | "claude"
    "dry_run":            bool
    "stories_fetched":    int
    "stories_after_dedup": int
    "brief":              str   generated digest text (or error message)
    "delivery":           dict  channel → "ok" | "skipped" | "failed: <msg>"
    "status":             str   "ok" | "no_stories" | "fetch_error" |
                                "analysis_error" | "delivery_error"
}
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_WIDTH = 72


class RunLogger:
    """Persist and display pipeline run history."""

    def __init__(self, path: str | Path, retention_days: int = 30) -> None:
        self._path = Path(path)
        self._retention = timedelta(days=retention_days)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write(self, record: dict) -> None:
        """Append *record* to the log file and prune expired entries."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._path.open("a") as fh:
                fh.write(json.dumps(record) + "\n")
        except OSError as exc:
            logger.warning("Could not write run history to %s: %s", self._path, exc)
            return
        self._prune()

    # ------------------------------------------------------------------
    # Read / display
    # ------------------------------------------------------------------

    def get_history(self, n: int = 10) -> list[dict]:
        """Return the *n* most recent run records."""
        records = self._load_all()
        return records[-n:] if len(records) > n else records

    def print_history(self, n: int = 10) -> None:
        """Print a formatted table of the *n* most recent runs."""
        records = self.get_history(n)
        if not records:
            print("No run history found.")
            return

        print("\n" + "─" * _WIDTH)
        print(f" SIGNAL BRIEF HISTORY (last {len(records)} runs)")
        print("─" * _WIDTH)
        header = f"{'#':<4} {'TIMESTAMP':<22} {'PROV':<8} {'STATUS':<18} {'STORIES':>7}  DELIVERY"
        print(header)
        print("─" * _WIDTH)

        for i, rec in enumerate(reversed(records), start=1):
            ts = _fmt_ts(rec.get("timestamp", ""))
            provider = rec.get("provider", "?")[:7]
            status = rec.get("status", "?")[:17]
            fetched = rec.get("stories_fetched", 0)
            after = rec.get("stories_after_dedup", 0)
            stories_col = f"{fetched}→{after}"

            delivery = rec.get("delivery", {})
            if delivery:
                delivery_col = " ".join(
                    f"{_short_name(ch)}:{v}" for ch, v in delivery.items()
                )
            elif rec.get("dry_run"):
                delivery_col = "dry-run"
            else:
                delivery_col = "-"

            print(f"{i:<4} {ts:<22} {provider:<8} {status:<18} {stories_col:>7}  {delivery_col}")

        print("─" * _WIDTH + "\n")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_all(self) -> list[dict]:
        if not self._path.exists():
            return []
        records: list[dict] = []
        try:
            for line in self._path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError as exc:
            logger.warning("Could not read run history from %s: %s", self._path, exc)
        return records

    def _prune(self) -> None:
        records = self._load_all()
        if not records:
            return
        cutoff = datetime.now(tz=timezone.utc) - self._retention
        kept = []
        for rec in records:
            try:
                ts = datetime.fromisoformat(rec.get("timestamp", ""))
                if ts >= cutoff:
                    kept.append(rec)
            except (ValueError, TypeError):
                kept.append(rec)  # keep records with unparseable timestamps

        pruned = len(records) - len(kept)
        if pruned:
            logger.info("History: pruned %d expired records (retention=%dd)", pruned, self._retention.days)
            try:
                self._path.write_text("".join(json.dumps(r) + "\n" for r in kept))
            except OSError as exc:
                logger.warning("Could not prune run history: %s", exc)


def _fmt_ts(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError):
        return iso[:22]


def _short_name(channel: str) -> str:
    """SlackDeliverer → slack, NtfyDeliverer → ntfy, etc."""
    return channel.lower().replace("deliverer", "")
