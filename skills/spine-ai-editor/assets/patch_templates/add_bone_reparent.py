#!/usr/bin/env python3
"""
patch_templates/add_bone_reparent.py — TEMPLATE

Structural Spine modifications (Spine 3.8):
  - Insert a new child bone into an existing parent
  - Optionally rebind a slot to the new bone (so its attachment follows the new bone)
  - Optionally reparent an existing bone (for visual connection fixes)

Use case examples:
  - 加 main_chest bone 讓胸甲能單獨動（不帶動手臂）
  - Reparent main_head 到 main_chest 之下，讓頭跟胸口連動
  - 加 main_aura bone + slot 掛新光環配件
  - 加 Hit_main_chest 對稱化 Hit_ 骨架

Pre-flight requirements:
  - run validator BEFORE: confirm baseline is valid
  - run validator AFTER: confirm no broken references
  - Cocos: structural change requires refresh + re-import skeleton data
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path


# ============================================================================
# FILL IN: structural modifications
# ============================================================================

# (1) New bones to insert
NEW_BONES = [
    # Example: insert main_chest under bady_up
    # {
    #     "name": "main_chest",
    #     "parent": "bady_up",
    #     # x, y default to 0  (do NOT set them unless you have a reason)
    #     # scaleX, scaleY default to 1
    #     # transform mode default = "normal"
    # },
    # Example: insert main_aura at scene origin (for full-body effect)
    # {
    #     "name": "main_aura",
    #     "parent": "main",
    #     "y": 100,
    #     "scaleX": 2, "scaleY": 2,
    # },
]

# (2) Slot.bone rebindings (move existing slots to new bones)
SLOT_REBINDS = {
    # Example: body_up slot moves from bady_up to main_chest
    # "body_up": "main_chest",
}

# (3) Bone reparents (move existing bones under new parents)
# Each entry must specify new x/y to maintain world position!
BONE_REPARENTS = {
    # Example: reparent main_head from main to main_chest
    # Compute new x, y so setup world position is unchanged.
    # Original main_head: relative to main, x=31.96, y=236.59
    # main_chest world (in main coords): bady_up.y + main_chest.y = 77.56 + 0 = 77.56
    # main_head new local y = 236.59 - 77.56 = 159.03
    # "main_head": {
    #     "parent": "main_chest",
    #     "x": 31.96,
    #     "y": 159.03,
    #     "transform": "onlyTranslation",  # 推薦：只繼承位移，避免 cascade scale
    # }
}

# (4) Add new slots (for new bones / new attachments)
NEW_SLOTS = [
    # Example: add aura slot bound to main_aura
    # {
    #     "name": "main_aura_slot",
    #     "bone": "main_aura",
    #     "blend": "additive",
    # }
]

# (5) Add new attachments to default skin (often referencing existing atlas regions)
# Format: {slot_name: {attachment_key: {attachment_data}}}
NEW_ATTACHMENTS_DEFAULT_SKIN = {
    # Example: reuse hit_main_glow_00 region as aura
    # "main_aura_slot": {
    #     "main_aura_attachment": {
    #         "name": "hit_main_glow_00",
    #         "width": 250, "height": 250,
    #     }
    # }
}

# (6) Optional: add a verification animation that exercises the new bone(s)
# Strongly recommended — proves the bone is actually animatable.
VERIFICATION_ANIM_NAME = None  # set to e.g. "Fg_Main_Chest_Demo" to enable
VERIFICATION_ANIM_BONES = {
    # Example: animate main_chest to demonstrate it works
    # "main_chest": {
    #     "translate": [
    #         {"time": 0.0, "y":  0},
    #         {"time": 1.0, "y": -7},
    #         {"time": 2.0, "y":  0},
    #     ]
    # }
}


# ============================================================================
# IMPLEMENTATION
# ============================================================================

def patch(spine_json_path: Path) -> dict:
    data = json.loads(spine_json_path.read_text())

    log = {"changes": []}

    # ---- 1. Insert new bones ----
    bone_names = {b["name"] for b in data["bones"]}
    for nb in NEW_BONES:
        if nb["name"] in bone_names:
            raise RuntimeError(f"Bone {nb['name']!r} already exists")
        parent = nb.get("parent")
        if parent and parent not in bone_names:
            raise RuntimeError(f"Parent bone {parent!r} not found")
        # Insert right after parent for tidy hierarchy display
        if parent:
            new_bones = []
            for b in data["bones"]:
                new_bones.append(b)
                if b["name"] == parent:
                    new_bones.append(nb)
            data["bones"] = new_bones
        else:
            data["bones"].append(nb)
        bone_names.add(nb["name"])
        log["changes"].append(f"added bone {nb['name']} under {parent or 'root'}")

    # ---- 2. Reparent existing bones ----
    for bone_name, new_props in BONE_REPARENTS.items():
        found = False
        for b in data["bones"]:
            if b["name"] == bone_name:
                old_parent = b.get("parent", "root")
                if new_props["parent"] not in bone_names:
                    raise RuntimeError(f"Reparent target {new_props['parent']!r} not found")
                b["parent"] = new_props["parent"]
                if "x" in new_props: b["x"] = new_props["x"]
                if "y" in new_props: b["y"] = new_props["y"]
                if "transform" in new_props: b["transform"] = new_props["transform"]
                log["changes"].append(
                    f"reparented {bone_name}: {old_parent} -> {new_props['parent']} "
                    f"(transform={new_props.get('transform', 'normal')})"
                )
                found = True
                break
        if not found:
            raise RuntimeError(f"Bone to reparent {bone_name!r} not found")

    # ---- 3. Slot rebinds ----
    slot_names = {s["name"] for s in data["slots"]}
    for slot_name, new_bone in SLOT_REBINDS.items():
        if slot_name not in slot_names:
            raise RuntimeError(f"Slot {slot_name!r} not found")
        if new_bone not in bone_names:
            raise RuntimeError(f"Slot rebind target {new_bone!r} bone not found")
        for s in data["slots"]:
            if s["name"] == slot_name:
                old_bone = s["bone"]
                s["bone"] = new_bone
                log["changes"].append(f"slot {slot_name}.bone: {old_bone} -> {new_bone}")
                break

    # ---- 4. New slots ----
    for ns in NEW_SLOTS:
        if ns["name"] in slot_names:
            raise RuntimeError(f"Slot {ns['name']!r} already exists")
        if ns.get("bone") not in bone_names:
            raise RuntimeError(f"New slot bone {ns.get('bone')!r} not found")
        data["slots"].append(ns)
        slot_names.add(ns["name"])
        log["changes"].append(f"added slot {ns['name']} bound to {ns['bone']}")

    # ---- 5. New attachments in default skin ----
    if NEW_ATTACHMENTS_DEFAULT_SKIN:
        default_skin = data["skins"][0]["attachments"]  # Spine 3.8 list form
        for slot_name, atts in NEW_ATTACHMENTS_DEFAULT_SKIN.items():
            default_skin.setdefault(slot_name, {})
            for att_key, att_data in atts.items():
                if att_key in default_skin[slot_name]:
                    raise RuntimeError(f"Attachment {slot_name}.{att_key} already exists")
                default_skin[slot_name][att_key] = att_data
                log["changes"].append(
                    f"added attachment default.{slot_name}.{att_key} "
                    f"-> region {att_data.get('name', att_key)!r}"
                )

    # ---- 6. Verification animation ----
    if VERIFICATION_ANIM_NAME:
        if VERIFICATION_ANIM_NAME in data["animations"]:
            print(f"[warn] {VERIFICATION_ANIM_NAME} exists, replacing")
        # Build default slot overrides (show all body parts, hide weapon)
        body_slots = ["arm_L", "arm_R", "body_down", "body_up", "hand_L", "hand_R", "head"]
        weapon_slots = ["sword", "sword-glow", "sword_glow_00"]
        slots_block = {sn: {"attachment": [{"name": sn}]} for sn in body_slots if sn in slot_names}
        slots_block.update({sn: {"attachment": [{"name": None}]} for sn in weapon_slots if sn in slot_names})
        data["animations"][VERIFICATION_ANIM_NAME] = {
            "slots": slots_block,
            "bones": VERIFICATION_ANIM_BONES,
        }
        log["changes"].append(f"added verification animation {VERIFICATION_ANIM_NAME}")

    spine_json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    log["total_bones"] = len(data["bones"])
    log["total_slots"] = len(data["slots"])
    log["total_animations"] = len(data["animations"])
    return log


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("spine_json", help="Path to spine .json")
    args = p.parse_args(argv)
    result = patch(Path(args.spine_json))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
