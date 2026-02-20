"""canon_snapshot_v1 — CanonSnapshot loader (Wave-6)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from world_engine.adaptation.models import CanonSnapshot


def load_canon_snapshot_strict(
    source: Union[str, bytes, dict, Path],
) -> CanonSnapshot:
    """Load and validate a CanonSnapshot.

    Raises:
        ValueError: "ERROR: invalid CanonSnapshot input"  (exact string, always)
    """
    try:
        if isinstance(source, Path):
            data = json.loads(source.read_text(encoding="utf-8"))
        elif isinstance(source, (str, bytes)):
            data = json.loads(source)
        else:
            data = source
        return CanonSnapshot.model_validate(data)
    except Exception:
        raise ValueError("ERROR: invalid CanonSnapshot input")
