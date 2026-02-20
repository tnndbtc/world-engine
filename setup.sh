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

while true; do
    echo ""
    echo "world-engine — dev menu"
    echo "  1) Run Tests"
    echo "  0) Exit"
    echo ""
    read -rp "Choice: " choice
    case "$choice" in
        1) run_tests ;;
        0) echo "Bye."; exit 0 ;;
        *) echo "Unknown option: $choice" ;;
    esac
done
