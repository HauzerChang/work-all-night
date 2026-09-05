#!/usr/bin/env python3
"""candidate 0i 延伸(G-3)驗收 — 「件繞關節 pivot **縮放**」keyframe 生成閘。

0i 讓件繞關節 pivot **轉**;本閘驗證把補償推廣到含 `scale` 的仿射 M=R·S 後,件能繞關節 pivot
**縮放(squash/stretch about joint)**——手臂從肩伸長、而非從自身中心脹縮。

真值來源同 0i:真實 Award 機器人左手件世界輪廓 + `infer_pivots` 推得接觸縫肩 pivot(|O−P|≈117px)。
以**純 Python** 模擬「bone(root 子、setup 旋轉0/scale1)加 rotate θ(t)+scale s(t)+translate Δ(t)」
的世界變換(M=R·S,Spine TRS 序),在**密集測試網格**逐點量測(不靠肉眼、不需瀏覽器)。

AC(客觀、可量測):
  AC1 不動點      : 純 scale 補償版下 pivot 附著點世界座標 == P(幀間最大殘差 < TOL_FIX)。
  AC2 負對照      : **不補償**(繞件中心 O 縮放)時 pivot 明顯位移(峰=|1−s|·|O−P|,≥ MIN_NEG px)。
  AC3 件真的在縮放: 補償版下,離 P 最遠點到 P 的距離逐幀 == s(t)·(setup 距離)(峰值相對變化 ≥ MIN_MOVE)。
  AC4 identity 介面: s=1(且 θ=0)幀 Δ=0(< EPS)→ setup/端點介面保持 identity(0d 無縫不被破壞)。
  AC5 相似(等比) : 純均勻 scale 約 pivot 為**相似變換**——∀件點 |world(x)−P| == s(t)·|x−P|
                    (逐幀逐點絕對偏差 < TOL_SIM)→ 真的繞 P 等比縮放(scale 版的「等距」類比)。
  AC6 旋轉+縮放併 : rotate θ(t) 與 scale s(t) **同時**作用時 pivot 仍不動(< TOL_FIX)→ 證 M=R·S 組合正確。
  AC7 端到端整合  : 經真實 `gen_animations.build_animations` 產 pulse 節拍(limb scale+rotate,無 translate)→
                    `apply_pivots(include_scale=True)` → (a)通道有限;(b)pulse 端點相等(無縫);
                    (c)生成節拍上 pivot 不動;(d)內建負對照=未套用版 pivot 會動。
"""
import os, sys, math
import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "rig"))
sys.path.insert(0, os.path.join(HERE, "..", "mesh_gen"))

import spine_anim
import pivot_rotation as pr
import infer_pivots as ip

TOL_FIX = 0.5      # px,pivot 不動點幀間最大殘差上限
TOL_SIM = 0.5      # px,相似變換 |world(x)−P|=s|x−P| 的逐點絕對偏差上限
MIN_NEG = 10.0     # px,負對照(繞件中心縮放)pivot 位移下限
MIN_MOVE = 0.10    # 相對:件最遠點到 P 距離的峰值相對變化下限(證有縮放)
EPS = 1e-6
NEG_RATIO = 20.0   # AC2/AC1 位移比下限


def _R(deg):
    r = math.radians(deg); c, s = math.cos(r), math.sin(r)
    return np.array([[c, -s], [s, c]])


def _M(deg, sx, sy):
    """M = R(θ)·diag(sx,sy)(Spine TRS 序)。"""
    return _R(deg) @ np.diag([sx, sy])


def _world(local, O, rot_frames, sc_frames, tr_frames, t):
    """bone(root 子、setup 旋轉0/scale1)加 rotate/scale/translate 對局部點 local 的世界座標。"""
    ang = spine_anim._interp(rot_frames, t, ["angle"])["angle"] if rot_frames else 0.0
    if sc_frames:
        sd = spine_anim._interp(sc_frames, t, ["x", "y"]); sx, sy = sd["x"], sd["y"]
    else:
        sx = sy = 1.0
    if tr_frames:
        td = spine_anim._interp(tr_frames, t, ["x", "y"]); tx, ty = td["x"], td["y"]
    else:
        tx = ty = 0.0
    O = np.asarray(O, float)
    return (O + np.array([tx, ty])) + _M(ang, sx, sy) @ np.asarray(local, float)


def _dense_ts(frames, n=400):
    t0, t1 = frames[0]["time"], frames[-1]["time"]
    return [t0 + (t1 - t0) * i / n for i in range(n + 1)]


def _scale_swing(peak=1.6, bezier=False):
    """一條 pure-scale 縮放 timeline(首尾 s=1 identity,峰 s=peak)。"""
    fr = [{"time": 0.0, "x": 1.0, "y": 1.0},
          {"time": 0.25, "x": peak, "y": peak},
          {"time": 0.5, "x": 1.0, "y": 1.0}]
    if bezier:
        for f in fr[:-1]:
            f.update({"curve": 0.25, "c2": 0.0, "c3": 0.25, "c4": 1.0})
    return fr


def _rot_swing(peak=24.0):
    return [{"time": 0.0, "angle": 0.0}, {"time": 0.25, "angle": peak},
            {"time": 0.5, "angle": 0.0}]


def _load_real():
    """真實 Award 左手件世界輪廓 + 推得肩 pivot。回傳 (pts Nx2, O 件中心, P pivot, fid)。"""
    parts, truth, tree, fid = ip.load_award_robot(use_alpha=True)
    inf = ip.infer_pivots(parts, tree)
    slot = "機器人拆件/左手"
    pts = np.asarray(parts[slot], float)
    O = pts.mean(axis=0)                 # 非 rig 下 bone 落件中心
    P = np.asarray(inf[slot], float)     # 接觸縫肩 pivot
    return pts, O, P, fid.get(slot, "?")


def _sample_s(sc_frames, t):
    d = spine_anim._interp(sc_frames, t, ["x", "y"]); return d["x"]


def main():
    results = {}
    print("=" * 70)
    print("candidate 0i 延伸(G-3)— 件繞關節 pivot 縮放(scale-about-pivot)閘")
    print("=" * 70)

    pts, O, P, fid = _load_real()
    armlen = float(np.linalg.norm(O - P))
    print(f"\n真值:左手 [{fid}] verts={len(pts)}  件中心 O=({O[0]:.1f},{O[1]:.1f})  "
          f"肩 pivot P=({P[0]:.1f},{P[1]:.1f})  |O-P|={armlen:.1f}px")

    # ---- AC1–AC5:純 scale swing(峰 1.6)----
    sc = _scale_swing(peak=1.6, bezier=False)
    _, sc_d, tr_d = pr.pivot_channels_srt(None, sc, tuple(O), tuple(P))
    ell_P = P - O
    ts = _dense_ts(sc)
    # AC1 補償版 pivot 殘差
    fix = max(np.linalg.norm(_world(ell_P, O, None, sc_d, tr_d, t) - P) for t in ts)
    # AC2 負對照:不補償(繞 O 縮放)pivot 位移
    neg = max(np.linalg.norm(_world(ell_P, O, None, sc, None, t) - P) for t in ts)
    # AC3 件最遠點:到 P 距離應 == s(t)·d0;量峰值相對變化
    far_i = int(np.argmax(np.linalg.norm(pts - P, axis=1)))
    far_local = pts[far_i] - O
    d0_far = np.linalg.norm(pts[far_i] - P)
    rel_change = 0.0
    for t in ts:
        w = _world(far_local, O, None, sc_d, tr_d, t)
        rel_change = max(rel_change, abs(np.linalg.norm(w - P) - d0_far) / d0_far)
    # AC4 identity:s=1 端點 Δ
    d_t0 = math.hypot(tr_d[0]["x"], tr_d[0]["y"])
    d_tN = math.hypot(tr_d[-1]["x"], tr_d[-1]["y"])
    # AC5 相似(等比):∀點 |world(x)−P| == s(t)·|x−P|,逐點逐幀絕對偏差
    d0 = np.linalg.norm(pts - P, axis=1)
    worst_sim = 0.0
    for t in ts[::7]:
        s_t = _sample_s(sc_d, t)
        for k in range(len(pts)):
            w = _world(pts[k] - O, O, None, sc_d, tr_d, t)
            worst_sim = max(worst_sim, abs(np.linalg.norm(w - P) - s_t * d0[k]))
    print(f"\n[pure scale swing 1.6]  dense keys={len(sc_d)}")
    print(f"  AC1 pivot 不動點殘差 max = {fix:.4f}px   (< {TOL_FIX})")
    print(f"  AC2 負對照(繞件中心縮放)= {neg:.2f}px    (>> AC1, ≥ {MIN_NEG})")
    print(f"  AC3 件最遠點到P 相對變化  = {rel_change:.3f}   (≥ {MIN_MOVE})")
    print(f"  AC4 identity Δ@t0/tN      = {d_t0:.2e}/{d_tN:.2e}px  (< {EPS})")
    print(f"  AC5 相似(|w-P|=s|x-P|偏差)= {worst_sim:.4f}px    (< {TOL_SIM})")
    results.update(
        AC1_fixed_point=fix < TOL_FIX,
        AC2_negctrl=(neg >= MIN_NEG) and (neg > fix * NEG_RATIO),
        AC3_scales=rel_change >= MIN_MOVE,
        AC4_identity=d_t0 < EPS and d_tN < EPS,
        AC5_similarity=worst_sim < TOL_SIM,
    )

    # ---- AC6:rotate + scale 同時作用,pivot 仍不動 ----
    rot = _rot_swing(24.0); sc2 = _scale_swing(peak=1.6, bezier=False)
    rot_d6, sc_d6, tr_d6 = pr.pivot_channels_srt(rot, sc2, tuple(O), tuple(P))
    ts6 = _dense_ts(rot_d6)
    fix6 = max(np.linalg.norm(_world(ell_P, O, rot_d6, sc_d6, tr_d6, t) - P) for t in ts6)
    # 負對照:同 rotate+scale 但不補償
    neg6 = max(np.linalg.norm(_world(ell_P, O, rot, sc2, None, t) - P) for t in ts6)
    print(f"\n[rotate 24° + scale 1.6 併]  AC6 pivot 殘差 max = {fix6:.4f}px  (< {TOL_FIX}) "
          f"| 負對照 {neg6:.1f}px")
    results["AC6_rot_scale_combo"] = (fix6 < TOL_FIX) and (neg6 > fix6 * NEG_RATIO)

    # ---- AC7:端到端經真實 build_animations(pulse:limb scale+rotate,無 translate)----
    from gen_animations import build_animations
    sk = {"skeleton": {"width": 700, "height": 700},
          "bones": [{"name": "root"},
                    {"name": "b_身體", "parent": "root", "x": 350, "y": 350},
                    {"name": "b_左手", "parent": "root", "x": 250, "y": 300}],
          "slots": [], "skins": {"default": {}}, "animations": {}}
    story = {"beats": [{"beat": "Win", "parts": [
        {"part": "身體", "role": "body"}, {"part": "左手", "role": "limb"}]}]}
    anims = build_animations(sk, story)
    pulse = anims["Win"]
    assert "scale" in pulse["bones"]["b_左手"], "pulse limb 應有 scale 通道"
    bone_origin = {b["name"]: (b.get("x", 0.0), b.get("y", 0.0))
                   for b in sk["bones"] if b["name"] != "root"}
    pivots = {"b_左手": (350.0, 350.0)}   # 肩(合成)
    O_lh = np.array(bone_origin["b_左手"]); P_lh = np.array(pivots["b_左手"])
    ell = P_lh - O_lh
    # 未套用版(負對照):raw scale+rotate 繞件中心 → pivot 會動
    raw_rot = [dict(f) for f in pulse["bones"]["b_左手"]["rotate"]]
    raw_sc = [dict(f) for f in pulse["bones"]["b_左手"]["scale"]]
    conv = pr.apply_pivots(pulse, bone_origin, pivots, include_scale=True)
    print(f"\n[端到端 build_animations pulse 'Win']  converted bones = {conv}")
    finite = spine_anim.all_finite(pulse)
    # (b) 無縫:轉換後端點相等(rotate/scale/translate)
    seamless = True
    lh = pulse["bones"]["b_左手"]
    for ch, keys in (("rotate", ["angle"]), ("scale", ["x", "y"]), ("translate", ["x", "y"])):
        fr = lh.get(ch)
        if not fr:
            continue
        for kk in keys:
            seamless &= abs(fr[0][kk] - fr[-1][kk]) < 1e-6
    # (c) 生成節拍上 pivot 不動
    rr = lh.get("rotate"); ss = lh.get("scale"); tt = lh.get("translate")
    tsx = _dense_ts(tt)
    fix_e = max(np.linalg.norm(_world(ell, O_lh, rr, ss, tt, t) - P_lh) for t in tsx)
    # (d) 內建負對照:未套用(繞件中心 scale+rotate)pivot 位移
    neg_e = max(np.linalg.norm(_world(ell, O_lh, raw_rot, raw_sc, None, t) - P_lh) for t in tsx)
    print(f"  (a) finite/mono increasing = {finite}")
    print(f"  (b) pulse 端點相等(無縫)  = {seamless}")
    print(f"  (c) 生成節拍 pivot 殘差     = {fix_e:.4f}px  (< {TOL_FIX})")
    print(f"  (d) 負對照未套用位移        = {neg_e:.2f}px   (>> (c))")
    results["AC7_end2end"] = finite and seamless and (fix_e < TOL_FIX) and \
        (neg_e > fix_e * NEG_RATIO) and (neg_e >= 1.0)

    print("\n" + "-" * 70)
    for k, v in results.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    overall = all(results.values())
    print("-" * 70)
    print("OVERALL:", "PASS ✅" if overall else "FAIL ❌")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
