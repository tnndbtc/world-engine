"""SHA-256 fixture tests — pin the canonical JSON output of two minimal scripts.

These tests guard the byte-identity guarantee: identical script input MUST
always produce byte-identical ShotList JSON regardless of code changes that
do not touch timing or shot structure.

Fixture A — minimal: 1 scene, no dialogue/actions (establishing + cutaway).
Fixture B — dialogue: 1 scene, 2 characters, 1 dialogue line (establishing +
            dialogue + reaction).
"""
from __future__ import annotations

import hashlib

from world_engine.adaptation.adapter import adapt_script
from world_engine.adaptation.models import DialogueLine, Scene, SceneAction, Script
from world_engine.schemas.shotlist_v1 import dump_shotlist

# Fixed timestamp — the adapter must never read the system clock, so we pin to
# the epoch constant defined in adapter.py.
CREATED_AT = "1970-01-01T00:00:00Z"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TestSHA256Fixtures:
    """Byte-identity regression suite.

    If either assertion fails, it means the serialized JSON changed for
    inputs that contain no timing-relevant differences.  Either the change is
    intentional (update the pinned hash with a comment explaining why) or it
    is an unintended regression (revert).
    """

    def test_fixture_a_sha256(self):
        """Fixture A: 1 scene, no dialogue/actions → establishing + cutaway."""
        script = Script(
            script_id="fixture_a",
            title="Fixture A",
            created_at=CREATED_AT,
            scenes=[
                Scene(
                    scene_id="fa_s001",
                    location="Empty Plain",
                    time_of_day="DAY",
                )
            ],
        )
        json_out = dump_shotlist(adapt_script(script, created_at=CREATED_AT))
        assert _sha256(json_out) == "a2682feb45b4708d37c0dd22adea286c21edc539161d4b792faac16a427468a1"

    def test_fixture_b_sha256(self):
        """Fixture B: 1 scene, 2 characters, 1 dialogue → establishing + dialogue + reaction."""
        script = Script(
            script_id="fixture_b",
            title="Fixture B",
            created_at=CREATED_AT,
            scenes=[
                Scene(
                    scene_id="fb_s001",
                    location="Town Square",
                    time_of_day="NOON",
                    characters=["char_alice", "char_bob"],
                    dialogue=[
                        DialogueLine(
                            speaker_id="char_alice",
                            text="Hello.",
                        )
                    ],
                )
            ],
        )
        json_out = dump_shotlist(adapt_script(script, created_at=CREATED_AT))
        assert _sha256(json_out) == "021c62ecd6d72c3c4651d17c48ccc7cefe0053b399dffca0dfec0dd6ae24050b"


# ---------------------------------------------------------------------------
# Wave-2 script factories
# ---------------------------------------------------------------------------


def _fixture_c_script() -> Script:
    """Minimal: 1 scene, 1 character ref, no dialogue, no actions → establishing + cutaway."""
    return Script(
        script_id="wave2_fixture_c",
        title="Wave-2 Fixture C",
        created_at=CREATED_AT,
        scenes=[
            Scene(
                scene_id="fc_s001",
                location="Hilltop",
                time_of_day="DUSK",
                characters=["char_scout"],
            )
        ],
    )


def _fixture_d_script() -> Script:
    """Multi-scene: 3 scenes → 9 shots total."""
    return Script(
        script_id="wave2_fixture_d",
        title="Wave-2 Fixture D",
        created_at=CREATED_AT,
        scenes=[
            Scene(
                scene_id="fd_s001",
                location="Market Square",
                time_of_day="MORNING",
                characters=["char_vendor"],
                actions=[SceneAction(description="Vendor sets up stall")],
            ),
            Scene(
                scene_id="fd_s002",
                location="Throne Room",
                time_of_day="NOON",
                characters=["char_king", "char_knight"],
                dialogue=[
                    DialogueLine(speaker_id="char_king", text="Bring me the report."),
                    DialogueLine(speaker_id="char_knight", text="At once, your majesty."),
                ],
            ),
            Scene(
                scene_id="fd_s003",
                location="Castle Courtyard",
                time_of_day="EVENING",
                characters=["char_guard"],
            ),
        ],
    )


def _fixture_e_script() -> Script:
    """FORBIDDEN text: 1 scene, 1 action whose description contains __FORBIDDEN__."""
    return Script(
        script_id="wave2_fixture_e",
        title="Wave-2 Fixture E",
        created_at=CREATED_AT,
        scenes=[
            Scene(
                scene_id="fe_s001",
                location="Dark Chamber",
                time_of_day="NIGHT",
                characters=["char_mage"],
                actions=[SceneAction(description="Mage performs __FORBIDDEN__ ritual")],
            )
        ],
    )


# ---------------------------------------------------------------------------
# Wave-2 pinned SHA-256 hashes — set by running pytest once with sentinel
# values, reading the actual hashes from assertion output, then replacing.
# ---------------------------------------------------------------------------
_HASH_C = "74b24e4457bc994ddfb95b326984684280ec7d6946fe983f9ca86033eeb6b965"
_HASH_D = "d24d90a10a7a9d81cf745aa6613317533087397f1bc65559081b3e8cd680dafd"
_HASH_E = "5cbf8aff508ddc4eeef9e70aac7709e148727b4d5252a279fe82949eaf93dbdc"


class TestWave2GoldenFixtures:
    """Byte-identity + SHA-256 regression for Wave-2 golden fixtures."""

    def test_fixture_c_minimal_byte_identity_and_hash(self):
        """Fixture C: minimal script → two runs produce byte-identical JSON."""
        script = _fixture_c_script()
        json_out_1 = dump_shotlist(adapt_script(script, created_at=CREATED_AT))
        json_out_2 = dump_shotlist(adapt_script(script, created_at=CREATED_AT))
        assert json_out_1 == json_out_2, "byte-identity failed for fixture C"
        assert _sha256(json_out_1) == _HASH_C

    def test_fixture_d_multi_scene_byte_identity_and_hash(self):
        """Fixture D: multi-scene script → two runs produce byte-identical JSON."""
        script = _fixture_d_script()
        json_out_1 = dump_shotlist(adapt_script(script, created_at=CREATED_AT))
        json_out_2 = dump_shotlist(adapt_script(script, created_at=CREATED_AT))
        assert json_out_1 == json_out_2, "byte-identity failed for fixture D"
        assert _sha256(json_out_1) == _HASH_D

    def test_fixture_e_forbidden_text_byte_identity_and_hash(self):
        """Fixture E: __FORBIDDEN__ in action text → carried deterministically."""
        script = _fixture_e_script()
        json_out_1 = dump_shotlist(adapt_script(script, created_at=CREATED_AT))
        json_out_2 = dump_shotlist(adapt_script(script, created_at=CREATED_AT))
        assert json_out_1 == json_out_2, "byte-identity failed for fixture E"
        assert _sha256(json_out_1) == _HASH_E
