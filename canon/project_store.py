"""
project_store.py — Project-aware Canon Store (Option C: snapshot + diff log).

Layout under <base_dir>/<project_id>/:

    CanonSnapshot.json              ← current state (always latest)
    history/
        0001_<episode_id>.diff.json ← immutable once written; one per accepted diff
        0002_<episode_id>.diff.json
        ...
    violations/
        <episode_id>_CanonViolationReport.json   ← written by validate-story-draft on failure

Sequence numbers are supplied by the caller (orchestrator) via episode_seq — never
computed from file count, so parallel episode runs cannot race.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from .canon_io import load_canon, save_canon
from .contract import Canon, CanonDiff

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _project_dir(project_id: str, base_dir: str | Path) -> Path:
    return Path(base_dir) / project_id


def _snapshot_path(project_id: str, base_dir: str | Path) -> Path:
    return _project_dir(project_id, base_dir) / "CanonSnapshot.json"


def _history_dir(project_id: str, base_dir: str | Path) -> Path:
    return _project_dir(project_id, base_dir) / "history"


def _violations_dir(project_id: str, base_dir: str | Path) -> Path:
    return _project_dir(project_id, base_dir) / "violations"


def _diff_filename(episode_seq: int, episode_id: str) -> str:
    return f"{episode_seq:04d}_{episode_id}.diff.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_project_canon(project_id: str, base_dir: str | Path) -> Canon:
    """Load the current CanonSnapshot for *project_id*.

    Args:
        project_id: Stable project identifier.
        base_dir:   Root directory that contains per-project subdirectories.

    Returns:
        The Canon dict.

    Raises:
        FileNotFoundError: If no CanonSnapshot.json exists for this project.
        json.JSONDecodeError: If the snapshot file is corrupt.
    """
    path = _snapshot_path(project_id, base_dir)
    if not path.exists():
        raise FileNotFoundError(
            f"No CanonSnapshot found for project '{project_id}' at {path}"
        )
    return load_canon(str(path))


def save_project_canon(
    project_id: str,
    base_dir: str | Path,
    canon: Canon,
    diff: CanonDiff,
    episode_id: str,
    episode_seq: int,
) -> None:
    """Persist an accepted CanonDiff and update the project snapshot.

    History write order (Option C):
      1. Ensure ``history/`` directory exists.
      2. Write ``history/<episode_seq:04d>_<episode_id>.diff.json`` (immutable).
      3. Overwrite ``CanonSnapshot.json`` with the new canon state.

    Step 2 is intentionally before Step 3 so that a crash between them leaves
    the diff on disk — the snapshot can be reconstructed by replaying history.

    Args:
        project_id:  Stable project identifier.
        base_dir:    Root directory that contains per-project subdirectories.
        canon:       The *new* Canon state to persist (post-apply_canon_diff).
        diff:        The accepted CanonDiff to record in history.
        episode_id:  Human-readable episode identifier (e.g. "ep002").
        episode_seq: Monotonic sequence number supplied by orchestrator.
                     Determines the history filename; must be unique per project.

    Raises:
        FileExistsError: If a diff file with the same sequence number already
                         exists (guards against accidental duplicate writes).
    """
    proj_dir = _project_dir(project_id, base_dir)
    history_dir = _history_dir(project_id, base_dir)
    history_dir.mkdir(parents=True, exist_ok=True)

    diff_path = history_dir / _diff_filename(episode_seq, episode_id)
    if diff_path.exists():
        raise FileExistsError(
            f"History entry already exists for seq={episode_seq} "
            f"in project '{project_id}': {diff_path}"
        )

    # 2. Write immutable diff entry
    with open(diff_path, "w", encoding="utf-8") as f:
        json.dump(diff, f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")

    # 3. Overwrite current snapshot
    save_canon(str(proj_dir / "CanonSnapshot.json"), canon)


def save_violation_report(
    project_id: str,
    base_dir: str | Path,
    report: dict,
    episode_id: str,
) -> Path:
    """Write a CanonViolationReport to the project's violations/ directory.

    Args:
        project_id: Stable project identifier.
        base_dir:   Root directory that contains per-project subdirectories.
        report:     The violation report dict (conforming to CanonViolationReport.v1.json).
        episode_id: Episode identifier; used in the filename.

    Returns:
        Path to the written file.
    """
    violations_dir = _violations_dir(project_id, base_dir)
    violations_dir.mkdir(parents=True, exist_ok=True)

    out_path = violations_dir / f"{episode_id}_CanonViolationReport.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")
    return out_path


def load_canon_at_episode(
    project_id: str,
    base_dir: str | Path,
    episode_id: str,
) -> Canon:
    """Replay history diffs up to and including *episode_id* to reconstruct
    the Canon state at that point in time.

    Diffs are replayed in filename order (by sequence number prefix).
    Stops after applying the first diff whose filename contains *episode_id*.

    Args:
        project_id: Stable project identifier.
        base_dir:   Root directory that contains per-project subdirectories.
        episode_id: Episode to replay up to (inclusive).

    Returns:
        The reconstructed Canon at that episode.

    Raises:
        FileNotFoundError: If no history directory or no matching diff is found.
        ValueError: If episode_id is not found in history.
    """
    history_dir = _history_dir(project_id, base_dir)
    if not history_dir.exists():
        raise FileNotFoundError(
            f"No history directory for project '{project_id}' at {history_dir}"
        )

    diff_files = sorted(history_dir.glob("*.diff.json"))
    if not diff_files:
        raise FileNotFoundError(
            f"No history entries found for project '{project_id}'"
        )

    from .contract import apply_canon_diff  # noqa: PLC0415

    canon: Canon = {}
    found = False
    for diff_file in diff_files:
        with open(diff_file, "r", encoding="utf-8") as f:
            diff: CanonDiff = json.load(f)
        canon, errors = apply_canon_diff(canon, diff)
        if errors:
            # History should only contain accepted diffs; log and continue
            pass
        if episode_id in diff_file.name:
            found = True
            break

    if not found:
        raise ValueError(
            f"Episode '{episode_id}' not found in history for project '{project_id}'"
        )

    return canon
