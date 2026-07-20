#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 generate_mesh_v2 → 對照 Award 真實生產 mesh。

背景(knowledge/s4-psd-to-spine-real.md):Award 機器人 3 件為 mesh(光暈/身體/左手),
且 PSD 切件 = spine 生產貼圖素材(alpha-IoU 0.92~0.99 已確認同素材)。
這些件在 Award **無 deform timeline**(靠骨骼權重變形),故真實 deform 閘 N/A;
本比對聚焦「靜態覆蓋率對照藝術家真值」+ 拓樸健全 + 頂點預算。

真值:Award mesh 的 `uvs` 為 region-local 0..1(Spine runtime 再映射到 atlas region),
故可直接 uv*(W,H) 疊回 PSD 切件 alpha 重建藝術家 mesh 覆蓋 → artist_iou。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from evaluate_mesh import evaluate
from generate_mesh_v2 import generate as gen_v2, load_mask


def award_attachment(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[slot][name]


def recon_iou(uvs_nx2, tris_nx3, mask, flip_v=False):
    H, W = mask.shape
    u = uvs_nx2.copy()
    if flip_v:
        u[:, 1] = 1.0 - u[:, 1]
    rp = np.column_stack([u[:, 0] * W, u[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris_nx3:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0


def compare(png, sk, slot, name):
    mask01, W, H = load_mask(png)          # 0/1 mask + dims
    mask = mask01.astype(bool)

    a = award_attachment(sk, slot, name)
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    # 方向自動偵測:v 不翻 vs 翻,取 IoU 高者(排除 y 軸慣例分歧)
    iou_noflip = recon_iou(uvs, tris, mask, flip_v=False)
    iou_flip = recon_iou(uvs, tris, mask, flip_v=True)
    flip_v = iou_flip > iou_noflip
    artist_iou = max(iou_noflip, iou_flip)
    artist_nv = len(uvs)
    artist_nt = len(tris)

    # 生成 mesh(v2 auto)+ 靜態評估
    mesh = gen_v2(png, mode="auto")
    ev = evaluate(mesh, mask01)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]
    gen_nv = len(mesh["uvs"]) // 2

    return {
        "piece": name,
        "dims": [W, H], "aspect": round(H / W, 3),
        "artist": {"vertices": artist_nv, "triangles": artist_nt,
                   "iou": round(artist_iou, 4),
                   "uv_flip_v_used": bool(flip_v)},
        "generated": {"mode": mesh.get("_mode"), "vertices": gen_nv,
                      "triangles": len(mesh["triangles"]) // 3,
                      "hull": mesh["hull"], "iou": round(gen_iou, 4)},
        "static_ac": {k: v["pass"] for k, v in ev["criteria"].items()},
        "iou_vs_artist_pass": bool(gen_iou >= artist_iou),
        "iou_gap": round(gen_iou - artist_iou, 4),
        "vertex_economy": round(gen_nv / artist_nv, 3),
    }


def ensure_pieces(base):
    """件 PNG 不存在時,自動從 robot_parts.psd 切出(跨 session 可重現)。"""
    if os.path.exists(os.path.join(base, "00_光暈.png")):
        return
    from psd_slice import slice_psd
    slice_psd("assets/robot_parts.psd", base)


def main():
    sk = json.load(open("assets/Award.json"))
    base = os.environ.get("PIECES_DIR", "/tmp/award_robot_pieces")
    ensure_pieces(base)
    jobs = [
        ("00_光暈.png", "機器人拆件/光暈", "機器人拆件/光暈"),
        ("03_身體.png", "機器人拆件/身體", "機器人拆件/身體"),
        ("04_左手.png", "機器人拆件/左手", "機器人拆件/左手"),
    ]
    reps = []
    for fn, slot, name in jobs:
        reps.append(compare(os.path.join(base, fn), sk, slot, name))
    out = {"reports": reps,
           "summary": {
               "all_static_ac_pass": all(all(r["static_ac"].values()) for r in reps),
               "all_iou_meets_artist": all(r["iou_vs_artist_pass"] for r in reps),
           }}
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
