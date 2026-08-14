#!/usr/bin/env python3
"""S3 泛化驗收 — 生成 mesh vs 真實 Award 藝術家 mesh(機器人件,非窗簾 strip 類)。

動機:先前 S3 v2 只在窗簾/陰影 4 個 mesh(高瘦 strip 拓樸)對照過藝術家真值。
Award 的機器人件(光暈/身體/左手)是「近方形 blob」拓樸(aspect<1.2 → 自動走 v1 Delaunay),
且**在 Award 無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform)。
本工具把「切件 → 生成 mesh → 對照真實藝術家 mesh」端到端跑起來,對一個**新拓樸類別**驗收生成器。

真值來源:Award.json 的藝術家 mesh(uvs/triangles/hull)+ Award atlas 切出的 alpha(uv 空間對齊,
已於 knowledge/s4-psd-to-spine-real.md 校正方向)。

AC(逐件,可自檢):
  AC1 覆蓋率:gen IoU ≥ 藝術家 IoU − margin(藝術家為基準,不用武斷絕對值)。
  AC2 頂點預算:gen 頂點數 ≤ budget_ratio × 藝術家頂點數(精簡度相當)。
  AC3 靜態拓樸:setup pose 0 自交 / 0 翻面 / 0 退化。
  AC4 變形裕度(以藝術家自校準):對 gen 與 artist 施「相同相對 stress 掃描」,
      量各自「首次自交的 stress 幅度(占 bbox 高比例)」。gen 門檻 ≥ artist × 0.8 視為不劣於藝術家。
      ⚠️ 無真實 deform 場,AC4 為**相對探測**(artist 當校準基準),非絕對 pass/fail 真值。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import load_mask, evaluate
from generate_mesh_v2 import generate as gen_v2
import deform_eval as de


def get_att(sk):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)


def artist_mesh(att, slot, name):
    a = att[slot][name]
    uvs = np.array(a["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    verts = np.array(a["vertices"], dtype=np.float64).reshape(-1, 2)
    return {"uvs": uvs, "triangles": tris, "vertices": verts, "hull": a.get("hull"),
            "width": a.get("width"), "height": a.get("height")}


def coverage_iou(uvs, tris, mask):
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    uni = np.logical_or(recon, mask).sum()
    return float(inter / uni) if uni else 0.0


def si_at(verts, tris, mag):
    """在相對 stress 幅度 mag(px)下的自交數。"""
    dv = de.stress_field(verts, mag)
    return de.check(dv, [list(t) for t in tris], None)["self_intersections"]


def deform_headroom(verts, tris, steps=20, frac_max=1.2):
    """回傳首次自交的 stress 幅度(占 bbox 高的比例);None=掃到 frac_max 都乾淨。"""
    v = np.asarray(verts, dtype=np.float64)
    h = float(v[:, 1].max() - v[:, 1].min()) or 1.0
    for k in range(1, steps + 1):
        frac = frac_max * k / steps
        if si_at(v, tris, frac * h) > 0:
            return round(frac, 3)
    return None  # 全程乾淨


def compare(sk, att, atlas, png, slot, name, budget_ratio=1.6, iou_margin=0.02):
    art = artist_mesh(att, slot, name)
    sub = extract(atlas, png, name)
    crop = os.path.join("/tmp", "_cmp_%s.png" % name.split("/")[-1])
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    gen = gen_v2(crop, mode="auto")
    if isinstance(gen, tuple):
        gen = gen[0]
    g_uvs = np.array(gen["uvs"], dtype=np.float64).reshape(-1, 2)
    g_tris = np.array(gen["triangles"], dtype=np.int32).reshape(-1, 3)
    g_verts = np.column_stack([np.array(gen["vertices"])[0::2], np.array(gen["vertices"])[1::2]])

    art_iou = coverage_iou(art["uvs"], art["triangles"], mask)
    gen_iou = coverage_iou(g_uvs, g_tris, mask)
    art_nv = len(art["uvs"]); gen_nv = len(g_uvs)

    # AC3 靜態
    g_setup = de.check(g_verts, [list(t) for t in g_tris], None)
    # AC4 變形裕度(相對,artist 校準)
    art_hr = deform_headroom(art["vertices"], art["triangles"])
    gen_hr = deform_headroom(g_verts, g_tris)

    def hr_val(x):  # None(全程乾淨)視為最大裕度
        return 1.2 if x is None else x

    ac1 = gen_iou >= art_iou - iou_margin
    ac2 = gen_nv <= budget_ratio * art_nv
    ac3 = g_setup["self_intersections"] == 0 and g_setup["triangle_flips"] == 0 and g_setup["degenerate"] == 0
    # AC4:相對變形裕度。⚠️ 這些件在 Award 無 deform timeline → 無真實位移場可比。
    # 實測 stress_field 對 blob **不可信**:真實藝術家 mesh 竟在 ~0.06 bbox 幅度就自交,
    # 代表這個合成剪切+正弦場對近方形 blob 過苛/形狀不對(第 N 次 evaluator miscalibration)。
    # 故 AC4 僅列為診斷(gen vs artist 相對),**不納入 overall_pass**;
    # artist 裕度過低時標記 stress 不適用。
    stress_trustworthy = hr_val(art_hr) >= 0.3
    gen_ge_artist = hr_val(gen_hr) >= hr_val(art_hr) * 0.8

    return {
        "slot": slot, "gen_mode": gen.get("_mode"),
        "AC1_coverage": {"gen_iou": round(gen_iou, 4), "artist_iou": round(art_iou, 4),
                         "margin": iou_margin, "pass": bool(ac1)},
        "AC2_vertex_budget": {"gen": gen_nv, "artist": art_nv, "ratio": round(gen_nv / art_nv, 2),
                              "budget_ratio": budget_ratio, "pass": bool(ac2)},
        "AC3_setup_topology": {**{k: g_setup[k] for k in ("self_intersections", "triangle_flips", "degenerate")},
                               "pass": bool(ac3)},
        "AC4_deform_headroom_diag": {"gen_first_si_frac": gen_hr, "artist_first_si_frac": art_hr,
                                     "gen_ge_artist": bool(gen_ge_artist),
                                     "stress_trustworthy": bool(stress_trustworthy),
                                     "note": "診斷用;無真實 deform 場。artist 裕度<0.3 表 stress_field 對 blob 不適用,不作 gate"},
        "overall_pass": bool(ac1 and ac2 and ac3),  # 僅採可信靜態閘(覆蓋率/預算/靜態拓樸)
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--slots", nargs="*",
                    default=["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"])
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    att = get_att(sk)
    reports = [compare(sk, att, a.atlas, a.png, s, s) for s in a.slots]
    allpass = all(r["overall_pass"] for r in reports)
    print(json.dumps({"reports": reports, "all_pass": allpass}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
