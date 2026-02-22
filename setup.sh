#!/usr/bin/env bash
# setup.sh — development helper for world-engine
# Usage: ./setup.sh

set -euo pipefail

run_tests() {
    echo ""
    echo "Running tests..."
    echo "──────────────────────────────────────────────"
    python -m pytest -q
    echo "──────────────────────────────────────────────"
    read -rp "Press ENTER to return to the menu..."
}

show_usage() {
    echo ""
    echo "world-engine — command usage"
    echo "──────────────────────────────────────────────"
    echo ""
    echo "Produce a ShotList from a Script:"
    echo ""
    echo "  world-engine produce-shotlist \\"
    echo "    --script  path/to/Script.json \\"
    echo "    --output  path/to/ShotList.json"
    echo ""
    echo "  Input  : Script.json must conform to Script.v1.json"
    echo "  Output : ShotList.json validated against ShotList.v1.json"
    echo "           (file is not written if validation fails)"
    echo ""
    echo "──────────────────────────────────────────────"
    echo ""
    echo "Validate an existing ShotList:"
    echo ""
    echo "  world-engine validate-shotlist \\"
    echo "    --shotlist path/to/ShotList.json"
    echo ""
    echo "  Exit 0 : OK — ShotList is valid"
    echo "  Exit 1 : ERROR — prints the failing constraint"
    echo ""
    echo "──────────────────────────────────────────────"
    read -rp "Press ENTER to return to the menu..."
}

while true; do
    echo ""
    echo "world-engine — dev menu"
    echo "  1) Run Tests"
    echo "  2) Show Usage"
    echo "  0) Exit"
    echo ""
    read -rp "Choice: " choice
    case "$choice" in
        1) run_tests ;;
        2) show_usage ;;
        0) echo "Bye."; exit 0 ;;
        *) echo "Unknown option: $choice" ;;
    esac
done
