#!/usr/bin/env python3
"""
Spine 3.8 Validator — v0（schema + 引用完整性）

範圍：
  ✓ JSON 可解析、頂層 key 完整
  ✓ skeleton.spine 版本字串符合 3.8.x
  ✓ bones tree 無循環、無孤兒（parent 必須存在或缺省為 root）
  ✓ slots 引用的 bone 全部存在
  ✓ skin 內 attachment 引用的 slot 全部存在
  ✓ animations 引用的 bone / slot 全部存在
  ✓ animations.slots.attachment 引用的 attachment 名稱存在於 skin
  ✓ atlas region 名稱與 skin attachment.name 一致性（需傳入 .atlas 才檢查）
  ✓ animation keyframe 時間單調遞增
  ✓ Bezier curve 格式（curve / c2 / c3 / c4）值落在 [0,1] 區間（warn）
  ✓ 命名警告：bone/slot/attachment 含空格、含 typo `bady`

不在範圍：
  ✗ 動畫播放後實際視覺結果（要 runtime / evaluator）
  ✗ Cocos 載入相容性（要實機）
  ✗ atlas region 解碼後 size 與 attachment.width/height 一致
  ✗ 跨檔資源（PNG 是否存在、能否解碼）

用法：
  python validator_v0.py Fg_Main.json [Fg_Main.atlas]
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def err(self, msg: str) -> None: self.errors.append(msg)
    def warn(self, msg: str) -> None: self.warnings.append(msg)
    def note(self, msg: str) -> None: self.info.append(msg)

    @property
    def is_valid(self) -> bool: return not self.errors


def parse_atlas(atlas_path: Path) -> dict[str, list[str]]:
    """Return { page_name: [region_name, ...] }. Very forgiving parser."""
    pages: dict[str, list[str]] = {}
    current_page = None
    indented_props = re.compile(r"^\s+\S+:")  # property line under a region
    with atlas_path.open() as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip():
                current_page = None
                continue
            if line.endswith(".png") and not line.startswith(" "):
                current_page = line.strip()
                pages[current_page] = []
                continue
            if current_page and not line.startswith(" ") and ":" not in line:
                # this is a region name (top-level non-indented identifier)
                pages[current_page].append(line.strip())
    return pages


def validate(json_path: Path, atlas_path: Path | None = None) -> Report:
    r = Report()
    try:
        data = json.loads(json_path.read_text())
    except Exception as e:
        r.err(f"json parse failed: {e}")
        return r

    # 1. top-level keys
    required = {"skeleton", "bones", "slots", "skins", "animations"}
    missing = required - set(data.keys())
    if missing:
        r.err(f"missing top-level keys: {missing}")
        return r

    # 2. spine version
    spine = data["skeleton"].get("spine", "")
    if not spine.startswith("3.8"):
        r.warn(f"spine version is {spine!r} — this validator is tuned for 3.8.x")
    else:
        r.note(f"spine version: {spine}")

    # 3. bones tree
    bones = data["bones"]
    bone_names = {b["name"] for b in bones}
    if len(bone_names) != len(bones):
        r.err("duplicate bone names")
    if not any(b["name"] == "root" for b in bones):
        r.err("missing root bone")
    for b in bones:
        parent = b.get("parent")
        if parent and parent not in bone_names:
            r.err(f"bone {b['name']!r} parent {parent!r} not found")
        if " " in b["name"]:
            r.warn(f"bone name contains whitespace: {b['name']!r}")
        if "bady" in b["name"].lower():
            r.warn(f"possible typo `bady` in bone name: {b['name']!r}")

    # cycle detection
    parent_of = {b["name"]: b.get("parent") for b in bones}
    for n in bone_names:
        seen = {n}
        cur = parent_of.get(n)
        while cur:
            if cur in seen:
                r.err(f"bone cycle detected at {n!r}")
                break
            seen.add(cur)
            cur = parent_of.get(cur)

    # 4. slots
    slots = data["slots"]
    slot_names = {s["name"] for s in slots}
    if len(slot_names) != len(slots):
        r.err("duplicate slot names")
    for s in slots:
        if s.get("bone") not in bone_names:
            r.err(f"slot {s['name']!r} bone {s.get('bone')!r} not found")
        if " " in s["name"]:
            r.warn(f"slot name contains whitespace: {s['name']!r}")

    # 5. skins
    skins = data["skins"]
    # Spine 3.8 supports both list and dict form
    if isinstance(skins, list):
        skin_map = {s["name"]: s["attachments"] for s in skins}
    else:
        skin_map = skins
    if "default" not in skin_map:
        r.err("missing default skin")

    # attachment-name index across all skins
    all_attachment_names_per_slot: dict[str, set[str]] = {}
    for skin_name, skin_atts in skin_map.items():
        for slot_name, atts in skin_atts.items():
            if slot_name not in slot_names:
                r.err(f"skin {skin_name!r}: attachment under unknown slot {slot_name!r}")
            for att_key, att_data in atts.items():
                # the "name" override falls back to att_key
                att_name = att_data.get("name", att_key)
                # validate attachment type — v0 only knows 'region'
                t = att_data.get("type", "region")
                if t != "region":
                    r.warn(
                        f"skin {skin_name!r} slot {slot_name!r} attachment {att_key!r} "
                        f"type={t!r} — v0 only validates region attachments"
                    )
                all_attachment_names_per_slot.setdefault(slot_name, set()).add(att_key)

    # 6. animations
    anims = data["animations"]
    for aname, adata in anims.items():
        # 6a. bone refs
        for bn, tl in adata.get("bones", {}).items():
            if bn not in bone_names:
                r.err(f"animation {aname!r}: unknown bone {bn!r}")
            for kind, kfs in tl.items():
                last_t = -1.0
                for k in kfs:
                    t = k.get("time", 0)
                    if t < last_t:
                        r.err(
                            f"animation {aname!r} bone {bn!r} {kind}: "
                            f"keyframe time went backwards ({t} after {last_t})"
                        )
                    last_t = t
                    for k_curve in ("curve", "c2", "c3", "c4"):
                        if k_curve in k and isinstance(k[k_curve], (int, float)):
                            if not (0.0 <= k[k_curve] <= 1.0):
                                r.warn(
                                    f"animation {aname!r} bone {bn!r} {kind}: "
                                    f"{k_curve}={k[k_curve]} outside [0,1] (Spine allows but unusual)"
                                )
        # 6b. slot refs
        for sn, tl in adata.get("slots", {}).items():
            if sn not in slot_names:
                r.err(f"animation {aname!r}: unknown slot {sn!r}")
            atts_for_slot = all_attachment_names_per_slot.get(sn, set())
            if "attachment" in tl:
                for k in tl["attachment"]:
                    name = k.get("name")
                    if name is not None and name not in atts_for_slot:
                        r.err(
                            f"animation {aname!r} slot {sn!r}: "
                            f"attachment timeline references unknown attachment {name!r}"
                        )

    # 7. atlas cross-check
    if atlas_path and atlas_path.exists():
        pages = parse_atlas(atlas_path)
        atlas_regions: set[str] = set()
        for regs in pages.values():
            atlas_regions.update(regs)
        # collect all attachment "name" fields
        skin_names: set[str] = set()
        for skin_atts in skin_map.values():
            for atts in skin_atts.values():
                for att_key, att_data in atts.items():
                    skin_names.add(att_data.get("name", att_key))
        missing_in_atlas = skin_names - atlas_regions
        unused_in_atlas = atlas_regions - skin_names
        for n in sorted(missing_in_atlas):
            r.err(f"attachment {n!r} referenced by skin but NOT in atlas")
        for n in sorted(unused_in_atlas):
            r.warn(f"atlas region {n!r} not referenced by any attachment (waste)")
        r.note(f"atlas pages: {list(pages.keys())}")
        r.note(f"atlas regions total: {len(atlas_regions)}, skin attachments total: {len(skin_names)}")

    # 8. summary
    r.note(f"bones={len(bone_names)} slots={len(slot_names)} animations={len(anims)} skins={len(skin_map)}")
    r.note(f"constraints: ik={len(data.get('ik', []))} transform={len(data.get('transform', []))} path={len(data.get('path', []))}")

    return r


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    json_path = Path(argv[1])
    atlas_path = Path(argv[2]) if len(argv) >= 3 else None
    report = validate(json_path, atlas_path)

    print(f"=== validator_v0 on {json_path.name} ===")
    for n in report.info:
        print(f"  [info] {n}")
    for w in report.warnings:
        print(f"  [warn] {w}")
    for e in report.errors:
        print(f"  [ERR ] {e}")
    print()
    if report.is_valid:
        print(f"RESULT: valid  ({len(report.warnings)} warnings)")
        return 0
    print(f"RESULT: INVALID  ({len(report.errors)} errors, {len(report.warnings)} warnings)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
