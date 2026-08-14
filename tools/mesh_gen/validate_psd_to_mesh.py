#!/usr/bin/env python3
"""端到端 AC:PSD 件 → S3 generate_mesh → 對照真實生產 Spine mesh(ground truth)。

情境(見 knowledge/s4-psd-to-spine-real.md):機器人拆件 PSD 的 3 個圖層(光暈/身體/左手)
在生產 spine `Award` 中是 **weighted mesh**(靠骨骼權重變形,**無 deform timeline**)。
因此這裡的真值不是「逐頂點 deform 場」,而是 **拓樸預算 + 靜態覆蓋 IoU 對照藝術家真實 mesh**。

共同座標系:直接用 **PSD 件 alpha**(最高保真、未旋轉、未縮小)當 mask。
經驗證(2026-08-14):藝術家 mesh 的 region-local uvs 疊到 PSD 件 alpha IoU 0.95~0.98,
故 PSD 件即為藝術家 mesh 與生成 mesh 的共同評估框。

每件流程:
  ① 先驗評估器:藝術家真實 mesh 對 PSD alpha 的覆蓋 IoU(baseline,同時是評估器自一致性檢查)。
  ② 生成:generate_mesh_v2(auto) 對 PSD 件 → 生成 mesh。
  ③ 評分:生成 mesh IoU(evaluate_mesh)、格式、頂點預算(以藝術家頂點數為預算)。
  ④ 判定:gen_iou >= artist_iou - margin 且 格式合法 且 nv <= 藝術家 nv(預算)。

用法:
  python3 tools/mesh_gen/validate_psd_to_mesh.py            # 跑全部 3 件
  python3 tools/mesh_gen/validate_psd_to_mesh.py --part 身體  # 單件
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask

# 機器人拆件 3 個 mesh 件:PSD 圖層名 → (PSD 切件檔, Award slot/attachment key)
PIECES = {
    "光暈": "00_光暈.png",
    "身體": "03_身體.png",
    "左手": "04_左手.png",
}


def artist_mesh(award_json, name):
    sk = json.load(open(award_json))
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att["機器人拆件/" + name]["機器人拆件/" + name]


def render_iou(uvs, tris, mask):
    """把 (region-local uvs, triangles) 填成多邊形,對 mask 算 IoU。"""
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    return float(np.logical_and(recon, m).sum() / max(int(np.logical_or(recon, m).sum()), 1))


def validate_piece(name, psd_file, award_json, parts_dir, iou_margin=0.03):
    piece_png = os.path.join(parts_dir, psd_file)
    mask = load_mask(piece_png)             # PSD 件 alpha = 共同評估框
    H, W = mask.shape

    # ① 藝術家真實 mesh(ground truth)→ baseline + 評估器自一致性
    a = artist_mesh(award_json, name)
    a_uvs = np.array(a["uvs"]).reshape(-1, 2)
    a_tris = np.array(a["triangles"]).reshape(-1, 3)
    a_nv = len(a_uvs)
    artist_iou = render_iou(a_uvs, a_tris, mask)

    # ② 生成 mesh(auto)
    mesh = gen_v2(piece_png, mode="auto")
    nv = len(mesh["uvs"]) // 2

    # ③ 評分(頂點預算 = 藝術家頂點數,對齊生產精簡度)
    ev = evaluate(mesh, mask, vertex_budget=a_nv)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]
    fmt_ok = ev["criteria"]["AC4_format"]["pass"]
    centroid_ok = ev["criteria"]["AC2a_centroid_in_mask"]["pass"]
    orphan_ok = ev["criteria"]["AC2c_orphans"]["pass"]
    budget_ok = nv <= a_nv

    iou_ok = gen_iou >= artist_iou - iou_margin
    overall = iou_ok and fmt_ok and centroid_ok and orphan_ok and budget_ok

    return {
        "piece": name, "psd_size": [W, H],
        "artist": {"vertices": a_nv, "hull": a["hull"], "triangles": len(a_tris),
                   "coverage_iou": round(artist_iou, 4), "weighted": len(a["vertices"]) != a_nv * 2},
        "generated": {"vertices": nv, "hull": mesh["hull"],
                      "triangles": len(mesh["triangles"]) // 3, "mode": mesh.get("_mode"),
                      "coverage_iou": round(gen_iou, 4)},
        "AC_coverage": {"gen": round(gen_iou, 4), "artist_baseline": round(artist_iou, 4),
                        "margin": iou_margin, "pass": iou_ok},
        "AC_budget": {"gen_nv": nv, "artist_nv": a_nv, "pass": budget_ok},
        "AC_format": {"pass": fmt_ok},
        "AC_centroid_in_mask": {"value": ev["criteria"]["AC2a_centroid_in_mask"]["value"],
                                "pass": centroid_ok},
        "AC_no_orphan": {"value": ev["criteria"]["AC2c_orphans"]["value"], "pass": orphan_ok},
        "overall_pass": overall,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--parts-dir", default="/tmp/robot_parts",
                    help="psd_slice 切出的件目錄(需先跑 psd_slice.py -o)")
    ap.add_argument("--part", default=None, help="只驗單件(光暈/身體/左手)")
    ap.add_argument("--margin", type=float, default=0.03)
    a = ap.parse_args()

    # 若件目錄不存在,先切
    if not os.path.isdir(a.parts_dir) or not os.listdir(a.parts_dir):
        from psd_slice import slice_psd
        slice_psd(a.psd, a.parts_dir)

    names = [a.part] if a.part else list(PIECES.keys())
    reports = [validate_piece(n, PIECES[n], a.award, a.parts_dir, a.margin) for n in names]
    allpass = all(r["overall_pass"] for r in reports)
    print(json.dumps({"overall_pass": allpass, "pieces": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
