"""Per-schedule digest profiles.

Named profiles are discovered from environment variables:

    SCHEDULE_MORNING=08:00
    SCHEDULE_MORNING_KEYWORDS=LLM,AI agents,Claude
    SCHEDULE_MORNING_STYLE=concise morning briefing for a technical lead

    SCHEDULE_EVENING=17:00
    SCHEDULE_EVENING_KEYWORDS=kubernetes,GKE,open source AI
    SCHEDULE_EVENING_STYLE=end-of-day roundup focusing on infrastructure

If no named profiles are defined the current ``SCHEDULE_TIMES`` /
``KEYWORDS`` settings are used to create a default profile per time.
"""

import os
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config import Settings

_HH_MM = re.compile(r"^\d{1,2}:\d{2}$")
_PROFILE_KEY = re.compile(r"^SCHEDULE_([A-Z][A-Z0-9_]*)$")
_IGNORED = {"SCHEDULE_TIMES"}


@dataclass
class DigestProfile:
    """Configuration for a single scheduled (or manual) digest run."""

    name: str
    time: str                      # HH:MM — used by the scheduler
    keywords: list[str] = field(default_factory=list)
    style: str = ""                # injected into the LLM prompt


def discover_profiles(config: "Settings") -> list[DigestProfile]:
    """Return named profiles from the environment, or a default profile list.

    Named profiles are env vars of the form ``SCHEDULE_<NAME>=HH:MM``.
    Each profile may have optional modifiers::

        SCHEDULE_<NAME>_KEYWORDS=<csv>
        SCHEDULE_<NAME>_STYLE=<free text>

    If no named profiles are found, one profile per ``SCHEDULE_TIMES`` entry
    is returned using the global ``KEYWORDS`` setting.
    """
    profiles: list[DigestProfile] = []

    for key, val in os.environ.items():
        if key in _IGNORED:
            continue
        m = _PROFILE_KEY.match(key)
        if not m or not _HH_MM.match(val.strip()):
            continue

        name = m.group(1).lower()
        upper = m.group(1).upper()

        keywords_str = os.environ.get(f"SCHEDULE_{upper}_KEYWORDS", config.keywords)
        style = os.environ.get(f"SCHEDULE_{upper}_STYLE", "")
        keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]

        profiles.append(DigestProfile(name=name, time=val.strip(), keywords=keywords, style=style))

    if profiles:
        return sorted(profiles, key=lambda p: p.time)

    # Fallback: one default profile per schedule time
    return [
        DigestProfile(name="default", time=t, keywords=config.keyword_list)
        for t in config.schedule_time_list
    ]


def get_profile(config: "Settings", name: str) -> DigestProfile | None:
    """Look up a named profile, or return None if not found."""
    for profile in discover_profiles(config):
        if profile.name == name.lower():
            return profile
    return None
