#!/usr/bin/env python3
"""candidate 0i 驗收 — 「件繞關節 pivot 轉」keyframe 生成閘(把 S5 接觸縫 pivot 接進 S1 keyframe)。

真值來源 = 真實 Award 機器人拆件世界幾何 + `infer_pivots` 推得的接觸縫 pivot(左手繞肩)。
以**純 Python** 模擬「bone(root 子、setup 旋轉0)加 rotate θ(t) + translate Δ(t)」對附著點的世界變換,
在**密集測試網格**上逐點量測(不靠肉眼、不需瀏覽器)。

AC(客觀、可量測):
  AC1 不動點      : 補償版下 pivot 的附著點世界座標 == P(幀間最大殘差 < TOL_FIX)。
  AC2 負對照      : **不補償**(繞件中心 O)時 pivot 明顯位移(最大 >> AC1,且 ≥ MIN_NEG px)。
  AC3 件真的在轉  : 離 P 最遠的件點確有位移(≥ MIN_MOVE px)→ 沒有把整件凍住。
  AC4 identity 介面: θ=0 幀 Δ=0(< EPS)→ setup/loop 端點/In-Out 介面保持 identity(0d 無縫不被破壞)。
  AC5 剛性(等距) : 補償版下**所有件點**到 P 的距離逐幀不變(相對偏差 < TOL_RIGID)→ 真繞 P 旋轉。
  AC6 端到端整合  : 經真實 `gen_animations.build_animations` 產 loop(limb rotate)→ `apply_pivots` →
                    (a) 通道有限、時間嚴格遞增;(b) loop 端點相等(無縫保持);
                    (c) 生成 loop 上 pivot 亦不動;(d) 內建負對照=未套用版 pivot 會動。
  AC7 曲線容忍    : rotate 帶緊湊 bezier 緩動時 AC1 仍成立(加密重取樣正確處理 curve)。
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
TOL_RIGID = 0.5    # px,到 P 距離絕對偏差上限(等距 → 幀間殘差量級)
MIN_NEG = 10.0     # px,負對照(繞件中心)pivot 位移下限
MIN_MOVE = 8.0     # px,件最遠點位移下限(證有轉)
EPS = 1e-6
NEG_RATIO = 20.0   # AC2/AC1 位移比下限


def _R(deg):
    r = math.radians(deg); c, s = math.cos(r), math.sin(r)
    return np.array([[c, -s], [s, c]])


def _world_of(local, O, rot_frames, tr_frames, t):
    """bone(root 子、setup 旋轉0、scale1)加 rotate/translate 對局部點 local 的世界座標。"""
    ang = spine_anim._interp(rot_frames, t, ["angle"])["angle"]
    xy = spine_anim._interp(tr_frames, t, ["x", "y"]) if tr_frames else {"x": 0.0, "y": 0.0}
    O = np.asarray(O, float)
    return (O + np.array([xy["x"], xy["y"]])) + _R(ang) @ np.asarray(local, float)


def _dense_ts(rot_frames, n=400):
    t0, t1 = rot_frames[0]["time"], rot_frames[-1]["time"]
    return [t0 + (t1 - t0) * i / n for i in range(n + 1)]


def _swing(bezier=False):
    """一條 pure-rotation 擺動 timeline(首尾 identity,峰 ±24°)。bezier=True 加緊湊緩動鍵。"""
    fr = [{"time": 0.0, "angle": 0.0}, {"time": 0.25, "angle": 24.0}, {"time": 0.5, "angle": 0.0}]
    if bezier:
        for f in fr[:-1]:
            f.update({"curve": 0.25, "c2": 0.0, "c3": 0.25, "c4": 1.0})
    return fr


def _load_real():
    """真實 Award 左手件世界輪廓 + 推得肩 pivot。回傳 (pts Nx2, O 件中心, P pivot, fid)。"""
    parts, truth, tree, fid = ip.load_award_robot(use_alpha=True)
    inf = ip.infer_pivots(parts, tree)
    slot = "機器人拆件/左手"
    pts = np.asarray(parts[slot], float)
    O = pts.mean(axis=0)                 # 非 rig 下 bone 落件中心
    P = np.asarray(inf[slot], float)     # 接觸縫肩 pivot
    return pts, O, P, fid.get(slot, "?")


def _pivot_metrics(pts, O, P, rot_frames):
    """回傳補償版/負對照的量測。"""
    rot_d, tr_d = pr.pivot_channels(rot_frames, tuple(O), tuple(P))
    ell_P = P - O                        # pivot 附著局部點
    ts = _dense_ts(rot_frames)
    # AC1 補償版 pivot 殘差
    fix = max(np.linalg.norm(_world_of(ell_P, O, rot_d, tr_d, t) - P) for t in ts)
    # AC2 負對照:不補償(繞 O)pivot 位移
    neg = max(np.linalg.norm(_world_of(ell_P, O, rot_frames, None, t) - P) for t in ts)
    # AC3 件最遠點位移(補償版,相對 setup)
    far_i = int(np.argmax(np.linalg.norm(pts - P, axis=1)))
    far_local = pts[far_i] - O
    far_setup = pts[far_i]
    move = max(np.linalg.norm(_world_of(far_local, O, rot_d, tr_d, t) - far_setup) for t in ts)
    # AC5 剛性(等距):所有件點到 P 距離逐幀**絕對偏差**(px);繞 P 旋轉為等距 → 應 ≈0。
    # 用絕對量(而非相對)避免近 pivot 點放大幀間內插殘差,直接對應物理 px 尺度。
    d0 = np.linalg.norm(pts - P, axis=1)
    worst_abs = 0.0
    for t in ts[::7]:                    # 抽樣(所有點×全時 grid 太大)
        for k in range(len(pts)):
            w = _world_of(pts[k] - O, O, rot_d, tr_d, t)
            worst_abs = max(worst_abs, abs(np.linalg.norm(w - P) - d0[k]))
    # AC4 identity:θ=0 幀 Δ
    d_t0 = math.hypot(tr_d[0]["x"], tr_d[0]["y"])
    d_tN = math.hypot(tr_d[-1]["x"], tr_d[-1]["y"])
    return dict(fix=fix, neg=neg, move=move, rigid=worst_abs, d0=d_t0, dN=d_tN,
                nkeys=len(rot_d))


def _synthetic_skeleton():
    """最小合成 skeleton(root + body + 左手limb + 頭head),供端到端 build_animations。"""
    return {
        "skeleton": {"width": 700, "height": 700},
        "bones": [
            {"name": "root"},
            {"name": "b_身體", "parent": "root", "x": 350, "y": 350},
            {"name": "b_左手", "parent": "root", "x": 250, "y": 300},
            {"name": "b_頭", "parent": "root", "x": 360, "y": 520},
        ],
        "slots": [], "skins": {"default": {}}, "animations": {},
    }


def _synthetic_storyboard():
    return {"beats": [{"beat": "Loop", "parts": [
        {"part": "身體", "role": "body"},
        {"part": "左手", "role": "limb"},
        {"part": "頭", "role": "head"},
    ]}]}


def main():
    results = {}
    print("=" * 70)
    print("candidate 0i — 件繞關節 pivot 轉 keyframe 閘")
    print("=" * 70)

    # ---- 真值幾何 ----
    pts, O, P, fid = _load_real()
    armlen = float(np.linalg.norm(O - P))
    print(f"\n真值:左手 [{fid}] verts={len(pts)}  件中心 O=({O[0]:.1f},{O[1]:.1f})  "
          f"肩 pivot P=({P[0]:.1f},{P[1]:.1f})  |O-P|={armlen:.1f}px")

    # ---- AC1–AC5(linear swing)----
    m = _pivot_metrics(pts, O, P, _swing(bezier=False))
    print(f"\n[linear swing 24°]  dense keys={m['nkeys']}")
    print(f"  AC1 pivot 不動點殘差 max = {m['fix']:.4f}px   (< {TOL_FIX})")
    print(f"  AC2 負對照(繞件中心)   = {m['neg']:.2f}px    (>> AC1, ≥ {MIN_NEG})")
    print(f"  AC3 件最遠點位移         = {m['move']:.2f}px   (≥ {MIN_MOVE})")
    print(f"  AC4 identity Δ@t0/tN     = {m['d0']:.2e}/{m['dN']:.2e}px  (< {EPS})")
    print(f"  AC5 剛性(距 P 絕對偏差) = {m['rigid']:.4f}px    (< {TOL_RIGID})")
    ac1 = m["fix"] < TOL_FIX
    ac2 = (m["neg"] >= MIN_NEG) and (m["neg"] > m["fix"] * NEG_RATIO)
    ac3 = m["move"] >= MIN_MOVE
    ac4 = m["d0"] < EPS and m["dN"] < EPS
    ac5 = m["rigid"] < TOL_RIGID
    results.update(AC1_fixed_point=ac1, AC2_negctrl=ac2, AC3_moves=ac3,
                   AC4_identity=ac4, AC5_rigid=ac5)

    # ---- AC7:bezier 緩動仍成立 ----
    mb = _pivot_metrics(pts, O, P, _swing(bezier=True))
    print(f"\n[bezier ease swing]  AC7 pivot 殘差 max = {mb['fix']:.4f}px  (< {TOL_FIX})")
    results["AC7_curve"] = mb["fix"] < TOL_FIX

    # ---- AC6:端到端經真實 build_animations ----
    from gen_animations import build_animations
    sk = _synthetic_skeleton()
    anims = build_animations(sk, _synthetic_storyboard())
    loop = anims["Loop"]
    # bone_origin / pivot(把左手繞 P、頭繞頸縫;此處用合成幾何驗機制,pivot 取件外一點)
    bone_origin = {b["name"]: (b.get("x", 0.0), b.get("y", 0.0))
                   for b in sk["bones"] if b["name"] != "root"}
    pivots = {"b_左手": (350.0, 350.0), "b_頭": (355.0, 420.0)}   # 肩/頸(合成)
    # 未套用版(負對照):loop 左手 rotate 繞件中心 → pivot 會動
    loop_raw_rot = [dict(f) for f in loop["bones"]["b_左手"]["rotate"]]
    conv = pr.apply_pivots(loop, bone_origin, pivots)
    print(f"\n[端到端 build_animations Loop]  converted bones = {conv}")
    # (a) 有限 + 時間嚴格遞增
    finite = spine_anim.all_finite(loop)
    # (b) loop 無縫:轉換後的 bone rotate/translate 端點相等
    seamless = True
    for b in conv:
        for ch in ("rotate", "translate"):
            fr = loop["bones"][b].get(ch)
            if not fr:
                continue
            if ch == "rotate":
                seamless &= abs(fr[0]["angle"] - fr[-1]["angle"]) < 1e-6
            else:
                seamless &= abs(fr[0]["x"] - fr[-1]["x"]) < 1e-6 and abs(fr[0]["y"] - fr[-1]["y"]) < 1e-6
    # (c) 生成 loop 上 pivot 不動(左手)
    O_lh = np.array(bone_origin["b_左手"]); P_lh = np.array(pivots["b_左手"])
    rr = loop["bones"]["b_左手"]["rotate"]; tt = loop["bones"]["b_左手"]["translate"]
    ell = P_lh - O_lh
    ts = _dense_ts(rr)
    fix_e = max(np.linalg.norm(_world_of(ell, O_lh, rr, tt, t) - P_lh) for t in ts)
    # (d) 內建負對照:未套用(繞件中心)pivot 位移
    neg_e = max(np.linalg.norm(_world_of(ell, O_lh, loop_raw_rot, None, t) - P_lh) for t in ts)
    print(f"  (a) finite/mono increasing = {finite}")
    print(f"  (b) loop 端點相等(無縫)    = {seamless}")
    print(f"  (c) 生成 loop pivot 殘差    = {fix_e:.4f}px  (< {TOL_FIX})")
    print(f"  (d) 負對照未套用位移        = {neg_e:.2f}px   (>> (c))")
    ac6 = finite and seamless and (fix_e < TOL_FIX) and (neg_e > fix_e * NEG_RATIO) and (neg_e >= 1.0)
    results["AC6_end2end"] = ac6

    print("\n" + "-" * 70)
    for k, v in results.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    overall = all(results.values())
    print("-" * 70)
    print("OVERALL:", "PASS ✅" if overall else "FAIL ❌")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
