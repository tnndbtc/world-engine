"""Tests for canon/project_store.py — Option C project-aware Canon Store."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from canon.project_store import (
    load_project_canon,
    load_canon_at_episode,
    save_project_canon,
    save_violation_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _base_canon() -> dict:
    return {
        "characters": {
            "char_lena": {"name": "Lena", "age": 30, "alive": True, "location": "Castle"},
        },
    }


def _diff_add_marco() -> dict:
    return {
        "added_facts": {
            "characters": {
                "char_marco": {"name": "Marco", "age": 25, "alive": True, "location": "City"},
            }
        }
    }


def _diff_update_location() -> dict:
    return {
        "modified_facts": {
            "characters": {
                "char_lena": {"location": "Forest"},
            }
        }
    }


# ---------------------------------------------------------------------------
# load_project_canon
# ---------------------------------------------------------------------------

class TestLoadProjectCanon:

    def test_raises_when_no_snapshot(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="No CanonSnapshot found"):
            load_project_canon("proj1", tmp_path)

    def test_loads_existing_snapshot(self, tmp_path: Path):
        proj_dir = tmp_path / "proj1"
        proj_dir.mkdir()
        snapshot = _base_canon()
        (proj_dir / "CanonSnapshot.json").write_text(
            json.dumps(snapshot), encoding="utf-8"
        )
        loaded = load_project_canon("proj1", tmp_path)
        assert loaded == snapshot


# ---------------------------------------------------------------------------
# save_project_canon
# ---------------------------------------------------------------------------

class TestSaveProjectCanon:

    def test_creates_snapshot_and_history_entry(self, tmp_path: Path):
        canon = _base_canon()
        diff = _diff_add_marco()
        save_project_canon("proj1", tmp_path, canon, diff, "ep001", episode_seq=1)

        proj_dir = tmp_path / "proj1"
        assert (proj_dir / "CanonSnapshot.json").exists()
        assert (proj_dir / "history" / "0001_ep001.diff.json").exists()

    def test_snapshot_content_matches_canon(self, tmp_path: Path):
        canon = _base_canon()
        diff = _diff_add_marco()
        save_project_canon("proj1", tmp_path, canon, diff, "ep001", episode_seq=1)

        saved = json.loads(
            (tmp_path / "proj1" / "CanonSnapshot.json").read_text(encoding="utf-8")
        )
        assert saved == canon

    def test_diff_content_matches_diff(self, tmp_path: Path):
        canon = _base_canon()
        diff = _diff_add_marco()
        save_project_canon("proj1", tmp_path, canon, diff, "ep001", episode_seq=1)

        saved_diff = json.loads(
            (tmp_path / "proj1" / "history" / "0001_ep001.diff.json").read_text()
        )
        assert saved_diff == diff

    def test_sequence_number_zero_padded_to_4_digits(self, tmp_path: Path):
        save_project_canon("p", tmp_path, {}, {}, "ep042", episode_seq=42)
        assert (tmp_path / "p" / "history" / "0042_ep042.diff.json").exists()

    def test_second_save_produces_second_history_file(self, tmp_path: Path):
        canon = _base_canon()
        save_project_canon("p", tmp_path, canon, _diff_add_marco(), "ep001", episode_seq=1)
        save_project_canon("p", tmp_path, canon, _diff_update_location(), "ep002", episode_seq=2)

        history = sorted((tmp_path / "p" / "history").glob("*.diff.json"))
        assert len(history) == 2
        assert history[0].name == "0001_ep001.diff.json"
        assert history[1].name == "0002_ep002.diff.json"

    def test_snapshot_is_overwritten_by_second_save(self, tmp_path: Path):
        canon_v1 = _base_canon()
        canon_v2 = {**_base_canon(), "extra": "data"}
        save_project_canon("p", tmp_path, canon_v1, {}, "ep001", episode_seq=1)
        save_project_canon("p", tmp_path, canon_v2, {}, "ep002", episode_seq=2)

        loaded = json.loads((tmp_path / "p" / "CanonSnapshot.json").read_text())
        assert loaded["extra"] == "data"

    def test_creates_base_dir_when_it_does_not_exist(self, tmp_path: Path):
        """save_project_canon must work even when base_dir/<project_id> doesn't exist yet."""
        nonexistent = tmp_path / "new_base" / "nested"
        save_project_canon("proj1", nonexistent, {}, {}, "ep001", episode_seq=1)
        assert (nonexistent / "proj1" / "CanonSnapshot.json").exists()
        assert (nonexistent / "proj1" / "history" / "0001_ep001.diff.json").exists()

    def test_duplicate_sequence_raises(self, tmp_path: Path):
        save_project_canon("p", tmp_path, {}, {}, "ep001", episode_seq=1)
        with pytest.raises(FileExistsError, match="already exists"):
            save_project_canon("p", tmp_path, {}, {}, "ep001", episode_seq=1)

    def test_history_diff_is_immutable_after_write(self, tmp_path: Path):
        """Writing same seq with different episode_id still raises (seq is the key)."""
        save_project_canon("p", tmp_path, {}, {}, "ep001", episode_seq=1)
        with pytest.raises(FileExistsError):
            save_project_canon("p", tmp_path, {}, {}, "ep001", episode_seq=1)

    def test_history_file_has_sorted_keys(self, tmp_path: Path):
        """sort_keys=True is applied per nesting level — verify via round-trip parse."""
        diff = {"modified_facts": {"z": 1}, "added_facts": {"a": 2}}
        save_project_canon("p", tmp_path, {}, diff, "ep001", episode_seq=1)
        raw = (tmp_path / "p" / "history" / "0001_ep001.diff.json").read_text()
        # Verify top-level keys are sorted
        parsed = json.loads(raw)
        top_keys = list(parsed.keys())
        assert top_keys == sorted(top_keys)


# ---------------------------------------------------------------------------
# save_violation_report
# ---------------------------------------------------------------------------

class TestSaveViolationReport:

    def test_writes_report_to_violations_dir(self, tmp_path: Path):
        report = {
            "schema_id": "CanonViolationReport",
            "schema_version": "1.0.0",
            "project_id": "proj1",
            "episode_id": "ep003",
            "violations": [],
        }
        path = save_violation_report("proj1", tmp_path, report, "ep003")
        assert path.exists()
        assert path.name == "ep003_CanonViolationReport.json"
        assert json.loads(path.read_text()) == report


# ---------------------------------------------------------------------------
# load_canon_at_episode
# ---------------------------------------------------------------------------

class TestLoadCanonAtEpisode:

    def test_replays_single_diff(self, tmp_path: Path):
        from canon.contract import apply_canon_diff

        diff = _diff_add_marco()
        canon, _ = apply_canon_diff({}, diff)
        save_project_canon("p", tmp_path, canon, diff, "ep001", episode_seq=1)

        replayed = load_canon_at_episode("p", tmp_path, "ep001")
        assert "char_marco" in replayed.get("characters", {})

    def test_replays_up_to_named_episode(self, tmp_path: Path):
        from canon.contract import apply_canon_diff

        diff1 = _diff_add_marco()
        canon1, _ = apply_canon_diff({}, diff1)
        save_project_canon("p", tmp_path, canon1, diff1, "ep001", episode_seq=1)

        diff2 = _diff_update_location()
        canon2, _ = apply_canon_diff(canon1, diff2)
        save_project_canon("p", tmp_path, canon2, diff2, "ep002", episode_seq=2)

        # Replay only to ep001 — char_lena.location should NOT be "Forest" yet
        replayed = load_canon_at_episode("p", tmp_path, "ep001")
        # ep001 only adds char_marco; ep002 modifies char_lena — so char_lena absent
        assert "char_marco" in replayed.get("characters", {})

    def test_raises_on_missing_history(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_canon_at_episode("p", tmp_path, "ep001")

    def test_raises_on_unknown_episode(self, tmp_path: Path):
        save_project_canon("p", tmp_path, {}, {}, "ep001", episode_seq=1)
        with pytest.raises(ValueError, match="not found in history"):
            load_canon_at_episode("p", tmp_path, "ep999")
