#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_lib.mesh_gen — spine-ai-editor 2.0 的 **mesh 生成 + 變形自交閘** 入口(MERGE_PLAN Phase C1)。

B2/B3/B4 把 repo 的**動畫**生成(單 beat / 繞關節 pivot / 序列組合)抽成 skill 入口;C1 補上**另一個結構軸**
——**deform-aware mesh 生成**:給一張件貼圖(或從 atlas 切出的 region)→ 產出一份 Spine 3.8 mesh
attachment(strip / delaunay / boundary 依件形狀自動選),並以**真實位移場轉移**的自交閘證明它在動畫拉扯下
不會撕裂(self_intersections=0)。

== 為什麼存在(C1 相對 v1.3.0 + repo 的增量)==
  - **v1.3.0 只「檢查」既有 mesh**(拓樸/權重合法性),**不會「生成」** mesh。C1 把 repo 的
    `generate_mesh_v2`(strip + delaunay + boundary-dense,2026 SpriteToMesh 式確定性拓樸)抽成 skill
    入口,讓 2.0 能**從一張件圖自動產出可變形 mesh**(結構擴充的上游缺口)。
  - repo 的 `deform_eval` 已證對真實 main_draw 4 mesh × 9 anim 全乾淨(`_checker_validated=True`)。C1 把
    「**真實位移場轉移**」自交閘(非未校準的 `stress_field`,見 RULES/run.md 警告)包成入口的 `deform_gate`,
    讓「生成 → 真實 deform 下 si=0」成為一條固定、可機讀的驗收流程。

== 核心設計(來自里程碑 knowledge/s3-*.md)==
  - **strip 拓樸**:高瘦、row-convex 件(如窗簾 curtain_left/right)→ 掃描線格點(邊界點順拉伸軸),
    變形時各帶平滑滑動、耐大單向拉伸(Delaunay 散點內部佈局會自交)。
  - **真實位移場轉移**:以 **UV 座標**為基底把某 mesh 在所有動畫中「總位移最大幀」的逐頂點位移內插到
    **任一拓樸**的新 mesh(griddata linear+nearest 補洞)→ 新生成 mesh 直接吃真實最壞變形做自交檢查。
  - **sign 約定**:mesh.vertices 已 y-up,field 為 y-up local → 直接相加(deform_eval 已自一致性驗證)。

== 過渡期相依(C1 → E1)==
  本檔經 `_wire_mesh_tools()` import repo 的 `tools/mesh_gen`(generate_mesh_v2 / deform_eval / atlas_crop /
  evaluate_mesh)。**Phase E1** 會 bundle 進 `assets/`(self-contained,G5),屆時移除此 shim。

對外主要入口:
  generate_mesh(image_path, rows=10, cols=3, mode="auto")        → Spine mesh attachment dict
  crop_region(atlas_path, png_path, name, out_path=None)         → 從 atlas 切 region 存 PNG,回路徑
  real_deform_field(skeleton, slot, name)                        → (uvs Nx2, field Nx2, 來源 anim 名)
  deform_gate(mesh, uvs_src, field)                              → {self_intersections, triangle_flips,
                                                                    degenerate, area_ratio, clean}
  generate_and_gate(skeleton_path, atlas, png, slot, name, ...)  → 端到端 {mesh, iou, deform, pass}

用法(CLI):
  python3 mesh_gen.py --image region.png --out mesh.json              # 單張件圖 → mesh
  python3 mesh_gen.py --gate --slot image/curtain_left               # 對真實 curtain 生成+真實 deform 閘
  python3 mesh_gen.py --self-test                                     # 4 main_draw mesh 真實 deform si=0 自檢

程式化:
  from gen_lib.mesh_gen import generate_mesh, generate_and_gate
  rep = generate_and_gate("assets/main_draw.json", "assets/main_draw.atlas", "assets/main_draw.png",
                          "image/curtain_left", "image/curtain_left")   # rep["pass"] == True
"""
from __future__ import annotations
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

_MESH_MODS = None


# --------------------------------------------------------------------- 過渡期路徑 shim
def _wire_mesh_tools():
    """掛上 repo 的 `tools/mesh_gen` 並 import 生成/評估模組(C1 過渡期相依,E1 bundle 後改指向 assets/)。

    回傳 namespace,帶 .gen_v2 / .de(deform_eval) / .atlas_crop / .evaluate_mesh。找不到給清楚錯誤。
    """
    global _MESH_MODS
    if _MESH_MODS is not None:
        return _MESH_MODS
    # 複用 make_beat 的路徑 shim(已含 tools/mesh_gen);獨立時亦自行補路徑。
    try:
        from make_beat import _wire_repo_tools
        _wire_repo_tools()
    except Exception:
        pass
    repo = os.path.normpath(os.path.join(_HERE, "..", "..", "..", ".."))
    mesh_dir = os.path.join(repo, "tools", "mesh_gen")
    if mesh_dir not in sys.path:
        sys.path.insert(0, mesh_dir)
    try:
        import generate_mesh_v2 as gen_v2
        import deform_eval as de
        import atlas_crop
        import evaluate_mesh
    except ImportError as e:
        raise ImportError(
            "C1 mesh_gen 過渡期需 repo tools/mesh_gen(generate_mesh_v2/deform_eval/"
            "atlas_crop/evaluate_mesh);找不到:{}。E1 bundle 後此相依移除。".format(e))

    class _NS:
        pass
    ns = _NS()
    ns.gen_v2 = gen_v2
    ns.de = de
    ns.atlas_crop = atlas_crop
    ns.evaluate_mesh = evaluate_mesh
    _MESH_MODS = ns
    return ns


# --------------------------------------------------------------------- 公開入口
def generate_mesh(image_path, rows=10, cols=3, mode="auto"):
    """從一張件貼圖(RGBA PNG / mask)產出 Spine 3.8 mesh attachment dict。

    mode="auto"(預設):高瘦 row-convex 件 → strip(耐變形);軟邊 blob(羽化帶高,如光暈)→ 密邊界;
                       其餘 → Delaunay v1。mode 可強制 "strip" / "delaunay"。
    回傳 dict:{type:"mesh", vertices, uvs, triangles, hull, width, height, _mode}。
    """
    ns = _wire_mesh_tools()
    return ns.gen_v2.generate(image_path, rows=rows, cols=cols, mode=mode)


def crop_region(atlas_path, png_path, name, out_path=None):
    """從 atlas+png 切出單一 region(含旋轉/CW 還原)存成 PNG,回傳檔案路徑。"""
    import cv2
    ns = _wire_mesh_tools()
    sub = ns.atlas_crop.extract(atlas_path, png_path, name)
    if out_path is None:
        import tempfile
        out_path = os.path.join(tempfile.mkdtemp(prefix="c1crop_"), "region.png")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    cv2.imwrite(out_path, sub)
    return out_path


def real_deform_field(skeleton, slot, name):
    """回傳該 mesh 在所有動畫中『總位移最大幀』的逐頂點位移場(UV 座標、y-up local)。

    skeleton 可為 dict 或 json 路徑。回傳 (uvs Nx2, field Nx2, 來源 anim 名)。
    ⚠️ 正式 deform 閘用此**真實位移場轉移**,不要用未校準的 `stress_field`(見 run.md)。
    """
    ns = _wire_mesh_tools()
    sk = json.load(open(skeleton, encoding="utf-8")) if isinstance(skeleton, str) else skeleton
    return ns.de.real_deform_field(sk, slot, name)


def deform_gate(mesh, uvs_src, field):
    """把真實位移場(uvs_src 座標、y-up)內插到 mesh 頂點並套用,回傳自交/翻面/退化量化 + clean 旗標。

    clean == (self_intersections==0 and triangle_flips==0 and degenerate==0)。此為 C1 的 **si=0 閘**。
    """
    ns = _wire_mesh_tools()
    return ns.de.transfer_deform_check(mesh, uvs_src, field)


def mesh_schema_ok(mesh):
    """Spine mesh attachment schema 自檢(C1 可機讀最小合法性)。回傳 (ok, detail)。"""
    import math
    nv2 = len(mesh.get("uvs", []))
    detail = {}
    verts = mesh.get("vertices", [])
    tris = mesh.get("triangles", [])
    hull = mesh.get("hull", -1)
    nv = nv2 // 2
    detail["nv"] = nv
    ok = True
    # unweighted:vertices 長度 == uvs 長度 == 2*nv(見 CLAUDE.md 雷點 #6)
    if nv2 == 0 or len(verts) != nv2:
        ok = False
    detail["verts_eq_uvs"] = (len(verts) == nv2 and nv2 > 0)
    # triangles:3 的倍數、索引皆 < nv
    tri_ok = (len(tris) % 3 == 0) and len(tris) > 0 and all(0 <= int(i) < nv for i in tris)
    detail["triangles_ok"] = tri_ok
    ok = ok and tri_ok
    # hull:1..nv
    hull_ok = isinstance(hull, int) and 1 <= hull <= nv
    detail["hull_ok"] = hull_ok
    ok = ok and hull_ok
    # 全有限
    finite = all(math.isfinite(float(x)) for x in verts) and all(math.isfinite(float(u)) for u in mesh.get("uvs", []))
    detail["finite"] = finite
    ok = ok and finite
    detail["mode"] = mesh.get("_mode")
    return ok, detail


def setup_clean(mesh):
    """setup pose(未變形)下 mesh 是否自交/翻面/退化乾淨(生成拓樸本身合法性)。回傳 eval dict。"""
    ns = _wire_mesh_tools()
    import numpy as np
    de = ns.de
    v = mesh["vertices"]
    s = np.column_stack([v[0::2], v[1::2]])
    t = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    signs = [de.signed_area(s, x) > 0 for x in t]
    area = sum(abs(de.signed_area(s, x)) for x in t)
    return de.eval_pose(s, t, signs, area)


def artist_iou_baseline(skeleton, slot, name, mask):
    """藝術家既有 mesh 對該件 alpha 的覆蓋率(IoU baseline;生成 mesh 不應明顯低於它)。"""
    import numpy as np
    import cv2
    sk = json.load(open(skeleton, encoding="utf-8")) if isinstance(skeleton, str) else skeleton
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return float(np.logical_and(recon, mask).sum() / np.logical_or(recon, mask).sum())


def generate_and_gate(skeleton_path, atlas_path, png_path, slot, name,
                      out_dir=None, mode="auto", iou_margin=0.0):
    """端到端 C1 流程:atlas 切 region → 生成 mesh → ① IoU(vs 真實 alpha,對照藝術家 baseline)
    ② 該件**真實 deform 場**轉移後 self_intersections=0。回傳可機讀報告 dict,`pass` 為總判。
    """
    import tempfile
    import cv2
    ns = _wire_mesh_tools()
    sk = json.load(open(skeleton_path, encoding="utf-8")) if isinstance(skeleton_path, str) else skeleton_path
    if out_dir is None:
        out_dir = tempfile.mkdtemp(prefix="c1gate_")
    crop = crop_region(atlas_path, png_path, name, os.path.join(out_dir, "region.png"))
    mask = ns.evaluate_mesh.load_mask(crop)

    mesh = generate_mesh(crop, mode=mode)
    nv = len(mesh["uvs"]) // 2
    schema_ok, schema = mesh_schema_ok(mesh)

    iou = ns.evaluate_mesh.evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
    base = artist_iou_baseline(sk, slot, name, mask)
    uvs_src, field, frame = ns.de.real_deform_field(sk, slot, name)
    dres = deform_gate(mesh, uvs_src, field)

    iou_pass = iou >= base - iou_margin
    return {
        "mesh": {"vertices": nv, "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3,
                 "mode": mesh.get("_mode")},
        "schema_ok": schema_ok, "schema": schema,
        "AC_iou": {"value": round(iou, 4), "artist_baseline": round(base, 4), "pass": iou_pass},
        "AC_real_deform": {"frame": frame,
                           "area_ratio": float(dres["area_ratio"]),
                           "self_intersections": int(dres["self_intersections"]),
                           "triangle_flips": int(dres["triangle_flips"]),
                           "degenerate": int(dres["degenerate"]),
                           "pass": bool(dres["clean"])},
        "pass": bool(schema_ok and iou_pass and dres["clean"]),
    }


# --------------------------------------------------------------------- 自檢(不寫檔)
_MAIN_DRAW_MESHES = [
    ("image/curtain_left", "image/curtain_left"),
    ("image/curtain_right", "image/curtain_right"),
    ("image/shadow", "image/shadow"),
    ("image/shadow2", "image/shadow"),
]


def _self_test(assets_dir=None):
    """對真實 main_draw 4 mesh 跑 generate_and_gate,全部須 schema_ok + 真實 deform si=0。"""
    if assets_dir is None:
        assets_dir = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "..", "assets"))
    sk = os.path.join(assets_dir, "main_draw.json")
    at = os.path.join(assets_dir, "main_draw.atlas")
    pg = os.path.join(assets_dir, "main_draw.png")
    ok = True
    for slot, name in _MAIN_DRAW_MESHES:
        rep = generate_and_gate(sk, at, pg, slot, name)
        good = rep["pass"]
        ok = ok and good
        d = rep["AC_real_deform"]
        print("  {:22s} mode={:18s} nv={:3d} iou={:.4f}/{:.4f} si={} flips={} -> {}".format(
            name, str(rep["mesh"]["mode"]), rep["mesh"]["vertices"],
            rep["AC_iou"]["value"], rep["AC_iou"]["artist_baseline"],
            d["self_intersections"], d["triangle_flips"], "OK" if good else "FAIL"))
    return ok


def main():
    ap = argparse.ArgumentParser(description="gen_lib mesh 生成 + 變形自交閘入口(C1)")
    ap.add_argument("--image", help="單張件貼圖(RGBA PNG)→ 生成 mesh")
    ap.add_argument("--out", help="輸出 mesh.json 路徑")
    ap.add_argument("--mode", choices=["auto", "strip", "delaunay"], default="auto")
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--gate", action="store_true", help="對真實資產跑生成+真實 deform 閘")
    ap.add_argument("--skeleton", default=None)
    ap.add_argument("--atlas", default=None)
    ap.add_argument("--png", default=None)
    ap.add_argument("--slot", default="image/curtain_left")
    ap.add_argument("--name", default="image/curtain_left")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        ok = _self_test()
        print("SELF-TEST:", "PASS" if ok else "FAIL")
        sys.exit(0 if ok else 1)

    if a.gate:
        assets = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "..", "assets"))
        sk = a.skeleton or os.path.join(assets, "main_draw.json")
        at = a.atlas or os.path.join(assets, "main_draw.atlas")
        pg = a.png or os.path.join(assets, "main_draw.png")
        rep = generate_and_gate(sk, at, pg, a.slot, a.name, mode=a.mode)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        sys.exit(0 if rep["pass"] else 1)

    if not a.image:
        ap.error("需要 --image(或 --gate / --self-test)")
    mesh = generate_mesh(a.image, rows=a.rows, cols=a.cols, mode=a.mode)
    out = a.out or (a.image.rsplit(".", 1)[0] + "_mesh.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(mesh, f, ensure_ascii=False)
    print(json.dumps({"out": out, "mode": mesh.get("_mode"),
                      "vertices": len(mesh["uvs"]) // 2, "hull": mesh["hull"],
                      "triangles": len(mesh["triangles"]) // 3}, ensure_ascii=False))


if __name__ == "__main__":
    main()
