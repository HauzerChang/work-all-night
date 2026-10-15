# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 的 **mesh 生成 + 變形自交閘** 入口(MERGE_PLAN Phase C1,結構軸)。

== 這支解決什麼(為何是「結構軸」)==
  B2/B3/B4 把**動畫軸**(beat / 繞關節 pivot / 序列)包成 skill 入口。C1 補上**結構軸的 mesh 面**:
  把 repo 的 deform-aware mesh 生成器(`tools/mesh_gen/generate_mesh_v2.py` strip)+ 真實位移場轉移
  自交閘(`deform_eval.py`)抽成一條 skill 層級流程 ——「件貼圖 → strip mesh → 裝進 skeleton → 兩真值驗收」。

  使用者既有 `validator_v1`(v1.3.0)**只檢查** mesh attachment 的 schema(型別/引用/hull),**不生成**、
  **也不驗變形期拓樸**(變形下自交/翻面 = 撕裂/破圖,是 mesh 軸獨有、animation 閘從不碰的真值)。
  C1 把這塊**生成 + 變形自交**能力併進結構軸,並機械化驗其**雙真值 G2**。

== mesh 軸的雙真值 G2(對映 animation 軸的「遊戲能播 且 編輯器能匯入」)==
  - **真值 A(可載入 / schema)**:生成的 mesh 裝進一份完整 skeleton → 真正的 `validator_v1` **0 error**
    (mesh attachment 型別合法、引用存在 slot、hull-first 契約;runtime 能載入 / editor 能匯入)。
  - **真值 B(變形安全)**:在**真實位移場**(自真實資產如 main_draw 窗簾的 deform timeline 取「總位移最大幀」)
    轉移到生成 mesh 的頂點後,拓樸保持乾淨(self-intersections=0、triangle_flips=0、degenerate=0)。
    ⚠️ **用真實位移場轉移,不用未校準的 `stress_field`**(見 `deform_eval.stress_field` docstring 的 2026-06-24 教訓)。

== 過渡期相依(C1 → E1)==
  同 make_beat:透過其 `_wire_repo_tools()` 掛 repo `tools/mesh_gen`(generate_mesh_v2 / deform_eval /
  evaluate_mesh / atlas_crop)。E1 self-contained bundle 後移除此相依。

== strip vs auto(honest)==
  `generate_mesh_v2` 預設 `mode="auto"`:高瘦且 row-convex 的件(如窗簾)→ **strip**(順拉伸軸的掃描線格點,
  耐變形);blobby / 軟邊件(如機器人光暈/身體)→ 回退 Delaunay / boundary-dense。這是**正確的生成行為**:
  「strip」是窗簾類件的拓樸選擇,不是所有件都該 strip。變形自交閘(真值 B)只對**有 deform timeline** 的件
  適用(窗簾);weighted、靠骨綁變形的件(機器人)無逐頂點 deform → 以靜態覆蓋率 + 拓樸合法性驗收(真值 A)。

用法(程式化):
  from gen_lib.mesh_forge import generate_strip_mesh, scaffold_skeleton, deform_safety_check
  mesh = generate_strip_mesh("curtain_region.png")              # dict(strip 拓樸)
  skel = scaffold_skeleton(mesh)                                # 可載入最小 skeleton(真值 A 驗收用)
  rep  = deform_safety_check(mesh, ref_skel, "image/curtain_left", "image/curtain_left")  # 真值 B

用法(CLI):
  python3 mesh_forge.py --image curtain_region.png --out /tmp/mesh.json
  python3 mesh_forge.py --self-test                             # 不寫檔,對真實窗簾跑雙真值自檢
"""
from __future__ import annotations
import argparse
import json
import os
import sys

# 取用 make_beat 的過渡期路徑 shim(把 repo tools/mesh_gen、tools/analyzer、assets 掛上 sys.path)。
try:
    from . import make_beat as _mb
except ImportError:  # 當 gen_lib 目錄被直接加進 sys.path 時
    import make_beat as _mb


def _wire():
    """掛上 repo tools,回傳 mesh_gen 子模組 (generate_mesh_v2, deform_eval, evaluate_mesh)。"""
    _mb._wire_repo_tools()                 # 把 tools/mesh_gen、tools/analyzer、assets 掛上 sys.path
    import generate_mesh_v2 as gm          # noqa: E402  tools/mesh_gen
    import deform_eval as de               # noqa: E402
    import evaluate_mesh as em             # noqa: E402
    return gm, de, em


# ----------------------------------------------------------------- 生成
def generate_strip_mesh(image_path, rows=10, cols=3, mode="auto"):
    """件貼圖 → Spine mesh attachment dict(mode=auto:窗簾類 row-convex → strip,否則回退)。

    回傳 dict:{type:"mesh", vertices, uvs, triangles, hull, width, height, _mode}。
    _mode ∈ {"strip","delaunay-v1","boundary-dense-v1"}(strip 是窗簾類件的 deform-aware 拓樸)。
    """
    gm, _, _ = _wire()
    return gm.generate(image_path, rows=rows, cols=cols, mode=mode)


def _mesh_attachment(mesh):
    """從生成 mesh dict 取出乾淨的 Spine mesh attachment(去掉 `_` 開頭的內部鍵)。"""
    keep = ("type", "vertices", "uvs", "triangles", "hull", "width", "height",
            "edges", "color")
    return {k: mesh[k] for k in keep if k in mesh}


# ----------------------------------------------------------------- 裝進 skeleton(真值 A 的接線)
def scaffold_skeleton(mesh, slot_name="mesh_slot", att_name="m", bone="root"):
    """繞一個 mesh 建一份**最小但完整、可載入**的 Spine 3.8 skeleton(真值 A 驗收用)。

    含 skeleton/bones/slots/skins/animations 五個必備 key;mesh 裝進 default skin 的 `slot_name`。
    """
    return install_mesh(_empty_skeleton(mesh), slot_name, att_name, mesh, bone=bone)


def _empty_skeleton(mesh):
    return {
        "skeleton": {"spine": "3.8.99", "hash": "c1mesh",
                     "width": int(mesh.get("width", 0)), "height": int(mesh.get("height", 0))},
        "bones": [{"name": "root"}],
        "slots": [],
        "skins": [{"name": "default", "attachments": {}}],
        "animations": {},
    }


def install_mesh(skel, slot_name, att_name, mesh, bone="root"):
    """就地把 mesh 裝進 `skel` 的 default skin(結構軸:mesh 併進既有 skeleton)。

    - bone 不存在 → 補一根(預設掛 root 下的簡單 bone;bone=="root" 則用既有 root)。
    - slot 不存在 → 補一個(綁 bone、setup attachment = att_name)。
    - default skin 不存在 → 補一個。
    回傳同一個 skel(就地改)。可把生成 mesh 併進 make_beat/pivot 產出的 skeleton(動畫軸 × mesh 軸組合)。
    """
    bones = skel.setdefault("bones", [])
    bnames = {b.get("name") for b in bones}
    if "root" not in bnames:
        bones.insert(0, {"name": "root"})
        bnames.add("root")
    if bone != "root" and bone not in bnames:
        bones.append({"name": bone, "parent": "root"})

    slots = skel.setdefault("slots", [])
    if not any(s.get("name") == slot_name for s in slots):
        slots.append({"name": slot_name, "bone": bone, "attachment": att_name})

    skins = skel.setdefault("skins", [{"name": "default", "attachments": {}}])
    if isinstance(skins, list):
        skin = next((s for s in skins if s.get("name") == "default"), None)
        if skin is None:
            skin = {"name": "default", "attachments": {}}
            skins.append(skin)
        atts = skin.setdefault("attachments", {})
    else:  # dict 形式 skin map
        atts = skins.setdefault("default", {})
    atts.setdefault(slot_name, {})[att_name] = _mesh_attachment(mesh)
    skel.setdefault("animations", {})
    return skel


# ----------------------------------------------------------------- 變形自交閘(真值 B)
def deform_safety_check(mesh, ref_skel, ref_slot, ref_name):
    """把**真實位移場**(自 ref_skel 的 ref_slot/ref_name 在所有動畫中『總位移最大幀』取出,以 UV 為座標)
    轉移到 `mesh` 的頂點並套用,檢查變形後拓樸。

    回傳 {frame, self_intersections, triangle_flips, degenerate, area_ratio, clean}。
    clean == (si==0 and flips==0 and degenerate==0)。⚠️ 用真實場轉移(非 stress_field)。
    """
    _, de, _ = _wire()
    uvs_src, field, frame = de.real_deform_field(ref_skel, ref_slot, ref_name)
    r = de.transfer_deform_check(mesh, uvs_src, field)
    return {"frame": frame, "self_intersections": r["self_intersections"],
            "triangle_flips": r["triangle_flips"], "degenerate": r["degenerate"],
            "area_ratio": r["area_ratio"], "clean": bool(r["clean"])}


def mesh_format_report(mesh, mask, vertex_budget=64):
    """對生成 mesh 跑 evaluate_mesh 的格式/拓樸閘(hull-first、三角索引、退化、孤兒、頂點預算)。
    回傳 evaluate_mesh.evaluate 的完整報告(含 AC1_iou 若給 mask)。"""
    _, _, em = _wire()
    return em.evaluate(mesh, mask, vertex_budget=vertex_budget, iou_thresh=0.0)


# ----------------------------------------------------------------- CLI / 自檢
def _self_test():
    """對真實 main_draw 窗簾件跑雙真值自檢(需 repo assets;無 PNG 則跳過真值 B)。"""
    gm, de, em = _wire()
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.normpath(os.path.join(here, "..", "..", "..", ".."))
    sk_path = os.path.join(repo, "assets", "main_draw.json")
    atlas = os.path.join(repo, "assets", "main_draw.atlas")
    png = os.path.join(repo, "assets", "main_draw.png")
    ref = json.load(open(sk_path, encoding="utf-8"))
    out = {"pieces": {}}
    import tempfile
    import cv2
    from atlas_crop import extract
    tmp = tempfile.mkdtemp(prefix="c1forge_")
    for slot, name in [("image/curtain_left", "image/curtain_left"),
                       ("image/curtain_right", "image/curtain_right")]:
        sub = extract(atlas, png, name)
        crop = os.path.join(tmp, "r.png")
        cv2.imwrite(crop, sub)
        mesh = generate_strip_mesh(crop)
        skel = scaffold_skeleton(mesh)
        d = deform_safety_check(mesh, ref, slot, name)
        out["pieces"][name] = {"mode": mesh.get("_mode"), "nv": len(mesh["uvs"]) // 2,
                               "hull": mesh["hull"], "scaffold_keys": sorted(skel.keys()),
                               "deform": d}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", help="件貼圖(png，有 alpha)")
    ap.add_argument("--out", default=None, help="輸出 mesh json(預設 <image>_mesh_c1.json)")
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--mode", choices=["auto", "strip", "delaunay"], default="auto")
    ap.add_argument("--scaffold", action="store_true", help="輸出繞 mesh 的最小 skeleton 而非裸 mesh")
    ap.add_argument("--self-test", action="store_true", help="對真實窗簾跑雙真值自檢(不寫檔)")
    a = ap.parse_args()
    if a.self_test:
        _self_test()
        return
    if not a.image:
        ap.error("需 --image 或 --self-test")
    mesh = generate_strip_mesh(a.image, rows=a.rows, cols=a.cols, mode=a.mode)
    obj = scaffold_skeleton(mesh) if a.scaffold else mesh
    out = a.out or (a.image.rsplit(".", 1)[0] + ("_skel_c1.json" if a.scaffold else "_mesh_c1.json"))
    json.dump(obj, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print("[{}] {}: 頂點 {} (hull {}), 三角 {}".format(
        mesh.get("_mode"), out, len(mesh["uvs"]) // 2, mesh["hull"], len(mesh["triangles"]) // 3))


if __name__ == "__main__":
    main()
