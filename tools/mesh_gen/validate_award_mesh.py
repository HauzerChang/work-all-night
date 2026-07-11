#!/usr/bin/env python3
"""端到端驗證：真實生產件 → S3 mesh → 對照 Award 真實藝術家 mesh。

背景(2026-07-11):`robot_parts.psd` 5 件對應真實 spine `Award` 的 slot
`機器人拆件/{光暈,右手,頭,身體,左手}`;其中 **光暈/身體/左手為 mesh**(右手/頭為 region)。
這 3 個是**weighted、由骨骼驅動、無 deform timeline** 的 mesh —— 與 main_draw 的
unweighted+deform 窗簾/陰影是不同拓樸類別,是驗證 S3 生成器泛化的真實生產標的。

驗證流程(有真值、純 CPU 可自驅):
  atlas 切件(Award.png/Award2.png,含 rotate 還原)→ alpha mask
  → S3 `generate_mesh_v2`(auto:緊湊件走 Delaunay)
  → ① 覆蓋率 IoU 對照藝術家 mesh 自身覆蓋率(baseline)
     ② setup pose 拓樸乾淨(0 自交 / 0 翻面 / 0 退化)

⚠️ deform 閘不適用:這 3 件無 deform timeline(靠骨骼權重變形),不能用
   main_draw 的真實位移場轉移。骨骼驅動變形驗證需重建骨層級 + 動畫 transform,
   屬後續獨立工作塊;本閘只驗「靜態覆蓋率 + setup 拓樸」對照真值。

用法:
  python tools/mesh_gen/validate_award_mesh.py            # 全 3 mesh 件
  python tools/mesh_gen/validate_award_mesh.py --slot 機器人拆件/光暈
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
import deform_eval as de
from evaluate_mesh import evaluate, load_mask
from atlas_crop import extract
from generate_mesh_v2 import generate as gen_v2

# Award 中 3 個 mesh 件(slot 名 == attachment 名)
MESH_SLOTS = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def artist_iou(skeleton, name, mask):
    """藝術家 mesh 自身對 alpha 的覆蓋率(baseline);UV 對 weighted/unweighted 皆適用。"""
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[name][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    uni = np.logical_or(recon, mask).sum()
    return float(inter / uni), len(uvs)


def validate_one(sk, atlas, png, name, tmp_dir, iou_margin=0.0):
    sub = extract(atlas, png, name)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    mesh = gen_v2(crop, mode="auto")
    nv = len(mesh["uvs"]) // 2
    iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
    base, art_nv = artist_iou(sk, name, mask)

    # setup pose 拓樸
    v = np.array(mesh["vertices"]).reshape(-1, 2)
    t = np.array(mesh["triangles"]).reshape(-1, 3)
    signs = [de.signed_area(v, x) > 0 for x in t]
    area = sum(abs(de.signed_area(v, x)) for x in t)
    topo = de.eval_pose(v, t, signs, area)

    iou_pass = iou >= base - iou_margin
    budget_pass = nv <= art_nv * 1.25  # 頂點數不顯著超過藝術家
    return {
        "slot": name,
        "gen": {"mode": mesh.get("_mode"), "vertices": nv, "hull": mesh["hull"],
                "triangles": len(mesh["triangles"]) // 3},
        "artist": {"vertices": art_nv},
        "AC_iou": {"value": round(iou, 4), "artist_baseline": round(base, 4), "pass": iou_pass},
        "AC_vertex_budget": {"gen": nv, "artist": art_nv, "pass": budget_pass},
        "AC_setup_topology": {"self_intersections": topo["self_intersections"],
                              "triangle_flips": topo["triangle_flips"],
                              "degenerate": topo["degenerate"], "pass": topo["clean"]},
        "overall_pass": iou_pass and budget_pass and topo["clean"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--slot", default=None, help="只驗單一 slot;預設全 3 mesh 件")
    ap.add_argument("--tmp", default="scratch")
    a = ap.parse_args()
    os.makedirs(a.tmp, exist_ok=True)
    sk = json.load(open(a.skeleton))
    slots = [a.slot] if a.slot else MESH_SLOTS
    reports = [validate_one(sk, a.atlas, a.png, s, a.tmp) for s in slots]
    overall = all(r["overall_pass"] for r in reports)
    out = {"overall_pass": overall, "pieces": reports}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
