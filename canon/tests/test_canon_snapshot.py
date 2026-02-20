"""Unit tests for CanonSnapshot contradiction enforcement — Wave-5.

Covers:
  - No snapshot: existing allow behaviour is unchanged.
  - Consistent snapshot (alive character appears): allow.
  - Contradiction snapshot (dead character appears): deny + CANON_CONTRADICTION.
  - Byte-determinism: dump_decision output is byte-identical across two calls.
  - Invalid snapshot shapes: ValueError with canonical message.
"""
from __future__ import annotations

import pytest

from world_engine.adaptation.models import AudioIntent, Shot, ShotList
from canon.decision import dump_decision, evaluate_shotlist


# ─────────────────────────────────────────────────────────────────────────────
# Snapshot fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _snapshot_dead_lena() -> dict:
    """CanonSnapshot: char_lena is dead (alive=false)."""
    return {
        "entities": [
            {
                "id": "char_lena",
                "type": "character",
                "facts": [
                    {"k": "alive", "v": "false"}
                ],
            }
        ]
    }


def _snapshot_alive_lena() -> dict:
    """CanonSnapshot: char_lena is alive (alive=true)."""
    return {
        "entities": [
            {
                "id": "char_lena",
                "type": "character",
                "facts": [
                    {"k": "alive", "v": "true"}
                ],
            }
        ]
    }


# ─────────────────────────────────────────────────────────────────────────────
# ShotList fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _appears_shotlist(char_id: str = "char_lena") -> ShotList:
    """ShotList with a shot whose action_beat contains APPEARS:<char_id>."""
    shot = Shot(
        shot_id="s001_shot_001",
        scene_id="s001",
        duration_sec=2.0,
        action_beat=f"APPEARS:{char_id} walks into the room",
        camera_framing="WIDE",
        camera_movement="STATIC",
        audio_intent=AudioIntent(),
    )
    return ShotList(
        shotlist_id="sl_snap_appears",
        script_id="snap_appears",
        shots=[shot],
        total_duration_sec=2.0,
        timing_lock_hash="e" * 64,
        created_at="2026-02-20T00:00:00Z",
    )


def _clean_shotlist() -> ShotList:
    """ShotList with no APPEARS token in any field."""
    shot = Shot(
        shot_id="s001_shot_002",
        scene_id="s001",
        duration_sec=3.0,
        action_beat="The sun rises over the hill",
        camera_framing="WIDE",
        camera_movement="STATIC",
        audio_intent=AudioIntent(),
    )
    return ShotList(
        shotlist_id="sl_snap_clean",
        script_id="snap_clean",
        shots=[shot],
        total_duration_sec=3.0,
        timing_lock_hash="f" * 64,
        created_at="2026-02-20T00:00:00Z",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestNoSnapshot:

    def test_no_snapshot_allow(self):
        """evaluate_shotlist without snapshot arg must still return 'allow' for clean list."""
        sl = _clean_shotlist()
        result = evaluate_shotlist(sl)
        assert result.decision == "allow"
        assert result.reasons == []


class TestConsistentSnapshot:

    def test_consistent_allow(self):
        """Alive character appearing in a shot must NOT trigger a contradiction → allow."""
        sl = _appears_shotlist("char_lena")
        snap = _snapshot_alive_lena()
        result = evaluate_shotlist(sl, snapshot=snap)
        assert result.decision == "allow"


class TestContradictionSnapshot:

    def test_contradiction_deny(self):
        """Dead character appearing in a shot must trigger deny + CANON_CONTRADICTION."""
        sl = _appears_shotlist("char_lena")
        snap = _snapshot_dead_lena()
        result = evaluate_shotlist(sl, snapshot=snap)
        assert result.decision == "deny"
        assert result.reasons == ["CANON_CONTRADICTION"]

    def test_byte_determinism(self):
        """Two calls with identical inputs must produce byte-identical dump_decision output."""
        sl = _appears_shotlist("char_lena")
        snap = _snapshot_dead_lena()
        out1 = dump_decision(evaluate_shotlist(sl, snapshot=snap))
        out2 = dump_decision(evaluate_shotlist(sl, snapshot=snap))
        assert out1 == out2


class TestInvalidSnapshot:

    def test_invalid_snapshot_raises(self):
        """Passing a non-dict snapshot must raise ValueError with canonical message."""
        sl = _clean_shotlist()
        with pytest.raises(ValueError, match="ERROR: invalid CanonSnapshot input"):
            evaluate_shotlist(sl, snapshot="not-a-dict")

    def test_missing_entities_raises(self):
        """Passing a dict without 'entities' key must raise ValueError."""
        sl = _clean_shotlist()
        with pytest.raises(ValueError, match="ERROR: invalid CanonSnapshot input"):
            evaluate_shotlist(sl, snapshot={"characters": []})


class TestAssertShotlistCanon:

    def test_contradiction_overrides_forbidden(self):
        # snapshot where alex is dead
        snapshot = {
            "entities": [
                {"id": "alex", "type": "character", "facts": [{"k": "alive", "v": "false"}]},
            ]
        }
    
        # ShotList whose text contains BOTH:
        #  - APPEARS:alex  (contradiction because alex is dead)
        #  - __FORBIDDEN__ (policy token)
        #
        # Use whatever field your Shot model exposes as a text field; action_beat is typical.
        shot = Shot(
            shot_id="s001_shot_999",
            scene_id="s001",
            duration_sec=2.0,
            action_beat="APPEARS:alex __FORBIDDEN__",
            camera_framing="WIDE",
            camera_movement="STATIC",
            audio_intent=AudioIntent(),
        )
        sl = ShotList(
            shotlist_id="sl_test_precedence",
            script_id="test_001",
            shots=[shot],
            total_duration_sec=2.0,
            timing_lock_hash="e" * 64,
            schema_id="ShotList",
            schema_version="0.0.1",
            created_at="2026-02-20T00:00:00Z",
        )
    
        decision = evaluate_shotlist(sl, snapshot=snapshot)
    
        assert decision.decision == "deny"
        # Precedence requirement: CANON_CONTRADICTION must override forbidden reasons
        assert decision.reasons == ["CANON_CONTRADICTION"]
    
    def test_contradiction_raises(self):
        """assert_shotlist_canon must raise ValueError with the canonical message."""
        from canon.decision import assert_shotlist_canon
        sl = _appears_shotlist("char_lena")
        snap = _snapshot_dead_lena()
        with pytest.raises(ValueError, match="ERROR: CanonGate denied: CANON_CONTRADICTION"):
            assert_shotlist_canon(sl, snapshot=snap)
