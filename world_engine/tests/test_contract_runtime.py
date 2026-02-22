"""Integration test: real produce-shotlist workflow validates against canonical schema."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from world_engine.cli import produce_shotlist, validate_shotlist_file
from world_engine.contract_validate import validate_shotlist

_CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "third_party" / "contracts"


_MINIMAL_SCRIPT = {
    "schema_id": "Script",
    "schema_version": "1.0.0",
    "script_id": "runtime_test_script",
    "project_id": "test_project",
    "title": "Runtime Contract Test",
    "scenes": [
        {
            "scene_id": "rts_s001",
            "location": "Test Location",
            "time_of_day": "DAY",
            "actions": [],
        }
    ],
}


def test_produce_shotlist_rejects_invalid_contract_input(tmp_path: Path) -> None:
    """produce-shotlist must raise jsonschema.ValidationError for a Script that
    fails Script.v1.json validation — not an opaque Pydantic crash.

    Currently FAILS (Bug 1): no input validation against Script.v1.json is
    performed, so the error is a pydantic ValidationError, not a jsonschema one.
    """
    import jsonschema

    invalid_script = {"script_id": "x", "title": "y"}  # missing project_id, scenes, schema_version
    script_file = tmp_path / "script.json"
    script_file.write_text(json.dumps(invalid_script), encoding="utf-8")
    out_file = tmp_path / "shotlist.json"

    with pytest.raises(jsonschema.ValidationError):
        produce_shotlist(script_file, out_file)

    assert not out_file.exists(), "Output must not be written for invalid contract input"


def test_produce_shotlist_accepts_canonical_contract_script(tmp_path: Path) -> None:
    """produce-shotlist must accept a Script.json that is valid against Script.v1.json.

    Currently FAILS (Bug 2): the internal Pydantic Script model is structurally
    out of sync with the canonical contract (different field names, different
    array layout, missing created_at).
    """
    canonical_script = _CONTRACTS_DIR / "goldens" / "e2e" / "example_episode" / "Script.json"
    out_file = tmp_path / "shotlist.json"

    produce_shotlist(canonical_script, out_file)

    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    validate_shotlist(data)


def test_produce_shotlist_validates_against_canonical_schema(tmp_path: Path) -> None:
    """Output of produce_shotlist() must pass canonical ShotList.v1.json validation."""
    script_file = tmp_path / "script.json"
    script_file.write_text(json.dumps(_MINIMAL_SCRIPT), encoding="utf-8")
    out_file = tmp_path / "shotlist.json"

    produce_shotlist(script_file, out_file)

    data = json.loads(out_file.read_text(encoding="utf-8"))
    validate_shotlist(data)


def test_validate_shotlist_file_accepts_valid(tmp_path: Path) -> None:
    """validate-shotlist accepts a ShotList that conforms to ShotList.v1.json."""
    script_file = tmp_path / "script.json"
    script_file.write_text(json.dumps(_MINIMAL_SCRIPT), encoding="utf-8")
    out_file = tmp_path / "shotlist.json"
    produce_shotlist(script_file, out_file)

    # Must not raise
    validate_shotlist_file(out_file)


def test_validate_shotlist_file_rejects_invalid(tmp_path: Path) -> None:
    """validate-shotlist raises jsonschema.ValidationError for a non-conformant file."""
    import jsonschema

    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json.dumps({"not": "a shotlist"}), encoding="utf-8")

    with pytest.raises(jsonschema.ValidationError):
        validate_shotlist_file(bad_file)
