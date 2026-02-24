"""CLI tests for the validate-story-draft subcommand."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from world_engine.tests.test_validate_script import _world_engine_cmd


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_SCRIPT = {
    "schema_id": "Script",
    "schema_version": "1.0.0",
    "script_id": "s001",
    "project_id": "proj1",
    "title": "Test Episode",
    "scenes": [
        {
            "scene_id": "sc001",
            "location": "INT. HALL",
            "time_of_day": "DAY",
            "actions": [
                {"type": "dialogue", "character": "char_lena", "text": "Hello."},
            ],
        }
    ],
}

_CANON_WITH_LENA = {
    "characters": {
        "char_lena": {"name": "Lena", "age": 30, "alive": True, "location": "Castle"},
    }
}

_CANON_WITH_DEAD_LENA = {
    "characters": {
        "char_lena": {"name": "Lena", "age": 30, "alive": False, "location": "Castle"},
    }
}


def _write(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _run(*args: str):
    return subprocess.run(
        [*_world_engine_cmd(), *args],
        capture_output=True, text=True,
    )


# ---------------------------------------------------------------------------
# Exit code 0 — valid draft
# ---------------------------------------------------------------------------

class TestValidDraftExits0:

    def test_alive_character_exits_0(self, tmp_path: Path):
        draft = _write(tmp_path / "Script.json", _VALID_SCRIPT)
        canon = _write(tmp_path / "Canon.json", _CANON_WITH_LENA)
        r = _run("validate-story-draft", "--draft", str(draft), "--canon", str(canon))
        assert r.returncode == 0

    def test_character_not_in_canon_exits_0(self, tmp_path: Path):
        """A character in the script but absent from canon is not a violation."""
        draft = _write(tmp_path / "Script.json", _VALID_SCRIPT)
        canon = _write(tmp_path / "Canon.json", {"characters": {}})
        r = _run("validate-story-draft", "--draft", str(draft), "--canon", str(canon))
        assert r.returncode == 0

    def test_no_out_file_written_on_success(self, tmp_path: Path):
        draft = _write(tmp_path / "Script.json", _VALID_SCRIPT)
        canon = _write(tmp_path / "Canon.json", _CANON_WITH_LENA)
        out = tmp_path / "report.json"
        _run("validate-story-draft", "--draft", str(draft), "--canon", str(canon),
             "--out", str(out))
        assert not out.exists()

    def test_stdout_is_empty_on_success(self, tmp_path: Path):
        draft = _write(tmp_path / "Script.json", _VALID_SCRIPT)
        canon = _write(tmp_path / "Canon.json", _CANON_WITH_LENA)
        r = _run("validate-story-draft", "--draft", str(draft), "--canon", str(canon))
        assert r.stdout.strip() == ""


# ---------------------------------------------------------------------------
# Exit code 1 — violations found
# ---------------------------------------------------------------------------

class TestViolationsExits1:

    def test_dead_character_exits_1(self, tmp_path: Path):
        draft = _write(tmp_path / "Script.json", _VALID_SCRIPT)
        canon = _write(tmp_path / "Canon.json", _CANON_WITH_DEAD_LENA)
        r = _run("validate-story-draft", "--draft", str(draft), "--canon", str(canon))
        assert r.returncode == 1

    def test_violation_report_written_to_out(self, tmp_path: Path):
        draft = _write(tmp_path / "Script.json", _VALID_SCRIPT)
        canon = _write(tmp_path / "Canon.json", _CANON_WITH_DEAD_LENA)
        out = tmp_path / "report.json"
        _run("validate-story-draft", "--draft", str(draft), "--canon", str(canon),
             "--out", str(out))
        assert out.exists()

    def test_violation_report_is_valid_json(self, tmp_path: Path):
        draft = _write(tmp_path / "Script.json", _VALID_SCRIPT)
        canon = _write(tmp_path / "Canon.json", _CANON_WITH_DEAD_LENA)
        out = tmp_path / "report.json"
        _run("validate-story-draft", "--draft", str(draft), "--canon", str(canon),
             "--out", str(out))
        report = json.loads(out.read_text())
        assert report["schema_id"] == "CanonViolationReport"
        assert report["project_id"] == "proj1"
        assert len(report["violations"]) >= 1

    def test_violation_report_printed_to_stdout(self, tmp_path: Path):
        draft = _write(tmp_path / "Script.json", _VALID_SCRIPT)
        canon = _write(tmp_path / "Canon.json", _CANON_WITH_DEAD_LENA)
        r = _run("validate-story-draft", "--draft", str(draft), "--canon", str(canon))
        parsed = json.loads(r.stdout)
        assert parsed["schema_id"] == "CanonViolationReport"
        assert len(parsed["violations"]) >= 1

    def test_violations_contain_required_fields(self, tmp_path: Path):
        draft = _write(tmp_path / "Script.json", _VALID_SCRIPT)
        canon = _write(tmp_path / "Canon.json", _CANON_WITH_DEAD_LENA)
        r = _run("validate-story-draft", "--draft", str(draft), "--canon", str(canon))
        report = json.loads(r.stdout)
        v = report["violations"][0]
        assert "field" in v
        assert "canon_value" in v
        assert "draft_value" in v
        assert "message" in v


# ---------------------------------------------------------------------------
# Exit code 1 — bad inputs
# ---------------------------------------------------------------------------

class TestBadInputsExit1:

    def test_missing_draft_file_exits_1(self, tmp_path: Path):
        canon = _write(tmp_path / "Canon.json", _CANON_WITH_LENA)
        r = _run("validate-story-draft",
                 "--draft", str(tmp_path / "ghost.json"),
                 "--canon", str(canon))
        assert r.returncode == 1
        assert "not found" in r.stdout

    def test_missing_canon_file_exits_1(self, tmp_path: Path):
        draft = _write(tmp_path / "Script.json", _VALID_SCRIPT)
        r = _run("validate-story-draft",
                 "--draft", str(draft),
                 "--canon", str(tmp_path / "ghost.json"))
        assert r.returncode == 1
        assert "not found" in r.stdout

    def test_invalid_json_draft_exits_1(self, tmp_path: Path):
        draft = tmp_path / "bad.json"
        draft.write_text("{not json}", encoding="utf-8")
        canon = _write(tmp_path / "Canon.json", _CANON_WITH_LENA)
        r = _run("validate-story-draft", "--draft", str(draft), "--canon", str(canon))
        assert r.returncode == 1

    def test_draft_failing_schema_validation_exits_1(self, tmp_path: Path):
        """Draft missing required Script.v1.json fields is rejected before canon check."""
        bad_script = {"schema_id": "Script", "schema_version": "1.0.0"}  # missing title etc.
        draft = _write(tmp_path / "Script.json", bad_script)
        canon = _write(tmp_path / "Canon.json", _CANON_WITH_LENA)
        r = _run("validate-story-draft", "--draft", str(draft), "--canon", str(canon))
        assert r.returncode == 1
        assert "Script.v1.json" in r.stdout


# ---------------------------------------------------------------------------
# Contract conformance — emitted report must satisfy CanonViolationReport.v1.json
# ---------------------------------------------------------------------------

class TestReportConformsToSchema:

    def test_violation_report_conforms_to_schema(self, tmp_path: Path):
        """The JSON printed to stdout must validate against CanonViolationReport.v1.json."""
        import jsonschema
        from world_engine.schema_loader import load_schema

        draft = _write(tmp_path / "Script.json", _VALID_SCRIPT)
        canon = _write(tmp_path / "Canon.json", _CANON_WITH_DEAD_LENA)
        r = _run("validate-story-draft", "--draft", str(draft), "--canon", str(canon))
        assert r.returncode == 1

        report = json.loads(r.stdout)
        schema = load_schema("CanonViolationReport.v1.json")
        # Raises jsonschema.ValidationError if report does not conform
        jsonschema.validate(report, schema)

    def test_written_out_file_conforms_to_schema(self, tmp_path: Path):
        """The --out file must also validate against CanonViolationReport.v1.json."""
        import jsonschema
        from world_engine.schema_loader import load_schema

        draft = _write(tmp_path / "Script.json", _VALID_SCRIPT)
        canon = _write(tmp_path / "Canon.json", _CANON_WITH_DEAD_LENA)
        out = tmp_path / "report.json"
        _run("validate-story-draft", "--draft", str(draft), "--canon", str(canon),
             "--out", str(out))

        report = json.loads(out.read_text())
        schema = load_schema("CanonViolationReport.v1.json")
        jsonschema.validate(report, schema)

    def test_report_schema_id_and_version_are_correct(self, tmp_path: Path):
        draft = _write(tmp_path / "Script.json", _VALID_SCRIPT)
        canon = _write(tmp_path / "Canon.json", _CANON_WITH_DEAD_LENA)
        r = _run("validate-story-draft", "--draft", str(draft), "--canon", str(canon))
        report = json.loads(r.stdout)
        assert report["schema_id"] == "CanonViolationReport"
        assert report["schema_version"] == "1.0.0"
