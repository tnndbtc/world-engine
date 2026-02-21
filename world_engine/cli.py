"""world-engine CLI entry point (Wave-5)."""
from __future__ import annotations

import argparse
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
    else:
        parser.print_help()
        sys.exit(1)
