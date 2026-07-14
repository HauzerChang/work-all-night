#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 生成 mesh → 對照 Award 真實生產 mesh(有真值)。

串起 S4(PSD 切件)+ S3(mesh 生成),對「機器人拆件」的 3 個 mesh 件
(光暈 / 身體 / 左手,Award 中為 mesh)做覆蓋率 IoU 與精簡度對照。

為什麼可比(apples-to-apples):Spine mesh 的 uvs 是件內正規化紋理座標 [0,1]。
生成 mesh 與 Award 藝術家 mesh 的 uvs 都落在「同一件的正規化座標系」,故兩者的
覆蓋率 IoU 可在**同一張 PSD 件 alpha 遮罩**上計算(免受 atlas 0.70 縮放 / 旋轉 /
anti-alias 干擾;也不需 Award.png/atlas,只需 Award.json 的 uvs)。

限制(誠實記錄):Award 這 3 件**無 deform timeline**(靠骨骼/權重變形,非逐頂點
deform),故本閘只驗**靜態覆蓋率 + 精簡度**,不驗真實 deform 穩健性(無真值可轉移)。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from evaluate_mesh import evaluate as eval_mesh, load_mask
import generate_mesh_v2 as g2

# PSD 圖層名 → Award slot(= attachment name),機器人 3 個 mesh 件
MESH_MAP = {
    "光暈": "機器人拆件/光暈",
    "身體": "機器人拆件/身體",
    "左手": "機器人拆件/左手",
}


def award_mesh(skeleton, name):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[name][name]


def coverage_iou_from_uvs(uvs, tris, mask):
    """把 mesh 的 uvs(正規化)在 mask 尺寸上填三角,回傳 vs mask 的覆蓋率 IoU。"""
    H, W = mask.shape
    uv = np.array(uvs).reshape(-1, 2)
    pts = np.column_stack([uv[:, 0] * W, uv[:, 1] * H])
    tri = np.array(tris).reshape(-1, 3)
    recon = np.zeros((H, W), np.uint8)
    for t in tri:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    inter = int(np.logical_and(recon, m).sum())
    union = int(np.logical_or(recon, m).sum())
    return (inter / union) if union else 0.0


def run(psd_path, award_json, tmp_dir, iou_margin=0.02, budget=110):
    os.makedirs(tmp_dir, exist_ok=True)
    sk = json.load(open(award_json))
    _, manifest, parts = slice_psd(psd_path)
    by_name = {e["name"]: im for e, im in parts}

    report = {"source_psd": os.path.basename(psd_path), "pieces": []}
    for layer, slot in MESH_MAP.items():
        if layer not in by_name:
            report["pieces"].append({"layer": layer, "error": "PSD 無此圖層"})
            continue
        im = by_name[layer]
        piece_png = os.path.join(tmp_dir, f"piece_{layer}.png")
        im.save(piece_png)
        mask = load_mask(piece_png)

        # S3 生成
        mesh = g2.generate(piece_png, mode="auto")
        gen_eval = eval_mesh(mesh, mask, vertex_budget=budget)
        gen_iou = gen_eval["criteria"]["AC1_iou"]["value"]
        gen_nv = gen_eval["vertices"]

        # Award 真實 mesh(藝術家真值),同一張 PSD 件遮罩上算覆蓋率
        am = award_mesh(sk, slot)
        art_nv = len(am["uvs"]) // 2
        art_iou = round(coverage_iou_from_uvs(am["uvs"], am["triangles"], mask), 4)

        entry = {
            "layer": layer, "slot": slot,
            "gen": {"mode": mesh.get("_mode"), "vertices": gen_nv,
                    "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3,
                    "iou": gen_iou, "format_ok": gen_eval["criteria"]["AC4_format"]["pass"],
                    "no_orphan": gen_eval["criteria"]["AC2c_orphans"]["pass"],
                    "no_degen": gen_eval["criteria"]["AC2b_degenerate"]["pass"]},
            "award": {"vertices": art_nv, "hull": am["hull"],
                      "triangles": len(am["triangles"]) // 3, "iou": art_iou},
            "iou_pass": gen_iou >= art_iou - iou_margin,
            "budget_pass": gen_nv <= budget,
            "clean_pass": (gen_eval["criteria"]["AC4_format"]["pass"]
                           and gen_eval["criteria"]["AC2c_orphans"]["pass"]
                           and gen_eval["criteria"]["AC2b_degenerate"]["pass"]),
        }
        entry["pass"] = entry["iou_pass"] and entry["budget_pass"] and entry["clean_pass"]
        report["pieces"].append(entry)

    report["iou_margin"] = iou_margin
    report["vertex_budget"] = budget
    report["overall_pass"] = all(p.get("pass") for p in report["pieces"])
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--tmp", default="/tmp/award_cmp")
    ap.add_argument("--margin", type=float, default=0.02)
    ap.add_argument("--budget", type=int, default=110)
    a = ap.parse_args()
    rep = run(a.psd, a.award, a.tmp, a.margin, a.budget)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
