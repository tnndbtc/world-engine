"""Script and ShotList data models — the canonical data contracts for Workstream B.

schema_version "1.0.0" is embedded in both top-level models so every artifact
is self-describing (§30.1).  extra="ignore" on all models gives forward-
compatibility: unknown fields from future schema versions are silently dropped
rather than rejected (§30.2).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


# ── Script models ─────────────────────────────────────────────────────────────


class DialogueLine(BaseModel):
    """A single line of dialogue within a scene."""

    model_config = ConfigDict(extra="ignore")

    speaker_id: str
    text: str
    emotion: Optional[str] = None


class SceneAction(BaseModel):
    """A physical action beat within a scene."""

    model_config = ConfigDict(extra="ignore")

    description: str
    characters: List[str] = []


class Scene(BaseModel):
    """A screenplay scene: location, time, characters, and ordered beats."""

    model_config = ConfigDict(extra="ignore")

    scene_id: str
    location: str
    time_of_day: str
    characters: List[str] = []
    dialogue: List[DialogueLine] = []
    actions: List[SceneAction] = []
    emotional_tags: List[str] = []


class Script(BaseModel):
    """Scene-based screenplay structure (§5.5).  No camera instructions."""

    model_config = ConfigDict(extra="ignore")

    schema_version: str = "1.0.0"
    script_id: str
    episode_id: Optional[str] = None
    title: str
    scenes: List[Scene]
    created_at: str  # ISO 8601
    metadata: Dict[str, Any] = {}


# ── ShotList models ───────────────────────────────────────────────────────────


class CharacterInShot(BaseModel):
    """A character's appearance within a single shot."""

    model_config = ConfigDict(extra="ignore")

    character_id: str
    expression: Optional[str] = None
    pose: Optional[str] = None


class AudioIntent(BaseModel):
    """Audio intent for a shot: VO reference, SFX tags, and music mood."""

    model_config = ConfigDict(extra="ignore")

    vo_text: Optional[str] = None
    vo_speaker_id: Optional[str] = None
    sfx_tags: List[str] = []
    music_mood: Optional[str] = None


class Shot(BaseModel):
    """A single film shot (§5.6).

    duration_sec is required and participates in the timing_lock_hash.  Every
    other field is creative metadata that may be revised without invalidating
    the timing lock.
    """

    model_config = ConfigDict(extra="ignore")

    shot_id: str
    scene_id: str
    duration_sec: float
    camera_framing: str
    camera_movement: str
    characters: List[CharacterInShot] = []
    environment_notes: str = ""
    action_beat: str = ""
    audio_intent: AudioIntent
    emotional_tag: Optional[str] = None
    shot_template_id: Optional[str] = None


class ShotList(BaseModel):
    """Film-ready shot breakdown derived from a Script (§5.6).

    timing_lock_hash is the single timing authority referenced by RenderPlan
    and all HQ providers (§5.8, §22.2).
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: str = "1.0.0"
    shotlist_id: str
    script_id: str
    episode_id: Optional[str] = None
    shots: List[Shot]
    total_duration_sec: float
    timing_lock_hash: str
    created_at: str  # ISO 8601
    metadata: Dict[str, Any] = {}
