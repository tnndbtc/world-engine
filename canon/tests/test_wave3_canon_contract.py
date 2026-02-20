"""Wave-3 CanonDecision contract enforcement tests — Agent D.

Three test classes:
  TestCanonDecisionContractFields   — field-level assertions for allow + deny
  TestGateMissingInputs             — 5 tests: missing/empty tlh, missing schema fields
  TestCanonDecisionByteDeterminism  — dump_decision byte-identical across 2 calls
"""
from __future__ import annotations

import types

import pytest

from world_engine.adaptation.models import AudioIntent, Shot, ShotList
from canon.decision import CanonDecision, dump_decision, evaluate_shotlist


# ─────────────────────────────────────────────────────────────────────────────
# Fixture helpers
# ─────────────────────────────────────────────────────────────────────────────

TIMING_HASH_ALLOW = "a" * 64
TIMING_HASH_DENY  = "b" * 64


def _allow_shotlist() -> ShotList:
    return ShotList(
        shotlist_id="sl_w3d_allow", script_id="w3d_allow",
        shots=[Shot(shot_id="allow_s001_shot_001", scene_id="allow_s001",
                    duration_sec=3.0, camera_framing="WIDE", camera_movement="STATIC",
                    audio_intent=AudioIntent())],
        total_duration_sec=3.0, timing_lock_hash=TIMING_HASH_ALLOW,
        created_at="1970-01-01T00:00:00Z",
    )


def _deny_shotlist() -> ShotList:
    return ShotList(
        shotlist_id="sl_w3d_deny", script_id="w3d_deny",
        shots=[Shot(shot_id="deny_s001_shot_001", scene_id="deny_s001",
                    duration_sec=2.5, camera_framing="WIDE", camera_movement="PAN_LEFT",
                    action_beat="Mage performs __FORBIDDEN__ ritual",
                    audio_intent=AudioIntent())],
        total_duration_sec=2.5, timing_lock_hash=TIMING_HASH_DENY,
        created_at="1970-01-01T00:00:00Z",
    )


# ─────────────────────────────────────────────────────────────────────────────
# TestCanonDecisionContractFields
# ─────────────────────────────────────────────────────────────────────────────

class TestCanonDecisionContractFields:
    """Field-level assertions for allow and deny CanonDecision outputs."""

    def _assert_base_fields(self, cd: CanonDecision, expected_tlh: str):
        assert cd.schema_id == "CanonDecision"
        assert cd.schema_version == "0.0.1"
        assert cd.producer.repo == "world-engine"
        assert cd.producer.component == "CanonGate"
        assert cd.timing_lock_hash == expected_tlh

    def test_allow_case_exact_content(self):
        sl = _allow_shotlist()
        cd = evaluate_shotlist(sl)
        self._assert_base_fields(cd, TIMING_HASH_ALLOW)
        assert cd.decision == "allow"
        assert cd.reasons == []

    def test_deny_case_exact_content(self):
        sl = _deny_shotlist()
        cd = evaluate_shotlist(sl)
        self._assert_base_fields(cd, TIMING_HASH_DENY)
        assert cd.decision == "deny"
        assert cd.reasons == ["FORBIDDEN_TOKEN"]


# ─────────────────────────────────────────────────────────────────────────────
# TestGateMissingInputs
# ─────────────────────────────────────────────────────────────────────────────

class TestGateMissingInputs:
    """Five deterministic failure-mode tests for missing/invalid gate inputs."""

    def test_none_timing_lock_hash_raises(self):
        sl = types.SimpleNamespace(schema_id="ShotList", schema_version="0.0.1",
                                   timing_lock_hash=None, shots=[])
        with pytest.raises(ValueError, match="ERROR: ShotList missing timing_lock_hash"):
            evaluate_shotlist(sl)

    def test_empty_timing_lock_hash_raises(self):
        sl = types.SimpleNamespace(schema_id="ShotList", schema_version="0.0.1",
                                   timing_lock_hash="", shots=[])
        with pytest.raises(ValueError, match="ERROR: ShotList missing timing_lock_hash"):
            evaluate_shotlist(sl)

    def test_missing_schema_id_raises(self):
        sl = types.SimpleNamespace(schema_id=None, schema_version="0.0.1",
                                   timing_lock_hash="a" * 64, shots=[])
        with pytest.raises(ValueError, match="ERROR: ShotList missing schema metadata"):
            evaluate_shotlist(sl)

    def test_missing_schema_version_raises(self):
        sl = types.SimpleNamespace(schema_id="ShotList", schema_version=None,
                                   timing_lock_hash="a" * 64, shots=[])
        with pytest.raises(ValueError, match="ERROR: ShotList missing schema metadata"):
            evaluate_shotlist(sl)

    def test_no_schema_attrs_raises(self):
        sl = types.SimpleNamespace(timing_lock_hash="a" * 64, shots=[])
        with pytest.raises(ValueError, match="ERROR: ShotList missing schema metadata"):
            evaluate_shotlist(sl)


# ─────────────────────────────────────────────────────────────────────────────
# TestCanonDecisionByteDeterminism
# ─────────────────────────────────────────────────────────────────────────────

class TestCanonDecisionByteDeterminism:
    """dump_decision output must be byte-identical across two calls."""

    @pytest.mark.parametrize("sl_fn", [_allow_shotlist, _deny_shotlist])
    def test_byte_identical_across_two_calls(self, sl_fn):
        sl = sl_fn()
        out1 = dump_decision(evaluate_shotlist(sl))
        out2 = dump_decision(evaluate_shotlist(sl))
        assert out1 == out2
