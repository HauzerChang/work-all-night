#!/usr/bin/env python3
"""
patch_templates/add_animation.py — TEMPLATE

Append a new animation to an existing Spine 3.8 JSON.
Use case: 加 idle 變體、舞步、特定動作等，不動骨架結構。

How to use:
  1. Copy this file to your project as `patch_<anim_name>.py`
  2. Fill in:
     - ANIM_NAME
     - DURATION (seconds, defines loop length)
     - SLOT_OVERRIDES (which slots to show/hide attachment-wise)
     - BONE_TIMELINES (the actual animation data)
  3. Run: `python patch_<anim_name>.py <path-to-spine.json>`
  4. Validate: `python validator_v0.py <path-to-spine.json> <path-to-spine.atlas>`
  5. Push to Cocos via cocos_mcp_push_sop.md procedure

Key constraints (broken = animation won't load):
  - All bone names referenced must exist in skeleton (run validator!)
  - All slot names referenced must exist in skeleton
  - All attachment names in slot.attachment timelines must exist in default skin
  - Linear curves are default (no "curve" key needed)
  - Bezier easing uses Spine 3.8 compact format: {"curve": cx1, "c2": cy1, "c3": cx2, "c4": cy2}
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path


# ============================================================================
# FILL IN: animation specification
# ============================================================================

ANIM_NAME = "Fg_Main_NewMove"   # <-- CHANGE THIS
DURATION = 2.0                   # seconds, defines loop endpoint

# Which slots show what during this animation.
# - {"name": "<attachment_name>"} → display this attachment
# - {"name": None}                → hide this slot
SLOT_OVERRIDES = {
    # examples:
    "arm_L":  {"attachment": [{"name": "arm_L"}]},
    "arm_R":  {"attachment": [{"name": "arm_R"}]},
    "body_up": {"attachment": [{"name": "body_up"}]},
    # ... fill in all body slots that should be visible

    # Hide weapon during dance:
    "sword":         {"attachment": [{"name": None}]},
    "sword-glow":    {"attachment": [{"name": None}]},
    "sword_glow_00": {"attachment": [{"name": None}]},
}

# Which bones move and how.
# Common patterns:
#   - 4-key loop:     t=0 (start) → t=D/3 → t=2D/3 → t=D (=start for seamless loop)
#   - 3-key triangle: t=0 → t=D/2 (peak) → t=D (back to start)
#   - frame-by-frame: every 1/30s a new key
BONE_TIMELINES = {
    # Example: body bobs up and down
    "main": {
        "translate": [
            {"time": 0.0, "y": 0},
            {"time": 1.0, "y": -3},   # sink down
            {"time": 2.0, "y": 0},    # back to start (loop point)
        ]
    },
    # Example: left arm tilts then resets
    "main_arm_L": {
        "rotate": [
            {"time": 0.0, "angle":  0},
            {"time": 1.0, "angle": 20},
            {"time": 2.0, "angle":  0},
        ]
    },
    # ... add as many bones as needed
}


# ============================================================================
# IMPLEMENTATION (usually no need to edit)
# ============================================================================

def patch(spine_json_path: Path, overwrite: bool = False) -> dict:
    data = json.loads(spine_json_path.read_text())

    # Pre-flight checks
    if ANIM_NAME in data["animations"] and not overwrite:
        raise RuntimeError(
            f"Animation {ANIM_NAME!r} already exists. Use --overwrite to replace."
        )

    bone_names = {b["name"] for b in data["bones"]}
    slot_names = {s["name"] for s in data["slots"]}

    for bn in BONE_TIMELINES:
        if bn not in bone_names:
            raise RuntimeError(f"Bone {bn!r} not in skeleton")
    for sn in SLOT_OVERRIDES:
        if sn not in slot_names:
            raise RuntimeError(f"Slot {sn!r} not in skeleton")

    # Build the new animation
    data["animations"][ANIM_NAME] = {
        "slots": copy.deepcopy(SLOT_OVERRIDES),
        "bones": copy.deepcopy(BONE_TIMELINES),
    }

    # Write back (pretty-printed for diff-ability)
    spine_json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    n_keys = sum(
        sum(len(kfs) for kfs in tl.values())
        for tl in BONE_TIMELINES.values()
    )
    return {
        "animation_added": ANIM_NAME,
        "duration_s": DURATION,
        "bones_animated": list(BONE_TIMELINES.keys()),
        "slots_touched": list(SLOT_OVERRIDES.keys()),
        "total_keyframes": n_keys,
        "total_animations_in_file": len(data["animations"]),
        "animation_names_in_file": list(data["animations"].keys()),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("spine_json", help="Path to spine .json")
    p.add_argument("--overwrite", action="store_true", help="Replace if animation exists")
    args = p.parse_args(argv)

    result = patch(Path(args.spine_json), overwrite=args.overwrite)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
