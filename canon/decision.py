"""CanonDecision artifact — Wave-1 / Wave-2 / Wave-4.

Produced by CanonGate: evaluates a ShotList and emits a decision artifact.
Default decision is "allow". A shot whose text fields contain the literal
token "FORBIDDEN" triggers a "deny" decision (Wave-1). The double-underscore
form "__FORBIDDEN__" triggers "deny" with reasons == ["FORBIDDEN_TOKEN"] (Wave-4:
now loaded from third_party/contracts/compat/forbidden_tokens.json rather than a compiled regex).
"""
from __future__ import annotations

import pathlib as _pathlib
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

_POLICY_FILE = _pathlib.Path(__file__).parent.parent / "third_party" / "contracts" / "compat" / "forbidden_tokens.json"


#def _load_policy_tokens(path: _pathlib.Path) -> frozenset:
#    import json as _j
#    with path.open("r", encoding="utf-8") as f:
#        return frozenset(_j.load(f).get("forbidden_tokens", []))
def _load_policy_tokens(path: _pathlib.Path) -> frozenset[str]:
    import json as _j
    try:
        with path.open("r", encoding="utf-8") as f:
            data = _j.load(f)
    except FileNotFoundError as e:
        raise ValueError(f"ERROR: policy file missing: {path}") from e

    if isinstance(data, list):
        tokens = data
    elif isinstance(data, dict):
        tokens = data.get("forbidden_tokens", [])
    else:
        raise ValueError(f"ERROR: invalid policy format: {path}")

    # keep only strings, deterministic
    return frozenset(t for t in tokens if isinstance(t, str))

_POLICY_TOKENS: frozenset = _load_policy_tokens(_POLICY_FILE)

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


def _dead_char_ids(snapshot: dict) -> frozenset:
    """Return frozenset of character IDs whose alive fact is 'false' in *snapshot*."""
    dead: set = set()
    for entity in snapshot.get("entities", []):
        if entity.get("type") != "character":
            continue
        char_id = entity.get("id")
        if not char_id:
            continue
        for fact in entity.get("facts", []):
            if fact.get("k") == "alive" and fact.get("v") == "false":
                dead.add(char_id)
    return frozenset(dead)


def evaluate_shotlist(shotlist, snapshot=None) -> CanonDecision:
    """Evaluate *shotlist* and return a CanonDecision artifact.

    Rules (Wave-2 / Wave-5):
    - Default decision: "allow"
    - If any shot text contains the literal token "FORBIDDEN" (word-boundary),
      decision → "deny" with verbose reason strings (Wave-1 behaviour, unchanged).
    - If any shot text contains the token "__FORBIDDEN__" (double-underscore form),
      decision → "deny" with reasons == ["FORBIDDEN_TOKEN"] exactly (Wave-2).
      This path takes precedence; the double-underscore form is NOT matched by
      the word-boundary regex because '_' is a word character.
    - (Wave-5) If *snapshot* is provided and a shot contains "APPEARS:<char_id>"
      where <char_id> has alive=false in the snapshot, decision → "deny" with
      reasons == ["CANON_CONTRADICTION"].  CANON_CONTRADICTION takes highest
      precedence over all other deny reasons.
    """
    # --- Wave-3 contract guards ---
    tlh = getattr(shotlist, "timing_lock_hash", None)
    if not tlh:
        raise ValueError("ERROR: ShotList missing timing_lock_hash")
    sid = getattr(shotlist, "schema_id", None)
    sver = getattr(shotlist, "schema_version", None)
    if not sid or not sver:
        raise ValueError("ERROR: ShotList missing schema metadata")
    # --- Wave-5: validate snapshot and build dead-char set ---
    dead_chars: frozenset = frozenset()
    if snapshot is not None:
        if not isinstance(snapshot, dict) or "entities" not in snapshot:
            raise ValueError("ERROR: invalid CanonSnapshot input")
        dead_chars = _dead_char_ids(snapshot)
    # --- existing logic + Wave-5 contradiction check ---
    verbose_reasons: List[str] = []
    double_forbidden_found: bool = False
    canon_contradiction: bool = False
    for shot in shotlist.shots:
        texts = _shot_texts(shot)
        # Wave-5: APPEARS token against dead characters (highest priority deny)
        if dead_chars:
            for text in texts:
                for char_id in dead_chars:
                    if f"APPEARS:{char_id}" in text:
                        canon_contradiction = True
        for text in texts:
            if any(tok in text for tok in _POLICY_TOKENS):   # Wave-4: policy-file tokens
                double_forbidden_found = True
            elif _FORBIDDEN_RE.search(text):
                snippet = text[:_REASON_TEXT_MAX]
                verbose_reasons.append(
                    f"shot {shot.shot_id!r} contains FORBIDDEN token: {snippet!r}"
                )
    if canon_contradiction:
        reasons: List[str] = ["CANON_CONTRADICTION"]
    elif double_forbidden_found:
        reasons = ["FORBIDDEN_TOKEN"]
    else:
        reasons = verbose_reasons
    return CanonDecision(
        timing_lock_hash=shotlist.timing_lock_hash,
        decision="deny" if reasons else "allow",
        reasons=reasons,
    )


def assert_shotlist_canon(shotlist, snapshot=None) -> CanonDecision:
    """Like evaluate_shotlist but raises ValueError on deny.

    Raises:
        ValueError: "ERROR: CanonGate denied: <reason>" where <reason> is the
            first entry in decision.reasons (e.g. "CANON_CONTRADICTION").
    """
    decision = evaluate_shotlist(shotlist, snapshot=snapshot)
    if decision.decision == "deny":
        reason = decision.reasons[0] if decision.reasons else "DENIED"
        raise ValueError(f"ERROR: CanonGate denied: {reason}")
    return decision


def dump_decision(decision: CanonDecision) -> str:
    """Serialize a CanonDecision to canonical JSON (sort_keys=True, indent=2)."""
    import json as _json
    # raw = _json.loads(decision.model_dump_json())
    raw = decision.model_dump(mode="python")
    return _json.dumps(raw, sort_keys=True, indent=2, ensure_ascii=False)
