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
    echo ""
    echo "Smoke test — produce and validate a ShotList:"
    echo ""
    _ts="$(date '+%Y%m%d_%H%M%S')"
    _out="/tmp/ShotList_${_ts}.json"
    echo "  \$ world-engine produce-shotlist \\"
    echo "      --script  third_party/contracts/goldens/e2e/example_episode/Script.json \\"
    echo "      --output  ${_out}"
    world-engine produce-shotlist \
        --script  third_party/contracts/goldens/e2e/example_episode/Script.json \
        --output  "${_out}"
    echo ""
    echo "  \$ world-engine validate-shotlist --shotlist ${_out}"
    world-engine validate-shotlist --shotlist "${_out}"
    rm -f "${_out}"
    echo "  (cleaned up ${_out})"
    echo ""
    echo "──────────────────────────────────────────────"
    read -rp "Press ENTER to return to the menu..."
}

install_requirements() {
    echo ""
    echo "Installing requirements..."
    echo "──────────────────────────────────────────────"

    local pip_cmd
    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        pip_cmd="$VIRTUAL_ENV/bin/pip"
    elif command -v pip3 &>/dev/null; then
        pip_cmd="pip3"
    elif command -v pip &>/dev/null; then
        pip_cmd="pip"
    else
        echo "Error: pip not found. Please install Python/pip first." >&2
        return 1
    fi

    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local req_file="${script_dir}/requirements.txt"

    if [[ ! -f "$req_file" ]]; then
        echo "Error: requirements.txt not found at ${req_file}" >&2
        return 1
    fi

    echo "  \$ ${pip_cmd} install -r ${req_file}"
    "$pip_cmd" install -r "$req_file"

    echo "──────────────────────────────────────────────"
    echo "Done. All requirements installed."
    echo ""
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
    echo "  2) Install requirements"
    echo "  3) Show Usage"
    echo "  0) Exit"
    echo ""
    read -rp "Choice: " choice
    case "$choice" in
        1) run_tests ;;
        2) install_requirements ;;
        3) show_usage ;;
        0) echo "Bye."; exit 0 ;;
        *) echo "Unknown option: $choice" ;;
    esac
done
