#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 mesh v2 → 對照 Award 真實生產 mesh(有真值)。

背景(knowledge/s4-psd-to-spine-real.md):robot_parts.psd 的 3 個件(光暈/身體/左手)
在生產 spine `Award` 中被美術做成 **weighted mesh**,且**無 deform timeline**
(靠骨骼/權重變形,非逐頂點 deform)。故本閘用「靜態覆蓋率 vs 藝術家 mesh」當真值,
不套真實位移場 deform 閘(該資產沒有可轉移的 deform 場)。

流程(每件):
  PSD 切件 alpha(psd_slice)→ generate_mesh_v2(auto)→
  ① 生成 mesh 對 alpha 的覆蓋率 IoU
  ② Award 藝術家 mesh 對同一 alpha 的覆蓋率 IoU(真值基準,uvs 已是 region-local[0,1])
  ③ AC:生成 IoU ≥ 藝術家基準 − margin;格式合法;頂點在預算內。

真值對齊:PSD 件與 Award attachment 為同一素材(alpha-IoU 0.92~0.99 已證);
uvs 皆 normalize 到各自 region [0,1],rasterize 到同一張 alpha mask 上比對即一致。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask


def award_meshes(award_json):
    sk = json.load(open(award_json))
    skins = sk["skins"]; skin = skins[0] if isinstance(skins, list) else skins
    att = skin.get("attachments", skin)
    out = {}
    for slot, d in att.items():
        for name, a in d.items():
            if a.get("type") == "mesh":
                out[name] = a
    return out


def artist_iou_on_mask(att, mask):
    """把藝術家 mesh 的 uvs(region-local [0,1])rasterize 到 mask 尺寸,算覆蓋率 IoU。"""
    uvs = np.array(att["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(att["triangles"], dtype=np.int32).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    return (inter / union) if union else 0.0


# PSD 圖層名 → Award mesh attachment 名(ground truth 對應,見 s4-psd-to-spine-real.md)
MESH_PARTS = {
    "光暈": "機器人拆件/光暈",
    "身體": "機器人拆件/身體",
    "左手": "機器人拆件/左手",
}


def validate_part(part_png, award_att, budget=64, iou_margin=0.03):
    mask = load_mask(part_png)
    mesh = gen_v2(part_png, mode="auto")
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    rep = evaluate(mesh, mask, vertex_budget=budget)
    gen_iou = rep["criteria"]["AC1_iou"]["value"]
    base = artist_iou_on_mask(award_att, mask)
    fmt_ok = (rep["criteria"]["AC4_format"]["pass"]
              and rep["criteria"]["AC2b_degenerate"]["pass"]
              and rep["criteria"]["AC2c_orphans"]["pass"])
    budget_ok = rep["criteria"]["AC3_vertex_budget"]["pass"]
    iou_ok = gen_iou >= base - iou_margin
    return {
        "gen_mode": mesh.get("_mode"),
        "gen_vertices": rep["vertices"], "gen_hull": mesh["hull"],
        "gen_triangles": rep["triangles"],
        "artist_vertices": len(award_att["uvs"]) // 2,
        "artist_hull": award_att["hull"],
        "artist_triangles": len(award_att["triangles"]) // 3,
        "gen_iou": round(gen_iou, 4),
        "artist_baseline_iou": round(base, 4),
        "iou_margin": iou_margin,
        "AC_iou_pass": bool(iou_ok),
        "AC_format_pass": bool(fmt_ok),
        "AC_budget_pass": bool(budget_ok),
        "overall_pass": bool(iou_ok and fmt_ok and budget_ok),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--parts_dir", default="/tmp/robot_parts")
    ap.add_argument("--budget", type=int, default=64)
    ap.add_argument("--margin", type=float, default=0.03)
    a = ap.parse_args()

    # 確保切件存在
    if not os.path.isdir(a.parts_dir) or not os.path.exists(os.path.join(a.parts_dir, "manifest.json")):
        from psd_slice import slice_psd
        slice_psd(a.psd, a.parts_dir)
    man = json.load(open(os.path.join(a.parts_dir, "manifest.json")))
    fmap = {e["name"]: e["file"] for e in man["parts"]}

    aw = award_meshes(a.award)
    results = {}
    for layer, att_name in MESH_PARTS.items():
        png = os.path.join(a.parts_dir, fmap[layer])
        results[layer] = validate_part(png, aw[att_name], a.budget, a.margin)

    overall = all(r["overall_pass"] for r in results.values())
    print(json.dumps({"overall_pass": overall, "parts": results},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
