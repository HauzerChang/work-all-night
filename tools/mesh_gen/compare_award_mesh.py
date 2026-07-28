#!/usr/bin/env python3
"""S3 端到端驗收:機器人件 → generate_mesh_v2 → 對照 Award 真實生產 mesh。

情境(見 knowledge/s4-psd-to-spine-real.md):Award(big win spine)裡機器人拆件的
3 個件是 **mesh**(光暈/身體/左手),另 2 件是 region(右手/頭)。本工具拿這 3 個真實
生產 mesh 當 **ground truth**,對照 S3 自動生成 mesh 的靜態覆蓋率(IoU)與拓樸精簡度。

與 validate_against_real.py 的差異:
  - main_draw 的 4 mesh 有 deform timeline(逐頂點變形)→ 可做「真實位移場轉移」變形閘。
  - **Award 機器人這 5 件在 spine 無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform)
    → 沒有真實位移場可轉移,故本工具**不做變形閘**(誠實:不用未校準的合成壓力冒充)。
    只做「靜態覆蓋率對照生產 mesh」+ 格式/退化/孤兒自檢。

遮罩來源:atlas 切件(de-rotate 後,atlas ~0.70 縮放尺度)。Award mesh 的 uvs 是
region-local [0,1](與 main_draw 同慣例),故 uvs×(W,H) 直接落在該切件上 → 可與生成 mesh
在同一像素框比對。生成器吃同一張切件 → 兩者同尺度、公平對照。
"""
import argparse, json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from atlas_crop import extract
from evaluate_mesh import evaluate
from generate_mesh_v2 import generate as gen_v2


PIECES = [
    ("機器人拆件/光暈", "assets/Award2.png"),
    ("機器人拆件/身體", "assets/Award2.png"),
    ("機器人拆件/左手", "assets/Award.png"),
]


def get_artist_attachment(sk, slot, name):
    skins = sk["skins"]
    skin = skins[0] if isinstance(skins, list) else skins
    att = skin.get("attachments", skin)
    return att[slot][name]


def reconstruct_iou(uvs, tris, mask):
    """把 mesh(uvs region-local + triangles)填滿,與 alpha 遮罩算 IoU(覆蓋率)。"""
    H, W = mask.shape
    uv = np.array(uvs).reshape(-1, 2)
    tri = np.array(tris).reshape(-1, 3)
    rp = np.column_stack([uv[:, 0] * W, uv[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tri:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    inter = int(np.logical_and(recon, m).sum())
    union = int(np.logical_or(recon, m).sum())
    return inter / union if union else 0.0


def compare_one(sk, atlas, slot, page_png, tmp_dir, iou_margin):
    sub = extract(atlas, page_png, slot)           # de-rotate 後的切件(atlas 尺度)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = (sub[:, :, 3] > 8).astype(np.uint8) if sub.ndim == 3 and sub.shape[2] == 4 \
        else (cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY) > 8).astype(np.uint8)

    # 生產 mesh(ground truth)
    a = get_artist_attachment(sk, slot, slot)
    art_iou = reconstruct_iou(a["uvs"], a["triangles"], mask)
    art_nv = len(a["uvs"]) // 2
    art_tri = len(a["triangles"]) // 3
    art_hull = a.get("hull", art_nv)

    # 生成 mesh
    mesh = gen_v2(crop, mode="auto")
    ev = evaluate(mesh, mask)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]
    gen_nv = len(mesh["uvs"]) // 2

    return {
        "slot": slot,
        "mask_wh": [int(mask.shape[1]), int(mask.shape[0])],
        "artist": {"vertices": art_nv, "triangles": art_tri, "hull": art_hull,
                   "iou": round(art_iou, 4)},
        "generated": {"vertices": gen_nv, "triangles": len(mesh["triangles"]) // 3,
                      "hull": mesh["hull"], "mode": mesh.get("_mode"),
                      "iou": round(gen_iou, 4)},
        "format_clean": ev["criteria"]["AC4_format"]["pass"]
                        and ev["criteria"]["AC2b_degenerate"]["pass"]
                        and ev["criteria"]["AC2c_orphans"]["pass"],
        "AC_iou_parity": {"pass": gen_iou >= art_iou - iou_margin,
                          "gap": round(gen_iou - art_iou, 4)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--iou-margin", type=float, default=0.02)
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reports = []
    for slot, page in PIECES:
        reports.append(compare_one(sk, a.atlas, slot, page, a.tmp, a.iou_margin))
    overall = all(r["AC_iou_parity"]["pass"] and r["format_clean"] for r in reports)
    out = {"overall_pass": overall, "pieces": reports}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
