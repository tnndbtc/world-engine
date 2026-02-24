"""
story_draft_validator.py — Validate a Script.json draft against a Canon snapshot.

Phase 0 checks
--------------
For each character that *appears* in the script (speaks or acts), the validator
asserts that character is alive in canon.  A character is considered to "appear"
if their ID is found in:
  - the top-level ``characters`` list (``[{"id": "<char_id>", ...}]``), OR
  - the ``character`` field of any dialogue action in any scene.

Additionally, if the script's ``characters`` list carries explicit facts
(name, age, alive, location), those are checked against canon too.

The validator constructs a synthetic CanonDiff and passes it through the
existing ``check_hard_contradictions`` in ``gate.py`` — no new gate logic.

Return value
------------
    []                  — draft is canon-consistent; no violations.
    [violation, ...]    — one dict per hard contradiction:
        {
            "field":       "characters.<char_id>.<fact>",
            "canon_value": <current canon value>,
            "draft_value": <implied or explicit draft value>,
            "message":     "CONTRADICTION: ...",
        }
"""

from __future__ import annotations

import re
from typing import Any

from canon.contract import Canon
from canon.gate import check_hard_contradictions


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_characters(script: dict) -> dict[str, dict[str, Any]]:
    """Return a mapping of char_id → explicit facts extracted from *script*.

    Sources (in priority order):
    1. ``script["characters"]`` list — each entry with at least ``{"id": ...}``;
       optional keys: name, age, alive, location.
    2. ``character`` field of dialogue actions across all scenes — char_id only,
       no additional facts.

    Characters from source 2 that are already covered by source 1 are not
    duplicated.
    """
    chars: dict[str, dict[str, Any]] = {}

    # Source 1: explicit characters list
    for entry in script.get("characters") or []:
        if not isinstance(entry, dict):
            continue
        char_id = entry.get("id")
        if not char_id or not isinstance(char_id, str):
            continue
        facts: dict[str, Any] = {}
        for fact_key in ("name", "age", "alive", "location"):
            if fact_key in entry:
                facts[fact_key] = entry[fact_key]
        chars[char_id] = facts

    # Source 2: dialogue actions
    for scene in script.get("scenes") or []:
        for action in scene.get("actions") or []:
            if action.get("type") != "dialogue":
                continue
            char_id = action.get("character") or action.get("speaker")
            if not char_id or not isinstance(char_id, str):
                continue
            if char_id not in chars:
                chars[char_id] = {}   # no explicit facts — just presence

    return chars


def _parse_contradiction_message(message: str) -> dict[str, Any]:
    """Parse a CONTRADICTION error string from gate.py into a violation dict.

    Expected format produced by gate.py:
        "CONTRADICTION: characters.<char_id>.<field> — canon='<v>' vs diff='<v>'"

    Falls back to a generic violation dict if the format doesn't match.
    """
    pattern = re.compile(
        r"CONTRADICTION: (characters\.\S+)\s+[—-]+\s+canon='?([^']*)'?\s+vs\s+diff='?([^']*)'"
    )
    m = pattern.search(message)
    if m:
        return {
            "field":       m.group(1),
            "canon_value": m.group(2),
            "draft_value": m.group(3),
            "message":     message,
        }
    # Fallback for INVALID_DIFF or unexpected formats
    return {
        "field":       "unknown",
        "canon_value": None,
        "draft_value": None,
        "message":     message,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_story_draft(script: dict, canon: Canon) -> list[dict]:
    """Validate *script* against *canon* and return a list of violations.

    Args:
        script: A Script.json dict (must have passed Script.v1.json schema check).
        canon:  The current CanonSnapshot dict for the project.

    Returns:
        Empty list if the script is canon-consistent.
        List of violation dicts (see module docstring) if contradictions are found.
    """
    chars = _extract_characters(script)
    if not chars:
        return []  # no characters to check

    canon_chars: dict = canon.get("characters", {})

    modified_facts: dict[str, dict[str, Any]] = {}

    for char_id, explicit_facts in chars.items():
        if char_id not in canon_chars:
            # Character not in canon — no contradiction possible (not yet defined)
            continue

        char_facts: dict[str, Any] = {}

        # Appearance in script implies the character is alive
        char_facts["alive"] = True

        # Merge any explicit facts from the script's characters list
        for fact_key in ("name", "age", "alive", "location"):
            if fact_key in explicit_facts:
                char_facts[fact_key] = explicit_facts[fact_key]

        if char_facts:
            modified_facts[char_id] = char_facts

    if not modified_facts:
        return []

    diff: dict = {"modified_facts": {"characters": modified_facts}}
    error_strings = check_hard_contradictions(canon, diff)

    return [_parse_contradiction_message(e) for e in error_strings]
