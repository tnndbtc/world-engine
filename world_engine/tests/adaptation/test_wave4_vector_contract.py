"""Wave-4 Agent B: ShotList contract vector verification.

For each committed golden file in tests/contract_vectors/shotlist/, regenerate the
ShotList from its Script fixture and assert the produced bytes are EXACTLY equal
to the golden bytes (strict bytes compare; no pretty diff).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from world_engine.adaptation.adapter import adapt_script
from world_engine.adaptation.models import DialogueLine, Scene, SceneAction, Script
from world_engine.schemas.shotlist_v1 import canonical_json_bytes

VECTORS_DIR = Path(__file__).parent.parent / "contract_vectors" / "shotlist"


# ─────────────────────────────────────────────────────────────────────────────
# Script fixture factories — must match bodies used to generate the goldens
# ─────────────────────────────────────────────────────────────────────────────

def _script_fixture_a() -> Script:
    return Script(
        script_id="fixture_a", title="Fixture A",
        created_at="1970-01-01T00:00:00Z",
        scenes=[Scene(scene_id="fa_s001", location="Empty Plain", time_of_day="DAY")])


def _script_fixture_b() -> Script:
    return Script(
        script_id="fixture_b", title="Fixture B",
        created_at="1970-01-01T00:00:00Z",
        scenes=[Scene(
            scene_id="fb_s001", location="Town Square", time_of_day="NOON",
            characters=["char_alice", "char_bob"],
            dialogue=[DialogueLine(speaker_id="char_alice", text="Hello.")])])


def _script_fixture_d() -> Script:
    return Script(
        script_id="wave2_fixture_d", title="Fixture D",
        created_at="1970-01-01T00:00:00Z",
        scenes=[
            Scene(scene_id="fd_s001", location="Market", time_of_day="DAY",
                  characters=["char_scout"],
                  actions=[SceneAction(description="Scout scans the crowd.",
                                       characters=["char_scout"])]),
            Scene(scene_id="fd_s002", location="Throne Room", time_of_day="INTERIOR",
                  characters=["char_lena", "char_king"],
                  dialogue=[DialogueLine(speaker_id="char_lena",
                                         text="I bring news from the frontier."),
                             DialogueLine(speaker_id="char_king", text="Speak.")]),
            Scene(scene_id="fd_s003", location="Castle Courtyard", time_of_day="DUSK")])


# ─────────────────────────────────────────────────────────────────────────────
# Vector verification
# ─────────────────────────────────────────────────────────────────────────────

_FIXTURES = [
    ("fixture_a", _script_fixture_a),
    ("fixture_b", _script_fixture_b),
    ("fixture_d", _script_fixture_d),
]


class TestShotListVectorContract:
    @pytest.mark.parametrize("vector_name,script_fn", _FIXTURES)
    def test_produced_bytes_match_golden(self, vector_name: str, script_fn):
        golden_path = VECTORS_DIR / f"{vector_name}.json"
        assert golden_path.exists(), f"Golden file missing: {golden_path}"
        golden_bytes = golden_path.read_bytes()
        sl = adapt_script(script_fn())
        produced_bytes = canonical_json_bytes(sl)
        assert produced_bytes == golden_bytes, (
            f"Byte mismatch for {vector_name}: "
            f"produced {len(produced_bytes)} bytes, golden {len(golden_bytes)} bytes"
        )
