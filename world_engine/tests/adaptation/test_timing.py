"""Tests for timing estimation and timing_lock_hash computation."""
from __future__ import annotations

import pytest

from world_engine.adaptation.models import AudioIntent, Shot
from world_engine.adaptation.shot_templates import SHOT_TEMPLATES
from world_engine.adaptation.timing import compute_timing_lock_hash, estimate_shot_duration


def _make_shot(shot_id: str, duration: float, **kwargs) -> Shot:
    return Shot(
        shot_id=shot_id,
        scene_id="s001",
        duration_sec=duration,
        camera_framing=kwargs.get("camera_framing", "WIDE"),
        camera_movement=kwargs.get("camera_movement", "STATIC"),
        audio_intent=AudioIntent(music_mood=kwargs.get("music_mood")),
        emotional_tag=kwargs.get("emotional_tag"),
    )


# ── Duration estimation ────────────────────────────────────────────────────────


class TestDurationEstimation:
    def test_no_text_returns_base_duration(self):
        tpl = SHOT_TEMPLATES["tpl_establishing"]
        assert estimate_shot_duration(tpl) == tpl.base_duration_sec

    def test_short_text_clamped_to_min(self):
        tpl = SHOT_TEMPLATES["tpl_dialogue"]
        dur = estimate_shot_duration(tpl, text="Hi.")  # 1 word
        assert dur >= tpl.duration_min_sec

    def test_long_text_clamped_to_max(self):
        tpl = SHOT_TEMPLATES["tpl_dialogue"]
        long_text = " ".join(["word"] * 300)
        dur = estimate_shot_duration(tpl, text=long_text)
        assert dur <= tpl.duration_max_sec

    def test_duration_increases_with_word_count(self):
        tpl = SHOT_TEMPLATES["tpl_dialogue"]
        short = estimate_shot_duration(tpl, text="Hi there.")
        long = estimate_shot_duration(tpl, text=" ".join(["word"] * 20))
        assert long > short

    def test_result_rounded_to_3dp(self):
        tpl = SHOT_TEMPLATES["tpl_dialogue"]
        dur = estimate_shot_duration(tpl, text="One two three four five six seven.")
        assert round(dur, 3) == dur

    @pytest.mark.parametrize("template_id", list(SHOT_TEMPLATES.keys()))
    def test_all_templates_return_positive_duration(self, template_id: str):
        tpl = SHOT_TEMPLATES[template_id]
        dur = estimate_shot_duration(tpl)
        assert dur > 0


# ── timing_lock_hash ───────────────────────────────────────────────────────────


class TestTimingLockHash:
    def test_empty_shotlist_returns_valid_hash(self):
        h = compute_timing_lock_hash([])
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_is_64_char_lowercase_hex(self):
        shots = [_make_shot("s001_shot_000", 3.0)]
        h = compute_timing_lock_hash(shots)
        assert len(h) == 64
        assert h == h.lower()
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_changes_on_duration_change(self):
        shots_a = [_make_shot("s001_shot_000", 3.0)]
        shots_b = [_make_shot("s001_shot_000", 3.001)]
        assert compute_timing_lock_hash(shots_a) != compute_timing_lock_hash(shots_b)

    def test_hash_changes_on_shot_added(self):
        shots_a = [_make_shot("s001_shot_000", 3.0)]
        shots_b = [
            _make_shot("s001_shot_000", 3.0),
            _make_shot("s001_shot_001", 2.0),
        ]
        assert compute_timing_lock_hash(shots_a) != compute_timing_lock_hash(shots_b)

    def test_hash_changes_on_order_change(self):
        shots_a = [_make_shot("s001_shot_000", 3.0), _make_shot("s001_shot_001", 2.0)]
        shots_b = [_make_shot("s001_shot_001", 2.0), _make_shot("s001_shot_000", 3.0)]
        assert compute_timing_lock_hash(shots_a) != compute_timing_lock_hash(shots_b)

    def test_hash_changes_on_shot_id_change(self):
        shots_a = [_make_shot("s001_shot_000", 3.0)]
        shots_b = [_make_shot("s001_shot_999", 3.0)]
        assert compute_timing_lock_hash(shots_a) != compute_timing_lock_hash(shots_b)

    def test_hash_stable_on_camera_change(self):
        shots_a = [_make_shot("s001_shot_000", 3.0, camera_framing="WIDE")]
        shots_b = [_make_shot("s001_shot_000", 3.0, camera_framing="CLOSE_UP")]
        assert compute_timing_lock_hash(shots_a) == compute_timing_lock_hash(shots_b)

    def test_hash_stable_on_music_mood_change(self):
        shots_a = [_make_shot("s001_shot_000", 3.0, music_mood="tense")]
        shots_b = [_make_shot("s001_shot_000", 3.0, music_mood="hopeful")]
        assert compute_timing_lock_hash(shots_a) == compute_timing_lock_hash(shots_b)

    def test_hash_stable_on_emotional_tag_change(self):
        shots_a = [_make_shot("s001_shot_000", 3.0, emotional_tag="happy")]
        shots_b = [_make_shot("s001_shot_000", 3.0, emotional_tag="sad")]
        assert compute_timing_lock_hash(shots_a) == compute_timing_lock_hash(shots_b)

    def test_hash_deterministic_across_calls(self):
        shots = [
            _make_shot("s001_shot_000", 3.0),
            _make_shot("s001_shot_001", 2.5),
        ]
        hashes = {compute_timing_lock_hash(shots) for _ in range(50)}
        assert len(hashes) == 1
