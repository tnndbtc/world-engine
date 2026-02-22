"""Integration test: real produce-shotlist workflow validates against canonical schema."""
from __future__ import annotations

import json
from pathlib import Path

from world_engine.cli import produce_shotlist
from world_engine.contract_validate import validate_shotlist


_MINIMAL_SCRIPT = {
    "script_id": "runtime_test_script",
    "title": "Runtime Contract Test",
    "created_at": "1970-01-01T00:00:00Z",
    "scenes": [
        {
            "scene_id": "rts_s001",
            "location": "Test Location",
            "time_of_day": "DAY",
        }
    ],
}


def test_produce_shotlist_validates_against_canonical_schema(tmp_path: Path) -> None:
    """Output of produce_shotlist() must pass canonical ShotList.v1.json validation."""
    script_file = tmp_path / "script.json"
    script_file.write_text(json.dumps(_MINIMAL_SCRIPT), encoding="utf-8")
    out_file = tmp_path / "shotlist.json"

    produce_shotlist(script_file, out_file)

    data = json.loads(out_file.read_text(encoding="utf-8"))
    validate_shotlist(data)
