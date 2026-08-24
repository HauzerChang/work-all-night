#!/usr/bin/env python3
"""S3 — weighted mesh 骨骼驅動變形評估器(補上 deform_eval 的缺口)。

deform_eval.py 只處理 **unweighted** 逐頂點 deform;本檔處理 **weighted mesh**:
用 spine_skeleton 的骨骼 FK + 蒙皮,把真實動畫的骨骼 pose 轉移到 mesh,量化:
  - self_intersections / triangle_flips / degenerate(拓樸壞損)
  - smoothness(相鄰三角法向/面積梯度的平滑度 → 骨綁權重平滑度指標)
  - hull bbox / area_ratio(變形幅度)

**可信度錨(calibration anchor)**:Award 機器人 3 件是**生產級美術 weighted mesh**,
在其真實動畫(Award_Legend_In / _Loop)下**必然乾淨**(0 自交 / 0 翻面)。
若本評估器對美術 mesh 判 fail → 是 FK / 曲線內插錯,不是 mesh 壞。
`_checker_validated` 即此錨。另附負對照(擾動權重 → 必須抓到壞損)驗鑑別力。
"""
import json, math, sys
import numpy as np

from deform_eval import signed_area, eval_pose
import spine_skeleton as ss

ROBOT_PARTS = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]
# 這 3 件的驅動骨在這些動畫有 keyframe(其餘動畫不驅動它們)
DRIVING_ANIMS = ["Award_Legend_In", "Award_Legend_Loop"]


def anim_duration(data, anim):
    d = 0.0
    a = data["animations"][anim]
    for section in ("bones", "slots", "deform"):
        for _, chans in a.get(section, {}).items():
            def walk(x):
                nonlocal d
                if isinstance(x, list):
                    for f in x:
                        if isinstance(f, dict) and "time" in f:
                            d = max(d, f["time"])
                        else:
                            walk(f)
                elif isinstance(x, dict):
                    for v in x.values():
                        walk(v)
            walk(chans)
    return d


def _setup_alpha(data, slot):
    for s in data["slots"]:
        if s["name"] == slot:
            c = s.get("color", "FFFFFFFF")
            return int(c[6:8], 16) / 255.0
    return 1.0


def slot_visible(data, anim, slot, attname, t, alpha_eps=0.02):
    """gating(雷點 #2/#3):某幀該 attachment 是否**實際被渲染**。
    需 (a) slot 當前 attachment == attname,且 (b) slot 顏色 alpha > eps。
    回傳 (visible: bool, alpha: float)。"""
    stl = data["animations"][anim].get("slots", {}).get(slot, {})
    # attachment gating
    att_active = True
    if "attachment" in stl:
        frames = stl["attachment"]
        cur = None
        for f in frames:
            if f.get("time", 0.0) <= t + 1e-9:
                cur = f.get("name")
            else:
                break
        att_active = (cur == attname)
    # alpha gating(以 color/rgba timeline 內插 alpha;curve 用緊湊 bezier / stepped)
    alpha = _setup_alpha(data, slot)
    if "color" in stl:
        frames = stl["color"]
        avals = [{"time": f.get("time", 0.0), "a": int(f["color"][6:8], 16) / 255.0,
                  "curve": f.get("curve"), "c2": f.get("c2"), "c3": f.get("c3"),
                  "c4": f.get("c4")} for f in frames]
        alpha = ss._interp(avals, t, ["a"], [alpha])["a"]
    return (att_active and alpha > alpha_eps), alpha


def tri_smoothness(verts, tris):
    """局部彎折度:每個內部共邊,兩三角單位法向(2D 用 signed-area 正負 + 邊長比)之差。
    這裡用可機讀替代:相鄰三角面積比的變異係數(權重平滑 → 面積漸變 → 低 CV)。"""
    areas = np.array([abs(signed_area(verts, t)) for t in tris])
    areas = areas[areas > 1e-9]
    if len(areas) < 2:
        return 0.0
    return float(areas.std() / (areas.mean() + 1e-9))


def load_part(data, slot):
    att, name = ss.get_attachment(data, slot)
    vw = ss.decode_weighted(att["vertices"])
    tris = np.array(att["triangles"], dtype=np.int32).reshape(-1, 3)
    return vw, tris, att["hull"], name


def eval_part(sk, slot, attname, vw, tris, anims, substeps=6):
    bone_names = sk.order
    W0 = sk.world_transforms()
    setup = ss.skin_vertices(vw, bone_names, W0)
    setup_signs = [signed_area(setup, t) > 0 for t in tris]
    setup_area = sum(abs(signed_area(setup, t)) for t in tris)
    per_anim = {}
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    for anim in anims:
        dur = anim_duration(sk.data, anim)
        if dur <= 0:
            continue
        times = [dur * i / (substeps * 4) for i in range(substeps * 4 + 1)]
        res = []
        for t in times:
            vis, alpha = slot_visible(sk.data, anim, slot, attname, t)
            W = sk.world_transforms(anim, t)
            v = ss.skin_vertices(vw, bone_names, W)
            r = eval_pose(v, tris, setup_signs, setup_area)
            r["smoothness_cv"] = round(tri_smoothness(v, tris), 3)
            r["visible"] = vis
            r["t"] = round(t, 3)
            res.append(r)
        vis_res = [r for r in res if r["visible"]]
        # 只在「實際被渲染」的幀上判定乾淨(雷點 #2/#3);全隱藏則退回全幀
        judge = vis_res if vis_res else res
        agg = {
            "frames": len(res),
            "visible_frames": len(vis_res),
            "max_self_intersections": max(r["self_intersections"] for r in judge),
            "max_triangle_flips": max(r["triangle_flips"] for r in judge),
            "max_degenerate": max(r["degenerate"] for r in judge),
            "area_ratio_range": [min(r["area_ratio"] for r in judge), max(r["area_ratio"] for r in judge)],
            "smoothness_cv_range": [min(r["smoothness_cv"] for r in judge),
                                    max(r["smoothness_cv"] for r in judge)],
            "all_clean": all(r["self_intersections"] == 0 and r["triangle_flips"] == 0
                             and r["degenerate"] == 0 for r in judge),
        }
        per_anim[anim] = agg
        for k in worst:
            worst[k] = max(worst[k], agg["max_" + k])
    return per_anim, worst, setup


def benchmark_artist(path="assets/Award.json"):
    sk = ss.load(path)
    report = {}
    worst_all = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    for slot in ROBOT_PARTS:
        vw, tris, hull, name = load_part(sk.data, slot)
        per_anim, worst, setup = eval_part(sk, slot, name, vw, tris, DRIVING_ANIMS)
        report[slot] = {"nv": len(vw), "hull": hull, "tris": len(tris), "anims": per_anim}
        for k in worst_all:
            worst_all[k] = max(worst_all[k], worst[k])
    report["_worst_across_all"] = worst_all
    report["_checker_validated"] = all(v == 0 for v in worst_all.values())
    return report


def negative_control(path="assets/Award.json"):
    """把身體件 30% 頂點的權重整根換成一根遠端骨(4_LEG9)→ 應產生翻面/自交。
    驗評估器有鑑別力(而非全 pass 空過)。"""
    sk = ss.load(path)
    slot = "機器人拆件/身體"
    vw, tris, hull, name = load_part(sk.data, slot)
    bad_bi = sk.order.index("4_LEG9")  # 身體原本不受此骨驅動
    # 用固定 stride 破壞(避免 Math.random;可重現)
    corrupt = vw
    corrupt = [list(e) for e in vw]
    for i in range(0, len(corrupt), 3):  # ~1/3 頂點
        bx, by = corrupt[i][0][1], corrupt[i][0][2]
        corrupt[i] = [(bad_bi, bx, by, 1.0)]
    per_anim, worst, setup = eval_part(sk, slot, name, corrupt, tris, DRIVING_ANIMS)
    detected = any(v > 0 for v in worst.values())
    return {"worst": worst, "detected_breakage": detected, "per_anim": per_anim}


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "artist"
    if mode == "neg":
        print(json.dumps(negative_control(), ensure_ascii=False, indent=2))
    else:
        rep = benchmark_artist()
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        print("\n_checker_validated (artist mesh clean under real anims):",
              rep["_checker_validated"])
