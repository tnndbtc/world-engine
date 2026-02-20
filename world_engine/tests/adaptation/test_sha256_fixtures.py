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
from world_engine.adaptation.models import DialogueLine, Scene, Script
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
