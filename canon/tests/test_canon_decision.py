"""Unit tests for CanonDecision / evaluate_shotlist — Wave-1.

Covers:
  - Allow path: clean ShotList → "allow", empty reasons, hash propagation,
    schema_id, producer metadata, determinism.
  - Deny path: FORBIDDEN in action_beat, environment_notes, vo_text,
    reasons populated, single dirty shot among clean shots poisons the list,
    lowercase "forbidden" does NOT trigger deny (case-sensitive).
"""
from __future__ import annotations

import pytest

from world_engine.adaptation.models import AudioIntent, Shot, ShotList
from canon.decision import CanonDecision, evaluate_shotlist


# ─────────────────────────────────────────────────────────────────────────────
# Helper factory
# ─────────────────────────────────────────────────────────────────────────────

def _minimal_shotlist(shots=None) -> ShotList:
    """Return a minimal valid ShotList, optionally overriding the shots list."""
    if shots is None:
        shots = [
            Shot(
                shot_id="s001_shot_000",
                scene_id="s001",
                duration_sec=3.0,
                camera_framing="WIDE",
                camera_movement="STATIC",
                audio_intent=AudioIntent(),
            )
        ]
    return ShotList(
        shotlist_id="sl_test001",
        script_id="test_001",
        shots=shots,
        total_duration_sec=sum(s.duration_sec for s in shots),
        timing_lock_hash="b" * 64,
        created_at="2026-02-20T00:00:00Z",
    )


def _clean_shot(shot_id: str = "s001_shot_000") -> Shot:
    return Shot(
        shot_id=shot_id,
        scene_id="s001",
        duration_sec=2.0,
        camera_framing="WIDE",
        camera_movement="STATIC",
        audio_intent=AudioIntent(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Allow tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCanonDecisionAllow:

    def test_default_decision_is_allow(self):
        """A clean ShotList must produce decision='allow'."""
        sl = _minimal_shotlist()
        result = evaluate_shotlist(sl)
        assert result.decision == "allow"

    def test_reasons_empty_on_allow(self):
        """No FORBIDDEN tokens → reasons list must be empty."""
        sl = _minimal_shotlist()
        result = evaluate_shotlist(sl)
        assert result.reasons == []

    def test_timing_lock_hash_copied(self):
        """timing_lock_hash must be propagated verbatim from the ShotList."""
        sl = _minimal_shotlist()
        result = evaluate_shotlist(sl)
        assert result.timing_lock_hash == sl.timing_lock_hash

    def test_schema_id_is_canon_decision(self):
        """schema_id must equal 'CanonDecision'."""
        sl = _minimal_shotlist()
        result = evaluate_shotlist(sl)
        assert result.schema_id == "CanonDecision"

    def test_producer_is_canon_gate(self):
        """producer must identify the CanonGate component in world-engine."""
        sl = _minimal_shotlist()
        result = evaluate_shotlist(sl)
        assert result.producer.component == "CanonGate"
        assert result.producer.repo == "world-engine"

    def test_deterministic_same_input(self):
        """evaluate_shotlist must be deterministic: same input → same output."""
        sl = _minimal_shotlist()
        result_a = evaluate_shotlist(sl)
        result_b = evaluate_shotlist(sl)
        assert result_a == result_b


# ─────────────────────────────────────────────────────────────────────────────
# Deny tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCanonDecisionDeny:

    def test_forbidden_in_action_beat_triggers_deny(self):
        """FORBIDDEN in action_beat must flip decision to 'deny'."""
        shot = Shot(
            shot_id="s001_shot_001",
            scene_id="s001",
            duration_sec=2.0,
            action_beat="Character does FORBIDDEN action",
            camera_framing="CLOSE",
            camera_movement="STATIC",
            audio_intent=AudioIntent(),
        )
        sl = _minimal_shotlist(shots=[shot])
        result = evaluate_shotlist(sl)
        assert result.decision == "deny"

    def test_forbidden_in_environment_notes_triggers_deny(self):
        """FORBIDDEN in environment_notes must flip decision to 'deny'."""
        shot = Shot(
            shot_id="s001_shot_002",
            scene_id="s001",
            duration_sec=2.0,
            environment_notes="FORBIDDEN zone — do not render",
            camera_framing="WIDE",
            camera_movement="PAN",
            audio_intent=AudioIntent(),
        )
        sl = _minimal_shotlist(shots=[shot])
        result = evaluate_shotlist(sl)
        assert result.decision == "deny"

    def test_forbidden_in_vo_text_triggers_deny(self):
        """FORBIDDEN in audio_intent.vo_text must flip decision to 'deny'."""
        audio = AudioIntent(vo_text="FORBIDDEN content here")
        shot = Shot(
            shot_id="s001_shot_003",
            scene_id="s001",
            duration_sec=2.0,
            camera_framing="MEDIUM",
            camera_movement="STATIC",
            audio_intent=audio,
        )
        sl = _minimal_shotlist(shots=[shot])
        result = evaluate_shotlist(sl)
        assert result.decision == "deny"

    def test_reasons_populated_on_deny(self):
        """At least one reason string must be present and mention FORBIDDEN."""
        shot = Shot(
            shot_id="s001_shot_004",
            scene_id="s001",
            duration_sec=2.0,
            action_beat="FORBIDDEN move",
            camera_framing="WIDE",
            camera_movement="STATIC",
            audio_intent=AudioIntent(),
        )
        sl = _minimal_shotlist(shots=[shot])
        result = evaluate_shotlist(sl)
        assert len(result.reasons) >= 1
        assert any("FORBIDDEN" in r for r in result.reasons)

    def test_single_forbidden_shot_among_clean_shots(self):
        """One dirty shot among clean shots must poison the entire list → 'deny'."""
        clean_1 = _clean_shot("s001_shot_010")
        clean_2 = _clean_shot("s001_shot_011")
        dirty = Shot(
            shot_id="s001_shot_012",
            scene_id="s001",
            duration_sec=2.0,
            action_beat="Contains FORBIDDEN token",
            camera_framing="WIDE",
            camera_movement="STATIC",
            audio_intent=AudioIntent(),
        )
        clean_3 = _clean_shot("s001_shot_013")
        sl = _minimal_shotlist(shots=[clean_1, clean_2, dirty, clean_3])
        result = evaluate_shotlist(sl)
        assert result.decision == "deny"
        # Only the dirty shot contributes a reason
        assert len(result.reasons) == 1
        assert "s001_shot_012" in result.reasons[0]

    def test_lowercase_forbidden_does_not_trigger_deny(self):
        """The check is case-sensitive; 'forbidden' (lowercase) must not deny."""
        shot = Shot(
            shot_id="s001_shot_020",
            scene_id="s001",
            duration_sec=2.0,
            action_beat="this is a forbidden move (lowercase)",
            camera_framing="WIDE",
            camera_movement="STATIC",
            audio_intent=AudioIntent(),
        )
        sl = _minimal_shotlist(shots=[shot])
        result = evaluate_shotlist(sl)
        assert result.decision == "allow"
        assert result.reasons == []
