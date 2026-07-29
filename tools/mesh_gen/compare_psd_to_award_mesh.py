#!/usr/bin/env python3
"""端到端 S4→S3 驗收:PSD 件 → S3 生成 mesh → 對照 Award 真實生產 mesh(ground truth)。

背景(knowledge/s4-psd-to-spine-real.md):robot_parts.psd 的 光暈/身體/左手 三件在生產
spine `Award` 中是 **mesh**(78 / 98 / 80 頂點)。本工具把切圖(S4)與 mesh 生成(S3)串成
端到端流程,並用美術手做的 Award mesh 當**真值基準**做量化對照。

流程(每件):
  psd_slice 切出該 leaf 圖層的緊湊 PNG
  → 讀 alpha 當來源遮罩
  → ① artist_iou:Award mesh(region-local uvs,已驗證為 [0,1] 正規化)柵格化覆蓋率(基準)
  → ② generate_mesh_v2 生成 mesh → evaluate_mesh 量 IoU / 格式 / 重心 / 孤兒(受測)
  → AC:coverage(受測 IoU ≥ 基準−margin)+ topology 有效 + 頂點精簡度。

⚠️ 這 5 件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform)→ 不套用
   逐頂點 deform 閘(那需要 deform 位移場);此處以「靜態覆蓋率 + 拓樸有效性」為 AC。

Award mesh UV 座標系(2026-07-29 實測確認):mesh "uvs" 為 **region-local 正規化 [0,1]**
(Spine JSON 標準;rotate/scale 只影響 atlas 打包,不影響邏輯 uv)→ 可直接 uvs*[W,H]
對映到原始朝向的 PSD 切件。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from evaluate_mesh import evaluate as eval_mesh
from generate_mesh_v2 import generate as gen_v2


def award_mesh(skeleton, slot, name):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)[slot][name]


def raster_iou(uvs, tris, mask):
    """把 uvs(region-local [0,1])× mask 尺寸柵格化三角,對 alpha 遮罩算 IoU。"""
    H, W = mask.shape
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    inter = int(np.logical_and(recon, m).sum())
    union = int(np.logical_or(recon, m).sum())
    return (inter / union) if union else 0.0


def compare_piece(piece_png, skeleton, slot, name, iou_margin, vert_ratio):
    # 來源遮罩(PSD 切件 alpha)
    img = cv2.imread(piece_png, cv2.IMREAD_UNCHANGED)
    mask = (img[:, :, 3] > 8).astype(np.uint8) if (img.ndim == 3 and img.shape[2] == 4) \
        else (cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) > 8).astype(np.uint8)
    H, W = mask.shape

    # ① 美術真值 mesh 覆蓋率(基準)
    a = award_mesh(skeleton, slot, name)
    a_uvs = np.array(a["uvs"]).reshape(-1, 2)
    a_tris = np.array(a["triangles"]).reshape(-1, 3)
    a_nv = len(a_uvs)
    weighted = (len(a["vertices"]) != 2 * a_nv)
    artist_iou = raster_iou(a_uvs, a_tris, mask)

    # ② 受測:S3 v2 生成 mesh(square-ish → auto 落回 Delaunay v1)
    mesh = gen_v2(piece_png, mode="auto")
    g_nv = len(mesh["uvs"]) // 2
    # 頂點預算設寬鬆(以美術頂點數的 vert_ratio 倍為上限)以聚焦覆蓋率/拓樸
    budget = max(a_nv, int(a_nv * vert_ratio)) + 8
    ev = eval_mesh(mesh, mask, vertex_budget=budget)
    g_iou = ev["criteria"]["AC1_iou"]["value"]

    ac_cov = g_iou >= artist_iou - iou_margin
    ac_topo = ev["criteria"]["AC4_format"]["pass"] and \
        ev["criteria"]["AC2a_centroid_in_mask"]["pass"] and \
        ev["criteria"]["AC2b_degenerate"]["pass"] and ev["criteria"]["AC2c_orphans"]["pass"]
    ac_pars = g_nv <= a_nv * vert_ratio

    return {
        "piece": name, "mask_wh": [W, H],
        "artist": {"vertices": a_nv, "hull": a["hull"], "triangles": len(a_tris),
                   "weighted": weighted, "iou": round(artist_iou, 4)},
        "generated": {"vertices": g_nv, "hull": mesh["hull"],
                      "triangles": len(mesh["triangles"]) // 3,
                      "mode": mesh.get("_mode"), "iou": round(g_iou, 4)},
        "AC_coverage": {"pass": bool(ac_cov), "gen_iou": round(g_iou, 4),
                        "artist_baseline": round(artist_iou, 4), "margin": iou_margin},
        "AC_topology": {"pass": bool(ac_topo),
                        "format": ev["criteria"]["AC4_format"]["pass"],
                        "centroid": ev["criteria"]["AC2a_centroid_in_mask"]["value"],
                        "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                        "orphans": ev["criteria"]["AC2c_orphans"]["value"]},
        "AC_parsimony": {"pass": bool(ac_pars), "gen_verts": g_nv,
                         "artist_verts": a_nv, "ratio_cap": vert_ratio},
        "overall_pass": bool(ac_cov and ac_topo and ac_pars),
    }


# PSD 圖層名 → Award slot/attachment(見 s4-psd-to-spine-real.md 對應表;僅取 mesh 件)
MESH_MAP = {
    "光暈": "機器人拆件/光暈",
    "身體": "機器人拆件/身體",
    "左手": "機器人拆件/左手",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--out-dir", default="/tmp/robot_parts")
    ap.add_argument("--iou-margin", type=float, default=0.02)
    ap.add_argument("--vert-ratio", type=float, default=1.6)
    a = ap.parse_args()

    sk = json.load(open(a.skeleton))
    # 切件(拿到各 leaf 圖層的緊湊 PNG)
    _, manifest, _ = slice_psd(a.psd, a.out_dir)
    by_name = {e["name"]: e for e in manifest["parts"]}

    reports = []
    for layer, slotname in MESH_MAP.items():
        e = by_name.get(layer)
        if e is None:
            reports.append({"piece": layer, "error": "PSD 找不到此圖層"}); continue
        png = os.path.join(a.out_dir, e["file"])
        reports.append(compare_piece(png, sk, slotname, slotname,
                                     a.iou_margin, a.vert_ratio))

    overall = all(r.get("overall_pass") for r in reports)
    print(json.dumps({"overall_pass": overall, "pieces": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
