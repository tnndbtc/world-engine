"""Script → ShotList adapter (§8 Film Adaptation Flow).

Public entry point
------------------
    adapt_script(script, created_at=...) -> ShotList

All sub-stages are pure functions.  No file I/O, no external state, no
randomness.

Determinism guarantees
----------------------
- shot_id     — f"{scene_id}_shot_{global_index:03d}", zero-padded, monotonic
- shotlist_id — "sl_" + SHA-256(script_id)[:16]
- durations   — word-count formula with fixed constants; round(x, 3)
- created_at  — always caller-supplied or the fixed epoch constant below;
                the adapter NEVER reads the system clock
"""
from __future__ import annotations

import hashlib
from typing import List, Optional, Tuple

from world_engine.adaptation.emotional_tagger import (
    derive_music_mood,
    tag_for_dialogue,
    tag_for_reaction,
    tag_for_scene_beat,
)
from world_engine.adaptation.models import (
    AudioIntent,
    CanonSnapshot,
    CharacterInShot,
    Scene,
    Script,
    Shot,
    ShotList,
)
from world_engine.adaptation.shot_templates import SHOT_TEMPLATES
from world_engine.adaptation.timing import compute_timing_lock_hash, estimate_shot_duration


# ── Public API ────────────────────────────────────────────────────────────────


# Deterministic epoch default — used when the caller does not supply created_at.
# This constant ensures adapt_script() is fully pure even when called without
# arguments; the system clock is never consulted.
_DEFAULT_CREATED_AT: str = "1970-01-01T00:00:00Z"


def adapt_script(
    script: Script,
    created_at: str = _DEFAULT_CREATED_AT,
    *,
    canon_snapshot: Optional[CanonSnapshot] = None,  # noqa: F841 – plumbing only
) -> ShotList:
    """Convert a validated Script into a ShotList with timing_lock_hash.

    Args:
        script:         A validated Script model (§5.5).
        created_at:     ISO 8601 datetime string stamped on the ShotList artifact.
                        Defaults to "1970-01-01T00:00:00Z".  The adapter NEVER
                        reads the system clock; callers that need a real timestamp
                        must supply it explicitly.
        canon_snapshot: Optional validated CanonSnapshot (Wave-6 plumbing).
                        Accepted and validated by the caller but not used in any
                        computation — ShotList output is byte-identical with or
                        without it.

    Returns:
        A ShotList (§5.6) where every shot has duration_sec > 0 and the
        timing_lock_hash covers shot ordering and all durations.
    """
    shots = _build_shots(script)
    total = round(sum(s.duration_sec for s in shots), 3)
    timing_hash = compute_timing_lock_hash(shots)
    shotlist_id = _make_shotlist_id(script.script_id)

    shotlist = ShotList(
        schema_id="ShotList",
        schema_version="0.0.1",
        producer={"repo": "world-engine", "component": "ShotListAdapter"},
        shotlist_id=shotlist_id,
        script_id=script.script_id,
        episode_id=script.episode_id,
        shots=shots,
        total_duration_sec=total,
        timing_lock_hash=timing_hash,
        created_at=created_at,
    )
    # Local import avoids a circular import via adaptation/__init__.py → adapter
    # → contract_validate → shotlist_v1 → adaptation.models → __init__.py.
    from world_engine.contract_validate import validate_shotlist_model  # noqa: PLC0415
    validate_shotlist_model(shotlist)
    return shotlist


# ── ID helpers ────────────────────────────────────────────────────────────────


def _make_shotlist_id(script_id: str) -> str:
    """Deterministic shotlist ID: "sl_" + first 16 hex chars of SHA-256(script_id)."""
    digest = hashlib.sha256(script_id.encode("utf-8")).hexdigest()
    return f"sl_{digest[:16]}"


def _make_shot_id(scene_id: str, global_index: int) -> str:
    """Deterministic shot ID: "{scene_id}_shot_{index:03d}"."""
    return f"{scene_id}_shot_{global_index:03d}"


# ── Shot construction ─────────────────────────────────────────────────────────


def _build_shots(script: Script) -> List[Shot]:
    shots: List[Shot] = []
    global_index = 0
    for scene in script.scenes:
        scene_shots, global_index = _process_scene(scene, global_index)
        shots.extend(scene_shots)
    return shots


def _process_scene(scene: Scene, start_index: int) -> Tuple[List[Shot], int]:
    """Expand one scene into an ordered list of shots.

    Beat order:
        1. ESTABLISHING (always first)
        2. For each dialogue line:
               DIALOGUE shot
               + REACTION shot (only when scene has ≥ 2 characters)
        3. For each action: ACTION shot
        4. If no dialogue AND no actions: single CUTAWAY shot
    """
    shots: List[Shot] = []
    idx = start_index
    has_content = bool(scene.dialogue or scene.actions)
    multi_char = len(scene.characters) >= 2
    music_mood = derive_music_mood(scene)
    env_notes = f"{scene.location}, {scene.time_of_day}"

    # ── 1. Establishing ───────────────────────────────────────────────────
    tpl = SHOT_TEMPLATES["tpl_establishing"]
    shots.append(
        Shot(
            shot_id=_make_shot_id(scene.scene_id, idx),
            scene_id=scene.scene_id,
            duration_sec=estimate_shot_duration(tpl),
            camera_framing=tpl.camera_framing,
            camera_movement=tpl.camera_movement,
            characters=[CharacterInShot(character_id=c) for c in scene.characters],
            environment_notes=env_notes,
            action_beat=f"Establishing shot of {scene.location}.",
            audio_intent=AudioIntent(music_mood=music_mood),
            emotional_tag=tag_for_scene_beat(scene),
            shot_template_id=tpl.template_id,
        )
    )
    idx += 1

    # ── 2. Dialogue beats ──────────────────────────────────────────────────
    for line in scene.dialogue:
        tpl_dlg = SHOT_TEMPLATES["tpl_dialogue"]
        shots.append(
            Shot(
                shot_id=_make_shot_id(scene.scene_id, idx),
                scene_id=scene.scene_id,
                duration_sec=estimate_shot_duration(tpl_dlg, text=line.text),
                camera_framing=tpl_dlg.camera_framing,
                camera_movement=tpl_dlg.camera_movement,
                characters=[CharacterInShot(character_id=line.speaker_id)],
                environment_notes=env_notes,
                action_beat=f"{line.speaker_id} speaks.",
                audio_intent=AudioIntent(
                    vo_text=line.text,
                    vo_speaker_id=line.speaker_id,
                    music_mood=music_mood,
                ),
                emotional_tag=tag_for_dialogue(line, scene),
                shot_template_id=tpl_dlg.template_id,
            )
        )
        idx += 1

        if multi_char:
            tpl_rx = SHOT_TEMPLATES["tpl_reaction"]
            react_chars = [
                CharacterInShot(character_id=c)
                for c in scene.characters
                if c != line.speaker_id
            ]
            shots.append(
                Shot(
                    shot_id=_make_shot_id(scene.scene_id, idx),
                    scene_id=scene.scene_id,
                    duration_sec=estimate_shot_duration(tpl_rx),
                    camera_framing=tpl_rx.camera_framing,
                    camera_movement=tpl_rx.camera_movement,
                    characters=react_chars,
                    environment_notes=env_notes,
                    action_beat="Reaction shot.",
                    audio_intent=AudioIntent(music_mood=music_mood),
                    emotional_tag=tag_for_reaction(scene),
                    shot_template_id=tpl_rx.template_id,
                )
            )
            idx += 1

    # ── 3. Action beats ────────────────────────────────────────────────────
    for action in scene.actions:
        tpl_act = SHOT_TEMPLATES["tpl_action"]
        action_chars = (
            [CharacterInShot(character_id=c) for c in action.characters]
            if action.characters
            else [CharacterInShot(character_id=c) for c in scene.characters]
        )
        shots.append(
            Shot(
                shot_id=_make_shot_id(scene.scene_id, idx),
                scene_id=scene.scene_id,
                duration_sec=estimate_shot_duration(tpl_act),
                camera_framing=tpl_act.camera_framing,
                camera_movement=tpl_act.camera_movement,
                characters=action_chars,
                environment_notes=env_notes,
                action_beat=action.description,
                audio_intent=AudioIntent(music_mood=music_mood),
                emotional_tag=tag_for_scene_beat(scene),
                shot_template_id=tpl_act.template_id,
            )
        )
        idx += 1

    # ── 4. Cutaway — only when no other content ────────────────────────────
    if not has_content:
        tpl_cut = SHOT_TEMPLATES["tpl_cutaway"]
        shots.append(
            Shot(
                shot_id=_make_shot_id(scene.scene_id, idx),
                scene_id=scene.scene_id,
                duration_sec=estimate_shot_duration(tpl_cut),
                camera_framing=tpl_cut.camera_framing,
                camera_movement=tpl_cut.camera_movement,
                characters=[CharacterInShot(character_id=c) for c in scene.characters],
                environment_notes=env_notes,
                action_beat="Cutaway detail.",
                audio_intent=AudioIntent(music_mood=music_mood),
                emotional_tag=tag_for_scene_beat(scene),
                shot_template_id=tpl_cut.template_id,
            )
        )
        idx += 1

    return shots, idx
