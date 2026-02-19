"""
diff.py — CanonDiff structural validation and pure application.

validate_diff  — checks shape/types only; no canon-awareness.
apply_diff     — merges a validated diff into a Canon; pure, no side-effects.
"""

import copy
from typing import List

from .contract import Canon, CanonDiff

_ALLOWED_TOP_KEYS = frozenset(
    {"modified_facts", "added_facts", "removed_facts", "justification", "provenance"}
)


def validate_diff(diff: CanonDiff) -> List[str]:
    """Structural validation of a CanonDiff.

    Checks types and shapes only — does not look at Canon state.

    Returns:
        List of error strings; empty list means the diff is structurally valid.
    """
    errors: List[str] = []

    if not isinstance(diff, dict):
        return ["INVALID_DIFF: diff must be a dict"]

    unknown = set(diff.keys()) - _ALLOWED_TOP_KEYS
    if unknown:
        errors.append(
            f"INVALID_DIFF: unknown top-level keys: {sorted(unknown)}"
        )

    for key in ("modified_facts", "added_facts"):
        if key in diff and not isinstance(diff[key], dict):
            errors.append(f"INVALID_DIFF: '{key}' must be a dict")

    if "removed_facts" in diff:
        rf = diff["removed_facts"]
        if not isinstance(rf, dict):
            errors.append("INVALID_DIFF: 'removed_facts' must be a dict")
        else:
            for section, keys in rf.items():
                if not isinstance(keys, list):
                    errors.append(
                        f"INVALID_DIFF: removed_facts.{section} must be a list of str keys"
                    )
                elif not all(isinstance(k, str) for k in keys):
                    errors.append(
                        f"INVALID_DIFF: removed_facts.{section} must contain only str keys"
                    )

    return errors


def apply_diff(canon: Canon, diff: CanonDiff) -> Canon:
    """Apply a CanonDiff to a Canon and return the updated Canon.

    Pure function — the input *canon* is never mutated.
    Assumes the diff has already been validated (validate_diff returned []).

    Merge order:
        1. added_facts   — insert new entries (do not overwrite existing)
        2. modified_facts — shallow-merge field updates into existing entries
        3. removed_facts  — delete listed keys from their sections

    Args:
        canon: Current Canon state.
        diff:  A structurally valid CanonDiff.

    Returns:
        A new Canon dict reflecting the applied changes.
    """
    new_canon: Canon = copy.deepcopy(canon)

    # 1. added_facts — add new characters/entries; skip if key already exists
    for section, entries in diff.get("added_facts", {}).items():
        if isinstance(entries, dict):
            if section not in new_canon or not isinstance(new_canon[section], dict):
                new_canon[section] = {}
            for entry_id, data in entries.items():
                if entry_id not in new_canon[section]:
                    new_canon[section][entry_id] = copy.deepcopy(data)
        elif isinstance(entries, list):
            if section not in new_canon or not isinstance(new_canon[section], list):
                new_canon[section] = []
            new_canon[section].extend(copy.deepcopy(entries))

    # 2. modified_facts — shallow-merge updates into existing entries
    for section, entries in diff.get("modified_facts", {}).items():
        if isinstance(entries, dict):
            if section not in new_canon or not isinstance(new_canon[section], dict):
                new_canon[section] = {}
            for entry_id, data in entries.items():
                if isinstance(data, dict):
                    if entry_id not in new_canon[section]:
                        new_canon[section][entry_id] = {}
                    new_canon[section][entry_id].update(copy.deepcopy(data))

    # 3. removed_facts — delete keys from dict sections
    for section, keys in diff.get("removed_facts", {}).items():
        section_data = new_canon.get(section)
        if isinstance(section_data, dict):
            for key in keys:
                section_data.pop(key, None)
        elif isinstance(section_data, list):
            new_canon[section] = [e for e in section_data if e not in keys]

    return new_canon
