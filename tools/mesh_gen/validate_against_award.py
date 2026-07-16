#!/usr/bin/env python3
"""S3+S4 端到端驗收：真實生產貼圖區 → S3 mesh → 對照 Award 真實(藝術家)mesh。

情境(2026-07-16 發現):Award 機器人拆件的 3 個 mesh 件(光暈/身體/左手)在生產 spine 中
**全是 weighted mesh**(靠骨骼權重蒙皮變形),且**無 per-vertex deform timeline**。
這與 main_draw 的 4 個 unweighted mesh(逐頂點 deform)本質不同。

因此本驗收拆成:
  ① 靜態輪廓保真(對藝術家真值)★核心閘 — 生成 mesh 填滿 IoU ≥ 藝術家同件 IoU − margin。
     用 attachment 的 `uvs`(永遠 nv×2,weighted 也適用)映射到 atlas 裁切件像素框比對。
  ② mesh 有效性(AC2/3/4,evaluate_mesh)。
  ③ 拓樸耐變形【探測,非主閘】—— 這些件本身無 per-vertex deform,故轉移 main_draw
     curtain_left 的『真實位移場』作為最壞情況探測,檢查生成拓樸自交/翻面。

⚠️ 重要落差(記入 knowledge):S3 目前產 **unweighted** mesh;要真正貼近生產視覺變形需
   **權重**(S3 規劃中的 BBW,尚未實作)。本閘驗證的是「靜態輪廓 + 拓樸」,非蒙皮權重。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
import deform_eval as de
from evaluate_mesh import evaluate
from atlas_crop import extract


def artist_iou_and_nv(skeleton, slot, name, mask):
    """藝術家 mesh 的填滿 IoU(用 uvs;weighted 也適用)+ 頂點數。"""
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    iou = float(np.logical_and(recon, mask).sum() / np.logical_or(recon, mask).sum())
    weighted = len(a["vertices"]) != len(a["uvs"])
    return iou, len(uvs), (len(tris)), a["hull"], weighted


def load_curtain_field(md_path):
    sk = json.load(open(md_path))
    return de.real_deform_field(sk, "image/curtain_left", "image/curtain_left")


def validate(award_path, atlas_path, png_path, slot, name, gen_fn, tmp_dir,
             md_path="assets/main_draw.json", iou_margin=0.02, budget=64):
    sk = json.load(open(award_path))
    sub = extract(atlas_path, png_path, name)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = (cv2.imread(crop, cv2.IMREAD_UNCHANGED)[:, :, 3] > 8).astype(np.uint8) \
        if sub.ndim == 3 and sub.shape[2] == 4 else (sub > 8).astype(np.uint8)

    mesh = gen_fn(crop)
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    nv = len(mesh["uvs"]) // 2

    base_iou, art_nv, art_tris, art_hull, weighted = artist_iou_and_nv(sk, slot, name, mask)
    ev = evaluate(mesh, mask, vertex_budget=budget, iou_thresh=base_iou - iou_margin)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]

    # ③ 拓樸耐變形探測:轉移 main_draw curtain 真實位移場(最壞情況;件本身無 deform)
    uvs_src, field, frame = load_curtain_field(md_path)
    probe = de.transfer_deform_check(mesh, uvs_src, field)

    ac_contour = gen_iou >= base_iou - iou_margin
    ac_valid = (ev["criteria"]["AC2a_centroid_in_mask"]["pass"]
                and ev["criteria"]["AC2b_degenerate"]["pass"]
                and ev["criteria"]["AC2c_orphans"]["pass"])
    ac_budget = ev["criteria"]["AC3_vertex_budget"]["pass"]
    ac_format = ev["criteria"]["AC4_format"]["pass"]

    return {
        "part": name,
        "crop_size": [int(mask.shape[1]), int(mask.shape[0])],
        "artist": {"vertices": art_nv, "triangles": art_tris, "hull": art_hull,
                   "weighted": weighted, "fill_iou": round(base_iou, 4)},
        "generated": {"vertices": nv, "triangles": len(mesh["triangles"]) // 3,
                      "hull": mesh["hull"], "mode": mesh.get("_mode"),
                      "fill_iou": round(gen_iou, 4)},
        "AC_A_contour": {"pass": bool(ac_contour), "gen": round(gen_iou, 4),
                         "artist_baseline": round(base_iou, 4), "margin": iou_margin},
        "AC_B_validity": {"pass": bool(ac_valid),
                          "centroid_in_mask": ev["criteria"]["AC2a_centroid_in_mask"]["value"],
                          "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                          "orphans": ev["criteria"]["AC2c_orphans"]["value"]},
        "AC_C_budget": {"pass": bool(ac_budget), "gen_nv": nv, "budget": budget,
                        "artist_nv": art_nv},
        "AC_D_format": {"pass": bool(ac_format)},
        "AC_E_deform_probe": {"note": "worst-case curtain field transfer; part has NO native deform",
                              "self_intersections": probe["self_intersections"],
                              "triangle_flips": probe["triangle_flips"],
                              "clean": probe["clean"]},
        "overall_pass": bool(ac_contour and ac_valid and ac_budget and ac_format),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--md", default="assets/main_draw.json")
    ap.add_argument("--slot", required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--gen", choices=["v1", "v2"], default="v2")
    ap.add_argument("--budget", type=int, default=64)
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    name = a.name or a.slot
    if a.gen == "v1":
        from generate_mesh import generate as g
        gen = lambda p: g(p)
    else:
        from generate_mesh_v2 import generate as g
        gen = lambda p: g(p, mode="auto")
    rep = validate(a.award, a.atlas, a.png, a.slot, name, gen, a.tmp,
                   md_path=a.md, budget=a.budget)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
