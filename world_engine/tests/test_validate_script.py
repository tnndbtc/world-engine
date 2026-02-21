"""Tests for validate-script command (T1 / T2 / T3 + CLI exact-message)."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from world_engine.validator import validate_script_rules, validate_script_file

_VALID = {
    "schema_id": "Script",
    "schema_version": "1.0.0",
    "script_id": "s001",
    "characters": [{"id": "c001"}],
    "scenes": [
        {
            "scene_id": "sc001",
            "beats": [{"type": "action"}],
        }
    ],
}


@pytest.fixture
def valid_script_path(tmp_path: Path) -> Path:
    p = tmp_path / "script.json"
    p.write_text(json.dumps(_VALID), encoding="utf-8")
    return p


class TestValidateScriptRules:

    def test_t1_valid_minimal_script_passes(self):
        """T1: a valid minimal Script returns no errors."""
        assert validate_script_rules(_VALID) == []

    def test_t2_missing_schema_id_fails(self):
        """T2: missing schema_id produces an error."""
        bad = {**_VALID}
        del bad["schema_id"]
        errors = validate_script_rules(bad)
        assert errors  # non-empty error list

    def test_t2_wrong_schema_id_fails(self):
        """T2 variant: schema_id != 'Script' produces an error."""
        bad = {**_VALID, "schema_id": "ShotList"}
        errors = validate_script_rules(bad)
        assert errors

    def test_t3_invalid_beat_type_fails(self):
        """T3: unknown beat type produces an error."""
        bad = copy.deepcopy(_VALID)
        bad["scenes"][0]["beats"][0]["type"] = "narration"
        errors = validate_script_rules(bad)
        assert errors

    def test_dialogue_beat_missing_speaker_fails(self):
        bad = copy.deepcopy(_VALID)
        bad["scenes"][0]["beats"] = [{"type": "dialogue", "line": "Hi"}]
        assert validate_script_rules(bad)

    def test_dialogue_beat_missing_line_fails(self):
        bad = copy.deepcopy(_VALID)
        bad["scenes"][0]["beats"] = [{"type": "dialogue", "speaker": "c001"}]
        assert validate_script_rules(bad)

    def test_dialogue_beat_full_passes(self):
        good = copy.deepcopy(_VALID)
        good["scenes"][0]["beats"] = [{"type": "dialogue", "speaker": "c001", "line": "Hello"}]
        assert validate_script_rules(good) == []

    def test_all_beat_types_pass(self):
        for bt in ("action", "dialogue", "character_enter", "character_exit"):
            beat = {"type": bt}
            if bt == "dialogue":
                beat.update({"speaker": "c001", "line": "..."})
            good = copy.deepcopy(_VALID)
            good["scenes"][0]["beats"] = [beat]
            assert validate_script_rules(good) == []

    def test_missing_schema_version_fails(self):
        bad = {**_VALID}
        del bad["schema_version"]
        assert validate_script_rules(bad)

    def test_missing_script_id_fails(self):
        bad = {**_VALID}
        del bad["script_id"]
        assert validate_script_rules(bad)

    def test_missing_scenes_fails(self):
        bad = {**_VALID}
        del bad["scenes"]
        assert validate_script_rules(bad)

    def test_scene_missing_scene_id_fails(self):
        bad = copy.deepcopy(_VALID)
        del bad["scenes"][0]["scene_id"]
        assert validate_script_rules(bad)


class TestValidateScriptFile:

    def test_valid_file_returns_empty(self, valid_script_path: Path):
        assert validate_script_file(valid_script_path) == []

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(ValueError):
            validate_script_file(tmp_path / "no_such.json")

    def test_invalid_json_raises(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json}", encoding="utf-8")
        with pytest.raises(ValueError):
            validate_script_file(bad)


class TestCLIValidateScript:
    """End-to-end CLI tests — verify exact output and exit codes."""

    _EXE = "/home/tnnd/.virtualenvs/world-engine/bin/world-engine"

    def _run(self, *args: str):
        return subprocess.run(
            [self._EXE, *args],
            capture_output=True, text=True,
        )

    def test_cli_valid_script_exits_0(self, valid_script_path: Path):
        r = self._run("validate-script", "--script", str(valid_script_path))
        assert r.returncode == 0

    def test_cli_invalid_script_exits_1_exact_message(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({**_VALID, "schema_id": "WRONG"}), encoding="utf-8")
        r = self._run("validate-script", "--script", str(bad))
        assert r.returncode == 1
        assert r.stdout.strip() == "ERROR: invalid Script"

    def test_cli_missing_file_exits_1_exact_message(self, tmp_path: Path):
        r = self._run("validate-script", "--script", str(tmp_path / "ghost.json"))
        assert r.returncode == 1
        assert r.stdout.strip() == "ERROR: invalid Script"


class TestDeterminism:
    """Spec: run tests twice — same result."""

    def test_validate_rules_is_deterministic(self):
        r1 = validate_script_rules(_VALID)
        r2 = validate_script_rules(_VALID)
        assert r1 == r2

    def test_validate_rules_errors_deterministic(self):
        bad = {**_VALID, "schema_id": "Wrong"}
        assert validate_script_rules(bad) == validate_script_rules(bad)
