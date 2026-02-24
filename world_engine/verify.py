"""world-engine verify — system verification export (Wave-5)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict

# ── ShotList imports ──────────────────────────────────────────────────────────
from world_engine.adaptation.adapter import adapt_script
from world_engine.adaptation.models import (
    DialogueLine, Scene, SceneAction, Script, ShotList,
)
from world_engine.contract_validate import validate_shotlist as _validate_canonical
from world_engine.schemas.shotlist_v1 import canonical_json_bytes

# ── CanonGate — canon/ is at repo root; importable via editable install path ──
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from canon.decision import dump_decision, evaluate_shotlist  # noqa: E402

# ── Golden file paths ─────────────────────────────────────────────────────────
_SHOTLIST_GOLDENS = Path(__file__).parent / "tests" / "contract_vectors" / "shotlist"
_CANON_FIXTURES   = _REPO_ROOT / "tests" / "contract_vectors" / "canon_gate" / "fixtures"
_CANON_GOLDENS    = _REPO_ROOT / "tests" / "contract_vectors" / "canon_gate" / "goldens"


# ── ShotList script factories — mirrors test_wave4_vector_contract.py exactly ─

def _script_fixture_a() -> Script:
    return Script(
        script_id="fixture_a", title="Fixture A",
        created_at="1970-01-01T00:00:00Z",
        scenes=[Scene(scene_id="fa_s001", location="Empty Plain", time_of_day="DAY")])

def _script_fixture_b() -> Script:
    return Script(
        script_id="fixture_b", title="Fixture B",
        created_at="1970-01-01T00:00:00Z",
        scenes=[Scene(
            scene_id="fb_s001", location="Town Square", time_of_day="NOON",
            characters=["char_alice", "char_bob"],
            dialogue=[DialogueLine(speaker_id="char_alice", text="Hello.")])])

def _script_fixture_d() -> Script:
    return Script(
        script_id="wave2_fixture_d", title="Fixture D",
        created_at="1970-01-01T00:00:00Z",
        scenes=[
            Scene(scene_id="fd_s001", location="Market", time_of_day="DAY",
                  characters=["char_scout"],
                  actions=[SceneAction(description="Scout scans the crowd.",
                                       characters=["char_scout"])]),
            Scene(scene_id="fd_s002", location="Throne Room", time_of_day="INTERIOR",
                  characters=["char_lena", "char_king"],
                  dialogue=[DialogueLine(speaker_id="char_lena",
                                         text="I bring news from the frontier."),
                             DialogueLine(speaker_id="char_king", text="Speak.")]),
            Scene(scene_id="fd_s003", location="Castle Courtyard", time_of_day="DUSK")])


# ── Pipeline runners ──────────────────────────────────────────────────────────

def _run_shotlist_vectors() -> Dict[str, bytes]:
    """Run 3 ShotList contract vectors → {key: produced_bytes}.

    Each produced ShotList is validated against
    third_party/contracts/schemas/ShotList.v1.json before being returned.
    Raises FileNotFoundError if the canonical schema is absent.
    """
    results: Dict[str, bytes] = {}
    for name, factory in [
        ("shotlist/fixture_a", _script_fixture_a),
        ("shotlist/fixture_b", _script_fixture_b),
        ("shotlist/fixture_d", _script_fixture_d),
    ]:
        sl = adapt_script(factory())
        produced = canonical_json_bytes(sl)
        # Project to canonical v1.0.0 format before validation
        raw = json.loads(produced.decode("utf-8"))
        canonical = {k: v for k, v in raw.items() if k != "producer"}
        canonical["schema_version"] = "1.0.0"
        _validate_canonical(canonical)  # raises FileNotFoundError if contracts missing
        results[name] = produced
    return results


def _run_canongate_vectors() -> Dict[str, bytes]:
    """Run 2 CanonGate contract vectors → {key: produced_bytes}.

    dump_decision() returns str; encode to UTF-8 for uniform bytes comparison.
    Golden files were written without trailing newline (confirmed by existing
    passing tests: test_canon_gate_vectors.py uses read_text() == dump_decision()).
    """
    results: Dict[str, bytes] = {}
    for fixture_file, key in [
        ("allow_shotlist.json", "canon/allow"),
        ("deny_shotlist.json",  "canon/deny"),
    ]:
        with (_CANON_FIXTURES / fixture_file).open("r", encoding="utf-8") as f:
            sl = ShotList.model_validate(json.load(f))
        decision = evaluate_shotlist(sl)
        results[key] = dump_decision(decision).encode("utf-8")
    return results


def _check_against_goldens(artifacts: Dict[str, bytes]) -> bool:
    """Return True iff every artifact matches its committed golden file (bytes)."""
    for key, produced in artifacts.items():
        kind, name = key.split("/", 1)
        if kind == "shotlist":
            golden_bytes = (_SHOTLIST_GOLDENS / f"{name}.json").read_bytes()
        else:  # "canon"
            golden_bytes = (_CANON_GOLDENS / f"{name}_canon_decision.json").read_bytes()
        if produced != golden_bytes:
            return False
    return True


def run_verify() -> bool:
    """Run all 5 contract vectors twice; return True only if every check passes.

    Checks (in order):
      1. ShotList vectors (3) bytes match committed goldens.
      2. CanonGate vectors (2) bytes match committed goldens.
      3. Run-1 artifacts == Run-2 artifacts (byte-by-byte determinism across runs).
    """
    try:
        run1 = {**_run_shotlist_vectors(), **_run_canongate_vectors()}
        run2 = {**_run_shotlist_vectors(), **_run_canongate_vectors()}
        return _check_against_goldens(run1) and (run1 == run2)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return False
    except Exception:
        return False
