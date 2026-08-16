#!/usr/bin/env python3
"""端到端 AC:PSD 件 → S3 生成 mesh → 對照 Award 真實生產 mesh。

這是「S4(PSD 切件)＋ S3(mesh 生成)」串成端到端、對**真實生產標的**驗收的閘。
真值 = 機器人拆件在 Award spine 裡的藝術家 mesh(光暈/身體/左手,皆 weighted mesh)。

三件事(每件 mesh):
  AC1 覆蓋率 gen ≥ artist − margin
      - gen_iou   :generate_mesh_v2 對 **PSD 切件 alpha** 的覆蓋(件由 PSD 切出→在自身紋理空間量)。
      - artist_iou:Award 藝術家 mesh 對 **atlas page 上該 region 的 alpha** 的覆蓋
                    (在 page 像素空間量,不需 de-rotate;藝術家 mesh 與 region alpha 同座標系,
                     IoU 對旋轉不敏感)。v-origin 以「取覆蓋率較高者」自校準(正確慣例必高)。
      兩者都是「該件 alpha 被 mesh 覆蓋的比例」→ 同性質可直接比。
  AC2 頂點預算:gen 頂點數 ≤ artist 頂點數(v2 strip 預設 30v << 藝術家 78~98v)。
  AC3 deform 穩健(轉移真實場):Award 這些件無 deform(靠骨骼),故轉移 main_draw
      curtain_left 的真實位移場(已校準)→ 0 自交 / 0 翻面,確認生成拓樸耐變形。

⚠️ 誠實聲明:gen 與 artist 的覆蓋率在各自的原生紋理座標量測(PSD 件 vs atlas region);
   兩者為同一素材(PSD↔atlas alpha-IoU 0.92~0.99,見 s4-psd-to-spine-real.md),
   IoU 為比例量(尺度不變),故可比。這不是「同一張點陣圖上疊兩個 mesh」,而是
   「兩個 mesh 各自覆蓋同一件的能力」對照。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
import deform_eval as de
from evaluate_mesh import evaluate, load_mask

# 機器人 mesh 件:PSD 切件檔(psd_slice 產出) ↔ Award slot/attachment 名
PARTS = [
    {"key": "光暈",  "psd_file": "00_光暈.png",  "award": "機器人拆件/光暈"},
    {"key": "身體",  "psd_file": "03_身體.png",  "award": "機器人拆件/身體"},
    {"key": "左手",  "psd_file": "04_左手.png",  "award": "機器人拆件/左手"},
]


def artist_coverage(sk, atlas_path, page_dir, slot):
    """藝術家 mesh 對 atlas region alpha 的覆蓋率。
    Award mesh uvs 為 **region-local [0,1]**(非 page 正規化;經數值確認 raw uv≈0..1),
    故直接對 atlas_crop 還原(de-rotate 為 upright)的 region 點陣圖量測。
    回傳 (iou, nverts, v_origin_used)。v-origin(top/bottom)自校準取覆蓋率較高者。"""
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][slot]
    uvs = np.array(a["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    nv = len(uvs)

    sub = extract(atlas_path, os.path.join(page_dir, "_ignored.png"), slot)  # 多頁時自動取 region 的 page
    reg_alpha = (sub[:, :, 3] > 8).astype(np.uint8) if sub.shape[2] >= 4 else (sub.max(2) > 8).astype(np.uint8)
    Hc, Wc = reg_alpha.shape

    best = None
    for v_up in (False, True):
        px = uvs[:, 0] * Wc
        vv = (1.0 - uvs[:, 1]) if v_up else uvs[:, 1]
        py = vv * Hc
        pts = np.column_stack([px, py])
        recon = np.zeros((Hc, Wc), np.uint8)
        for t in tris:
            cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
        inter = np.logical_and(recon, reg_alpha).sum()
        union = np.logical_or(recon, reg_alpha).sum()
        iou = float(inter / union) if union else 0.0
        if best is None or iou > best[0]:
            best = (iou, "y-up" if v_up else "y-down")
    return best[0], nv, best[1]


def make_gen(gen):
    """回傳 (part_png)->mesh。v3(緊湊件預設)/ v2(strip)/ v1。"""
    if gen == "v3":
        from generate_mesh_v3 import generate as g
        return lambda p: g(p, target_hull=40)
    if gen == "v2":
        from generate_mesh_v2 import generate as g
        return lambda p: g(p, mode="auto")
    from generate_mesh import generate as g

    def _v1(p):
        m = g(p)
        return m[0] if isinstance(m, tuple) else m
    return _v1


def validate(psd_parts_dir, award_json, award_atlas, award_dir,
             main_draw_json, iou_margin=0.03, gen="v3", tmp="/tmp"):
    sk = json.load(open(award_json))
    md = json.load(open(main_draw_json))
    uvs_src, field, field_frame = de.real_deform_field(md, "image/curtain_left", "image/curtain_left")
    gen_fn = make_gen(gen)

    results = []
    for p in PARTS:
        part_png = os.path.join(psd_parts_dir, p["psd_file"])
        mask = load_mask(part_png)  # PSD 件 alpha

        mesh = gen_fn(part_png)
        gen_iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
        gen_nv = len(mesh["uvs"]) // 2

        art_iou, art_nv, vorig = artist_coverage(sk, award_atlas, award_dir, p["award"])

        dres = de.transfer_deform_check(mesh, uvs_src, field)

        ac1 = gen_iou >= art_iou - iou_margin
        ac2 = gen_nv <= art_nv
        ac3 = dres["clean"]
        results.append({
            "part": p["key"], "award_slot": p["award"],
            "AC1_coverage": {"gen_iou": round(gen_iou, 4), "artist_iou": round(art_iou, 4),
                             "margin": iou_margin, "v_origin": vorig, "pass": ac1},
            "AC2_vertex_budget": {"gen_verts": gen_nv, "artist_verts": art_nv,
                                  "mode": mesh.get("_mode"), "pass": ac2},
            "AC3_deform_transfer": {"src": "main_draw/curtain_left@" + str(field_frame),
                                    "self_intersections": dres["self_intersections"],
                                    "triangle_flips": dres["triangle_flips"],
                                    "area_ratio": dres["area_ratio"], "pass": ac3},
            "overall_pass": ac1 and ac2 and ac3,
        })
    overall = all(r["overall_pass"] for r in results)
    return {"overall_pass": overall, "parts": results}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd-parts", default="/tmp/robot_parts")
    ap.add_argument("--award-json", default="assets/Award.json")
    ap.add_argument("--award-atlas", default="assets/Award.atlas")
    ap.add_argument("--award-dir", default="assets")
    ap.add_argument("--main-draw", default="assets/main_draw.json")
    ap.add_argument("--margin", type=float, default=0.03)
    ap.add_argument("--gen", choices=["v1", "v2", "v3"], default="v3")
    a = ap.parse_args()
    rep = validate(a.psd_parts, a.award_json, a.award_atlas, a.award_dir,
                   a.main_draw, a.margin, a.gen)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
