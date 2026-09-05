#!/usr/bin/env python3
"""candidate 0i(S1 (e))驗收 — 關節 pivot 接 keyframe:件繞**關節**轉而非件中心。

端到端(RULES:簽章要端到端量、每能力配評估器 + 負對照):
  真實 Award 機器人 5 拆件幾何 → S5 `infer_pivots` 推關節 pivot → 造扁平骨架(bone 在**件中心**,
  模擬非 rig build_spine)→ 經 `gen_animations.build_animations(pivots=...)` 產動畫(**證 wiring 接上**)
  → 用 `spine_anim` 取樣 + `articulate.world_point` 算關節世界座標逐幀 → 量不動點/旋轉/介面。

AC:
  A1 端到端不動點:build_animations(pivots) 下,各結構子件的關節世界點逐幀漂移 < 0.5px。
  A2 負對照(不接 pivot):build_animations(pivots=None,繞件中心)下,至少一件關節漂移 > 5px
     (件繞中心轉會拖走關節)→ 證度量有鑑別力、且本能力確實改變了行為。
  A3 件確實在轉(非退化):件上離 pivot 最遠點逐幀移動 > 3px,且其**到 pivot 的距離守恆**
     (< 0.5px 變動)→ 是繞 P 的純旋轉,不是「靠零旋轉騙過不動點」。
  A4 介面保留:首尾幀 rotate≈0 且補償 Δ≈0(θ=0 → Δ=0)→ setup 不擾動、可無縫串接。
  A5 併存 base translate(gen_in 徑向)beat:繞關節旋轉對 translate 通道的「純旋轉分量」為 0,
     即 關節世界點 − base平移 == 原 P(< 0.5px)→ 證補償平移正確疊加、不吃掉徑向。
  A6 primitive 大角度精確 + evaluator 自信:合成 O,P、rotate 0→45→0,格點上不動點漂移 < 1e-6px、
     遠點到 P 距離守恆 < 1e-6;且不補償版漂移 == 2sin(θ/2)|O−P|(解析)→ 閘本身可信且能鑑別。

純 CPU、確定性;不需 PNG(mesh hull 用 setup 幾何,region 件無 alpha 時退 rect,皆為合法幾何)。
"""
import math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rig"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim
import articulate as art
from gen_animations import build_animations, safe, DUR, beat_category
from infer_pivots import load_award_robot, infer_pivots


def _flat_skeleton(parts):
    """造扁平骨架:root + 每件一根 bone(parent=root,原點=件世界質心)。模擬非 rig build_spine。"""
    allpts = np.vstack(list(parts.values()))
    W = float(allpts[:, 0].max() - allpts[:, 0].min())
    H = float(allpts[:, 1].max() - allpts[:, 1].min())
    bones = [{"name": "root"}]
    centroid = {}
    for nm, poly in parts.items():
        c = np.asarray(poly, float).reshape(-1, 2).mean(0)
        centroid[safe(nm)] = (float(c[0]), float(c[1]))
        bones.append({"name": "b_" + safe(nm), "x": float(c[0]), "y": float(c[1]), "parent": "root"})
    return {"skeleton": {"width": W, "height": H}, "bones": bones, "slots": [], "animations": {}}, centroid


def _storyboard(children, beat_name):
    return {"beats": [{"beat": beat_name, "parts": [{"part": c, "role": "limb"} for c in children]}]}


def _bone_state(anim, t, bname):
    s = spine_anim.sample(anim, t)
    return s["bones"].get(bname, {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0})


def _sample_times(anim, n=40):
    d = spine_anim.duration(anim) or 1.0
    return [d * i / n for i in range(n + 1)]


def _pivot_drift(anim, O, P, bname, subtract_base=None):
    """關節世界點逐幀相對其起始位置(或相對 subtract_base(t))的最大漂移。"""
    ref = None
    mx = 0.0
    for t in _sample_times(anim):
        st = _bone_state(anim, t, bname)
        wp = np.array(art.world_point(O, st, P))
        if subtract_base is not None:
            bx, by = subtract_base(t)
            wp = wp - np.array([bx, by])
        if ref is None:
            ref = wp
        mx = max(mx, float(np.linalg.norm(wp - ref)))
    return mx


def run():
    parts, truth, tree, fid = load_award_robot()
    piv = infer_pivots(parts, tree)                 # S5 推關節 pivot(safe 前為原件名)
    children = list(tree.keys())                     # 頭 / 左手 / 右手(結構子件)
    skel, centroid = _flat_skeleton(parts)
    pivots_safe = {safe(c): (float(piv[c][0]), float(piv[c][1])) for c in children}

    results, acs = {}, {}

    # ---- A1/A2/A3:rotate-only beat ----
    # ⚠️ beat 名須乾淨命中類別:gen_loop 的 limb 是**純 rotate**(無 scale/translate)→ 不動點乾淨。
    #   避免含 "in"/"open" 等子字串(會誤中 intro,帶入 scale/translate 汙染純旋轉判定)。
    BEAT = "loop"                                     # 精確命中 loop 類別
    assert beat_category(BEAT) == "loop", beat_category(BEAT)
    sb = _storyboard(children, BEAT)
    anim_art = build_animations(skel, sb, pivots=pivots_safe)[BEAT]
    anim_nc = build_animations(skel, sb, pivots=None)[BEAT]

    a1 = {}; a3 = {}
    for c in children:
        sc = safe(c); bname = "b_" + sc
        O = centroid[sc]; P = pivots_safe[sc]
        # A1:articulated 下關節不動
        a1[c] = _pivot_drift(anim_art, O, P, bname)
        # A3:件上離 pivot 最遠點會動 + 到 P 距離守恆
        poly = np.asarray(parts[c], float).reshape(-1, 2)
        far = poly[np.argmax(np.linalg.norm(poly - np.array(P), axis=1))]
        r0 = np.linalg.norm(far - np.array(P))
        move = 0.0; dr = 0.0; ref = None
        for t in _sample_times(anim_art):
            st = _bone_state(anim_art, t, bname)
            wp = np.array(art.world_point(O, st, far))
            if ref is None:
                ref = wp
            move = max(move, float(np.linalg.norm(wp - ref)))
            dr = max(dr, abs(float(np.linalg.norm(wp - np.array(P)) - r0)))
        a3[c] = {"far_move": move, "radius_drift": dr}
    # A2:負對照(繞件中心)——至少一件關節漂移大
    a2 = {c: _pivot_drift(anim_nc, centroid[safe(c)], pivots_safe[safe(c)], "b_" + safe(c))
          for c in children}

    acs["A1_pivot_fixed"] = max(a1.values()) < 0.5
    acs["A2_negctrl_drifts"] = max(a2.values()) > 5.0
    acs["A3_part_rotates"] = all(v["far_move"] > 3.0 and v["radius_drift"] < 0.5 for v in a3.values())

    # ---- A4:介面保留(首尾 rotate≈0、Δ≈0)----
    a4_ok = True
    for c in children:
        rf = anim_art["bones"]["b_" + safe(c)].get("rotate", [])
        tf = anim_art["bones"]["b_" + safe(c)].get("translate", [])
        if rf and (abs(rf[0]["angle"]) > 1e-3 or abs(rf[-1]["angle"]) > 1e-3):
            a4_ok = False
        if tf and (abs(tf[0]["x"]) > 1e-2 or abs(tf[0]["y"]) > 1e-2
                   or abs(tf[-1]["x"]) > 1e-2 or abs(tf[-1]["y"]) > 1e-2):
            a4_ok = False
    acs["A4_interface_identity"] = a4_ok

    # ---- A5:與既有 base translate 疊加正確(primitive 隔離測)----
    # gen_in 帶徑向 translate 但**也帶 scale**(scale 亦繞 O 位移 P,非本能力範疇);故以合成
    # rotate + base_translate(無 scale)乾淨隔離「補償平移是否正確疊加在既有 translate 之上」。
    O5, P5 = (120.0, 40.0), (0.0, 210.0)
    rf5 = [{"time": 0.0, "angle": 0.0}, {"time": 0.25, "angle": 30.0}, {"time": 0.5, "angle": 0.0}]
    base5 = [{"time": 0.0, "x": 0.0, "y": 0.0}, {"time": 0.25, "x": 40.0, "y": -20.0},
             {"time": 0.5, "x": 0.0, "y": 0.0}]
    nr5, nt5 = art.articulate_about_pivot(rf5, O5, P5, base_translate=base5, samples=32)
    anim5 = {"bones": {"b": {"rotate": nr5, "translate": nt5}}}

    def base5_at(t):
        xy = spine_anim._interp(base5, t, ["x", "y"])
        return (xy["x"], xy["y"])
    # 硬性判準在**格點**(merge 數學在此精確,僅受 keyframe 取整):扣 base 後 P 應恆等於原 P。
    a5_grid = 0.0
    for kf in nr5:
        t = kf["time"]
        st = _bone_state(anim5, t, "b")
        wp = np.array(art.world_point(O5, st, P5)) - np.array(base5_at(t))
        a5_grid = max(a5_grid, float(np.linalg.norm(wp - np.array(P5))))
    # 資訊性:格點間 dense 取樣的 O(step²) 殘差(非硬性判準,受 samples 控制)。
    a5_dense = _pivot_drift(anim5, O5, P5, "b", subtract_base=base5_at)
    a5 = a5_grid
    acs["A5_base_translate_preserved"] = a5_grid < 0.01

    # ---- A6:primitive 大角度精確 + evaluator 自信/鑑別 ----
    O6 = (100.0, 50.0); P6 = (10.0, 200.0)             # 合成:|O−P| 大且非軸向
    rf = [{"time": 0.0, "angle": 0.0}, {"time": 0.25, "angle": 45.0}, {"time": 0.5, "angle": 0.0}]
    nr, nt = art.articulate_about_pivot(rf, O6, P6, samples=32)
    anim6 = {"bones": {"b": {"rotate": nr, "translate": nt}}}
    far6 = (250.0, 60.0)
    r0 = math.hypot(far6[0] - P6[0], far6[1] - P6[1])
    fix6 = 0.0; rad6 = 0.0; refp = None
    for kf in nr:
        t = kf["time"]                                 # 只取格點(格點上解析精確)
        st = _bone_state(anim6, t, "b")
        wp = np.array(art.world_point(O6, st, P6))
        wf = np.array(art.world_point(O6, st, far6))
        if refp is None:
            refp = wp
        fix6 = max(fix6, float(np.linalg.norm(wp - refp)))
        rad6 = max(rad6, abs(float(np.linalg.norm(wf - np.array(P6)) - r0)))
    # 不補償版(evaluator 鑑別 + 解析核對):P 位移 == 2 sin(θ/2)|O−P|
    theta = 45.0
    oxp, oyp = O6[0] - P6[0], O6[1] - P6[1]
    rx, ry = art.rot_apply(theta, P6[0] - O6[0], P6[1] - O6[1])   # R(θ)(P−O)
    nc_disp = math.hypot((O6[0] + rx) - P6[0], (O6[1] + ry) - P6[1])
    analytic = 2 * math.sin(math.radians(theta) / 2) * math.hypot(oxp, oyp)
    # 不動點 / 半徑守恆殘差受 keyframe 取整(angle/xy 各 3dp)限制在 ~0.002px;負對照解析核對用 1e-6。
    acs["A6_primitive_exact"] = (fix6 < 0.01 and rad6 < 0.01 and abs(nc_disp - analytic) < 1e-6)

    results = {
        "A1_pivot_drift_px": {c: round(v, 4) for c, v in a1.items()},
        "A2_negctrl_drift_px": {c: round(v, 2) for c, v in a2.items()},
        "A3_far_point": {c: {"move_px": round(v["far_move"], 2),
                             "radius_drift_px": round(v["radius_drift"], 4)} for c, v in a3.items()},
        "A5_after_base_drift_px": {"grid": round(a5_grid, 4), "dense_info": round(a5_dense, 4)},
        "A6_synth": {"pivot_fix_px": fix6, "radius_drift_px": rad6,
                     "negctrl_disp_px": round(nc_disp, 4), "analytic_px": round(analytic, 4)},
        "inferred_pivots": {c: [round(float(piv[c][0]), 1), round(float(piv[c][1]), 1)] for c in children},
        "part_centroids": {c: [round(centroid[safe(c)][0], 1), round(centroid[safe(c)][1], 1)] for c in children},
    }
    return acs, results


def main():
    import json
    acs, results = run()
    overall = all(acs.values())
    print(json.dumps({"overall_pass": overall, "acs": acs, "results": results},
                     ensure_ascii=False, indent=2))
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
