"""CanonDecision artifact — Wave-1.

Produced by CanonGate: evaluates a ShotList and emits a decision artifact.
Default decision is "allow". A shot whose text fields contain the literal
token "FORBIDDEN" triggers a "deny" decision.
"""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class _Producer(BaseModel):
    repo: str
    component: str


class CanonDecision(BaseModel):
    schema_id: str = "CanonDecision"
    schema_version: str = "0.0.1"
    producer: _Producer = Field(
        default_factory=lambda: _Producer(repo="world-engine", component="CanonGate")
    )
    timing_lock_hash: str
    decision: Literal["allow", "deny"] = "allow"
    reasons: List[str] = Field(default_factory=list)


_TEXT_FIELDS = ("action_beat", "environment_notes", "camera_framing", "camera_movement")
_AUDIO_TEXT_FIELDS = ("vo_text", "vo_speaker_id")


def _shot_texts(shot) -> List[str]:
    """Collect all human-readable string fields from a Shot."""
    texts: List[str] = []
    for field in _TEXT_FIELDS:
        val = getattr(shot, field, None)
        if isinstance(val, str):
            texts.append(val)
    if shot.audio_intent:
        for field in _AUDIO_TEXT_FIELDS:
            val = getattr(shot.audio_intent, field, None)
            if isinstance(val, str):
                texts.append(val)
    return texts


def evaluate_shotlist(shotlist) -> CanonDecision:
    """Evaluate *shotlist* and return a CanonDecision artifact.

    Rules (Wave-1):
    - Default decision: "allow"
    - If any shot text contains the literal token "FORBIDDEN", decision → "deny"
    """
    reasons: List[str] = []
    for shot in shotlist.shots:
        for text in _shot_texts(shot):
            if "FORBIDDEN" in text:
                reasons.append(
                    f"shot {shot.shot_id!r} contains FORBIDDEN token: {text!r}"
                )
    return CanonDecision(
        timing_lock_hash=shotlist.timing_lock_hash,
        decision="deny" if reasons else "allow",
        reasons=reasons,
    )
