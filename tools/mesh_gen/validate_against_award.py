#!/usr/bin/env python3
"""端到端 AC:PSD件 → S3 generate_mesh → 對照 Award 真實生產 mesh(有 ground truth)。

流程:robot_parts.psd → psd_slice 切件 → generate_mesh_v2 → 覆蓋 IoU vs 件 alpha,
對照 Award 藝術家真實 mesh 對同一件 alpha 的覆蓋 IoU(baseline)。

⚠️ 這 3 件(光暈/身體/左手)在 Award **無 deform timeline**(靠骨骼權重變形,非逐頂點 deform),
故本 AC 只驗**靜態覆蓋**與**頂點預算/拓樸健全**;deform 耐受度已在 main_draw 4 mesh 驗過(見 s3-four-mesh)。
Award mesh uvs 經實測為 **region-local 0..1**(藝術家 mesh 對件 alpha IoU 0.95~0.98 佐證)。
"""
import argparse, json, os, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2

ROBOT = {"光暈": "00_光暈.png", "身體": "03_身體.png", "左手": "04_左手.png"}

def load_alpha(p):
    img = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    a = img[:, :, 3] if (img.ndim == 3 and img.shape[2] == 4) else (cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) > 0).astype(np.uint8) * 255
    return (a > 8).astype(np.uint8)

def cover(uvs, tris, W, H):
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    r = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(r, np.round(rp[t]).astype(np.int32), 1)
    return r

def iou(a, b):
    return float(np.logical_and(a, b).sum() / max(np.logical_or(a, b).sum(), 1))

def degen_tris(pts, tris):
    p = np.array(pts); n = 0
    for t in tris:
        a, b, c = p[t[0]], p[t[1]], p[t[2]]
        if abs((b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])) < 1e-6:
            n += 1
    return n

def validate(award_json, parts_dir, margin=0.02):
    sk = json.load(open(award_json))
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    out = {}
    ok = True
    for part, fn in ROBOT.items():
        slot = f"機器人拆件/{part}"; a = att[slot][slot]
        art_uvs = np.array(a["uvs"]).reshape(-1, 2); art_tris = np.array(a["triangles"]).reshape(-1, 3)
        mask = load_alpha(os.path.join(parts_dir, fn)); H, W = mask.shape
        art_iou = iou(cover(art_uvs, art_tris, W, H), mask)
        m = gen_v2(os.path.join(parts_dir, fn), mode="auto")
        guvs = np.array(m["uvs"]).reshape(-1, 2); gtris = np.array(m["triangles"]).reshape(-1, 3)
        gen_iou = iou(cover(guvs, gtris, W, H), mask)
        gpts = np.column_stack([guvs[:, 0] * W, guvs[:, 1] * H])
        p = gen_iou >= art_iou - margin and degen_tris(gpts, gtris) == 0
        ok = ok and p
        out[part] = {"piece": [W, H], "mode": m["_mode"],
                     "artist": {"nv": len(art_uvs), "iou": round(art_iou, 4)},
                     "gen": {"nv": len(guvs), "iou": round(gen_iou, 4), "degen": degen_tris(gpts, gtris)},
                     "delta_iou": round(gen_iou - art_iou, 4), "pass": p}
    return {"overall_pass": ok, "margin": margin, "parts": out}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--parts", default="/tmp/robot_parts", help="psd_slice 切件目錄")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    rep = validate(a.award, a.parts, a.margin)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)

if __name__ == "__main__":
    main()
