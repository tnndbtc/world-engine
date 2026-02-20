"""Phase 0 shot template library.

Templates are deterministic rules mapping a beat type to camera parameters and
duration bounds.  No external state; no randomness.  The five templates cover
every beat type produced by the Phase 0 adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class ShotTemplate:
    template_id: str
    camera_framing: str
    camera_movement: str
    base_duration_sec: float
    duration_min_sec: float
    duration_max_sec: float
    default_music_mood: Optional[str] = None


SHOT_TEMPLATES: Dict[str, ShotTemplate] = {
    "tpl_establishing": ShotTemplate(
        template_id="tpl_establishing",
        camera_framing="WIDE",
        camera_movement="STATIC",
        base_duration_sec=3.0,
        duration_min_sec=2.5,
        duration_max_sec=5.0,
    ),
    "tpl_dialogue": ShotTemplate(
        template_id="tpl_dialogue",
        camera_framing="MEDIUM",
        camera_movement="STATIC",
        base_duration_sec=3.0,
        duration_min_sec=2.0,
        duration_max_sec=8.0,
    ),
    "tpl_reaction": ShotTemplate(
        template_id="tpl_reaction",
        camera_framing="CLOSE_UP",
        camera_movement="STATIC",
        base_duration_sec=2.0,
        duration_min_sec=1.5,
        duration_max_sec=3.0,
    ),
    "tpl_action": ShotTemplate(
        template_id="tpl_action",
        camera_framing="WIDE",
        camera_movement="PAN_LEFT",
        base_duration_sec=2.5,
        duration_min_sec=1.5,
        duration_max_sec=5.0,
    ),
    "tpl_cutaway": ShotTemplate(
        template_id="tpl_cutaway",
        camera_framing="CLOSE_UP",
        camera_movement="SLOW_ZOOM_IN",
        base_duration_sec=2.0,
        duration_min_sec=1.5,
        duration_max_sec=3.0,
    ),
}
