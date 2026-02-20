"""Script schema v1.0.0 — load, dump, validate.

Canonical JSON (sort_keys=True) ensures byte-identical serialization of
identical models regardless of Python dict insertion order.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Union

from pydantic import ValidationError

from world_engine.adaptation.models import Script

SCHEMA_VERSION = "1.0.0"


def load_script(source: Union[str, bytes, dict, Path]) -> Script:
    """Parse a Script from JSON string, bytes, dict, or file Path.

    Raises:
        ValidationError: data does not conform to the Script schema.
        FileNotFoundError: Path does not exist.
    """
    if isinstance(source, Path):
        data = json.loads(source.read_text(encoding="utf-8"))
    elif isinstance(source, (str, bytes)):
        data = json.loads(source)
    else:
        data = source
    return Script.model_validate(data)


def dump_script(script: Script, *, indent: int = 2) -> str:
    """Serialize a Script to canonical JSON (sort_keys=True, indent=2).

    sort_keys=True guarantees byte-identical output for identical models
    (Determinism First principle, §2).
    """
    raw = json.loads(script.model_dump_json())
    return json.dumps(raw, sort_keys=True, indent=indent, ensure_ascii=False)


def validate_script(data: dict) -> List[str]:
    """Validate a raw dict against the Script schema.

    Returns a list of human-readable error strings (empty list = valid).
    Does not raise.
    """
    try:
        Script.model_validate(data)
        return []
    except ValidationError as exc:
        return [f"{e['loc']}: {e['msg']}" for e in exc.errors()]
