from pathlib import Path
import json

def load_schema(name: str):
    root = Path(__file__).resolve().parents[1]
    schema_path = root / "third_party" / "contracts" / "schemas" / name
    if not schema_path.exists():
        raise FileNotFoundError(f"Missing canonical schema: {schema_path}")
    return json.loads(schema_path.read_text())
