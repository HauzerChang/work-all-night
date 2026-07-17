#!/usr/bin/env python3
"""端到端「PSD 件 → S3 mesh → 對照 Award 真實 mesh」— 對真實生產標的的整合 AC。

背景(STATE.md 最高優先候選 #1):`robot_parts.psd` 的 3 件在生產 spine `Award` 裡是 mesh
(光暈 / 身體 / 左手)。本工具用「PSD 切件的乾淨 alpha」跑 S3 `generate_mesh_v2`,再與
Award 藝術家真實 mesh 做覆蓋率(IoU)與拓樸對照 —— 端到端驗收 S3 對真實標的是否堪用。

⚠️ 這 3 件在 Award **無 deform timeline**(靠骨骼權重變形,非逐頂點 deform),
故本閘只做**靜態幾何/拓樸**對照,不做 deform 轉移(那需 deform 場,此處不存在)。
這是誠實的能力邊界:S3 對「有 deform 的件」(main_draw 窗簾)已由 validate_against_real 驗過變形穩健。

真值鏈:PSD 切件 alpha == Award 生產貼圖素材(knowledge/s4-psd-to-spine-real,alpha-IoU 0.92~0.99)。
Award mesh uvs 為**未旋轉 logical 區域內** normalize(rotate flag 只影響 atlas 打包,不影響 JSON uv);
以藝術家 mesh 自身覆蓋率(self-IoU)做座標慣例的 sanity check + 當作 pass 基準。
"""
import argparse, json, os, sys
import numpy as np
import cv2
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from evaluate_mesh import evaluate as eval_mesh
from generate_mesh_v2 import generate as gen_v2

# PSD 圖層名 → Award slot/attachment(ground truth,見 s4-psd-to-spine-real.md)
PART_MAP = {
    "光暈": "機器人拆件/光暈",
    "身體": "機器人拆件/身體",
    "左手": "機器人拆件/左手",
}


def load_award_mesh(award_json, slot):
    sk = json.load(open(award_json))
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[slot][slot]


def coverage_iou(uvs_flat, tris_flat, mask):
    """用 region-local normalized uvs 把三角形填進 mask 尺寸,算對 mask 的覆蓋 IoU。"""
    H, W = mask.shape
    uvs = np.array(uvs_flat, dtype=np.float64).reshape(-1, 2)
    tris = np.array(tris_flat, dtype=np.int32).reshape(-1, 3)
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    return (inter / union) if union else 0.0


def validate_part(layer_name, parts, award_json, tmp_dir, iou_margin=0.02):
    slot = PART_MAP[layer_name]
    # 1. 取 PSD 切件(乾淨 alpha)
    entry_im = next(((e, im) for e, im in parts if e["name"] == layer_name), None)
    if entry_im is None:
        raise SystemExit(f"PSD 找不到圖層: {layer_name}")
    entry, im = entry_im
    crop = os.path.join(tmp_dir, f"_award_{slot.replace('/', '_')}.png")
    im.save(crop)
    mask = (np.array(im.split()[-1]) > 8).astype(np.uint8)

    # 2. S3 v2 生成 mesh
    mesh = gen_v2(crop, mode="auto")
    nv = len(mesh["uvs"]) // 2
    rep = eval_mesh(mesh, mask, vertex_budget=nv)  # budget 不卡(這裡只看 IoU/format)
    gen_iou = rep["criteria"]["AC1_iou"]["value"]

    # 3. Award 藝術家真實 mesh(基準 + 座標 sanity check)
    am = load_award_mesh(award_json, slot)
    art_iou = coverage_iou(am["uvs"], am["triangles"], mask)
    art_nv = len(am["uvs"]) // 2
    art_hull = am.get("hull")
    art_tris = len(am["triangles"]) // 3
    weighted = len(am.get("vertices", [])) != len(am["uvs"])

    return {
        "part": layer_name, "slot": slot,
        "psd_slice_size": [im.width, im.height],
        "generated": {
            "mode": mesh.get("_mode"), "vertices": nv, "hull": mesh["hull"],
            "triangles": len(mesh["triangles"]) // 3, "iou": round(gen_iou, 4),
            "format_ok": rep["criteria"]["AC4_format"]["pass"],
            "no_degenerate": rep["criteria"]["AC2b_degenerate"]["pass"],
            "no_orphan": rep["criteria"]["AC2c_orphans"]["pass"],
        },
        "artist": {
            "vertices": art_nv, "hull": art_hull, "triangles": art_tris,
            "weighted": weighted, "self_iou": round(art_iou, 4),
        },
        "coord_sanity_ok": art_iou >= 0.80,   # 藝術家 mesh 應覆蓋自身 alpha;過低=座標慣例錯
        "iou_pass": gen_iou >= art_iou - iou_margin,  # 達到/接近藝術家覆蓋率
        "overall_pass": (art_iou >= 0.80) and (gen_iou >= art_iou - iou_margin)
                        and rep["criteria"]["AC4_format"]["pass"]
                        and rep["criteria"]["AC2b_degenerate"]["pass"]
                        and rep["criteria"]["AC2c_orphans"]["pass"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--parts", nargs="*", default=list(PART_MAP.keys()))
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    _, _, parts = slice_psd(a.psd)
    reports = [validate_part(p, parts, a.award, a.tmp) for p in a.parts]
    out = {"reports": reports,
           "all_pass": all(r["overall_pass"] for r in reports)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["all_pass"] else 1)


if __name__ == "__main__":
    main()
