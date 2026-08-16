#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 生成 mesh → 對照 Award 真實(藝術家)mesh。

這是第一個把 S4(切圖)+ S3(mesh 生成)串起來、且**對真實生產標的有 ground truth**
的整合驗收。流程:

  robot_parts.psd ──psd_slice──▶ 件 PNG(緊湊 bbox + 真實 alpha)
      │                              │
      │                        generate_mesh(v1/v2) ─▶ 生成 mesh
      │                              │
      └── Award.json 藝術家 mesh(uvs) ── 兩者都對「同一張件 alpha mask」量 IoU

比較維度(對 3 個在 Award 中為 mesh 的件:光暈 / 身體 / 左手):
  ① 覆蓋率 IoU:生成 mesh vs 件 alpha,基準 = 藝術家 mesh 對同 mask 的 IoU。
  ② 頂點/三角預算:生成 vs 藝術家(是否精簡度相當)。

⚠️ deform 閘:這 3 件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform),
   沒有真實位移場可轉移。依 RULES「不要用未校準 stress_field」,此處 deform 閘標為 N/A,
   只做靜態覆蓋率 + 預算對照(皆有藝術家 ground truth,可信)。

藝術家 mesh 皆為 weighted;artist_iou 只用 uvs+triangles(不碰 vertices bind 資料),故適用。
uvs 為 region 正規化 [0,1];件 PNG 是該 region 的緊湊裁切(±2px atlas padding),兩者對齊
(已驗:藝術家 mesh 對件 mask IoU 0.948~0.977,證明座標系一致)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from evaluate_mesh import evaluate as eval_mesh


# Award 中為 mesh 的 3 件:PSD 圖層名 → Award slot（attachment 同名）
MESH_PIECES = {
    "光暈": "機器人拆件/光暈",
    "身體": "機器人拆件/身體",
    "左手": "機器人拆件/左手",
}


def award_mesh(skeleton, slot):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)[slot]
    for nm, a in atts.items():
        if a.get("type") == "mesh":
            return a
    raise SystemExit(f"{slot} 無 mesh attachment")


def mesh_iou_vs_mask(uvs, tris, mask):
    """以 mesh uvs(region 正規化)重建覆蓋圖,對 alpha mask 量 IoU。"""
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / max(union, 1))


def piece_masks(psd_path):
    """切 PSD,回傳 {圖層名: (rgba_ndarray, mask, W, H)}(件緊湊 bbox)。"""
    _, _, parts = slice_psd(psd_path)
    out = {}
    for entry, im in parts:
        rgba = np.array(im.convert("RGBA"))          # H,W,4  (RGBA order)
        mask = (rgba[:, :, 3] > 8).astype(np.uint8)
        out[entry["name"]] = (rgba, mask, im.width, im.height)
    return out


def run(psd_path, skeleton_path, gen, tmp_dir, iou_margin=0.02):
    sk = json.load(open(skeleton_path))
    masks = piece_masks(psd_path)
    os.makedirs(tmp_dir, exist_ok=True)
    results = {}
    for layer, slot in MESH_PIECES.items():
        rgba, mask, W, H = masks[layer]
        # 寫出件 PNG 供生成器讀(BGRA for cv2)
        crop = os.path.join(tmp_dir, f"_{slot.replace('/', '_')}.png")
        cv2.imwrite(crop, cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))

        # 藝術家 ground truth
        a = award_mesh(sk, slot)
        a_uv = np.array(a["uvs"]).reshape(-1, 2)
        a_tri = np.array(a["triangles"]).reshape(-1, 3)
        a_iou = mesh_iou_vs_mask(a_uv, a_tri, mask)
        a_nv = len(a["uvs"]) // 2

        # 生成 mesh
        m = gen(crop)
        if isinstance(m, tuple):
            m = m[0]
        g_uv = np.array(m["uvs"]).reshape(-1, 2)
        g_tri = np.array(m["triangles"]).reshape(-1, 3)
        g_iou = mesh_iou_vs_mask(g_uv, g_tri, mask)
        g_nv = len(m["uvs"]) // 2
        static = eval_mesh(m, mask)["criteria"]

        results[layer] = {
            "slot": slot, "piece_px": [W, H],
            "artist": {"vertices": a_nv, "hull": a.get("hull"),
                       "triangles": len(a["triangles"]) // 3, "iou_vs_piece": round(a_iou, 4)},
            "generated": {"vertices": g_nv, "hull": m["hull"],
                          "triangles": len(m["triangles"]) // 3, "mode": m.get("_mode"),
                          "iou_vs_piece": round(g_iou, 4)},
            "AC_iou": {"gen": round(g_iou, 4), "artist_baseline": round(a_iou, 4),
                       "margin": iou_margin, "pass": g_iou >= a_iou - iou_margin},
            "AC_clean_topology": {   # 靜態拓樸乾淨:重心在 mask、無退化、無孤兒
                "pass": bool(static["AC2a_centroid_in_mask"]["pass"]
                             and static["AC2b_degenerate"]["pass"]
                             and static["AC2c_orphans"]["pass"]),
                "centroid_in_mask": static["AC2a_centroid_in_mask"]["value"],
                "degenerate": static["AC2b_degenerate"]["value"],
                "orphans": static["AC2c_orphans"]["value"]},
            "AC_budget": {"gen_v": g_nv, "artist_v": a_nv,
                          "pass": g_nv <= a_nv * 2.0},   # 不超過藝術家 2 倍即算精簡
        }
        results[layer]["piece_pass"] = all(
            results[layer][k]["pass"] for k in ("AC_iou", "AC_clean_topology", "AC_budget"))

    overall = all(r["piece_pass"] for r in results.values())
    return {"overall_pass": overall, "deform_gate": "N/A (無 deform timeline;靠骨骼/權重變形)",
            "pieces": results}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--gen", choices=["v1", "v2"], default="v2")
    ap.add_argument("--tmp", default="/tmp/psd2award")
    a = ap.parse_args()
    if a.gen == "v1":
        from generate_mesh import generate as g
        gen = lambda p: g(p)
    else:
        from generate_mesh_v2 import generate as g
        gen = lambda p: g(p, mode="auto")
    rep = run(a.psd, a.skeleton, gen, a.tmp)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
