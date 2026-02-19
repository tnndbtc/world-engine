"""
canon_io.py — Load and save Canon JSON snapshots.

Canon files are written with sorted keys and consistent indentation so that
identical Canon states always produce byte-identical files (deterministic).
"""

import json
from .contract import Canon


def load_canon(path: str) -> Canon:
    """Load a Canon snapshot from a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        The Canon dict.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_canon(path: str, canon: Canon) -> None:
    """Save a Canon snapshot to a JSON file.

    Keys are sorted at every level and indentation is fixed at 2 spaces so
    that repeated saves of the same Canon produce identical bytes.

    Args:
        path: Destination file path (created or overwritten).
        canon: The Canon dict to persist.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(canon, f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")  # POSIX trailing newline
