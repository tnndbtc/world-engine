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
    draft_parser = sub.add_parser(
        "validate-story-draft",
        help="Validate a Script JSON draft against a CanonSnapshot before compilation",
    )
    draft_parser.add_argument(
        "--draft", required=True, metavar="Script.json",
        help="Path to a Script JSON file to validate",
    )
    draft_parser.add_argument(
        "--canon", required=True, metavar="CanonSnapshot.json",
        help="Path to the current CanonSnapshot JSON file",
    )
    draft_parser.add_argument(
        "--out", required=False, metavar="CanonViolationReport.json",
        help="Optional path to write CanonViolationReport.json (only written on failure)",
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
        import jsonschema
        from world_engine.schema_loader import load_schema
        script_path = Path(args.script)
        if not script_path.exists():
            print("ERROR: invalid Script")
            sys.exit(1)
        try:
            data = json.loads(script_path.read_text(encoding="utf-8"))
            jsonschema.validate(data, load_schema("Script.v1.json"))
        except (json.JSONDecodeError, jsonschema.ValidationError, Exception):
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
    elif args.command == "validate-story-draft":
        _run_validate_story_draft(args)
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


def _run_validate_story_draft(args) -> None:
    """Handler for the validate-story-draft subcommand."""
    import jsonschema  # noqa: PLC0415

    from canon.canon_io import load_canon                          # noqa: PLC0415
    from world_engine.schema_loader import load_schema             # noqa: PLC0415
    from world_engine.story_draft_validator import validate_story_draft  # noqa: PLC0415

    draft_path = Path(args.draft)
    canon_path = Path(args.canon)

    # --- load and schema-validate the draft --------------------------------
    if not draft_path.exists():
        print(f"ERROR: draft file not found: {draft_path}")
        sys.exit(1)

    try:
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in draft: {exc}")
        sys.exit(1)

    try:
        jsonschema.validate(draft, load_schema("Script.v1.json"))
    except jsonschema.ValidationError as exc:
        print(f"ERROR: draft does not conform to Script.v1.json — {exc.message}")
        sys.exit(1)

    # --- load canon --------------------------------------------------------
    if not canon_path.exists():
        print(f"ERROR: canon file not found: {canon_path}")
        sys.exit(1)

    try:
        canon = load_canon(str(canon_path))
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in canon: {exc}")
        sys.exit(1)

    # --- validate ----------------------------------------------------------
    violations = validate_story_draft(draft, canon)

    if not violations:
        sys.exit(0)

    # --- violations found --------------------------------------------------
    project_id = draft.get("project_id", "unknown")
    episode_id = draft.get("script_id", "unknown")

    report = {
        "schema_id":      "CanonViolationReport",
        "schema_version": "1.0.0",
        "project_id":     project_id,
        "episode_id":     episode_id,
        "violations":     violations,
    }

    # validate report against its own schema before writing
    try:
        jsonschema.validate(report, load_schema("CanonViolationReport.v1.json"))
    except jsonschema.ValidationError:
        pass  # schema mismatch is a bug, not user error — still emit the report

    report_json = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False)
    print(report_json)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report_json + "\n", encoding="utf-8")

    sys.exit(1)


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
    canonical = {k: v for k, v in raw.items() if k != "producer"}
    canonical["schema_version"] = "1.0.0"

    # Validate BEFORE writing — raises ValidationError if non-conformant
    validate_shotlist(canonical)

    output_path.write_text(
        json.dumps(canonical, sort_keys=True, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
