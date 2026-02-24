# world-engine

Converts a narrative **Script** into a production-ready **ShotList**, and enforces canon consistency via the **Canon Gate**.

It is **Stage 2** of the agent pipeline:

```
writing-agent → [Script.json]
                     │
              world-engine          ← this repo
                     │
               [ShotList.json]
                     │
              media-agent → orchestrator → video-agent
```

Protocol version: `1.0.2` (see `PROTOCOL_VERSION`)

---

## Purpose

| Responsibility | Where |
|---|---|
| Adapt `Script.json` → `ShotList.json` (deterministic) | `world_engine/adaptation/` |
| Validate `Script.json` against contract rules | `world_engine/validator.py` |
| Validate `ShotList.json` against `ShotList.v1.json` schema | `world_engine/contract_validate.py` |
| Canon Store — load/save Canon JSON snapshots | `canon/canon_io.py` |
| Canon Gate — block hard contradictions (name/age/alive/location) | `canon/gate.py` |
| Canon Decision — evaluate a ShotList and emit allow/deny artifact | `canon/decision.py` |

All core functions are **pure and deterministic** — no randomness, no clock reads, no network I/O.

---

## Installation

```bash
pip install -e ".[dev]"
```

Or install dependencies only:

```bash
pip install -r requirements.txt
```

---

## CLI

The binary is `world-engine`. All commands exit `0` on success and `1` on failure.

### `produce-shotlist` — adapt Script → ShotList

Reads a `Script.json`, runs the full adaptation pipeline, validates the output
against `ShotList.v1.json`, and writes `ShotList.json`.

```bash
world-engine produce-shotlist \
    --script  path/to/Script.json \
    --output  path/to/ShotList.json
```

- Input must conform to `Script.v1.json` — validation runs before adaptation.
- Output file is **not written** if either the input or output validation fails.

---

### `validate-script` — check a Script JSON file

Validates a `Script.json` against the contract rules without producing any output.

```bash
world-engine validate-script --script path/to/Script.json
```

| Exit code | Meaning |
|---|---|
| `0` | Script is valid |
| `1` | Script is invalid — prints `ERROR: invalid Script` |

---

### `validate-shotlist` — check a ShotList JSON file

Validates an existing `ShotList.json` against the canonical `ShotList.v1.json` schema.

```bash
world-engine validate-shotlist --shotlist path/to/ShotList.json
```

| Exit code | Meaning |
|---|---|
| `0` | Prints `OK: ShotList is valid` |
| `1` | Prints `ERROR: invalid ShotList — <reason>` |

---

### `verify` — run contract vector verification

Runs the internal contract verification suite to confirm all golden vectors pass.

```bash
world-engine verify
```

| Exit code | Meaning |
|---|---|
| `0` | Prints `OK: world-engine verified` |
| `1` | Prints `ERROR: world-engine verification failed` |

---

## Canon Python API

The `canon` package is imported directly (no CLI). It implements the **Phase 0 Canon Store + Canon Gate**.

```python
from canon import Canon, CanonDiff, apply_canon_diff, CanonDecision, evaluate_shotlist
from canon.canon_io import load_canon, save_canon
```

### `apply_canon_diff(canon, diff) -> (new_canon, errors)`

The single public entry point for updating canon state.

```python
new_canon, errors = apply_canon_diff(canon, diff)
if errors:
    print("Rejected:", errors)   # original canon is unchanged
else:
    save_canon("canon.json", new_canon)
```

Pipeline run internally:
1. `validate_diff(diff)` — structural / shape checks (type checks, allowed keys)
2. `check_hard_contradictions(canon, diff)` — blocks changes to `name`, `age`, `alive`, `location` when canon already holds a value
3. `apply_diff(canon, diff)` — pure merge; returns a new dict, never mutates input

Returns `(original_canon, errors)` on any failure — the canon is **always left unchanged on rejection**.

---

### `load_canon` / `save_canon`

Local-only JSON store. `save_canon` always writes with `sort_keys=True, indent=2`
so identical canon states produce byte-identical files.

```python
from canon.canon_io import load_canon, save_canon

canon = load_canon("canon.json")
new_canon, errors = apply_canon_diff(canon, diff)
if not errors:
    save_canon("canon.json", new_canon)
```

---

### `evaluate_shotlist(shotlist, snapshot=None) -> CanonDecision`

Evaluates a `ShotList` and returns a `CanonDecision` artifact (`allow` or `deny`).

```python
from canon import evaluate_shotlist

decision = evaluate_shotlist(shotlist)          # allow / deny
decision = evaluate_shotlist(shotlist, snapshot) # also checks dead characters
```

Deny triggers (in priority order):

| Priority | Trigger | `reasons` value |
|---|---|---|
| 1 (highest) | Shot text contains `APPEARS:<char_id>` and that character is dead in snapshot | `["CANON_CONTRADICTION"]` |
| 2 | Shot text contains `__FORBIDDEN__` (policy-file token) | `["FORBIDDEN_TOKEN"]` |
| 3 | Shot text contains bare `FORBIDDEN` (word boundary) | verbose reason strings |

---

## Contract schemas

All JSON schemas are in `third_party/contracts/schemas/`:

| Schema | Purpose |
|---|---|
| `Script.v1.json` | Input to `produce-shotlist` and `validate-script` |
| `ShotList.v1.json` | Output of `produce-shotlist`; input to `validate-shotlist` |

---

## Development

```bash
./setup.sh
```

| Option | Action |
|---|---|
| `1` | Run all tests (`pytest -q` — covers `world_engine/tests/`, `canon/tests/`, `tests/`) |
| `2` | Install requirements (`pip install -r requirements.txt`) |
| `3` | Show CLI usage |

### Run tests directly

```bash
# All tests
python -m pytest -q

# Canon tests only
python -m pytest canon/tests/ -v

# World-engine tests only
python -m pytest world_engine/tests/ -v
```

Current test count: **222 passed, 1 skipped**.
