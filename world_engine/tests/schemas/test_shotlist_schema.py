"""Schema-level tests for shotlist_v1: load, dump, validate."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from world_engine.adaptation.models import AudioIntent, Shot, ShotList
from world_engine.schema_loader import load_schema
from world_engine.schemas.shotlist_v1 import dump_shotlist, load_shotlist, validate_shotlist

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"
SHOTLIST_EXAMPLE = EXAMPLES_DIR / "shotlist_v1_example.json"


def _minimal_shotlist() -> ShotList:
    return ShotList(
        shotlist_id="sl_abc123",
        script_id="test_001",
        shots=[
            Shot(
                shot_id="s001_shot_000",
                scene_id="s001",
                duration_sec=3.0,
                camera_framing="WIDE",
                camera_movement="STATIC",
                audio_intent=AudioIntent(),
            )
        ],
        total_duration_sec=3.0,
        timing_lock_hash="a" * 64,
        created_at="2026-02-19T00:00:00Z",
    )


class TestLoadShotlist:
    def test_load_from_dict(self):
        data = json.loads(_minimal_shotlist().model_dump_json())
        sl = load_shotlist(data)
        assert sl.shotlist_id == "sl_abc123"

    def test_load_from_json_string(self):
        json_str = _minimal_shotlist().model_dump_json()
        sl = load_shotlist(json_str)
        assert sl.script_id == "test_001"

    def test_load_from_path(self, tmp_path: Path):
        data = json.loads(_minimal_shotlist().model_dump_json())
        p = tmp_path / "shotlist.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        sl = load_shotlist(p)
        assert sl.shotlist_id == "sl_abc123"

    def test_load_invalid_raises_validation_error(self):
        with pytest.raises(ValidationError):
            load_shotlist({"script_id": "missing_required_fields"})


class TestDumpShotlist:
    def test_dump_produces_valid_json(self):
        out = dump_shotlist(_minimal_shotlist())
        parsed = json.loads(out)
        assert parsed["shotlist_id"] == "sl_abc123"

    def test_dump_has_sorted_top_level_keys(self):
        out = dump_shotlist(_minimal_shotlist())
        keys = list(json.loads(out).keys())
        assert keys == sorted(keys)

    def test_dump_load_roundtrip(self):
        sl = _minimal_shotlist()
        assert load_shotlist(dump_shotlist(sl)) == sl

    def test_dump_is_byte_identical_for_same_model(self):
        sl = _minimal_shotlist()
        assert dump_shotlist(sl) == dump_shotlist(sl)


class TestValidateShotlist:
    def test_valid_shotlist_returns_empty_errors(self):
        data = json.loads(_minimal_shotlist().model_dump_json())
        assert validate_shotlist(data) == []

    def test_missing_timing_lock_hash_returns_errors(self):
        data = {
            "shotlist_id": "sl_x",
            "script_id": "s",
            "shots": [],
            "total_duration_sec": 0.0,
            "created_at": "2026-01-01T00:00:00Z",
        }
        errors = validate_shotlist(data)
        assert len(errors) > 0

    def test_shot_missing_duration_returns_errors(self):
        data = {
            "shotlist_id": "sl_x",
            "script_id": "s",
            "shots": [
                {
                    "shot_id": "s001_shot_000",
                    "scene_id": "s001",
                    "camera_framing": "WIDE",
                    "camera_movement": "STATIC",
                    "audio_intent": {},
                }
            ],
            "total_duration_sec": 0.0,
            "timing_lock_hash": "a" * 64,
            "created_at": "2026-01-01T00:00:00Z",
        }
        errors = validate_shotlist(data)
        assert len(errors) > 0

    @pytest.mark.skipif(
        not SHOTLIST_EXAMPLE.exists(),
        reason="shotlist_v1_example.json not generated yet",
    )
    def test_example_file_validates_cleanly(self):
        data = json.loads(SHOTLIST_EXAMPLE.read_text(encoding="utf-8"))
        assert validate_shotlist(data) == []


class TestJsonSchemaContract:
    def _schema(self) -> dict:
        return load_schema("ShotList.v1.json")

    @pytest.mark.skipif(
        not SHOTLIST_EXAMPLE.exists()
        or "producer" in json.loads(SHOTLIST_EXAMPLE.read_text(encoding="utf-8")),
        reason="shotlist_v1_example.json predates canonical contracts-v1.0.0 (has producer field)",
    )
    def test_example_json_validates_against_schema(self):
        """Golden example must pass the JSON Schema contract."""
        jsonschema.validate(
            json.loads(SHOTLIST_EXAMPLE.read_text(encoding="utf-8")),
            self._schema(),
        )

    def test_missing_required_fields_rejected(self):
        """Dict missing required root fields must fail JSON Schema validation."""
        bad = {"script_id": "x", "shots": [], "total_duration_sec": 0.0}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, self._schema())

    def test_missing_schema_id_rejected(self):
        """schema_id is now required — artifact without it must fail JSON Schema."""
        data = json.loads(_minimal_shotlist().model_dump_json())
        del data["schema_id"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(data, self._schema())

    def test_missing_producer_rejected(self):
        """producer is now required — artifact without it must fail JSON Schema."""
        data = json.loads(_minimal_shotlist().model_dump_json())
        del data["producer"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(data, self._schema())

    def test_producer_missing_required_fields_rejected(self):
        """producer with neither repo nor component must fail JSON Schema."""
        data = json.loads(_minimal_shotlist().model_dump_json())
        data["producer"] = {}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(data, self._schema())

    def test_extra_root_field_rejected(self):
        """additionalProperties:false must reject unknown top-level keys."""
        data = json.loads(_minimal_shotlist().model_dump_json())
        data["unknown_v3_field"] = "should_be_rejected"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(data, self._schema())
