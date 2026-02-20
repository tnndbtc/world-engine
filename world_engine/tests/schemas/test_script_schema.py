"""Schema-level tests for script_v1: load, dump, validate."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from world_engine.adaptation.models import Scene, Script
from world_engine.schemas.script_v1 import dump_script, load_script, validate_script

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"
SCRIPT_EXAMPLE = EXAMPLES_DIR / "script_v1_example.json"


class TestLoadScript:
    def test_load_from_dict(self):
        data = {
            "script_id": "x",
            "title": "T",
            "created_at": "2026-01-01T00:00:00Z",
            "scenes": [],
        }
        script = load_script(data)
        assert script.script_id == "x"

    def test_load_from_json_string(self):
        json_str = json.dumps({
            "script_id": "x",
            "title": "T",
            "created_at": "2026-01-01T00:00:00Z",
            "scenes": [],
        })
        script = load_script(json_str)
        assert script.script_id == "x"

    def test_load_from_json_bytes(self):
        json_bytes = json.dumps({
            "script_id": "x",
            "title": "T",
            "created_at": "2026-01-01T00:00:00Z",
            "scenes": [],
        }).encode()
        script = load_script(json_bytes)
        assert script.script_id == "x"

    def test_load_from_path(self, tmp_path: Path):
        data = {
            "script_id": "x",
            "title": "T",
            "created_at": "2026-01-01T00:00:00Z",
            "scenes": [],
        }
        p = tmp_path / "script.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        script = load_script(p)
        assert script.script_id == "x"

    def test_load_invalid_raises_validation_error(self):
        with pytest.raises(ValidationError):
            load_script({"title": "Missing required fields"})


class TestDumpScript:
    def _simple_script(self) -> Script:
        return Script(
            script_id="dump_test",
            title="Dump Test",
            created_at="2026-01-01T00:00:00Z",
            scenes=[],
        )

    def test_dump_produces_valid_json(self):
        out = dump_script(self._simple_script())
        parsed = json.loads(out)
        assert parsed["script_id"] == "dump_test"

    def test_dump_has_sorted_top_level_keys(self):
        out = dump_script(self._simple_script())
        keys = list(json.loads(out).keys())
        assert keys == sorted(keys)

    def test_dump_load_roundtrip(self):
        script = Script(
            script_id="roundtrip_001",
            title="Roundtrip",
            created_at="2026-01-01T00:00:00Z",
            scenes=[Scene(scene_id="s001", location="X", time_of_day="DAY")],
        )
        assert load_script(dump_script(script)) == script

    def test_dump_is_byte_identical_for_same_model(self):
        s = self._simple_script()
        assert dump_script(s) == dump_script(s)


class TestValidateScript:
    def test_valid_dict_returns_empty_error_list(self):
        errors = validate_script({
            "script_id": "x",
            "title": "T",
            "created_at": "2026-01-01T00:00:00Z",
            "scenes": [],
        })
        assert errors == []

    def test_invalid_dict_returns_error_strings(self):
        errors = validate_script({"title": "Missing fields"})
        assert len(errors) > 0
        assert all(isinstance(e, str) for e in errors)

    @pytest.mark.skipif(
        not SCRIPT_EXAMPLE.exists(),
        reason="script_v1_example.json not generated yet",
    )
    def test_example_file_validates_cleanly(self):
        data = json.loads(SCRIPT_EXAMPLE.read_text(encoding="utf-8"))
        assert validate_script(data) == []
