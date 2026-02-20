"""Timing estimation and timing_lock_hash computation.

All functions are pure: no I/O, no external state, no randomness.

The timing_lock_hash is the single timing authority for all downstream render
stages and HQ providers (§5.8, §22.2, §38.6).  Only shot_id and duration_sec
feed into the hash; creative fields (camera, audio, emotions) are intentionally
excluded so they can be revised without breaking the timing lock.
"""
from __future__ import annotations

import hashlib
import json
from typing import List, Optional

from world_engine.adaptation.models import Shot
from world_engine.adaptation.shot_templates import ShotTemplate

# Speech rate: ~150 wpm → 2.5 words/sec
_SPEECH_RATE_WPS: float = 2.5
# Buffer added after the last spoken word (reaction / cut time)
_DIALOGUE_BUFFER_SEC: float = 0.5


def estimate_shot_duration(
    template: ShotTemplate,
    text: Optional[str] = None,
) -> float:
    """Estimate shot duration in seconds.

    For DIALOGUE beats:
        duration = clamp(words / SPEECH_RATE + BUFFER, min, max)
    For all other beats:
        duration = template.base_duration_sec

    Returns a value rounded to 3 decimal places (float precision safety).
    """
    if text is not None:
        word_count = len(text.split())
        raw = word_count / _SPEECH_RATE_WPS + _DIALOGUE_BUFFER_SEC
        duration = max(template.duration_min_sec, min(raw, template.duration_max_sec))
    else:
        duration = template.base_duration_sec
    return round(duration, 3)


def compute_timing_lock_hash(shots: List[Shot]) -> str:
    """Compute a deterministic SHA-256 hash over shot timing data.

    Only shot_id and duration_sec (rounded to 3 dp) are included.
    Creative fields do not affect the hash.

    Canonical JSON guarantees (§38.6):
      - sort_keys=True → key order independent of insertion order
      - separators=(',', ':') → no whitespace → byte-identical across platforms

    Returns a lowercase 64-character hex string.
    """
    timing_data = [
        {
            "shot_id": shot.shot_id,
            "duration_sec": round(shot.duration_sec, 3),
        }
        for shot in shots
    ]
    canonical = json.dumps(timing_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
