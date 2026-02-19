from typing import Tuple, Dict, Any

Canon = Dict[str, Any]
CanonDiff = Dict[str, Any]


def apply_canon_diff(canon: Canon, diff: CanonDiff) -> Tuple[Canon, list[str]]:
    """Apply *diff* to *canon* after validation.

    Pipeline:
      1. validate_diff  — structural / shape checks
      2. check_hard_contradictions — canon-aware gate (name/age/alive/location)
      3. apply_diff     — pure merge (only reached when no errors)

    Returns:
        (new_canon, [])      — diff accepted; new_canon reflects changes.
        (canon,     errors)  — diff rejected; original canon is returned unchanged.
    """
    # Lazy imports avoid circular dependency while keeping contract.py importable
    # by gate.py and diff.py (which import only the type aliases defined above).
    from .diff import validate_diff, apply_diff          # noqa: PLC0415
    from .gate import check_hard_contradictions          # noqa: PLC0415

    errors = validate_diff(diff)
    if errors:
        return (canon, errors)

    errors = check_hard_contradictions(canon, diff)
    if errors:
        return (canon, errors)

    new_canon = apply_diff(canon, diff)
    return (new_canon, [])
