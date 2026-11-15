"""Run timestamps written into project files (when a receipt was made, a run started, a list was saved).

**Paused.** While ``RECORD`` is False, writers leave these fields out entirely. To resume, set ``RECORD = True``, or set
the environment variable ``HIDDEN_FLOODS_TIMESTAMPS=1`` for a single run.

Writers use ``stamp(key)`` inside a dict, e.g. ``{**stamp("started_utc"), "case": case_id}``. Readers must treat these
fields as optional. Times that are data (flood dates, NISAR passes, gauge readings) don't go through here.
"""

import os
from datetime import UTC, datetime

RECORD = False


def recording() -> bool:
    return RECORD or os.environ.get("HIDDEN_FLOODS_TIMESTAMPS") == "1"


def utc_now() -> str | None:
    """The current UTC time while recording, otherwise None."""
    return datetime.now(UTC).isoformat(timespec="seconds") if recording() else None


def stamp(key: str) -> dict:
    """``{key: current UTC time}`` while recording, ``{}`` while paused."""
    t = utc_now()
    return {key: t} if t else {}
