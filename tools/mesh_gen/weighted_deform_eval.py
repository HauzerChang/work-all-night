#!/usr/bin/env python3
"""S3 weighted-mesh 變形評估器 — 量化「骨骼驅動的 weighted mesh 在動畫下變不變形壞掉,
以及應變(strain)分布」,補上 compare_robot_mesh 的唯一未驗維度(見
knowledge/s3-robot-mesh-vs-award.md 誠實限制)。

真值:Award 3 個機器人 weighted mesh(光暈/左手/身體),綁到 leg 骨鏈。三件 setup attachment
皆 null,只在所屬的 **Legend 檔位 In/Loop/Out** 三支動畫被掛載顯示(可見性 gating 自動判定),
靠 bone rotate/scale/translate 變形。用 weighted_skin 的 Spine FK+蒙皮引擎驅動,量測:
  - 幾何合法性:self-intersections / triangle flips / degenerate(沿用 deform_eval 判準)
  - 應變非均勻度:edge 應變 dispersion=p95−p50(|strain|)+ triangle area ratio 範圍
    → 這是「內部取樣密度服務變形平滑度」的可量化簽章,供 S3 weighted 生成器對照。

⚠️ **可見性 gating(誠實關鍵)**:只在 attachment 實際可見(attachment==name 且 slot alpha>門檻)
   的幀評估。否則會誤判:光暈在 Award_Legend_In 前段(t≤0.29)被壓到自交 71 處,但那段 alpha=0
   (淡入前完全透明),根本沒顯示 → 不算壞掉。gating 後 3 件全乾淨。

三條可機讀 AC:
  AC1 仿射再現性(引擎正確性,非循環):對 root 骨施加剛體 T(旋轉θ+平移),
      所有蒙皮頂點必恰好被 T 映射 → 同時驗 FK 組合 + 權重正規化。權重先正規化以隔離
      藝術家捨入,殘差為純浮點(實測 2.8e-13)。max_err < 1e-6 px。
  AC2 權重單位分解:每頂點權重和 = 1(閾 2e-4;藝術家 3~5 位小數捨入,實測 dev 1e-5)。
  AC3 真值基準:3 件在其掛載的 Legend In/Loop/Out 動畫**可見幀**逐幀 0 自交 / 0 翻面 / 0 退化。

用法:
  python3 tools/mesh_gen/weighted_deform_eval.py            # 全 AC → exit 0
  python3 tools/mesh_gen/weighted_deform_eval.py --json     # 詳細報告
  python3 tools/mesh_gen/weighted_deform_eval.py --selftest # 負對照:退化拓樸應被抓到
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import numpy as np

from weighted_skin import (Skeleton, load_weighted_mesh, apply_animation,
                           anim_duration, load_skeleton, visible_at)
from deform_eval import signed_area, tri_edges, _seg_cross

ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


# ---------- geometry ----------
def geom_check(verts, tris, setup_signs):
    flips = degen = 0
    for i, t in enumerate(tris):
        a = signed_area(verts, t)
        if abs(a) < 1e-6:
            degen += 1
        elif setup_signs is not None and (a > 0) != setup_signs[i]:
            flips += 1
    edges = tri_edges(tris)
    xs = 0
    for i in range(len(edges)):
        e1 = edges[i]
        for j in range(i + 1, len(edges)):
            e2 = edges[j]
            if e1[0] in e2 or e1[1] in e2:
                continue
            if _seg_cross(verts[e1[0]], verts[e1[1]], verts[e2[0]], verts[e2[1]]):
                xs += 1
    return xs, flips, degen


def edge_strain(verts, edges, rest_len):
    """回傳 (mean_abs, dispersion):相對 setup 的邊長應變分布。
    - mean_abs      = 平均絕對應變(整體變形幅度)。
    - dispersion    = p95(|strain|) − p50(|strain|) = **應變非均勻度**(穩健版)。
      關鍵:均勻縮放時每條邊應變相同 → dispersion≈0(非平滑度問題);
      **局部撕扯/取樣過疏**才會讓少數邊應變爆高 → dispersion 大。
      這才是「內部取樣密度服務變形平滑度」的可比對信號(取代被均勻縮放主導的 max 應變)。"""
    strains = []
    for k, (i, j) in enumerate(edges):
        L = math.hypot(verts[i][0] - verts[j][0], verts[i][1] - verts[j][1])
        r = rest_len[k]
        if r > 1e-6:
            strains.append(abs((L - r) / r))
    if not strains:
        return 0.0, 0.0
    strains = np.array(strains)
    disp = float(np.percentile(strains, 95) - np.percentile(strains, 50))
    return round(float(np.mean(strains)), 4), round(disp, 4)


# ---------- AC1: affine reproduction ----------
def _normalize_weights(m):
    """回傳權重和恰為 1 的 mesh 複本(隔離 FK 測試與藝術家 3~5 位小數捨入)。"""
    nm = dict(m)
    nb = []
    for entry in m["bones"]:
        s = sum(w for (_, _, _, w) in entry) or 1.0
        nb.append([(b, bx, by, w / s) for (b, bx, by, w) in entry])
    nm["bones"] = nb
    return nm


def ac1_affine_reproduction(sk, meshes, theta=37.0, tx=123.4, ty=-88.7):
    """對 root 骨施加剛體 T,驗蒙皮頂點 == T·(setup 蒙皮頂點)。
    權重先正規化為和=1,使殘差 = 純 FK 浮點誤差(隔離藝術家權重捨入)。"""
    skel = Skeleton(sk)
    max_err = 0.0
    for m0 in meshes:
        m = _normalize_weights(m0)
        skel.set_to_setup(); skel.update_world()
        base = skel.skin(m)
        # 施加剛體到 root(idx 0 假定為 root;用 name2idx 保險)
        ri = skel.name2idx["root"]
        skel.set_to_setup()
        skel.lrot[ri] += theta
        skel.lx[ri] += tx; skel.ly[ri] += ty
        skel.update_world()
        got = skel.skin(m)
        c, s = math.cos(math.radians(theta)), math.sin(math.radians(theta))
        exp = np.column_stack([
            c * base[:, 0] - s * base[:, 1] + tx,
            s * base[:, 0] + c * base[:, 1] + ty])
        err = float(np.max(np.abs(got - exp)))
        max_err = max(max_err, err)
    return max_err


def ac2_partition_of_unity(meshes):
    worst = 0.0
    for m in meshes:
        for entry in m["bones"]:
            worst = max(worst, abs(sum(w for (_, _, _, w) in entry) - 1.0))
    return worst


# ---------- AC3 + strain benchmark ----------
def benchmark_mesh(sk, slot, substeps=3):
    m = load_weighted_mesh(sk, slot)
    tris = m["triangles"]
    skel = Skeleton(sk)
    skel.set_to_setup(); skel.update_world()
    setup = skel.skin(m)
    setup_signs = [signed_area(setup, t) > 0 for t in tris]
    setup_area = sum(abs(signed_area(setup, t)) for t in tris)
    edges = tri_edges(tris)
    rest_len = [math.hypot(setup[i][0] - setup[j][0], setup[i][1] - setup[j][1])
                for (i, j) in edges]

    per_anim = {}
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    global_strain = 0.0; global_cv = 0.0; area_lo = 1.0; area_hi = 1.0
    for anim in sk["animations"]:
        dur = anim_duration(sk, anim)
        # 取樣:0..dur 均勻 substeps*keyframes 密度(至少 8 幀)
        nsamp = max(8, int(dur / 0.05) if dur > 0 else 8)
        times = [dur * k / (nsamp - 1) for k in range(nsamp)] if dur > 0 else [0.0]
        agg_xs = agg_fl = agg_dg = 0
        s_mean = s_p95 = 0.0
        n_vis = 0
        for t in times:
            # 只在該 attachment 實際可見(attachment==name 且 alpha>門檻)的幀評估變形品質;
            # 透明/未掛載幀不算「壞掉」(見 knowledge 誠實限制:光暈 In 前段 alpha=0)。
            if not visible_at(sk, anim, slot, slot, t):
                continue
            n_vis += 1
            apply_animation(skel, anim, t)
            v = skel.skin(m)
            xs, fl, dg = geom_check(v, tris, setup_signs)
            agg_xs = max(agg_xs, xs); agg_fl = max(agg_fl, fl); agg_dg = max(agg_dg, dg)
            sm, p95 = edge_strain(v, edges, rest_len)
            s_mean = max(s_mean, sm); s_p95 = max(s_p95, p95)
            area = sum(abs(signed_area(v, t2)) for t2 in tris)
            ar = area / setup_area if setup_area else 1.0
            area_lo = min(area_lo, ar); area_hi = max(area_hi, ar)
        per_anim[anim] = {
            "frames_visible": n_vis, "frames_total": len(times),
            "max_self_intersections": agg_xs,
            "max_triangle_flips": agg_fl,
            "max_degenerate": agg_dg,
            "max_edge_strain_mean": round(s_mean, 4),
            "max_strain_dispersion": round(s_p95, 4),
            "clean": agg_xs == 0 and agg_fl == 0 and agg_dg == 0,
        }
        worst["self_intersections"] = max(worst["self_intersections"], agg_xs)
        worst["triangle_flips"] = max(worst["triangle_flips"], agg_fl)
        worst["degenerate"] = max(worst["degenerate"], agg_dg)
        global_strain = max(global_strain, s_mean); global_cv = max(global_cv, s_p95)

    return {
        "slot": slot,
        "nverts": m["n"], "ntris": len(tris), "hull": m["hull"],
        "bones": sorted({b for e in m["bones"] for (b, *_ ) in e}),
        "worst_geom": worst,
        "all_clean": (worst["self_intersections"] == 0 and worst["triangle_flips"] == 0
                      and worst["degenerate"] == 0),
        "strain_signature": {
            "max_edge_strain_mean": round(global_strain, 4),
            "max_strain_dispersion": round(global_cv, 4),
            "area_ratio_range": [round(area_lo, 3), round(area_hi, 3)],
        },
        "per_anim": per_anim,
    }


def _hard_skin(m):
    """負對照:把混合權重改成硬綁(每頂點只綁最高權重骨,權重=1)。
    移除骨間平滑混合 → 關節處相鄰頂點被不同骨硬拉開,應變非均勻度暴增/幾何破裂。
    用來證明評估器有鑑別力(藝術家平滑混合 vs 退化硬綁)。"""
    nm = dict(m)
    nb = []
    for entry in m["bones"]:
        b, bx, by, _ = max(entry, key=lambda e: e[3])
        nb.append([(b, bx, by, 1.0)])
    nm["bones"] = nb
    return nm


def _selftest(sk):
    """負對照:對**關節articulation最強的光暈件**(綁到會大幅旋轉的 LEG5/LEG6)跑
    藝術家平滑混合 vs 硬綁 兩版。硬綁在關節處把相鄰頂點硬拉開 → 產生自交;
    藝術家混合則乾淨。證明評估器的幾何閘有鑑別力(非恆真)。"""
    slot = "機器人拆件/光暈"
    art = benchmark_mesh(sk, slot)
    # 硬綁版:替換 skin() 讀的 mesh。臨時 monkeypatch load 不便 → 直接複算。
    m = _hard_skin(load_weighted_mesh(sk, slot))
    tris = m["triangles"]
    skel = Skeleton(sk); skel.set_to_setup(); skel.update_world()
    setup = skel.skin(m)
    signs = [signed_area(setup, t) > 0 for t in tris]
    edges = tri_edges(tris)
    rest = [math.hypot(setup[i][0] - setup[j][0], setup[i][1] - setup[j][1]) for (i, j) in edges]
    worst_xs = worst_fl = 0; worst_disp = 0.0
    for anim in sk["animations"]:
        dur = anim_duration(sk, anim)
        times = [dur * k / 11 for k in range(12)] if dur > 0 else [0.0]
        for t in times:
            if not visible_at(sk, anim, slot, slot, t):
                continue
            apply_animation(skel, anim, t); v = skel.skin(m)
            xs, fl, _ = geom_check(v, tris, signs)
            _, disp = edge_strain(v, edges, rest)
            worst_xs = max(worst_xs, xs); worst_fl = max(worst_fl, fl)
            worst_disp = max(worst_disp, disp)
    art_disp = art["strain_signature"]["max_strain_dispersion"]
    hard_bad = worst_xs + worst_fl
    # 鑑別力:藝術家可見幀全乾淨,硬綁在關節破裂(自交/翻面) → 閘能區分好壞蒙皮
    discriminates = art["all_clean"] and hard_bad > 0
    out = {
        "negative_control": "hard-skin glow (single-bone weights on LEG5/LEG6 joint)",
        "artist": {"clean": art["all_clean"], "dispersion": art_disp},
        "hard_skin": {"self_intersections": worst_xs, "triangle_flips": worst_fl,
                      "dispersion": round(worst_disp, 4)},
        "discriminates": discriminates,
        "note": "藝術家可見幀全乾淨、硬綁在關節自交破裂 → 幾何閘能區分好壞蒙皮(非恆真)",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if discriminates else 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--json", action="store_true", help="印完整報告")
    ap.add_argument("--selftest", action="store_true", help="負對照(硬綁)鑑別力測試")
    a = ap.parse_args()
    sk = load_skeleton(a.skeleton)
    if a.selftest:
        _selftest(sk)
    meshes = [load_weighted_mesh(sk, s) for s in ROBOT_MESHES]

    ac1_err = ac1_affine_reproduction(sk, meshes)
    ac2_err = ac2_partition_of_unity(meshes)
    reports = [benchmark_mesh(sk, s) for s in ROBOT_MESHES]

    ac1_pass = ac1_err < 1e-6
    ac2_pass = ac2_err < 2e-4   # 藝術家權重 3~5 位小數捨入(實測 dev ~1e-5),此閘驗解析正確
    ac3_pass = all(r["all_clean"] for r in reports)

    out = {
        "AC1_affine_reproduction": {"max_err_px": ac1_err, "pass": ac1_pass,
                                    "note": "root 剛體 T → 所有蒙皮頂點恰被 T 映射(驗 FK+權重正規化)"},
        "AC2_partition_of_unity": {"max_dev": ac2_err, "pass": ac2_pass},
        "AC3_artist_meshes_clean": {"pass": ac3_pass,
                                    "note": "3 件在其掛載的 Legend In/Loop/Out 動畫可見幀逐幀 0 自交/0 翻面/0 退化"},
        "overall_pass": ac1_pass and ac2_pass and ac3_pass,
        "pieces": reports if a.json else [
            {"slot": r["slot"], "nverts": r["nverts"], "all_clean": r["all_clean"],
             "strain_signature": r["strain_signature"]} for r in reports],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["overall_pass"] else 1)


if __name__ == "__main__":
    main()
