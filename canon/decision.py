"""CanonDecision artifact — Wave-1.

Produced by CanonGate: evaluates a ShotList and emits a decision artifact.
Default decision is "allow". A shot whose text fields contain the literal
token "FORBIDDEN" triggers a "deny" decision.
"""
from __future__ import annotations

import re
from typing import List, Literal

from pydantic import BaseModel, Field


class _Producer(BaseModel):
    repo: str
    component: str


class CanonDecision(BaseModel):
    schema_id: str = "CanonDecision"  # convention: PascalCase artifact class name
    schema_version: str = "0.0.1"
    producer: _Producer = Field(
        default_factory=lambda: _Producer(repo="world-engine", component="CanonGate")
    )
    timing_lock_hash: str
    decision: Literal["allow", "deny"] = "allow"
    reasons: List[str] = Field(default_factory=list)


_FORBIDDEN_RE = re.compile(r'\bFORBIDDEN\b')
_REASON_TEXT_MAX = 200  # chars; keeps artifact size bounded

_TEXT_FIELDS = (
    "action_beat", "environment_notes",
    "camera_framing", "camera_movement",
    "action_summary",                     # forward-compat: not in current Shot model
)
_CAMERA_FIELDS = ("framing_hint", "movement")   # nested shot.camera — forward-compat
_AUDIO_TEXT_FIELDS = ("vo_text", "vo_speaker_id")


def _shot_texts(shot) -> List[str]:
    """Collect all human-readable string fields from a Shot (defensively)."""
    texts: List[str] = []
    # flat text fields (current model + forward-compat additions)
    for field in _TEXT_FIELDS:
        val = getattr(shot, field, None)
        if isinstance(val, str):
            texts.append(val)
    # nested camera object — not in current Shot model; supported defensively
    camera = getattr(shot, "camera", None)
    if camera is not None:
        for field in _CAMERA_FIELDS:
            val = getattr(camera, field, None)
            if isinstance(val, str):
                texts.append(val)
    # audio intent — required on current Shot, but getattr guards duck-typed callers
    audio_intent = getattr(shot, "audio_intent", None)
    if audio_intent is not None:
        for field in _AUDIO_TEXT_FIELDS:
            val = getattr(audio_intent, field, None)
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
            if _FORBIDDEN_RE.search(text):
                snippet = text[:_REASON_TEXT_MAX]
                reasons.append(
                    f"shot {shot.shot_id!r} contains FORBIDDEN token: {snippet!r}"
                )
    return CanonDecision(
        timing_lock_hash=shotlist.timing_lock_hash,
        decision="deny" if reasons else "allow",
        reasons=reasons,
    )
