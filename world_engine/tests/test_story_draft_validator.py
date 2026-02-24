"""Tests for world_engine/story_draft_validator.py."""
from __future__ import annotations

import pytest

from world_engine.story_draft_validator import validate_story_draft


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _canon() -> dict:
    return {
        "characters": {
            "char_lena": {
                "name": "Lena",
                "age": 30,
                "alive": True,
                "location": "Castle",
            },
            "char_marco": {
                "name": "Marco",
                "age": 25,
                "alive": False,   # Marco is dead
                "location": "City",
            },
        }
    }


def _script_with_dialogue(*char_ids: str) -> dict:
    """Minimal Script.json with dialogue actions for the given character IDs."""
    return {
        "schema_id": "Script",
        "schema_version": "1.0.0",
        "script_id": "s001",
        "project_id": "proj1",
        "title": "Test",
        "scenes": [
            {
                "scene_id": "sc001",
                "location": "INT. HALL",
                "time_of_day": "DAY",
                "actions": [
                    {"type": "dialogue", "character": cid, "text": "Hello."}
                    for cid in char_ids
                ],
            }
        ],
    }


def _script_with_characters_list(entries: list) -> dict:
    """Script with explicit top-level characters list."""
    return {
        "schema_id": "Script",
        "schema_version": "1.0.0",
        "script_id": "s001",
        "project_id": "proj1",
        "title": "Test",
        "characters": entries,
        "scenes": [
            {
                "scene_id": "sc001",
                "location": "INT. HALL",
                "time_of_day": "DAY",
                "actions": [],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestValidDraft:

    def test_empty_characters_returns_no_violations(self):
        script = _script_with_dialogue()  # no characters
        assert validate_story_draft(script, _canon()) == []

    def test_alive_character_in_dialogue_returns_no_violations(self):
        script = _script_with_dialogue("char_lena")
        assert validate_story_draft(script, _canon()) == []

    def test_character_not_in_canon_is_not_flagged(self):
        """A brand-new character has no canon entry — no contradiction possible."""
        script = _script_with_dialogue("char_new")
        assert validate_story_draft(script, _canon()) == []

    def test_empty_canon_returns_no_violations(self):
        script = _script_with_dialogue("char_lena")
        assert validate_story_draft(script, {}) == []

    def test_explicit_same_name_is_not_a_contradiction(self):
        script = _script_with_characters_list([{"id": "char_lena", "name": "Lena"}])
        assert validate_story_draft(script, _canon()) == []

    def test_no_scenes_returns_no_violations(self):
        script = {
            "schema_id": "Script", "schema_version": "1.0.0",
            "script_id": "s1", "project_id": "p1", "title": "T",
            "scenes": [],
        }
        assert validate_story_draft(script, _canon()) == []


# ---------------------------------------------------------------------------
# Alive contradiction
# ---------------------------------------------------------------------------

class TestAliveContradiction:

    def test_dead_character_in_dialogue_triggers_violation(self):
        script = _script_with_dialogue("char_marco")  # Marco is dead in canon
        violations = validate_story_draft(script, _canon())
        assert len(violations) == 1
        assert "char_marco" in violations[0]["field"]
        assert "alive" in violations[0]["field"]

    def test_violation_has_required_keys(self):
        script = _script_with_dialogue("char_marco")
        v = validate_story_draft(script, _canon())[0]
        assert "field" in v
        assert "canon_value" in v
        assert "draft_value" in v
        assert "message" in v

    def test_explicit_alive_false_in_characters_list_triggers_violation(self):
        """Script explicitly marks a living canon character as dead."""
        script = _script_with_characters_list(
            [{"id": "char_lena", "alive": False}]
        )
        violations = validate_story_draft(script, _canon())
        assert any("char_lena" in v["field"] and "alive" in v["field"] for v in violations)


# ---------------------------------------------------------------------------
# Name contradiction
# ---------------------------------------------------------------------------

class TestNameContradiction:

    def test_different_name_triggers_violation(self):
        script = _script_with_characters_list(
            [{"id": "char_lena", "name": "Elena"}]   # canon name is "Lena"
        )
        violations = validate_story_draft(script, _canon())
        assert any("name" in v["field"] for v in violations)

    def test_same_name_no_violation(self):
        script = _script_with_characters_list(
            [{"id": "char_lena", "name": "Lena"}]
        )
        assert validate_story_draft(script, _canon()) == []


# ---------------------------------------------------------------------------
# Age contradiction
# ---------------------------------------------------------------------------

class TestAgeContradiction:

    def test_different_age_triggers_violation(self):
        script = _script_with_characters_list(
            [{"id": "char_lena", "age": 31}]   # canon age is 30
        )
        violations = validate_story_draft(script, _canon())
        assert any("age" in v["field"] for v in violations)

    def test_same_age_no_violation(self):
        script = _script_with_characters_list(
            [{"id": "char_lena", "age": 30}]
        )
        assert validate_story_draft(script, _canon()) == []


# ---------------------------------------------------------------------------
# Location contradiction
# ---------------------------------------------------------------------------

class TestLocationContradiction:

    def test_different_location_triggers_violation(self):
        script = _script_with_characters_list(
            [{"id": "char_lena", "location": "Desert"}]   # canon location is "Castle"
        )
        violations = validate_story_draft(script, _canon())
        assert any("location" in v["field"] for v in violations)

    def test_same_location_no_violation(self):
        script = _script_with_characters_list(
            [{"id": "char_lena", "location": "Castle"}]
        )
        assert validate_story_draft(script, _canon()) == []


# ---------------------------------------------------------------------------
# Multiple violations
# ---------------------------------------------------------------------------

class TestMultipleViolations:

    def test_multiple_violations_all_returned(self):
        script = _script_with_characters_list([
            {"id": "char_lena", "name": "Elena", "age": 99},
        ])
        violations = validate_story_draft(script, _canon())
        fields = [v["field"] for v in violations]
        assert any("name" in f for f in fields)
        assert any("age" in f for f in fields)

    def test_dead_and_alive_characters_in_same_script(self):
        """Lena (alive) and Marco (dead) — only Marco triggers violation."""
        script = _script_with_dialogue("char_lena", "char_marco")
        violations = validate_story_draft(script, _canon())
        assert len(violations) == 1
        assert "char_marco" in violations[0]["field"]


# ---------------------------------------------------------------------------
# Characters list takes precedence over dialogue extraction
# ---------------------------------------------------------------------------

class TestCharacterSourcePriority:

    def test_parse_fallback_on_invalid_diff_message(self):
        """INVALID_DIFF messages from gate.py don't match the CONTRADICTION regex
        and must produce the fallback violation dict rather than crashing."""
        from world_engine.story_draft_validator import _parse_contradiction_message

        # INVALID_DIFF format produced by gate.py for non-existent char
        msg = "INVALID_DIFF: characters.char_ghost modified but does not exist (use added_facts)"
        v = _parse_contradiction_message(msg)
        assert v["field"] == "unknown"
        assert v["canon_value"] is None
        assert v["draft_value"] is None
        assert v["message"] == msg

    def test_parse_contradiction_message_extracts_fields(self):
        """CONTRADICTION messages are parsed into structured violation dicts."""
        from world_engine.story_draft_validator import _parse_contradiction_message

        msg = "CONTRADICTION: characters.char_lena.age — canon='30' vs diff='31'"
        v = _parse_contradiction_message(msg)
        assert v["field"] == "characters.char_lena.age"
        assert v["canon_value"] == "30"
        assert v["draft_value"] == "31"
        assert v["message"] == msg

    def test_characters_list_id_used_over_dialogue_character_field(self):
        """char_lena in characters list with explicit facts AND in dialogue.
        Should not double-count."""
        script = {
            "schema_id": "Script", "schema_version": "1.0.0",
            "script_id": "s1", "project_id": "p1", "title": "T",
            "characters": [{"id": "char_lena", "name": "Lena"}],
            "scenes": [{
                "scene_id": "sc1", "location": "INT. HALL", "time_of_day": "DAY",
                "actions": [
                    {"type": "dialogue", "character": "char_lena", "text": "Hi"},
                ],
            }],
        }
        assert validate_story_draft(script, _canon()) == []
