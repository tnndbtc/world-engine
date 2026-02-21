"""Script contract validator (validate-script command)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

_VALID_BEAT_TYPES = frozenset({"action", "dialogue", "character_enter", "character_exit"})


def validate_script_rules(data: dict) -> List[str]:
    """Validate *data* against Script contract rules.

    Returns a list of human-readable error strings; empty list means valid.
    Does NOT raise.
    """
    errors: List[str] = []

    # schema_id == "Script"
    if data.get("schema_id") != "Script":
        errors.append(f"schema_id must be 'Script', got {data.get('schema_id')!r}")

    # schema_version present
    if not data.get("schema_version"):
        errors.append("schema_version is required")

    # script_id present
    if not data.get("script_id"):
        errors.append("script_id is required")

    # characters[] present; each entry must have id
    characters = data.get("characters")
    if not isinstance(characters, list):
        errors.append("characters must be a list")
    else:
        for i, char in enumerate(characters):
            if not isinstance(char, dict) or not char.get("id"):
                errors.append(f"characters[{i}] must have an 'id'")

    # scenes[] present and non-empty
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or len(scenes) == 0:
        errors.append("scenes must be a non-empty list")
    else:
        for i, scene in enumerate(scenes):
            if not isinstance(scene, dict):
                errors.append(f"scenes[{i}] must be an object")
                continue
            if not scene.get("scene_id"):
                errors.append(f"scenes[{i}] must have scene_id")
            beats = scene.get("beats")
            if not isinstance(beats, list):
                errors.append(f"scenes[{i}] must have a beats list")
            else:
                for j, beat in enumerate(beats):
                    if not isinstance(beat, dict):
                        errors.append(f"scenes[{i}].beats[{j}] must be an object")
                        continue
                    beat_type = beat.get("type")
                    if beat_type not in _VALID_BEAT_TYPES:
                        errors.append(
                            f"scenes[{i}].beats[{j}].type must be one of "
                            f"{sorted(_VALID_BEAT_TYPES)}, got {beat_type!r}"
                        )
                    if beat_type == "dialogue":
                        if not beat.get("speaker"):
                            errors.append(f"scenes[{i}].beats[{j}] dialogue beat missing 'speaker'")
                        if not beat.get("line"):
                            errors.append(f"scenes[{i}].beats[{j}] dialogue beat missing 'line'")

    return errors


def validate_script_file(script_path: Path) -> List[str]:
    """Load JSON from *script_path* and run validate_script_rules().

    Raises:
        ValueError: if the file is missing or contains invalid JSON.
    """
    try:
        raw = script_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"Script file not found: {script_path}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {script_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Script must be a JSON object")

    return validate_script_rules(data)
