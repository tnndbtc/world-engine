"""Unit tests for CanonDecision / evaluate_shotlist — Wave-1.

Covers:
  - Allow path: clean ShotList → "allow", empty reasons, hash propagation,
    schema_id, producer metadata, determinism.
  - Deny path: FORBIDDEN in action_beat, environment_notes, vo_text,
    reasons populated, single dirty shot among clean shots poisons the list,
    lowercase "forbidden" does NOT trigger deny (case-sensitive).
"""
from __future__ import annotations

import hashlib
import json
import types

import pytest

from world_engine.adaptation.models import AudioIntent, Shot, ShotList
from canon.decision import CanonDecision, dump_decision, evaluate_shotlist


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


# ─────────────────────────────────────────────────────────────────────────────
# Token-boundary and edge-case tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCanonDecisionTokenBoundary:
    """Token-boundary and edge-case tests for evaluate_shotlist."""

    def test_not_forbidden_does_not_trigger_deny(self):
        """'NOT_FORBIDDEN' must NOT trigger deny (word-boundary check)."""
        shot = Shot(
            shot_id="s001_shot_050",
            scene_id="s001",
            duration_sec=2.0,
            action_beat="this is NOT_FORBIDDEN content",
            camera_framing="WIDE",
            camera_movement="STATIC",
            audio_intent=AudioIntent(),
        )
        sl = _minimal_shotlist(shots=[shot])
        result = evaluate_shotlist(sl)
        assert result.decision == "allow"
        assert result.reasons == []

    def test_nested_camera_forbidden_triggers_deny(self):
        """FORBIDDEN in a nested shot.camera.framing_hint must trigger deny."""
        # duck-typed shot — mimics a future Shot variant with nested camera
        camera = types.SimpleNamespace(framing_hint="FORBIDDEN angle", movement="STATIC")
        audio = types.SimpleNamespace(vo_text=None, vo_speaker_id=None)
        shot = types.SimpleNamespace(
            shot_id="s001_shot_051",
            audio_intent=audio,
            camera=camera,
            # no flat text fields
        )
        # wrap in a minimal duck-typed ShotList
        sl = types.SimpleNamespace(
            shots=[shot],
            timing_lock_hash="c" * 64,
        )
        result = evaluate_shotlist(sl)
        assert result.decision == "deny"
        assert any("FORBIDDEN" in r for r in result.reasons)

    def test_missing_audio_intent_does_not_crash(self):
        """A duck-typed shot with no audio_intent attribute must not raise."""
        shot = types.SimpleNamespace(
            shot_id="s001_shot_052",
            action_beat="normal content",
            # no audio_intent attribute at all
        )
        sl = types.SimpleNamespace(
            shots=[shot],
            timing_lock_hash="d" * 64,
        )
        result = evaluate_shotlist(sl)
        assert result.decision == "allow"


# ─────────────────────────────────────────────────────────────────────────────
# Wave-2 determinism helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _allow_shotlist_wave2() -> ShotList:
    """Clean ShotList — no FORBIDDEN tokens of any form."""
    return ShotList(
        shotlist_id="sl_wave2d_allow",
        script_id="wave2_d_allow",
        shots=[
            Shot(
                shot_id="allow_s001_shot_001",
                scene_id="allow_s001",
                duration_sec=3.0,
                camera_framing="WIDE",
                camera_movement="STATIC",
                audio_intent=AudioIntent(),
            )
        ],
        total_duration_sec=3.0,
        timing_lock_hash="a" * 64,
        created_at="1970-01-01T00:00:00Z",
    )


def _deny_shotlist_wave2() -> ShotList:
    """ShotList with __FORBIDDEN__ token in action_beat → deny + FORBIDDEN_TOKEN reason."""
    return ShotList(
        shotlist_id="sl_wave2d_deny",
        script_id="wave2_d_deny",
        shots=[
            Shot(
                shot_id="deny_s001_shot_001",
                scene_id="deny_s001",
                duration_sec=2.5,
                camera_framing="WIDE",
                camera_movement="PAN_LEFT",
                action_beat="Mage performs __FORBIDDEN__ ritual",
                audio_intent=AudioIntent(),
            )
        ],
        total_duration_sec=2.5,
        timing_lock_hash="b" * 64,
        created_at="1970-01-01T00:00:00Z",
    )


# Wave-2 pinned hashes — computed via auto-repair loop on 2026-02-20
_HASH_ALLOW_W2 = "2e02c0bfd3220a28115b06f3ef14de8e69c3933edc6df7e009e0a7c0141c8a8f"
_HASH_DENY_W2 = "71037b8009a8f462ea4500ebc19d4cd3ecdb7780932bf7be837574697c02734c"


class TestWave2CanonDecisionGoldenFixtures:
    """Byte-identity + SHA-256 regression for Wave-2 CanonDecision golden fixtures."""

    def test_allow_byte_identity_and_hash(self):
        """Allow fixture: two runs produce byte-identical JSON; decision/reasons exact."""
        sl = _allow_shotlist_wave2()
        json_out_1 = dump_decision(evaluate_shotlist(sl))
        json_out_2 = dump_decision(evaluate_shotlist(sl))
        assert json_out_1 == json_out_2, "byte-identity failed for allow fixture"
        decision = evaluate_shotlist(sl)
        assert decision.decision == "allow"
        assert decision.reasons == []
        assert _sha256(json_out_1) == _HASH_ALLOW_W2

    def test_deny_byte_identity_and_hash(self):
        """Deny fixture: __FORBIDDEN__ → decision='deny', reasons==['FORBIDDEN_TOKEN'], byte-identical."""
        sl = _deny_shotlist_wave2()
        json_out_1 = dump_decision(evaluate_shotlist(sl))
        json_out_2 = dump_decision(evaluate_shotlist(sl))
        assert json_out_1 == json_out_2, "byte-identity failed for deny fixture"
        decision = evaluate_shotlist(sl)
        assert decision.decision == "deny"
        assert decision.reasons == ["FORBIDDEN_TOKEN"]
        assert _sha256(json_out_1) == _HASH_DENY_W2
