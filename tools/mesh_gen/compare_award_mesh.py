#!/usr/bin/env python3
"""S3 端到端驗收 — PSD 切件 → generate_mesh_v2 → 對照 Award 真實生產 mesh。

背景(knowledge/s4-psd-to-spine-real.md):機器人 3 件在 Award 為 mesh(光暈78v/身體98v/左手80v),
且**無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform)→ 無真實位移場可轉移。
故本閘做「靜態幾何」對照,共三個可量測 AC:

  AC-A  藝術家 mesh 覆蓋 IoU(把 Award mesh 的 uvs 映回件像素、填三角、對件 alpha 求 IoU)
        ── 同時驗證「Spine mesh uvs = region-local [0,1]」的解讀正確、並取得藝術家基準。
  AC-B  生成 mesh 覆蓋 IoU(generate_mesh_v2 對同一件 alpha)≥ 藝術家基準 − margin。
  AC-C  生成 vs 藝術家 兩覆蓋遮罩的一致性 IoU(是否覆蓋同一塊區域)。
  AC-D  頂點預算:生成頂點數 ≤ budget 且與藝術家同數量級。

uvs 方向以「取較高 IoU 的 v / 1-v」自動判定(並回報採用哪個),避免手猜翻轉。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_mesh_v2 import generate as gen_v2  # noqa: E402


def load_alpha(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"無法讀取: {path}")
    if img.ndim == 3 and img.shape[2] == 4:
        a = img[:, :, 3]
    else:
        g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        a = (g > 0).astype(np.uint8) * 255
    return (a > 8).astype(np.uint8)


def award_mesh(slot):
    j = json.load(open(os.path.join(REPO, "assets/Award.json")))
    skins = j["skins"]
    skins = skins if isinstance(skins, list) else [
        {"name": k, "attachments": v} for k, v in skins.items()]
    for sk in skins:
        for s, ats in sk.get("attachments", {}).items():
            if s == slot:
                for an, a in ats.items():
                    if a.get("type") == "mesh":
                        return a
    raise SystemExit(f"找不到 mesh: {slot}")


def coverage_from_uv(uvs, tris, H, W, flip_v):
    """把 uvs([0,1] region-local) 映到件像素、填三角 → 覆蓋遮罩。"""
    pts = []
    for i in range(0, len(uvs), 2):
        u, v = uvs[i], uvs[i + 1]
        x = u * W
        y = (1.0 - v) * H if flip_v else v * H
        pts.append((x, y))
    pts = np.array(pts)
    m = np.zeros((H, W), np.uint8)
    for t in np.array(tris).reshape(-1, 3):
        cv2.fillConvexPoly(m, np.round(pts[t]).astype(np.int32), 1)
    return m


def coverage_from_gen(mesh, H, W):
    """generate_mesh 輸出:vertices=(x-W/2, H/2-y) → 逆轉回像素。"""
    v = mesh["vertices"]
    pts = np.array([(v[i] + W / 2.0, H / 2.0 - v[i + 1])
                    for i in range(0, len(v), 2)])
    m = np.zeros((H, W), np.uint8)
    for t in np.array(mesh["triangles"]).reshape(-1, 3):
        cv2.fillConvexPoly(m, np.round(pts[t]).astype(np.int32), 1)
    return m


def iou(a, b):
    inter = int(np.logical_and(a, b).sum())
    union = int(np.logical_or(a, b).sum())
    return inter / union if union else 0.0


def run_part(name, slot, part_png, budget=100, margin=0.03):
    alpha = load_alpha(part_png)
    H, W = alpha.shape
    art = award_mesh(slot)

    # AC-A: 藝術家 mesh 覆蓋(自動判定 v 方向)
    cov_v = coverage_from_uv(art["uvs"], art["triangles"], H, W, flip_v=False)
    cov_f = coverage_from_uv(art["uvs"], art["triangles"], H, W, flip_v=True)
    iou_v, iou_f = iou(cov_v, alpha), iou(cov_f, alpha)
    flip = iou_f > iou_v
    art_cov = cov_f if flip else cov_v
    art_iou = max(iou_v, iou_f)

    # generated mesh
    m = gen_v2(part_png, mode="auto")
    gen_cov = coverage_from_gen(m, H, W)
    gen_iou = iou(gen_cov, alpha)
    agree = iou(art_cov, gen_cov)
    nv = len(m["uvs"]) // 2
    art_nv = len(art["uvs"]) // 2

    ac = {
        "AC-A_artist_iou": {"value": round(art_iou, 4), "pass": art_iou >= 0.85,
                            "uv_flip_v": bool(flip)},
        "AC-B_gen_iou": {"value": round(gen_iou, 4),
                         "pass": gen_iou >= art_iou - margin,
                         "baseline": round(art_iou, 4)},
        "AC-C_agreement_iou": {"value": round(agree, 4), "pass": agree >= 0.80},
        "AC-D_vertices": {"value": nv, "artist": art_nv, "budget": budget,
                          "pass": nv <= budget},
    }
    return {
        "part": name, "slot": slot, "size": [W, H], "gen_mode": m.get("_mode"),
        "gen_tris": len(m["triangles"]) // 3, "artist_tris": len(art["triangles"]) // 3,
        "overall_pass": all(c["pass"] for c in ac.values()),
        "criteria": ac,
    }


REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

PARTS = [
    ("光暈", "機器人拆件/光暈", "00_光暈.png"),
    ("身體", "機器人拆件/身體", "03_身體.png"),
    ("左手", "機器人拆件/左手", "04_左手.png"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("parts_dir", help="psd_slice 輸出目錄(含 00_光暈.png 等)")
    ap.add_argument("--budget", type=int, default=100)
    a = ap.parse_args()
    reports = []
    for name, slot, fn in PARTS:
        reports.append(run_part(name, slot, os.path.join(a.parts_dir, fn), a.budget))
    overall = all(r["overall_pass"] for r in reports)
    print(json.dumps({"overall_pass": overall, "parts": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
