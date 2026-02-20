"""Tests for Script and ShotList Pydantic models.

Covers: roundtrip serialisation, required-field enforcement, forward
compatibility (unknown fields ignored), and schema_version presence.
"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from world_engine.adaptation.models import (
    AudioIntent,
    CharacterInShot,
    DialogueLine,
    Scene,
    SceneAction,
    Script,
    Shot,
    ShotList,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _minimal_script() -> Script:
    return Script(
        script_id="test_001",
        title="Test Script",
        created_at="2026-02-19T00:00:00Z",
        scenes=[
            Scene(
                scene_id="s001",
                location="Test Location",
                time_of_day="DAY",
            )
        ],
    )


def _minimal_shot() -> Shot:
    return Shot(
        shot_id="s001_shot_000",
        scene_id="s001",
        duration_sec=3.0,
        camera_framing="WIDE",
        camera_movement="STATIC",
        audio_intent=AudioIntent(),
    )


def _minimal_shotlist() -> ShotList:
    return ShotList(
        shotlist_id="sl_abc123",
        script_id="test_001",
        shots=[_minimal_shot()],
        total_duration_sec=3.0,
        timing_lock_hash="a" * 64,
        created_at="2026-02-19T00:00:00Z",
    )


# ── Roundtrip tests ───────────────────────────────────────────────────────────


class TestRoundtrip:
    def test_script_roundtrip(self):
        script = _minimal_script()
        reconstructed = Script.model_validate_json(script.model_dump_json())
        assert reconstructed == script

    def test_shotlist_roundtrip(self):
        sl = _minimal_shotlist()
        reconstructed = ShotList.model_validate_json(sl.model_dump_json())
        assert reconstructed == sl

    def test_script_schema_version_in_json(self):
        data = json.loads(_minimal_script().model_dump_json())
        assert data["schema_version"] == "1.0.0"

    def test_shotlist_schema_version_in_json(self):
        data = json.loads(_minimal_shotlist().model_dump_json())
        assert data["schema_version"] == "1.0.0"

    def test_shot_roundtrip(self):
        shot = _minimal_shot()
        reconstructed = Shot.model_validate_json(shot.model_dump_json())
        assert reconstructed == shot


# ── Required-field enforcement ────────────────────────────────────────────────


class TestScriptValidation:
    def test_missing_title_rejected(self):
        with pytest.raises(ValidationError):
            Script(script_id="x", created_at="2026-01-01T00:00:00Z", scenes=[])

    def test_missing_script_id_rejected(self):
        with pytest.raises(ValidationError):
            Script(title="T", created_at="2026-01-01T00:00:00Z", scenes=[])

    def test_missing_created_at_rejected(self):
        with pytest.raises(ValidationError):
            Script(script_id="x", title="T", scenes=[])

    def test_missing_scenes_rejected(self):
        with pytest.raises(ValidationError):
            Script(script_id="x", title="T", created_at="2026-01-01T00:00:00Z")


class TestShotValidation:
    def test_missing_duration_rejected(self):
        with pytest.raises(ValidationError):
            Shot(
                shot_id="s001_shot_000",
                scene_id="s001",
                camera_framing="WIDE",
                camera_movement="STATIC",
                audio_intent=AudioIntent(),
            )

    def test_int_duration_coerced_to_float(self):
        shot = Shot(
            shot_id="s001_shot_000",
            scene_id="s001",
            duration_sec=3,
            camera_framing="WIDE",
            camera_movement="STATIC",
            audio_intent=AudioIntent(),
        )
        assert shot.duration_sec == 3.0
        assert isinstance(shot.duration_sec, float)


class TestShotListValidation:
    def test_missing_timing_lock_hash_rejected(self):
        with pytest.raises(ValidationError):
            ShotList(
                shotlist_id="sl_x",
                script_id="s",
                shots=[],
                total_duration_sec=0.0,
                created_at="2026-01-01T00:00:00Z",
            )


# ── Forward-compatibility (unknown fields ignored) ────────────────────────────


class TestForwardCompatibility:
    def test_unknown_field_in_script_ignored(self):
        data = {
            "script_id": "x",
            "title": "T",
            "created_at": "2026-01-01T00:00:00Z",
            "scenes": [],
            "future_v2_field": "some_value",
        }
        script = Script.model_validate(data)
        assert script.script_id == "x"

    def test_unknown_field_in_shot_ignored(self):
        data = {
            "shot_id": "s001_shot_000",
            "scene_id": "s001",
            "duration_sec": 2.5,
            "camera_framing": "WIDE",
            "camera_movement": "STATIC",
            "audio_intent": {},
            "v2_hdr_flag": True,
        }
        shot = Shot.model_validate(data)
        assert shot.shot_id == "s001_shot_000"

    def test_unknown_field_in_scene_ignored(self):
        data = {
            "scene_id": "s001",
            "location": "X",
            "time_of_day": "DAY",
            "future_lighting_rig": "sunset_warm",
        }
        scene = Scene.model_validate(data)
        assert scene.scene_id == "s001"

    def test_unknown_field_in_audio_intent_ignored(self):
        data = {"v2_dolby_atmos": True}
        ai = AudioIntent.model_validate(data)
        assert ai.sfx_tags == []


# ── Optional-field defaults ───────────────────────────────────────────────────


class TestDefaults:
    def test_script_metadata_defaults_to_empty_dict(self):
        assert _minimal_script().metadata == {}

    def test_scene_characters_defaults_to_empty_list(self):
        scene = Scene(scene_id="s001", location="X", time_of_day="DAY")
        assert scene.characters == []

    def test_audio_intent_sfx_tags_defaults_to_empty_list(self):
        assert AudioIntent().sfx_tags == []

    def test_dialogue_emotion_defaults_to_none(self):
        line = DialogueLine(speaker_id="char_a", text="Hello.")
        assert line.emotion is None

    def test_shot_emotional_tag_defaults_to_none(self):
        assert _minimal_shot().emotional_tag is None
