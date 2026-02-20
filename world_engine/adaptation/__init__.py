"""Script → ShotList adaptation package (Workstream B)."""

from world_engine.adaptation.adapter import adapt_script
from world_engine.adaptation.models import (
    AudioIntent,
    CanonSnapshot,
    CharacterInShot,
    DialogueLine,
    Scene,
    SceneAction,
    Script,
    Shot,
    ShotList,
)

__all__ = [
    "adapt_script",
    "AudioIntent",
    "CanonSnapshot",
    "CharacterInShot",
    "DialogueLine",
    "Scene",
    "SceneAction",
    "Script",
    "Shot",
    "ShotList",
]
