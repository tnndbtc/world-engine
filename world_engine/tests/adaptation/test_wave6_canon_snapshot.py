"""Wave-6 Agent B: CanonSnapshot input plumbing tests."""
from __future__ import annotations

import pytest

from world_engine.adaptation.adapter import adapt_script
from world_engine.adaptation.models import Scene, Script
from world_engine.schemas.canon_snapshot_v1 import load_canon_snapshot_strict
from world_engine.schemas.shotlist_v1 import canonical_json_bytes

_VALID_SNAPSHOT = {
    "schema_id": "CanonSnapshot",
    "schema_version": "0.0.1",
    "episode_id": "ep_001",
    "canon_hash": "abc123def456",
    "entities": [],
}


def _simple_script() -> Script:
    """Mirrors fixture_a from test_wave4_vector_contract.py."""
    return Script(
        script_id="fixture_a", title="Fixture A",
        created_at="1970-01-01T00:00:00Z",
        scenes=[Scene(scene_id="fa_s001", location="Empty Plain", time_of_day="DAY")])


class TestCanonSnapshotPlumbing:

    # ── Spec test A ──────────────────────────────────────────────────────────
    def test_valid_snapshot_yields_identical_bytes(self):
        """ShotList bytes must be byte-identical with or without snapshot."""
        script = _simple_script()
        snap = load_canon_snapshot_strict(_VALID_SNAPSHOT)
        without_snap = canonical_json_bytes(adapt_script(script))
        with_snap    = canonical_json_bytes(adapt_script(script, canon_snapshot=snap))
        assert with_snap == without_snap

    # ── Spec test B ──────────────────────────────────────────────────────────
    def test_invalid_schema_id_raises_exact_message(self):
        """Wrong schema_id → exact ValueError message."""
        with pytest.raises(ValueError, match="ERROR: invalid CanonSnapshot input"):
            load_canon_snapshot_strict({
                "schema_id": "NotCanonSnapshot",
                "schema_version": "0.0.1",
                "episode_id": "ep_001",
                "canon_hash": "abc",
                "entities": [],
            })

    def test_missing_required_field_raises(self):
        """Missing canon_hash → exact ValueError message."""
        with pytest.raises(ValueError, match="ERROR: invalid CanonSnapshot input"):
            load_canon_snapshot_strict({
                "schema_id": "CanonSnapshot",
                "schema_version": "0.0.1",
                "episode_id": "ep_001",
                # canon_hash missing
                "entities": [],
            })

    def test_invalid_json_raises(self):
        """Malformed JSON string → exact ValueError message."""
        with pytest.raises(ValueError, match="ERROR: invalid CanonSnapshot input"):
            load_canon_snapshot_strict("{not valid json}")

    def test_timing_lock_hash_unchanged(self):
        """timing_lock_hash must be identical with and without snapshot."""
        script = _simple_script()
        snap = load_canon_snapshot_strict(_VALID_SNAPSHOT)
        tlh_without = adapt_script(script).timing_lock_hash
        tlh_with    = adapt_script(script, canon_snapshot=snap).timing_lock_hash
        assert tlh_with == tlh_without

    def test_extra_fields_ignored(self):
        """extra='ignore' — unknown fields in snapshot should not raise."""
        snap_with_extras = {**_VALID_SNAPSHOT, "future_field": "ignored"}
        snap = load_canon_snapshot_strict(snap_with_extras)
        assert snap.schema_id == "CanonSnapshot"
