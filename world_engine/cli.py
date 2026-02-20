"""world-engine CLI entry point (Wave-5)."""
from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="world-engine",
        description="World Engine — narrative-to-video platform",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.add_parser("verify", help="Run contract vector verification")
    args = parser.parse_args()

    if args.command == "verify":
        from world_engine.verify import run_verify
        if run_verify():
            print("OK: world-engine verified")
            sys.exit(0)
        else:
            print("ERROR: world-engine verification failed")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)
