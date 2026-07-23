#!/usr/bin/env python3
"""端到端整合 AC — 「PSD件 → S3 mesh → 對照 Award 真實 mesh」。

背景(STATE.md 最高優先候選):S3(v2 strip)與 S4(PSD 切圖)分別已對真實檔驗收,
但兩者尚未串成一條、且從未拿「自動生成的 mesh」對「真實生產 mesh」做正面對照。
Award 中機器人 3 件為 mesh(光暈/左手/身體),正好是自動 mesh 生成的**真值標的**。

與 validate_against_real.py 的差異:
- 標的資產從 main_draw(4 個 unweighted、有 deform timeline)換成 Award 機器人件
  (weighted mesh、**無 deform timeline** → 靠骨骼權重變形,不是逐頂點 deform)。
- 因此 deform 閘不能用「本資產的真實位移場」(不存在)。改以 **main_draw 窗簾的真實
  位移場(UV 座標、藝術家真值)轉移** 當**耐變形壓力測試**(honest:跨資產 robustness
  stress,非本資產運動);仍為真實幅度、非 stress_field 合成場。
- IoU 仍以「藝術家 mesh 自身覆蓋率」為基準(不用武斷 0.95);頂點數對照藝術家精簡度。

真值來源:Award atlas 切件(= PSD 切件,alpha-IoU 0.92~0.99 已確認同素材,見
knowledge/s4-psd-to-spine-real.md)。UV 為 region-local 正規化,artist_iou 直接可用。

用法:
  python3 tools/mesh_gen/validate_psd_to_mesh_award.py            # 3 件全跑
  python3 tools/mesh_gen/validate_psd_to_mesh_award.py --slot 機器人拆件/左手
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
import deform_eval as de
from evaluate_mesh import evaluate, load_mask
from atlas_crop import extract
from validate_against_real import artist_iou
from generate_mesh import generate as gen_v1

# Award 中為 mesh 的 3 件(見 knowledge/s4-psd-to-spine-real.md)
MESH_PARTS = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]

# 這 3 件皆為圓潤 blob(非高瘦 row-convex),strip 不適用 → 走 v1 Delaunay。
# v1 預設 epsilon_frac=0.008 是為 main_draw 小窗簾校準;此類大件(光暈 496px)輪廓
# 相對過粗 → 覆蓋率不足。0.002 讓 3 件覆蓋率皆達/超越藝術家,且頂點數仍低於藝術家。
BLOB_EPSILON = 0.002


def artist_vertex_count(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    return len(a["uvs"]) // 2


def stress_source_field():
    """取 main_draw 窗簾在所有動畫中最大位移幀的真實位移場(UV 座標),當跨資產耐變形壓測。"""
    md = json.load(open("assets/main_draw.json"))
    return de.real_deform_field(md, "image/curtain_left", "image/curtain_left")


def validate_part(award, atlas_path, png_path, slot, name, src_uv, src_field,
                  tmp_dir, iou_margin=0.02, budget_factor=1.0, epsilon=BLOB_EPSILON):
    sub = extract(atlas_path, png_path, name)
    crop = os.path.join(tmp_dir, "_award_part.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    mesh, _ = gen_v1(crop, epsilon_frac=epsilon)
    ev = evaluate(mesh, mask)
    nv = len(mesh["uvs"]) // 2

    iou = ev["criteria"]["AC1_iou"]["value"]
    base = artist_iou(award, slot, name, mask)
    art_nv = artist_vertex_count(award, slot, name)

    # 跨資產耐變形「探針」(informational,非 pass/fail 閘) —— 見下方 note。
    dres = de.transfer_deform_check(mesh, src_uv, src_field)

    coverage_pass = iou >= base - iou_margin
    budget_pass = nv <= art_nv * budget_factor
    fmt_pass = ev["criteria"]["AC4_format"]["pass"]

    return {
        "slot": slot,
        "mesh": {"vertices": nv, "hull": mesh["hull"],
                 "triangles": len(mesh["triangles"]) // 3, "mode": "delaunay-v1",
                 "epsilon": epsilon},
        # === 對真實 Award mesh 的 pass/fail 閘(有真值)===
        "AC_coverage_iou": {"value": round(iou, 4), "artist_baseline": round(base, 4),
                            "margin": iou_margin, "pass": coverage_pass},
        "AC_vertex_budget": {"generated": nv, "artist": art_nv,
                             "factor": budget_factor, "pass": budget_pass},
        "AC_format": {"pass": fmt_pass},
        # === 探針:非 pass/fail(此資產無逐頂點 deform,靠骨骼權重變形)===
        "probe_deform_stress": {
            "note": "informational only — Award 機器人件無 deform timeline;此為跨資產"
                    "轉移 main_draw 窗簾真實位移場的耐變形探針,area_ratio 偏離 ~1 表示 OOD 過拉伸",
            "source": "main_draw/curtain_left real field",
            "area_ratio": round(dres["area_ratio"], 4),
            "self_intersections": dres["self_intersections"],
            "triangle_flips": dres["triangle_flips"], "clean": dres["clean"]},
        "overall_pass": coverage_pass and budget_pass and fmt_pass,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--slot", default=None, help="單件驗證;預設跑全部 3 件 mesh")
    ap.add_argument("--iou-margin", type=float, default=0.02)
    ap.add_argument("--budget-factor", type=float, default=1.0)
    ap.add_argument("--epsilon", type=float, default=BLOB_EPSILON)
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()

    award = json.load(open(a.skeleton))
    src_uv, src_field, src_frame = stress_source_field()
    parts = [a.slot] if a.slot else MESH_PARTS

    reports = []
    for slot in parts:
        rep = validate_part(award, a.atlas, a.png, slot, slot, src_uv, src_field,
                            a.tmp, a.iou_margin, a.budget_factor, a.epsilon)
        reports.append(rep)

    out = {"stress_source_frame": src_frame,
           "parts": reports,
           "overall_pass": all(r["overall_pass"] for r in reports)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["overall_pass"] else 1)


if __name__ == "__main__":
    main()
