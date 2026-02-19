"""
gate.py — Canon Gate: hard-contradiction detection for Phase 0.

check_hard_contradictions enforces four immutable fields per character:
  name, age, alive (death status), location.

Character entries are keyed by a stable character_id (e.g. "char_lena"),
which is distinct from the human-readable "name" field inside the entry.

Phase 0 rules:
  - NO auto-repair
  - Contradictions are returned as structured error strings; Canon is unchanged.
  - A modified_facts entry for a character_id that does not exist in canon
    AND is not being introduced via added_facts in the same diff is itself an
    error (prevents silent creation through the modification path).
"""

from typing import List

from .contract import Canon, CanonDiff


def check_hard_contradictions(canon: Canon, diff: CanonDiff) -> List[str]:
    """Detect hard contradictions between *diff* and the current *canon*.

    Checks performed:
      1. modified_facts references a character_id that does not exist in canon
         and is not being added by added_facts in this same diff.
      2. name  — changing a character's canonical name to a different non-empty value.
      3. age   — changing age when it is already set in canon.
      4. alive — flipping alive/dead status when it is already set in canon.
      5. location — changing location when it is already set in canon.

    Args:
        canon: The current Canon state.
        diff:  A structurally valid CanonDiff (validate_diff returned []).

    Returns:
        List of error strings; empty list means no hard contradictions found.
    """
    errors: List[str] = []

    canon_chars: dict = canon.get("characters", {})
    added_chars: dict = diff.get("added_facts", {}).get("characters", {})
    modified_chars: dict = diff.get("modified_facts", {}).get("characters", {})

    for char_id, changes in modified_chars.items():
        # ── Existence check ────────────────────────────────────────────────
        if char_id not in canon_chars and char_id not in added_chars:
            errors.append(
                f"INVALID_DIFF: characters.{char_id} modified but does not exist"
                " (use added_facts)"
            )
            continue  # field checks are meaningless for a non-existent character

        # For chars being added in the same diff, canon_char will be empty —
        # no field-level contradiction is possible against empty canon data.
        canon_char: dict = canon_chars.get(char_id, {})

        if not isinstance(changes, dict):
            continue  # structural issues are caught by validate_diff

        # ── Name ───────────────────────────────────────────────────────────
        if "name" in changes:
            new_name = changes["name"]
            if isinstance(new_name, str) and new_name:
                old_name = canon_char.get("name")
                if old_name is not None and old_name != new_name:
                    errors.append(
                        f"CONTRADICTION: characters.{char_id}.name"
                        f" — canon='{old_name}' vs diff='{new_name}'"
                    )

        # ── Age ────────────────────────────────────────────────────────────
        if "age" in changes:
            new_age = changes["age"]
            old_age = canon_char.get("age")
            if old_age is not None and old_age != new_age:
                errors.append(
                    f"CONTRADICTION: characters.{char_id}.age"
                    f" — canon='{old_age}' vs diff='{new_age}'"
                )

        # ── Alive / death status ───────────────────────────────────────────
        if "alive" in changes:
            new_alive = changes["alive"]
            old_alive = canon_char.get("alive")
            if old_alive is not None and old_alive != new_alive:
                errors.append(
                    f"CONTRADICTION: characters.{char_id}.alive"
                    f" — canon='{old_alive}' vs diff='{new_alive}'"
                )

        # ── Location ───────────────────────────────────────────────────────
        if "location" in changes:
            new_loc = changes["location"]
            old_loc = canon_char.get("location")
            if old_loc is not None and old_loc != new_loc:
                errors.append(
                    f"CONTRADICTION: characters.{char_id}.location"
                    f" — canon='{old_loc}' vs diff='{new_loc}'"
                )

    return errors
