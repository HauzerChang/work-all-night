#!/usr/bin/env python3
"""S3 端到端閘:把生成的 mesh 對照「真實生產 Spine mesh」量化評分。

用途:先前 S3 只對 main_draw 的 4 個 mesh 自我驗證(合成/自一致)。本工具把生成器
放到**另一份、未見過的生產資產**(Award 機器人)上,對照美術實際手做的 weighted mesh,
輸出三個量化指標,確認 S3 的輪廓擬合泛化到真實標的。

指標(全部在「region-local 裁切影格」下計算,uv×crop_dims):
- gen_vs_real_iou:生成 hull 多邊形 ∩ 真實 hull 多邊形 的 IoU(端到端核心數字)。
- gen_cov       :生成 hull vs 真實 alpha 剪影 的 IoU(S3 自身輪廓覆蓋率)。
- real_cov      :真實 mesh hull vs alpha 剪影 的 IoU(美術基準;通常 ~0.97,hull 略在剪影外)。

⚠️ 座標對映(已用 alpha 外部真值校正,見 knowledge/s3-vs-real-production-mesh.md):
   Award mesh 的 uvs 是 **region-local [0,1]**(非整頁),width/height = 原始邏輯尺寸;
   直接 uv×crop_dims 即落在 atlas_crop 還原後的 upright region 上(無需 flip/swap)。
   校正法:掃 flip/swap 8 種組合,選「hull 點落在 dilate 後 alpha 內比例」最高者 —— 三件
   一致選中 u0v0s0(直對映),即證對映正確。

閘門(預設):gen_vs_real_iou >= 0.85 且 gen_cov >= 0.90。
"""
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract  # noqa: E402
import generate_mesh_v2 as g2  # noqa: E402


def _skin_atts(award_json):
    d = json.load(open(award_json, encoding="utf-8"))
    skins = d["skins"]
    return skins[0]["attachments"] if isinstance(skins, list) else skins["default"]


def _fill(hull_px, shape):
    m = np.zeros(shape, np.uint8)
    cv2.fillPoly(m, [np.round(hull_px).astype(np.int32)], 1)
    return m


def _iou(a, b):
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def compare(atlas, award_json, part, tmp_dir, rows=12, cols=3, mode="auto"):
    """回傳單一 part 的比對 dict。tmp_dir 用來落地 crop png 給生成器讀。"""
    att = list(_skin_atts(award_json)[part].values())[0]
    if att.get("type") != "mesh":
        raise SystemExit(f"{part} 不是 mesh(type={att.get('type')})")
    ruvs = np.array(att["uvs"]).reshape(-1, 2)
    rhull = att["hull"]

    crop = extract(atlas, "", part)
    ch, cw = crop.shape[:2]
    alpha = (crop[:, :, 3] > 10).astype(np.uint8) if crop.shape[2] == 4 else (crop.max(2) > 10).astype(np.uint8)

    os.makedirs(tmp_dir, exist_ok=True)
    png = os.path.join(tmp_dir, part.replace("/", "_") + ".png")
    cv2.imwrite(png, crop)

    real_px = np.stack([ruvs[:rhull, 0] * cw, ruvs[:rhull, 1] * ch], 1)
    real_fill = _fill(real_px, (ch, cw))

    m = g2.generate(png, rows=rows, cols=cols, mode=mode)
    guvs = np.array(m["uvs"]).reshape(-1, 2)
    ghull = m["hull"]
    gen_px = np.stack([guvs[:ghull, 0] * cw, guvs[:ghull, 1] * ch], 1)
    gen_fill = _fill(gen_px, (ch, cw))

    # 對映健全度:真實 hull 點落在 dilate(6) 後 alpha 內的比例(外部真值檢核)
    ad = cv2.dilate(alpha, np.ones((13, 13), np.uint8))
    inside = float(np.mean([
        0 <= int(u) < cw and 0 <= int(v) < ch and ad[int(v), int(u)] > 0
        for u, v in real_px
    ]))

    return {
        "part": part,
        "gen_mode": m.get("_mode", mode),
        "gen_verts": len(guvs), "real_verts": len(ruvs),
        "gen_hull": ghull, "real_hull": rhull,
        "gen_vs_real_iou": round(_iou(gen_fill, real_fill), 3),
        "gen_cov": round(_iou(gen_fill, alpha), 3),
        "real_cov": round(_iou(real_fill, alpha), 3),
        "map_inside": round(inside, 3),
    }


def gate(r, min_iou=0.85, min_cov=0.90, min_map=0.85):
    reasons = []
    if r["gen_vs_real_iou"] < min_iou:
        reasons.append(f"gen_vs_real_iou {r['gen_vs_real_iou']}<{min_iou}")
    if r["gen_cov"] < min_cov:
        reasons.append(f"gen_cov {r['gen_cov']}<{min_cov}")
    if r["map_inside"] < min_map:
        reasons.append(f"map_inside {r['map_inside']}<{min_map}(對映可疑)")
    return (len(reasons) == 0), reasons


ROBOT_MESH_PARTS = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--json", default="assets/Award.json")
    ap.add_argument("--parts", nargs="*", default=ROBOT_MESH_PARTS)
    ap.add_argument("--mode", default="auto")
    ap.add_argument("--tmp", default="scratch_cmp")
    a = ap.parse_args()

    print(f"{'part':16} {'mode':12} {'gV':>3} {'rV':>3} {'g∩r':>6} {'gcov':>6} {'rcov':>6} {'map':>5}  gate")
    all_pass = True
    for part in a.parts:
        r = compare(a.atlas, a.json, part, a.tmp, mode=a.mode)
        ok, reasons = gate(r)
        all_pass &= ok
        short = part.split("/")[-1]
        print(f"{short:16} {r['gen_mode']:12} {r['gen_verts']:>3} {r['real_verts']:>3} "
              f"{r['gen_vs_real_iou']:>6.3f} {r['gen_cov']:>6.3f} {r['real_cov']:>6.3f} "
              f"{r['map_inside']:>5.2f}  {'PASS' if ok else 'FAIL '+';'.join(reasons)}")
    print("OVERALL", "PASS" if all_pass else "FAIL")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
