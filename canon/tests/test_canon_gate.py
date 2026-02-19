"""
tests/test_canon_gate.py — Phase 0 Canon Store + Canon Gate tests.

Covers:
  - Rejection of each hard-contradiction type (name / age / alive / location)
  - Rejection of modified_facts referencing a non-existent character_id
  - Acceptance of valid diffs (new character, unset field updates, same-value no-ops,
    removal, modify-alongside-add in one diff)
  - Structural validation (malformed diff)
  - Determinism (same inputs → same Canon → same JSON bytes)
  - Immutability (apply_diff never mutates its input)

Character dict keys are stable character_ids (e.g. "char_lena"), separate from
the human-readable "name" field inside each entry.
"""

import copy
import json
import os
import tempfile

import pytest

from canon.contract import apply_canon_diff
from canon.diff import validate_diff, apply_diff
from canon.gate import check_hard_contradictions
from canon.canon_io import load_canon, save_canon


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _base_canon():
    """A minimal Canon with one fully-populated character."""
    return {
        "characters": {
            "char_lena": {
                "name": "Lena",
                "age": 30,
                "alive": True,
                "location": "Castle",
            }
        },
        "locations": {},
        "world_rules": [],
        "relationships": {},
        "timeline_events": [],
        "persistent_states": {},
    }


def _dead_canon():
    """Canon where char_lena is already dead."""
    c = _base_canon()
    c["characters"]["char_lena"]["alive"] = False
    return c


# ─────────────────────────────────────────────────────────────────────────────
# Rejection tests — hard contradictions
# ─────────────────────────────────────────────────────────────────────────────

class TestRejectHardContradictions:

    def test_reject_name_change(self):
        """Changing a character's canonical name must be blocked."""
        canon = _base_canon()
        diff = {
            "modified_facts": {
                "characters": {"char_lena": {"name": "Elena"}}
            }
        }
        new_canon, errors = apply_canon_diff(canon, diff)
        assert errors, "Expected errors for name change"
        assert any("char_lena.name" in e for e in errors)
        assert new_canon is canon or new_canon == canon  # canon unchanged

    def test_reject_age_change(self):
        """Changing a character's canonical age must be blocked."""
        canon = _base_canon()
        diff = {
            "modified_facts": {
                "characters": {"char_lena": {"age": 35}}
            }
        }
        _, errors = apply_canon_diff(canon, diff)
        assert errors
        assert any("char_lena.age" in e for e in errors)

    def test_reject_alive_to_dead(self):
        """Flipping a living character to dead must be blocked."""
        canon = _base_canon()  # char_lena alive=True
        diff = {
            "modified_facts": {
                "characters": {"char_lena": {"alive": False}}
            }
        }
        _, errors = apply_canon_diff(canon, diff)
        assert errors
        assert any("char_lena.alive" in e for e in errors)

    def test_reject_dead_to_alive(self):
        """Flipping a dead character to alive must be blocked."""
        canon = _dead_canon()  # char_lena alive=False
        diff = {
            "modified_facts": {
                "characters": {"char_lena": {"alive": True}}
            }
        }
        _, errors = apply_canon_diff(canon, diff)
        assert errors
        assert any("char_lena.alive" in e for e in errors)

    def test_reject_location_change(self):
        """Changing a character's canonical location must be blocked."""
        canon = _base_canon()
        diff = {
            "modified_facts": {
                "characters": {"char_lena": {"location": "Forest"}}
            }
        }
        _, errors = apply_canon_diff(canon, diff)
        assert errors
        assert any("char_lena.location" in e for e in errors)

    def test_reject_multiple_contradictions_in_one_diff(self):
        """All contradictions in a single diff are reported, not just the first."""
        canon = _base_canon()
        diff = {
            "modified_facts": {
                "characters": {
                    "char_lena": {"name": "Elena", "age": 99, "location": "Dungeon"}
                }
            }
        }
        _, errors = apply_canon_diff(canon, diff)
        assert len(errors) >= 3


# ─────────────────────────────────────────────────────────────────────────────
# Rejection tests — existence check (new in Phase 0 requirement)
# ─────────────────────────────────────────────────────────────────────────────

class TestRejectModifyNonExistentCharacter:

    def test_reject_modify_unknown_character(self):
        """modified_facts for a character_id absent from canon must error."""
        canon = _base_canon()
        diff = {
            "modified_facts": {
                "characters": {"char_ghost": {"location": "Void"}}
            }
        }
        _, errors = apply_canon_diff(canon, diff)
        assert errors
        assert any("char_ghost" in e and "does not exist" in e for e in errors)

    def test_reject_modify_character_not_in_added_facts(self):
        """modified_facts for a char not in added_facts of the same diff must error."""
        canon = _base_canon()
        diff = {
            "added_facts": {
                "characters": {
                    "char_new": {"name": "NewGuy"}
                }
            },
            "modified_facts": {
                "characters": {"char_other": {"location": "Tavern"}}
            }
        }
        _, errors = apply_canon_diff(canon, diff)
        assert errors
        assert any("char_other" in e and "does not exist" in e for e in errors)


# ─────────────────────────────────────────────────────────────────────────────
# Acceptance tests — valid diffs
# ─────────────────────────────────────────────────────────────────────────────

class TestAcceptValidDiffs:

    def test_accept_new_character_via_added_facts(self):
        """Adding a brand-new character via added_facts must succeed."""
        canon = _base_canon()
        diff = {
            "added_facts": {
                "characters": {
                    "char_marco": {"name": "Marco", "age": 25, "alive": True}
                }
            }
        }
        new_canon, errors = apply_canon_diff(canon, diff)
        assert not errors
        assert "char_marco" in new_canon["characters"]
        assert new_canon["characters"]["char_marco"]["name"] == "Marco"

    def test_accept_location_update_when_not_set(self):
        """Setting location for the first time (no prior value) must succeed."""
        canon = _base_canon()
        del canon["characters"]["char_lena"]["location"]  # remove prior value
        diff = {
            "modified_facts": {
                "characters": {"char_lena": {"location": "Dungeon"}}
            }
        }
        new_canon, errors = apply_canon_diff(canon, diff)
        assert not errors
        assert new_canon["characters"]["char_lena"]["location"] == "Dungeon"

    def test_accept_age_update_when_not_set(self):
        """Setting age for the first time must succeed."""
        canon = _base_canon()
        del canon["characters"]["char_lena"]["age"]
        diff = {
            "modified_facts": {
                "characters": {"char_lena": {"age": 31}}
            }
        }
        new_canon, errors = apply_canon_diff(canon, diff)
        assert not errors
        assert new_canon["characters"]["char_lena"]["age"] == 31

    def test_accept_same_name_is_not_contradiction(self):
        """Supplying the same name value must not be treated as a contradiction."""
        canon = _base_canon()
        diff = {
            "modified_facts": {
                "characters": {"char_lena": {"name": "Lena"}}  # identical
            }
        }
        _, errors = apply_canon_diff(canon, diff)
        assert not errors

    def test_accept_remove_character(self):
        """Removing a character via removed_facts must succeed."""
        canon = _base_canon()
        diff = {"removed_facts": {"characters": ["char_lena"]}}
        new_canon, errors = apply_canon_diff(canon, diff)
        assert not errors
        assert "char_lena" not in new_canon["characters"]

    def test_accept_modify_alongside_add_in_same_diff(self):
        """modified_facts for a char being added in the same diff must be allowed."""
        canon = _base_canon()
        diff = {
            "added_facts": {
                "characters": {"char_rex": {"name": "Rex"}}
            },
            "modified_facts": {
                "characters": {"char_rex": {"age": 40}}
            },
        }
        new_canon, errors = apply_canon_diff(canon, diff)
        assert not errors
        # char_rex should have both name (from added) and age (from modified)
        rex = new_canon["characters"]["char_rex"]
        assert rex["name"] == "Rex"
        assert rex["age"] == 40

    def test_accept_diff_with_justification_and_provenance(self):
        """Optional metadata fields must not cause errors."""
        canon = _base_canon()
        diff = {
            "added_facts": {
                "characters": {"char_iris": {"name": "Iris"}}
            },
            "justification": "episode 5 introduction",
            "provenance": "writer-room",
        }
        _, errors = apply_canon_diff(canon, diff)
        assert not errors

    def test_accept_empty_diff(self):
        """An empty diff (no changes) must be accepted and return canon unchanged."""
        canon = _base_canon()
        new_canon, errors = apply_canon_diff(canon, {})
        assert not errors
        assert new_canon == canon


# ─────────────────────────────────────────────────────────────────────────────
# Structural validation
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateDiff:

    def test_reject_non_dict_diff(self):
        errors = validate_diff("not a dict")
        assert errors
        assert any("must be a dict" in e for e in errors)

    def test_reject_unknown_top_level_keys(self):
        errors = validate_diff({"unexpected_key": {}})
        assert errors
        assert any("unknown top-level keys" in e for e in errors)

    def test_reject_modified_facts_not_dict(self):
        errors = validate_diff({"modified_facts": "oops"})
        assert errors
        assert any("'modified_facts' must be a dict" in e for e in errors)

    def test_reject_removed_facts_not_dict(self):
        errors = validate_diff({"removed_facts": ["should", "be", "a", "dict"]})
        assert errors
        assert any("'removed_facts' must be a dict" in e for e in errors)

    def test_reject_removed_facts_section_not_list(self):
        errors = validate_diff({"removed_facts": {"characters": "char_lena"}})
        assert errors
        assert any("must be a list" in e for e in errors)

    def test_valid_diff_structure_returns_no_errors(self):
        diff = {
            "added_facts": {"characters": {"char_x": {"name": "X"}}},
            "modified_facts": {"characters": {"char_x": {"age": 5}}},
            "removed_facts": {"characters": []},
            "justification": "test",
            "provenance": "unit-test",
        }
        assert validate_diff(diff) == []


# ─────────────────────────────────────────────────────────────────────────────
# Determinism
# ─────────────────────────────────────────────────────────────────────────────

class TestDeterminism:

    def test_same_inputs_produce_same_canon(self):
        """apply_canon_diff must be deterministic: same inputs → same output."""
        canon = _base_canon()
        diff = {
            "added_facts": {
                "characters": {"char_bob": {"name": "Bob", "age": 22, "alive": True}}
            }
        }
        result_1, _ = apply_canon_diff(copy.deepcopy(canon), copy.deepcopy(diff))
        result_2, _ = apply_canon_diff(copy.deepcopy(canon), copy.deepcopy(diff))
        assert result_1 == result_2

    def test_json_serialization_is_stable(self):
        """save_canon must produce byte-identical output for the same Canon."""
        canon = _base_canon()
        with tempfile.TemporaryDirectory() as tmpdir:
            path_a = os.path.join(tmpdir, "canon_a.json")
            path_b = os.path.join(tmpdir, "canon_b.json")
            save_canon(path_a, canon)
            save_canon(path_b, canon)
            with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
                assert fa.read() == fb.read()

    def test_load_save_roundtrip(self):
        """Canon saved and reloaded must equal the original."""
        canon = _base_canon()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "canon.json")
            save_canon(path, canon)
            loaded = load_canon(path)
        assert loaded == canon

    def test_json_keys_are_sorted(self):
        """Saved JSON must have sorted keys for deterministic diffs/hashing."""
        canon = _base_canon()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "canon.json")
            save_canon(path, canon)
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
        # Verify by re-parsing; key order in json.loads is insertion order (Python 3.7+).
        # The simplest check: dumping with sort_keys should equal the file content.
        reloaded = json.loads(raw)
        expected = json.dumps(reloaded, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        assert raw == expected


# ─────────────────────────────────────────────────────────────────────────────
# Immutability
# ─────────────────────────────────────────────────────────────────────────────

class TestImmutability:

    def test_apply_diff_does_not_mutate_input_canon(self):
        """apply_diff must return a new dict and leave the input untouched."""
        canon = _base_canon()
        original = copy.deepcopy(canon)
        diff = {
            "added_facts": {
                "characters": {"char_new": {"name": "NewChar"}}
            }
        }
        new_canon = apply_diff(canon, diff)
        assert canon == original, "apply_diff mutated the input canon"
        assert new_canon is not canon

    def test_apply_diff_does_not_mutate_input_diff(self):
        """apply_diff must not mutate the diff dict either."""
        canon = _base_canon()
        diff = {
            "added_facts": {
                "characters": {"char_new": {"name": "NewChar"}}
            }
        }
        original_diff = copy.deepcopy(diff)
        apply_diff(canon, diff)
        assert diff == original_diff

    def test_rejected_diff_leaves_canon_unchanged(self):
        """When apply_canon_diff rejects a diff, the returned canon must equal the input."""
        canon = _base_canon()
        original = copy.deepcopy(canon)
        diff = {
            "modified_facts": {
                "characters": {"char_lena": {"name": "Impostor"}}
            }
        }
        returned_canon, errors = apply_canon_diff(canon, diff)
        assert errors
        assert returned_canon == original
