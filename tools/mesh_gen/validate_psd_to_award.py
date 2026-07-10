#!/usr/bin/env python3
"""端到端 S4→S3 對真實生產標的驗收:PSD 件 → 生成 mesh → 對照 Award 真實藝術家 mesh。

背景(見 knowledge/s4-psd-to-spine-real.md):`robot_parts.psd` 5 圖層一對一對應
真實 spine `Award` 的 slot `機器人拆件/<圖層名>`。其中 3 件會 warp → 藝術家做成 **mesh**:
  - 光暈(78v / hull78 / 76 tri)、身體(98v / hull40 / 154 tri)、左手(80v / hull42 / 116 tri)。
剛體 2 件(右手/頭)為 region,不在本驗收範圍。

本工具把 S4(psd_slice)與 S3(generate_mesh_v2)串成端到端,並以藝術家 mesh 為**真值**:
  PSD 切件 PNG → 生成 mesh → ① 覆蓋 IoU(vs 切件 alpha)vs 藝術家 mesh 同法覆蓋(baseline)
  ② 頂點/hull/三角預算 vs 藝術家。

⚠️ 這 3 件在 Award 中**無 deform timeline**(靠骨骼擺 pose,非 mesh 變形)——
   故本驗收為「靜態拓樸 + 覆蓋」對真值,deform 耐受閘仍以 main_draw 窗簾(有 deform)為準。

比對空間:一律用 **uvs**(紋理座標),藝術家 mesh 為 weighted(vertices 為 [骨數,idx,bindX,bindY,w,...]
變長格式,不能直讀局部座標),但 uvs 每頂點一組,與切件 art 同向;rotate/縮放只影響 atlas 打包,
不影響 JSON uvs 的邏輯 [0,1] art 空間 → 直接 uv*(W,H) 映射切件像素即可(以 baseline 合理性反查)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from evaluate_mesh import evaluate, load_mask
from generate_mesh_v2 import generate as gen_v2

# PSD 圖層名 → Award slot(=attachment)名。3 件 mesh。
MESH_PARTS = {
    "光暈": "機器人拆件/光暈",
    "身體": "機器人拆件/身體",
    "左手": "機器人拆件/左手",
}


def artist_mesh(skeleton, slot_name):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[slot_name][slot_name]


def raster_uv(uvs, tris, H, W):
    """以 uvs(紋理座標)光柵化三角網 → 覆蓋 mask(切件像素空間)。"""
    uvs = np.array(uvs).reshape(-1, 2)
    tris = np.array(tris).reshape(-1, 3)
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return recon


def iou(a, b):
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def validate_part(psd_layer, slot_name, piece_png, award, iou_margin=0.0,
                  coverage=None, max_verts=100):
    mask = load_mask(piece_png)                 # (H,W) 0/1
    H, W = mask.shape

    # --- S3 生成 mesh(給 coverage → 評估器驅動自動精修 epsilon)---
    gen = gen_v2(piece_png, mode="auto", coverage=coverage, max_verts=max_verts)
    gen_nv = len(gen["uvs"]) // 2
    gen_iou = evaluate(gen, mask)["criteria"]["AC1_iou"]["value"]

    # --- 藝術家真值 mesh ---
    am = artist_mesh(award, slot_name)
    art_nv = len(am["uvs"]) // 2
    # baseline:藝術家 mesh 以同法(uvs)覆蓋同一切件 alpha
    art_recon = raster_uv(am["uvs"], am["triangles"], H, W)
    art_iou = iou(art_recon.astype(bool), mask.astype(bool))

    return {
        "psd_layer": psd_layer,
        "award_slot": slot_name,
        "generated": {"mode": gen.get("_mode"), "vertices": gen_nv,
                      "hull": gen["hull"], "triangles": len(gen["triangles"]) // 3,
                      **({"refine": gen["_refine"]} if "_refine" in gen else {})},
        "artist": {"vertices": art_nv, "hull": am["hull"],
                   "triangles": len(am["triangles"]) // 3, "weighted": len(am["vertices"]) != len(am["uvs"])},
        "AC_coverage": {"gen_iou_vs_alpha": round(gen_iou, 4),
                        "artist_iou_vs_alpha": round(art_iou, 4),
                        "pass": gen_iou >= art_iou - iou_margin},
        "AC_vertex_budget": {"gen": gen_nv, "artist": art_nv,
                             "pass": gen_nv <= art_nv},
        "overall_pass": (gen_iou >= art_iou - iou_margin) and (gen_nv <= art_nv),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--parts", default="/tmp/robot_parts",
                    help="psd_slice 輸出目錄(含 NN_<圖層名>.png + manifest.json)")
    ap.add_argument("--iou_margin", type=float, default=0.0,
                    help="覆蓋率容差(預設 0:精修後應直接達/超越藝術家基準)")
    ap.add_argument("--coverage", type=float, default=0.98,
                    help="評估器驅動自動精修的覆蓋率目標(自我品質閘,不依賴藝術家真值);"
                         "0.98 對 3 件全達/超越藝術家基準,0.97 則左手差 0.3pp(其藝術家 mesh 特別緊))")
    ap.add_argument("--max_verts", type=int, default=100)
    a = ap.parse_args()

    award = json.load(open(a.award))
    manifest = json.load(open(os.path.join(a.parts, "manifest.json")))
    file_of = {p["name"]: p["file"] for p in manifest["parts"]}

    reports = []
    for layer, slot in MESH_PARTS.items():
        png = os.path.join(a.parts, file_of[layer])
        reports.append(validate_part(layer, slot, png, award, a.iou_margin,
                                     coverage=a.coverage, max_verts=a.max_verts))

    overall = all(r["overall_pass"] for r in reports)
    out = {"overall_pass": overall, "iou_margin": a.iou_margin,
           "coverage_target": a.coverage, "parts": reports}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
