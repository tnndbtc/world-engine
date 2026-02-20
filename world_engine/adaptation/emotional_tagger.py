"""Emotional tag inference for shots.

Derives shot-level emotional tags from per-line dialogue emotions and
scene-level emotional_tags.  Pure functions — no I/O, no external state.
"""
from __future__ import annotations

from typing import Optional

from world_engine.adaptation.models import DialogueLine, Scene


def _first_scene_tag(scene: Scene) -> Optional[str]:
    """Return the first scene-level emotional tag, or None."""
    return scene.emotional_tags[0] if scene.emotional_tags else None


def tag_for_dialogue(line: DialogueLine, scene: Scene) -> Optional[str]:
    """Dialogue shot tag: prefer the line's own emotion, fall back to scene tag."""
    if line.emotion:
        return line.emotion
    return _first_scene_tag(scene)


def tag_for_reaction(scene: Scene) -> Optional[str]:
    """Reaction shot tag: inherit the scene-level emotion."""
    return _first_scene_tag(scene)


def tag_for_scene_beat(scene: Scene) -> Optional[str]:
    """Establishing, action, or cutaway shot tag: inherit scene-level emotion."""
    return _first_scene_tag(scene)


def derive_music_mood(scene: Scene) -> Optional[str]:
    """Map scene emotional_tags to a music mood hint (first tag, if present)."""
    return _first_scene_tag(scene)
