"""Wave-3 contract readiness and enforcement tests.

Covers:
  - TestShotListContractFields: field-level contract assertions per fixture
    (schema_id, schema_version, producer, timing_lock_hash pinned + self-consistent)
  - TestInvalidScriptInput: exact error message from load_script_strict
  - TestShotListByteDeterminism: dump_shotlist is byte-identical across two calls
"""
from __future__ import annotations

import hashlib
import pytest

from world_engine.adaptation.adapter import adapt_script
from world_engine.adaptation.timing import compute_timing_lock_hash
from world_engine.schemas.script_v1 import load_script_strict
from world_engine.schemas.shotlist_v1 import dump_shotlist
from world_engine.tests.adaptation.test_sha256_fixtures import (
    CREATED_AT,
    _fixture_c_script,
    _fixture_d_script,
    _fixture_e_script,
)
from world_engine.adaptation.models import DialogueLine, Scene, Script

# ---------------------------------------------------------------------------
# Fixture factories (A and B defined inline; C/D/E imported from Wave-2 suite)
# ---------------------------------------------------------------------------


def _fixture_a_script() -> Script:
    return Script(
        script_id="fixture_a",
        title="Fixture A",
        created_at=CREATED_AT,
        scenes=[Scene(scene_id="fa_s001", location="Empty Plain", time_of_day="DAY")],
    )


def _fixture_b_script() -> Script:
    return Script(
        script_id="fixture_b",
        title="Fixture B",
        created_at=CREATED_AT,
        scenes=[
            Scene(
                scene_id="fb_s001",
                location="Town Square",
                time_of_day="NOON",
                characters=["char_alice", "char_bob"],
                dialogue=[DialogueLine(speaker_id="char_alice", text="Hello.")],
            )
        ],
    )


# ---------------------------------------------------------------------------
# Pinned timing_lock_hash values — set by auto-repair loop.
# Replace PLACEHOLDER_X with actual hex strings after first pytest run.
# ---------------------------------------------------------------------------
_TLH_A = "95f20effe5e29136471761ce4998918596d5908858545ece2768d6dafbb7611b"
_TLH_B = "96a7655c4e9d2513dfd1a2df4bbc425dfafa9ba028d4a9b0d1b3830beaf7f6b7"
_TLH_C = "c24ebe04c5b0f7cd3e743ff986ff07ae4aa16cbb702e8d55fd707afff07fcee8"
_TLH_D = "6ea2dd6819c6fc7b5faa695618feb11b24a3ca9235f0fcfc0a7355066d11bd2d"
_TLH_E = "c6d6b906f90181d76869279fd6d92a2065c12ecfe5d22b64df1496d8e41b713c"


# ---------------------------------------------------------------------------
# TestShotListContractFields
# ---------------------------------------------------------------------------


class TestShotListContractFields:
    """Pin schema_id, schema_version, producer, and timing_lock_hash per fixture."""

    def _assert_contract(self, script: Script, expected_tlh: str) -> None:
        sl = adapt_script(script, created_at=CREATED_AT)
        assert sl.schema_id == "ShotList"
        assert sl.schema_version == "0.0.1"
        assert sl.producer == {"repo": "world-engine", "component": "ShotListAdapter"}
        assert len(sl.timing_lock_hash) == 64
        assert sl.timing_lock_hash == sl.timing_lock_hash.lower()  # hex format
        assert sl.timing_lock_hash == compute_timing_lock_hash(sl.shots)  # self-consistent
        assert sl.timing_lock_hash == expected_tlh  # pinned value

    def test_fixture_a_contract_fields(self):
        self._assert_contract(_fixture_a_script(), _TLH_A)

    def test_fixture_b_contract_fields(self):
        self._assert_contract(_fixture_b_script(), _TLH_B)

    def test_fixture_c_contract_fields(self):
        self._assert_contract(_fixture_c_script(), _TLH_C)

    def test_fixture_d_contract_fields(self):
        self._assert_contract(_fixture_d_script(), _TLH_D)

    def test_fixture_e_contract_fields(self):
        self._assert_contract(_fixture_e_script(), _TLH_E)


# ---------------------------------------------------------------------------
# TestInvalidScriptInput
# ---------------------------------------------------------------------------


class TestInvalidScriptInput:
    def test_empty_dict_raises(self):
        with pytest.raises(ValueError, match="ERROR: invalid Script input"):
            load_script_strict({})

    def test_missing_script_id_raises(self):
        with pytest.raises(ValueError, match="ERROR: invalid Script input"):
            load_script_strict(
                {"title": "X", "scenes": [], "created_at": "2026-01-01T00:00:00Z"}
            )

    def test_none_raises(self):
        with pytest.raises(ValueError, match="ERROR: invalid Script input"):
            load_script_strict(None)

    def test_invalid_json_string_raises(self):
        with pytest.raises(ValueError, match="ERROR: invalid Script input"):
            load_script_strict("not json{{{")


# ---------------------------------------------------------------------------
# TestShotListByteDeterminism
# ---------------------------------------------------------------------------


class TestShotListByteDeterminism:
    @pytest.mark.parametrize(
        "script_fn",
        [
            _fixture_a_script,
            _fixture_b_script,
            _fixture_c_script,
            _fixture_d_script,
            _fixture_e_script,
        ],
    )
    def test_byte_identical_across_two_calls(self, script_fn):
        s = script_fn()
        out1 = dump_shotlist(adapt_script(s, created_at=CREATED_AT))
        out2 = dump_shotlist(adapt_script(s, created_at=CREATED_AT))
        assert out1 == out2
