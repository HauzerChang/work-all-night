#!/usr/bin/env python3
"""端到端「PSD件 → S3 mesh → 對照真實生產 mesh(Award)」整合 AC。

背景(見 knowledge/s4-psd-to-spine-real.md):
  Award 是機器人拆件的真實生產 spine。其中 3 件是 **weighted mesh** 且 **無 deform timeline**
  (變形靠骨骼/權重,非逐頂點 deform):
    - 機器人拆件/光暈  (78v / 76t / hull78)
    - 機器人拆件/身體  (98v / 154t / hull40)
    - 機器人拆件/左手  (80v / 116t / hull42)
  這是我們第一個「有藝術家真值可比」的 S3 標的(main_draw 4 mesh 為 unweighted + 有 deform)。

為何 deform 閘 N/A:
  這 3 件在 Award **沒有 deform timeline**(逐頂點形變),所以 deform_eval.real_deform_field
  不適用。形變由骨骼+權重驅動。逐頂點拓樸穩健性改由靜態 well-formed 閘(evaluate_mesh 的
  退化/孤兒/質心)把關。

驗收目標(AC):
  對每個 mesh 件,以兩種來源餵 generate_mesh_v2:
  A) atlas 來源(Award 貼圖切出的 region;與藝術家 mesh 同一座標框):
     - AC-IoU:生成 mesh 覆蓋 IoU ≥ 藝術家 mesh 對同一 alpha 的 IoU − margin(真值 parity)。
     - AC-topo:evaluate_mesh 的 well-formed(0 退化 / 0 孤兒 / 質心在遮罩內)。
     - AC-budget:生成頂點數 ≤ 藝術家頂點數(效率不劣於真值)。
  B) PSD 來源(psd_slice 原生解析度切件;真正的 PSD-first pipeline 入口):
     - 自 IoU(對自身 alpha)+ well-formed → 證明生成器對尺度穩健(0.70 atlas 縮放不影響品質)。

Spine mesh uvs 為 **region-local 正規化**(0..1 over attachment region,經驗證 main_draw / 左手
span≈[0,1]);extract() 已把 rotate 件轉回原方向,故 uv*(W,H) 直接對應 mask(不需 v-flip;
已驗:direct 0.97 vs vflip 0.44-0.60)。
"""
import argparse, json, sys, os
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate as eval_mesh, load_mask
from generate_mesh_v2 import generate as gen_v2

# mesh 件:slot/attachment 名 (Award) ⇄ PSD 切件檔名 (psd_slice 產)
MESH_PARTS = [
    {"name": "機器人拆件/光暈", "psd": "00_光暈.png"},
    {"name": "機器人拆件/身體", "psd": "03_身體.png"},
    {"name": "機器人拆件/左手", "psd": "04_左手.png"},
]


def artist_mesh(skeleton, name):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    # slot 名 == attachment 名(Award 慣例)
    a = att[name][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    return uvs, tris


def poly_iou(uvs01, tris, mask):
    """uvs01: region-local 0..1;映到 mask 尺寸後三角填充求覆蓋 IoU。"""
    H, W = mask.shape
    rp = np.column_stack([uvs01[:, 0] * W, uvs01[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    uni = np.logical_or(recon, mask).sum()
    return float(inter / uni) if uni else 0.0


def gen_report(png_path, mask, budget, target_iou):
    """png_path: 真實切件影像(含 RGB → Canny 內部取樣可用);mask: 供 IoU/topo 評估。"""
    m = gen_v2(png_path, mode="auto", target_iou=target_iou)
    if isinstance(m, tuple):
        m = m[0]
    nv = len(m["uvs"]) // 2
    ev = eval_mesh(m, mask)["criteria"]
    gen_uvs = np.array(m["uvs"]).reshape(-1, 2)
    gen_tris = np.array(m["triangles"]).reshape(-1, 3)
    topo_clean = (ev["AC2b_degenerate"]["value"] == 0 and
                  ev["AC2c_orphans"]["value"] == 0 and
                  ev["AC2a_centroid_in_mask"]["value"] >= 0.999)
    return {
        "mode": m.get("_mode"), "vertices": nv, "hull": m["hull"],
        "triangles": len(m["triangles"]) // 3,
        "iou": round(ev["AC1_iou"]["value"], 4),
        "topo_clean": topo_clean,
        "degenerate": ev["AC2b_degenerate"]["value"],
        "orphans": ev["AC2c_orphans"]["value"],
        "centroid_in_mask": ev["AC2a_centroid_in_mask"]["value"],
        "within_budget": nv <= budget,
    }, (gen_uvs, gen_tris)


_TMP = os.environ.get("CMP_TMP", "/tmp/aw/_cmp")


def run(award_json, atlas, png, psd_dir, iou_margin, target_iou):
    sk = json.load(open(award_json))
    os.makedirs(_TMP, exist_ok=True)
    out = {"iou_margin": iou_margin, "target_iou": target_iou, "parts": []}
    for part in MESH_PARTS:
        name = part["name"]
        # ---- A) atlas 來源:與藝術家 mesh 同框(切件保留 RGB 供 Canny) ----
        sub = extract(atlas, png, name)
        crop = os.path.join(_TMP, part["psd"])
        cv2.imwrite(crop, sub)
        mask = load_mask(crop)

        a_uvs, a_tris = artist_mesh(sk, name)
        artist_iou = round(poly_iou(a_uvs, a_tris, mask), 4)
        artist_nv = len(a_uvs)

        g_atlas, _ = gen_report(crop, mask, budget=artist_nv, target_iou=target_iou)
        parity = g_atlas["iou"] >= artist_iou - iou_margin
        atlas_pass = parity and g_atlas["topo_clean"] and g_atlas["within_budget"]

        # ---- B) PSD 來源:原生解析度 pipeline 入口 ----
        psd_png = os.path.join(psd_dir, part["psd"])
        psd_mask = load_mask(psd_png)
        g_psd, _ = gen_report(psd_png, psd_mask, budget=artist_nv, target_iou=target_iou)
        psd_pass = g_psd["topo_clean"]  # 自 IoU 品質看 iou 值,通過條件為 well-formed

        out["parts"].append({
            "name": name,
            "artist": {"vertices": artist_nv, "iou": artist_iou,
                       "region_px": [int(mask.shape[1]), int(mask.shape[0])]},
            "gen_atlas": g_atlas,
            "gen_psd": {**g_psd, "src_px": [int(psd_mask.shape[1]), int(psd_mask.shape[0])]},
            "AC_iou_parity": {"gen": g_atlas["iou"], "artist": artist_iou,
                              "margin": iou_margin, "pass": parity},
            "AC_topo_clean": g_atlas["topo_clean"],
            "AC_vertex_budget": {"gen": g_atlas["vertices"], "artist_max": artist_nv,
                                 "pass": g_atlas["within_budget"]},
            "atlas_pass": atlas_pass,
            "psd_pass": psd_pass,
            "pass": atlas_pass and psd_pass,
        })
    out["overall_pass"] = all(p["pass"] for p in out["parts"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--psd-dir", default="/tmp/aw/psd_parts")
    ap.add_argument("--iou-margin", type=float, default=0.02)
    ap.add_argument("--target-iou", type=float, default=0.97,
                    help="生成器自適應邊界細化目標覆蓋 IoU(None→關閉)")
    a = ap.parse_args()
    rep = run(a.award, a.atlas, a.png, a.psd_dir, a.iou_margin, a.target_iou)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
