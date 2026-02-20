"""Determinism tests: same input → identical output on every run.

The golden tests load examples/script_v1_example.json, run the adapter, and
compare to examples/shotlist_v1_example.json.  They are skipped (not failed)
when the example files have not yet been generated.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from world_engine.adaptation.adapter import adapt_script
from world_engine.adaptation.models import DialogueLine, Scene, Script
from world_engine.adaptation.timing import compute_timing_lock_hash
from world_engine.schemas.script_v1 import dump_script, load_script
from world_engine.schemas.shotlist_v1 import dump_shotlist, load_shotlist

FIXED_AT = "2026-02-19T00:00:00Z"

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"
SCRIPT_EXAMPLE = EXAMPLES_DIR / "script_v1_example.json"
SHOTLIST_EXAMPLE = EXAMPLES_DIR / "shotlist_v1_example.json"


def _example_script() -> Script:
    return Script(
        script_id="example_script_001",
        title="The Crossing",
        created_at=FIXED_AT,
        scenes=[
            Scene(
                scene_id="s001",
                location="Castle Entrance",
                time_of_day="DAY",
                characters=["char_lena"],
                emotional_tags=["anticipation"],
            ),
            Scene(
                scene_id="s002",
                location="Throne Room",
                time_of_day="INTERIOR",
                characters=["char_lena", "char_king"],
                dialogue=[
                    DialogueLine(
                        speaker_id="char_lena",
                        text="I have come to seek your counsel, my lord.",
                        emotion="respectful",
                    ),
                    DialogueLine(
                        speaker_id="char_king",
                        text="State your purpose.",
                        emotion="stern",
                    ),
                ],
                emotional_tags=["tension"],
            ),
        ],
    )


class TestConsistency:
    def test_same_input_same_output(self):
        script = _example_script()
        sl_a = adapt_script(script, created_at=FIXED_AT)
        sl_b = adapt_script(script, created_at=FIXED_AT)
        assert sl_a == sl_b

    def test_json_bytes_identical(self):
        script = _example_script()
        sl_a = adapt_script(script, created_at=FIXED_AT)
        sl_b = adapt_script(script, created_at=FIXED_AT)
        assert dump_shotlist(sl_a) == dump_shotlist(sl_b)

    def test_script_json_bytes_identical(self):
        assert dump_script(_example_script()) == dump_script(_example_script())

    def test_timing_lock_hash_stable_100_runs(self):
        script = _example_script()
        hashes = {
            adapt_script(script, created_at=FIXED_AT).timing_lock_hash
            for _ in range(100)
        }
        assert len(hashes) == 1, f"Hash was not stable across 100 runs: {hashes}"

    def test_shotlist_id_stable(self):
        script = _example_script()
        ids = {adapt_script(script, created_at=FIXED_AT).shotlist_id for _ in range(10)}
        assert len(ids) == 1

    def test_shot_ids_stable_and_ordered(self):
        script = _example_script()
        shots_a = [s.shot_id for s in adapt_script(script, created_at=FIXED_AT).shots]
        shots_b = [s.shot_id for s in adapt_script(script, created_at=FIXED_AT).shots]
        assert shots_a == shots_b

    def test_total_duration_stable(self):
        script = _example_script()
        totals = {
            adapt_script(script, created_at=FIXED_AT).total_duration_sec
            for _ in range(10)
        }
        assert len(totals) == 1


class TestGolden:
    """Compare output against pinned golden artifacts in examples/.

    Skipped when the example files have not yet been generated.
    Run `python -m world_engine.scripts.generate_examples` to create them.
    """

    @pytest.mark.skipif(
        not SCRIPT_EXAMPLE.exists(),
        reason="script_v1_example.json not found — generate examples first",
    )
    @pytest.mark.skipif(
        not SHOTLIST_EXAMPLE.exists(),
        reason="shotlist_v1_example.json not found — generate examples first",
    )
    def test_golden_shot_timing(self):
        script = load_script(SCRIPT_EXAMPLE)
        actual = adapt_script(script, created_at=FIXED_AT)
        expected = load_shotlist(SHOTLIST_EXAMPLE)
        assert actual.timing_lock_hash == expected.timing_lock_hash
        assert actual.total_duration_sec == expected.total_duration_sec
        assert len(actual.shots) == len(expected.shots)
        for a, e in zip(actual.shots, expected.shots):
            assert a.shot_id == e.shot_id
            assert a.duration_sec == e.duration_sec

    @pytest.mark.skipif(
        not SHOTLIST_EXAMPLE.exists(),
        reason="shotlist_v1_example.json not found — generate examples first",
    )
    def test_golden_timing_lock_hash_self_consistent(self):
        """Hash stored in the golden file must equal the recomputed value."""
        sl = load_shotlist(SHOTLIST_EXAMPLE)
        recomputed = compute_timing_lock_hash(sl.shots)
        assert sl.timing_lock_hash == recomputed
