import json

import jsonschema

from .schema_loader import load_schema
from .schemas.shotlist_v1 import canonical_json_bytes


def validate_shotlist(data: dict) -> None:
    """Validate a ShotList dict against the canonical ShotList.v1.json contract.

    Raises jsonschema.ValidationError if non-conformant.
    """
    schema = load_schema("ShotList.v1.json")
    jsonschema.validate(data, schema)


def validate_shotlist_model(sl) -> None:
    """Validate a ShotList model against the canonical ShotList.v1.json contract.

    Projects the model to canonical format (strips internal-only fields
    ``producer`` and ``schema_id``; pins ``schema_version`` to ``"1.0.0"``)
    then validates against the JSON Schema.

    Raises jsonschema.ValidationError if the projected artifact is non-conformant.
    """
    raw = json.loads(canonical_json_bytes(sl).decode("utf-8"))
    canonical = {k: v for k, v in raw.items() if k != "producer"}
    canonical["schema_version"] = "1.0.0"
    validate_shotlist(canonical)
