"""End-to-end adapter correctness tests.

Tests are parameterised against concrete Script fixtures to cover all beat
types, edge cases, and field propagation rules.
"""
from __future__ import annotations

import pytest

from world_engine.adaptation.adapter import adapt_script
from world_engine.adaptation.models import (
    DialogueLine,
    Scene,
    SceneAction,
    Script,
)

FIXED_AT = "2026-02-19T00:00:00Z"


def _make_script(**kwargs) -> Script:
    defaults: dict = {
        "script_id": "test_script_001",
        "title": "Test Episode",
        "created_at": FIXED_AT,
        "scenes": [],
    }
    defaults.update(kwargs)
    return Script(**defaults)


# ── Shot count correctness ─────────────────────────────────────────────────────


class TestShotCounts:
    def test_empty_scene_gives_establishing_plus_cutaway(self):
        script = _make_script(scenes=[
            Scene(scene_id="s001", location="Ruins", time_of_day="DUSK"),
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        assert len(sl.shots) == 2
        assert sl.shots[0].shot_template_id == "tpl_establishing"
        assert sl.shots[1].shot_template_id == "tpl_cutaway"

    def test_single_char_dialogue_no_reaction(self):
        # 1 scene, 1 char, 1 dialogue line → establishing + dialogue = 2 shots
        script = _make_script(scenes=[
            Scene(
                scene_id="s001",
                location="A",
                time_of_day="DAY",
                characters=["char_a"],
                dialogue=[DialogueLine(speaker_id="char_a", text="Hello.")],
            )
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        assert len(sl.shots) == 2

    def test_two_char_dialogue_adds_reaction(self):
        # 1 scene, 2 chars, 1 dialogue line → establishing + dialogue + reaction = 3
        script = _make_script(scenes=[
            Scene(
                scene_id="s001",
                location="A",
                time_of_day="DAY",
                characters=["char_a", "char_b"],
                dialogue=[DialogueLine(speaker_id="char_a", text="Hello there.")],
            )
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        assert len(sl.shots) == 3

    def test_single_action_gives_establishing_plus_action(self):
        script = _make_script(scenes=[
            Scene(
                scene_id="s001",
                location="Field",
                time_of_day="DAY",
                characters=["char_a"],
                actions=[SceneAction(description="Char A runs.", characters=["char_a"])],
            )
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        assert len(sl.shots) == 2
        templates = [s.shot_template_id for s in sl.shots]
        assert "tpl_establishing" in templates
        assert "tpl_action" in templates

    def test_multi_scene_all_scenes_have_shots(self):
        script = _make_script(scenes=[
            Scene(scene_id="s001", location="A", time_of_day="DAY"),
            Scene(scene_id="s002", location="B", time_of_day="NIGHT"),
            Scene(scene_id="s003", location="C", time_of_day="DUSK"),
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        covered = {shot.scene_id for shot in sl.shots}
        assert covered == {"s001", "s002", "s003"}


# ── First shot of each scene is always establishing ────────────────────────────


class TestEstablishingFirst:
    def test_first_shot_of_every_scene_is_establishing(self):
        script = _make_script(scenes=[
            Scene(
                scene_id="s001",
                location="A",
                time_of_day="DAY",
                characters=["char_a"],
                dialogue=[DialogueLine(speaker_id="char_a", text="Hi.")],
            ),
            Scene(
                scene_id="s002",
                location="B",
                time_of_day="NIGHT",
                characters=["char_b"],
                actions=[SceneAction(description="Runs.", characters=["char_b"])],
            ),
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        for scene_id in ("s001", "s002"):
            scene_shots = [s for s in sl.shots if s.scene_id == scene_id]
            assert scene_shots[0].shot_template_id == "tpl_establishing", (
                f"Scene {scene_id}: first shot is not establishing"
            )


# ── Shot property correctness ─────────────────────────────────────────────────


class TestShotProperties:
    def test_all_shots_have_positive_duration(self):
        script = _make_script(scenes=[
            Scene(
                scene_id="s001",
                location="Forest",
                time_of_day="DAY",
                characters=["char_a", "char_b"],
                dialogue=[
                    DialogueLine(speaker_id="char_a", text="We must go now."),
                    DialogueLine(speaker_id="char_b", text="I agree."),
                ],
                actions=[SceneAction(description="They run.", characters=["char_a", "char_b"])],
            )
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        for shot in sl.shots:
            assert shot.duration_sec > 0, f"{shot.shot_id} has non-positive duration"

    def test_shot_ids_are_unique(self):
        script = _make_script(scenes=[
            Scene(
                scene_id="s001",
                location="A",
                time_of_day="DAY",
                characters=["char_a", "char_b"],
                dialogue=[
                    DialogueLine(speaker_id="char_a", text="Line one."),
                    DialogueLine(speaker_id="char_b", text="Line two."),
                ],
                actions=[SceneAction(description="Action.", characters=["char_a"])],
            )
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        ids = [s.shot_id for s in sl.shots]
        assert len(ids) == len(set(ids))

    def test_shot_ids_reference_correct_scene(self):
        script = _make_script(scenes=[
            Scene(scene_id="s001", location="A", time_of_day="DAY"),
            Scene(scene_id="s002", location="B", time_of_day="NIGHT"),
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        for shot in sl.shots:
            assert shot.shot_id.startswith(shot.scene_id), (
                f"{shot.shot_id} does not start with scene_id {shot.scene_id}"
            )

    def test_script_id_propagated_to_shotlist(self):
        script = _make_script(script_id="ep_007")
        sl = adapt_script(script, created_at=FIXED_AT)
        assert sl.script_id == "ep_007"

    def test_episode_id_propagated(self):
        script = _make_script(episode_id="season_1_ep_3")
        sl = adapt_script(script, created_at=FIXED_AT)
        assert sl.episode_id == "season_1_ep_3"

    def test_total_duration_equals_sum_of_shots(self):
        script = _make_script(scenes=[
            Scene(
                scene_id="s001",
                location="A",
                time_of_day="DAY",
                characters=["char_a"],
                dialogue=[DialogueLine(speaker_id="char_a", text="Hello.")],
            )
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        expected = round(sum(s.duration_sec for s in sl.shots), 3)
        assert sl.total_duration_sec == expected

    def test_timing_lock_hash_is_64_char_hex(self):
        script = _make_script(scenes=[
            Scene(scene_id="s001", location="X", time_of_day="DAY"),
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        assert len(sl.timing_lock_hash) == 64
        assert all(c in "0123456789abcdef" for c in sl.timing_lock_hash)


# ── Reaction shot rules ────────────────────────────────────────────────────────


class TestReactionShots:
    def test_no_reaction_with_single_character(self):
        script = _make_script(scenes=[
            Scene(
                scene_id="s001",
                location="A",
                time_of_day="DAY",
                characters=["char_a"],
                dialogue=[DialogueLine(speaker_id="char_a", text="Alone.")],
            )
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        templates = [s.shot_template_id for s in sl.shots]
        assert "tpl_reaction" not in templates

    def test_reaction_with_two_characters(self):
        script = _make_script(scenes=[
            Scene(
                scene_id="s001",
                location="A",
                time_of_day="DAY",
                characters=["char_a", "char_b"],
                dialogue=[DialogueLine(speaker_id="char_a", text="Together.")],
            )
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        templates = [s.shot_template_id for s in sl.shots]
        assert "tpl_reaction" in templates

    def test_reaction_characters_exclude_speaker(self):
        script = _make_script(scenes=[
            Scene(
                scene_id="s001",
                location="A",
                time_of_day="DAY",
                characters=["char_a", "char_b"],
                dialogue=[DialogueLine(speaker_id="char_a", text="I speak.")],
            )
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        reaction_shots = [s for s in sl.shots if s.shot_template_id == "tpl_reaction"]
        assert len(reaction_shots) == 1
        char_ids = [c.character_id for c in reaction_shots[0].characters]
        assert "char_a" not in char_ids
        assert "char_b" in char_ids


# ── Audio intent ───────────────────────────────────────────────────────────────


class TestAudioIntent:
    def test_dialogue_shot_has_vo_text_and_speaker(self):
        text = "This is my line."
        script = _make_script(scenes=[
            Scene(
                scene_id="s001",
                location="A",
                time_of_day="DAY",
                characters=["char_a"],
                dialogue=[DialogueLine(speaker_id="char_a", text=text)],
            )
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        dlg_shots = [s for s in sl.shots if s.shot_template_id == "tpl_dialogue"]
        assert len(dlg_shots) == 1
        assert dlg_shots[0].audio_intent.vo_text == text
        assert dlg_shots[0].audio_intent.vo_speaker_id == "char_a"

    def test_establishing_shot_has_no_vo(self):
        script = _make_script(scenes=[
            Scene(scene_id="s001", location="A", time_of_day="DAY"),
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        establishing = sl.shots[0]
        assert establishing.audio_intent.vo_text is None
        assert establishing.audio_intent.vo_speaker_id is None

    def test_music_mood_from_scene_emotional_tag(self):
        script = _make_script(scenes=[
            Scene(
                scene_id="s001",
                location="A",
                time_of_day="DAY",
                emotional_tags=["tension"],
            )
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        for shot in sl.shots:
            assert shot.audio_intent.music_mood == "tension"


# ── Emotional tags ─────────────────────────────────────────────────────────────


class TestEmotionalTags:
    def test_dialogue_shot_uses_line_emotion(self):
        script = _make_script(scenes=[
            Scene(
                scene_id="s001",
                location="A",
                time_of_day="DAY",
                characters=["char_a"],
                dialogue=[DialogueLine(speaker_id="char_a", text="Hi.", emotion="joyful")],
                emotional_tags=["tension"],
            )
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        dlg = [s for s in sl.shots if s.shot_template_id == "tpl_dialogue"][0]
        # Line emotion takes priority over scene tag
        assert dlg.emotional_tag == "joyful"

    def test_establishing_inherits_scene_tag(self):
        script = _make_script(scenes=[
            Scene(
                scene_id="s001",
                location="A",
                time_of_day="DAY",
                emotional_tags=["dread"],
            )
        ])
        sl = adapt_script(script, created_at=FIXED_AT)
        assert sl.shots[0].emotional_tag == "dread"
