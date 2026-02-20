"""ShotList schema v1.0.0 — load, dump, validate."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Union

from pydantic import ValidationError

from world_engine.adaptation.models import ShotList

SCHEMA_VERSION = "0.0.1"


def load_shotlist(source: Union[str, bytes, dict, Path]) -> ShotList:
    """Parse a ShotList from JSON string, bytes, dict, or file Path.

    Raises:
        ValidationError: data does not conform to the ShotList schema.
        FileNotFoundError: Path does not exist.
    """
    if isinstance(source, Path):
        data = json.loads(source.read_text(encoding="utf-8"))
    elif isinstance(source, (str, bytes)):
        data = json.loads(source)
    else:
        data = source
    return ShotList.model_validate(data)


def dump_shotlist(shotlist: ShotList, *, indent: int = 2) -> str:
    """Serialize a ShotList to canonical JSON (sort_keys=True, indent=2)."""
    raw = json.loads(shotlist.model_dump_json())
    return json.dumps(raw, sort_keys=True, indent=indent, ensure_ascii=False)


def canonical_json_bytes(shotlist: ShotList) -> bytes:
    """Return canonical UTF-8 bytes for a ShotList (sort_keys=True, indent=2).

    Used by vector verification tests to produce a byte-stable artifact.
    Identical algorithm to dump_shotlist() but returns bytes, not str.
    """
    raw = json.loads(shotlist.model_dump_json())
    return json.dumps(raw, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")


def validate_shotlist(data: dict) -> List[str]:
    """Validate a raw dict against the ShotList schema.

    Returns a list of human-readable error strings (empty list = valid).
    Does not raise.
    """
    try:
        ShotList.model_validate(data)
        return []
    except ValidationError as exc:
        return [f"{e['loc']}: {e['msg']}" for e in exc.errors()]
