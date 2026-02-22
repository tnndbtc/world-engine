"""world-engine CLI entry point (Wave-5)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="world-engine",
        description="World Engine — narrative-to-video platform",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.add_parser("verify", help="Run contract vector verification")
    validate_parser = sub.add_parser("validate-script", help="Validate a Script JSON file")
    validate_parser.add_argument(
        "--script", required=True, metavar="script.json",
        help="Path to a Script JSON file",
    )
    validate_shotlist_parser = sub.add_parser(
        "validate-shotlist",
        help="Validate an existing ShotList JSON file against the canonical contract",
    )
    validate_shotlist_parser.add_argument(
        "--shotlist", required=True, metavar="shotlist.json",
        help="Path to a ShotList JSON file",
    )
    produce_parser = sub.add_parser(
        "produce-shotlist",
        help="Adapt a Script JSON → validated canonical ShotList JSON",
    )
    produce_parser.add_argument(
        "--script", required=True, metavar="script.json",
        help="Path to a Script JSON file",
    )
    produce_parser.add_argument(
        "--output", required=True, metavar="shotlist.json",
        help="Destination path for the canonical ShotList JSON",
    )
    args = parser.parse_args()

    if args.command == "verify":
        from world_engine.verify import run_verify
        if run_verify():
            print("OK: world-engine verified")
            sys.exit(0)
        else:
            print("ERROR: world-engine verification failed")
            sys.exit(1)
    elif args.command == "validate-script":
        from world_engine.validator import validate_script_file
        try:
            errors = validate_script_file(Path(args.script))
        except (ValueError, Exception):
            print("ERROR: invalid Script")
            sys.exit(1)
        if errors:
            print("ERROR: invalid Script")
            sys.exit(1)
        sys.exit(0)
    elif args.command == "validate-shotlist":
        import jsonschema
        try:
            validate_shotlist_file(Path(args.shotlist))
        except jsonschema.ValidationError as exc:
            print(f"ERROR: invalid ShotList — {exc.message}")
            sys.exit(1)
        except Exception as exc:
            print(f"ERROR: {exc}")
            sys.exit(1)
        print("OK: ShotList is valid")
        sys.exit(0)
    elif args.command == "produce-shotlist":
        produce_shotlist(Path(args.script), Path(args.output))
    else:
        parser.print_help()
        sys.exit(1)


def validate_shotlist_file(shotlist_path: Path) -> None:
    """Load a ShotList JSON file and validate it against the canonical contract.

    Raises ``jsonschema.ValidationError`` if the file does not conform to
    ``third_party/contracts/schemas/ShotList.v1.json``.
    """
    from world_engine.contract_validate import validate_shotlist

    data = json.loads(shotlist_path.read_text(encoding="utf-8"))
    validate_shotlist(data)


def _contract_to_internal(data: dict) -> dict:
    """Map canonical Script.v1.json structure to internal Pydantic Script format.

    The canonical contract uses a flat ``actions`` array with typed items::

        {"type": "dialogue", "character": "X", "text": "..."  }
        {"type": "action",   "text": "..."                     }

    Field-name variants accepted: ``character`` or ``speaker`` for the
    speaker ID; ``text`` or ``line`` for content.

    The internal model uses separate ``dialogue`` and ``actions`` lists, and
    requires ``created_at`` (which the contract makes optional).
    """
    internal_scenes = []
    for scene in data.get("scenes", []):
        dialogue: list = []
        actions: list = []
        characters: list = []
        for item in scene.get("actions", []):
            text = item.get("text") or item.get("line", "")
            if item.get("type") == "dialogue":
                speaker = item.get("character") or item.get("speaker", "")
                dialogue.append({"speaker_id": speaker, "text": text})
                if speaker and speaker not in characters:
                    characters.append(speaker)
            else:
                actions.append({
                    "description": text,
                    "characters": item.get("characters", []),
                })
        internal_scenes.append({
            "scene_id": scene["scene_id"],
            "location": scene["location"],
            "time_of_day": scene["time_of_day"],
            "characters": characters,
            "dialogue": dialogue,
            "actions": actions,
        })
    return {
        "script_id": data["script_id"],
        "title": data["title"],
        # created_at is optional in the contract; internal model requires it
        "created_at": data.get("created_at", "1970-01-01T00:00:00Z"),
        "episode_id": data.get("episode_id"),
        "scenes": internal_scenes,
    }


def produce_shotlist(script_path: Path, output_path: Path) -> None:
    """Adapt script → canonical ShotList, validate against contracts, write file.

    Raises ``jsonschema.ValidationError`` if:
    - the input Script.json does not conform to ``Script.v1.json``, or
    - the produced ShotList does not conform to ``ShotList.v1.json``.

    The output file is never written when validation fails.
    """
    import jsonschema  # noqa: PLC0415
    from world_engine.adaptation.adapter import adapt_script
    from world_engine.adaptation.models import Script
    from world_engine.contract_validate import validate_shotlist
    from world_engine.schema_loader import load_schema
    from world_engine.schemas.shotlist_v1 import canonical_json_bytes

    raw_data = json.loads(script_path.read_text(encoding="utf-8"))

    # Bug 1 fix: validate input against canonical Script.v1.json BEFORE Pydantic.
    # Raises jsonschema.ValidationError on any contract violation.
    jsonschema.validate(raw_data, load_schema("Script.v1.json"))

    # Bug 2 fix: map canonical contract format → internal Pydantic format.
    script = Script.model_validate(_contract_to_internal(raw_data))
    sl = adapt_script(script)

    # Project to canonical v1.0.0 format:
    #   • remove internal-only fields not present in the canonical schema
    #     (producer, schema_id) so additionalProperties:false is satisfied
    #   • pin schema_version to the canonical constant "1.0.0"
    raw = json.loads(canonical_json_bytes(sl).decode("utf-8"))
    canonical = {k: v for k, v in raw.items() if k not in ("producer", "schema_id")}
    canonical["schema_version"] = "1.0.0"

    # Validate BEFORE writing — raises ValidationError if non-conformant
    validate_shotlist(canonical)

    output_path.write_text(
        json.dumps(canonical, sort_keys=True, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
