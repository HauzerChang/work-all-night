#!/usr/bin/env python3
"""端到端驗收:PSD 切件 → S3 generate_mesh_v2 → 對照 Award 真實生產 mesh。

背景(knowledge/s4-psd-to-spine-real.md):機器人拆件 3 件(光暈/身體/左手)在生產 spine
`Award` 中是 mesh。本工具把 psd_slice 切出的**真實 alpha** 餵進 S3 生成器,與 Award 藝術家
mesh 做「靜態覆蓋 IoU + 頂點預算 + 拓樸」對照。

⚠️ 範圍界定:這 3 件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform),
故本輪只驗**靜態覆蓋 + 拓樸精簡度**,不套 deform 閘(deform 閘適用於 main_draw 窗簾/陰影)。

真值來源:Award mesh 是 weighted(vertices≠uvs);覆蓋率只需 uvs(region 局部 texcoord)+
triangles。把 uvs→件像素(px=u*W, py=v*H),填三角求 IoU,即藝術家 mesh 的自我覆蓋基準。
評估器可信度:先確認藝術家 mesh 對自己的 alpha 覆蓋率高(自一致),再拿它當生成 mesh 的參照。
"""
import argparse, json, sys, os
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
import generate_mesh_v2 as g2
import evaluate_mesh as em


def load_award_meshes(award_json, prefix="機器人拆件"):
    d = json.load(open(award_json))
    out = {}
    for sk in d["skins"]:
        for slot, atts in sk["attachments"].items():
            if not slot.startswith(prefix):
                continue
            for aname, a in atts.items():
                if a.get("type") == "mesh":
                    out[slot] = a
    return out


def part_alpha(png_path):
    img = cv2.imread(png_path, cv2.IMREAD_UNCHANGED)
    if img.ndim == 3 and img.shape[2] == 4:
        a = img[:, :, 3]
    else:
        g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        a = (g > 0).astype(np.uint8) * 255
    return (a > 8).astype(np.uint8)


def coverage_iou_from_uvs(uvs, triangles, mask, flip_v=False):
    """把 region-local uvs(0..1)映到件像素,填三角,對 mask 求 IoU。"""
    H, W = mask.shape
    pts = []
    for i in range(0, len(uvs), 2):
        u = uvs[i]; v = uvs[i + 1]
        if flip_v:
            v = 1.0 - v
        pts.append((u * W, v * H))
    pts = np.array(pts, dtype=np.float64)
    tris = np.array(triangles, dtype=np.int32).reshape(-1, 3)
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    return (inter / union if union else 0.0), recon


def artist_baseline(att, mask):
    """藝術家 mesh 自我覆蓋 IoU(取 flip_v 兩者較佳者,並回報方向)。"""
    best = None
    for flip in (False, True):
        iou, _ = coverage_iou_from_uvs(att["uvs"], att["triangles"], mask, flip)
        if best is None or iou > best[0]:
            best = (iou, flip)
    return {"iou": round(best[0], 4), "flip_v": best[1],
            "vertices": len(att["uvs"]) // 2, "triangles": len(att["triangles"]) // 3,
            "hull": att["hull"], "weighted": len(att["vertices"]) != len(att["uvs"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--parts-dir", default="/tmp/robot_parts")
    ap.add_argument("--budget", type=int, default=100)
    ap.add_argument("--iou-margin", type=float, default=0.02,
                    help="生成 IoU 至少要 ≥ 藝術家基準 - margin 才算覆蓋達標")
    a = ap.parse_args()

    # PSD 圖層名 → Award slot / 切件檔
    mapping = {
        "光暈": ("機器人拆件/光暈", "00_光暈.png"),
        "身體": ("機器人拆件/身體", "03_身體.png"),
        "左手": ("機器人拆件/左手", "04_左手.png"),
    }
    aw = load_award_meshes(a.award)

    report = {"parts": {}, "summary": {}}
    all_pass = True
    for layer, (slot, fn) in mapping.items():
        png = os.path.join(a.parts_dir, fn)
        mask = part_alpha(png)
        att = aw[slot]

        base = artist_baseline(att, mask)

        gen = g2.generate(png, mode="auto")
        gen_eval = em.evaluate(gen, mask, vertex_budget=a.budget,
                               iou_thresh=0.0)  # 用相對基準判 IoU,這裡先拿值
        gen_iou = gen_eval["criteria"]["AC1_iou"]["value"]

        iou_ok = gen_iou >= base["iou"] - a.iou_margin
        budget_ok = gen_eval["criteria"]["AC3_vertex_budget"]["pass"]
        fmt_ok = gen_eval["criteria"]["AC4_format"]["pass"]
        degen_ok = gen_eval["criteria"]["AC2b_degenerate"]["pass"]
        orphan_ok = gen_eval["criteria"]["AC2c_orphans"]["pass"]
        part_pass = iou_ok and budget_ok and fmt_ok and degen_ok and orphan_ok
        all_pass = all_pass and part_pass

        report["parts"][layer] = {
            "slot": slot, "mask_size": [int(mask.shape[1]), int(mask.shape[0])],
            "artist": base,
            "generated": {
                "mode": gen.get("_mode"), "vertices": gen_eval["vertices"],
                "triangles": gen_eval["triangles"], "hull": gen["hull"],
                "iou": gen_iou,
                "degenerate": gen_eval["criteria"]["AC2b_degenerate"]["value"],
                "orphans": gen_eval["criteria"]["AC2c_orphans"]["value"],
                "centroid_in_mask": gen_eval["criteria"]["AC2a_centroid_in_mask"]["value"],
            },
            "checks": {
                "iou_ge_artist": iou_ok, "vertex_budget": budget_ok,
                "format": fmt_ok, "no_degenerate": degen_ok, "no_orphan": orphan_ok,
            },
            "pass": part_pass,
        }

    report["summary"]["overall_pass"] = all_pass
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
