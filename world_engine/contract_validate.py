import jsonschema
from .schema_loader import load_schema


def validate_shotlist(data: dict):
    schema = load_schema("ShotList.v1.json")
    jsonschema.validate(data, schema)
