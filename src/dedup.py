"""Cross-run story deduplication.

Persists seen story IDs with timestamps to a JSON file so repeat
HN front-pagers don't appear in every digest.  Entries older than
``dedup_window_days`` are pruned on load so stories can resurface
after the window expires.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class SeenStoryTracker:
    """Persist and filter seen story IDs across pipeline runs.

    Storage format (JSON):
        {"<objectID>": "<ISO-8601 UTC timestamp>", ...}
    """

    def __init__(self, path: str | Path, dedup_window_days: int = 7) -> None:
        self._path = Path(path)
        self._window = timedelta(days=dedup_window_days)
        self._seen: dict[str, datetime] = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def filter_new(self, stories: list[dict]) -> list[dict]:
        """Return only stories whose objectID has not been seen before."""
        new = [s for s in stories if s.get("objectID") not in self._seen]
        skipped = len(stories) - len(new)
        if skipped:
            logger.info("Dedup: skipped %d already-seen stories, %d new", skipped, len(new))
        return new

    def mark_seen(self, stories: list[dict]) -> None:
        """Record story IDs as seen with the current UTC timestamp."""
        now = datetime.now(tz=timezone.utc)
        for story in stories:
            obj_id = story.get("objectID")
            if obj_id:
                self._seen[obj_id] = now
        self._save()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, datetime]:
        if not self._path.exists():
            return {}
        try:
            raw: dict[str, str] = json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read seen-stories file %s: %s", self._path, exc)
            return {}

        cutoff = datetime.now(tz=timezone.utc) - self._window
        seen: dict[str, datetime] = {}
        for obj_id, ts_str in raw.items():
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts >= cutoff:
                    seen[obj_id] = ts
            except ValueError:
                continue  # skip malformed entries

        pruned = len(raw) - len(seen)
        if pruned:
            logger.info("Dedup: pruned %d expired entries (window=%dd)", pruned, self._window.days)
        return seen

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {obj_id: ts.isoformat() for obj_id, ts in self._seen.items()}
        try:
            self._path.write_text(json.dumps(data, indent=2))
        except OSError as exc:
            logger.warning("Could not write seen-stories file %s: %s", self._path, exc)
