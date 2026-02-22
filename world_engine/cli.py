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
    elif args.command == "produce-shotlist":
        produce_shotlist(Path(args.script), Path(args.output))
    else:
        parser.print_help()
        sys.exit(1)


def produce_shotlist(script_path: Path, output_path: Path) -> None:
    """Adapt script → canonical ShotList, validate against contracts, write file.

    Raises jsonschema.ValidationError if the produced artifact does not conform
    to third_party/contracts/schemas/ShotList.v1.json.  The output file is
    never written when validation fails.
    """
    from world_engine.adaptation.adapter import adapt_script
    from world_engine.adaptation.models import Script
    from world_engine.contract_validate import validate_shotlist
    from world_engine.schemas.shotlist_v1 import canonical_json_bytes

    script = Script.model_validate(json.loads(script_path.read_text(encoding="utf-8")))
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
