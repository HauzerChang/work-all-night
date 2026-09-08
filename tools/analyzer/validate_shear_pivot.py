#!/usr/bin/env python3
"""candidate (G-4) 驗收 — 「件繞關節 pivot 的**任意仿射**變形」保形閘(非均勻 scale / shear)。

0i 讓件繞 pivot **轉**(等距);G-3 推廣到均勻 **scale**(相似:|world−P|=s|x−P|)。本閘再推廣到
**任意仿射線性部 M**(非均勻 scale sx≠sy、shear)——此時**相似性失效**(到 P 的距離比不再是單一常數 s),
但**仿射保形**仍嚴格成立:
    world(x) − P == M·(x − P)      ∀件點 x
這是同一條補償 Δ=(M−I)(O−P) 的必然結果(見 `pivot_rotation.pivot_delta_matrix` 推導)。本閘的核心
判別點(相對 G-3):**同一組件點下,非均勻 M 使「到 P 距離比」的離散度顯著 > 0(相似性 FALSE),
仿射殘差仍 ~0(保形 TRUE)**;均勻 M 則距離比離散度 ~0(相似性 TRUE)—— 內建正對照證判別力。

真值來源同 0i/G-3:真實 Award 機器人左手件世界輪廓 + `infer_pivots` 推得接觸縫肩 pivot(|O−P|≈117px)。
純 Python 模擬「bone(root 子、setup 旋轉0/scale1)加 rotate/scale/translate」的世界變換,密網格逐點量測。

AC(客觀、可量測):
  AC1 不動點(非均勻)  : 非均勻 scale M(sx≠sy)補償版下 pivot 附著點世界座標 == P(殘差 < TOL_FIX)。
  AC2 負對照           : **不補償**(繞件中心 O)時 pivot 明顯位移(≥ MIN_NEG px、≥ NEG_RATIO×AC1)。
  AC3 crux 仿射保形    : ∀件點 |world(x) − (M(x−P)+P)| < TOL_AFF(非均勻 M 仿射恆等式逐點成立)。
  AC4 crux 相似性失效  : 非均勻 M 下「到 P 距離比」r_k=|world(x_k)−P|/|x_k−P| **離散度 ≥ MIN_ANISO**
                         (證 G-3 的相似 AC 對此 M 會 FAIL);內建正對照 = 均勻 M 離散度 < TOL_ISO(≈0)。
  AC5 shear 保形       : 純 **shear** M=[[1,kx],[ky,1]](經 `pivot_delta_matrix`)pivot 不動 + 仿射保形
                         + 相似性失效 → 證補償對**完整仿射群**正確,非僅 R·S。負對照繞 O 位移。
  AC6 identity 介面    : M=I(θ=0,sx=sy=1,shear=0)→ Δ=0(< EPS)、∀件點零位移 → setup/端點 identity 保持。
  AC7 端到端           : 造 limb **非均勻 scale**(sx≠sy)+rotate 節拍 → 真實 `apply_pivots(include_scale=True)`
                         → (a)通道有限;(b)pivot 逐幀不動;(c)逐幀仿射保形;(d)內建負對照未套用版 pivot 會動。
                         (此為 `pivot_channels_srt` 在 sx≠sy 下的首次端到端驗證;G-3 端到端只走 sx==sy。)
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

TOL_FIX = 0.5       # px,pivot 不動點殘差上限
TOL_AFF = 0.5       # px,仿射恆等式 world(x)==M(x−P)+P 逐點殘差上限
MIN_NEG = 10.0      # px,負對照(繞件中心)pivot 位移下限
NEG_RATIO = 20.0    # 負對照/不動點 位移比下限
MIN_ANISO = 0.05    # 非均勻 M「到P距離比」離散度(std)下限 → 相似性確實失效
TOL_ISO = 1e-3      # 均勻 M「到P距離比」離散度上限(正對照:相似性成立)
EPS = 1e-6


def _R(deg):
    r = math.radians(deg); c, s = math.cos(r), math.sin(r)
    return np.array([[c, -s], [s, c]])


def _M_np(deg, sx, sy, kx=0.0, ky=0.0):
    """M = R(θ)·K(kx,ky)·diag(sx,sy)(與 pivot_rotation.transform_matrix_full 一致)。"""
    K = np.array([[1.0, kx], [ky, 1.0]])
    return _R(deg) @ K @ np.diag([sx, sy])


def _world_static(local, O, Delta, M):
    """靜態(單一 M+Δ)下 bone 局部點 local 的世界座標 = (O+Δ) + M·local。"""
    return (np.asarray(O, float) + np.asarray(Delta, float)) + M @ np.asarray(local, float)


def _world_anim(local, O, rot_frames, sc_frames, tr_frames, t):
    """時序(rotate/scale/translate timeline)下的世界座標,M=R·diag(sx,sy)。"""
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
    return (O + np.array([tx, ty])) + _M_np(ang, sx, sy) @ np.asarray(local, float)


def _dense_ts(frames, n=400):
    t0, t1 = frames[0]["time"], frames[-1]["time"]
    return [t0 + (t1 - t0) * i / n for i in range(n + 1)]


def _load_real():
    """真實 Award 左手件世界輪廓 + 推得肩 pivot。回傳 (pts Nx2, O 件中心, P pivot, fid)。"""
    parts, truth, tree, fid = ip.load_award_robot(use_alpha=True)
    inf = ip.infer_pivots(parts, tree)
    slot = "機器人拆件/左手"
    pts = np.asarray(parts[slot], float)
    O = pts.mean(axis=0)
    P = np.asarray(inf[slot], float)
    return pts, O, P, fid.get(slot, "?")


def _dist_ratio_spread(pts, O, P, M, Delta):
    """量「各件點到 P 的距離 / setup 到 P 距離」的離散度(std)。均勻 scale → ~0;非均勻/shear → >0。"""
    d0 = np.linalg.norm(pts - P, axis=1)
    ratios = []
    for k in range(len(pts)):
        if d0[k] < 1e-9:
            continue
        w = _world_static(pts[k] - O, O, Delta, M)
        ratios.append(np.linalg.norm(w - P) / d0[k])
    return float(np.std(ratios)), float(np.mean(ratios))


def _affine_residual(pts, O, P, M, Delta):
    """∀件點 max |world(x) − (M(x−P)+P)|(仿射恆等式殘差)。"""
    worst = 0.0
    for k in range(len(pts)):
        w = _world_static(pts[k] - O, O, Delta, M)
        expect = M @ (pts[k] - P) + P
        worst = max(worst, float(np.linalg.norm(w - expect)))
    return worst


def _check_static(name, pts, O, P, M_tuple, require_aniso=True):
    """對一個靜態 M 做 AC1/AC2/AC3/AC4 的量測。回傳 dict of metrics。"""
    M = np.array([[M_tuple[0], M_tuple[1]], [M_tuple[2], M_tuple[3]]])
    Delta = pr.pivot_delta_matrix(M_tuple, tuple(O), tuple(P))
    # AC1 不動點:pivot 附著局部點 ℓ_P = P−O
    ell_P = P - O
    fix = float(np.linalg.norm(_world_static(ell_P, O, Delta, M) - P))
    # AC2 負對照:不補償(Δ=0,繞件中心)pivot 位移
    neg = float(np.linalg.norm(_world_static(ell_P, O, (0.0, 0.0), M) - P))
    # AC3 仿射殘差
    aff = _affine_residual(pts, O, P, M, Delta)
    # AC4 相似性(距離比離散度)
    spread, mean_r = _dist_ratio_spread(pts, O, P, M, Delta)
    print(f"\n[{name}]  M=({M_tuple[0]:.3f},{M_tuple[1]:.3f},{M_tuple[2]:.3f},{M_tuple[3]:.3f})")
    print(f"  不動點殘差 = {fix:.4f}px  | 負對照 = {neg:.2f}px  | 仿射殘差 = {aff:.4f}px")
    print(f"  到P距離比:mean={mean_r:.3f}  std(離散度)={spread:.4f}  "
          f"({'非均勻→相似性失效' if require_aniso else '均勻→相似'})")
    return dict(fix=fix, neg=neg, aff=aff, spread=spread)


def main():
    results = {}
    print("=" * 74)
    print("candidate (G-4) — 件繞關節 pivot 任意仿射(非均勻 scale / shear)保形閘")
    print("=" * 74)

    pts, O, P, fid = _load_real()
    armlen = float(np.linalg.norm(O - P))
    print(f"\n真值:左手 [{fid}] verts={len(pts)}  件中心 O=({O[0]:.1f},{O[1]:.1f})  "
          f"肩 pivot P=({P[0]:.1f},{P[1]:.1f})  |O-P|={armlen:.1f}px")

    # ── 非均勻 scale M = diag(1.6, 0.7)(sx≠sy)── AC1/AC2/AC3/AC4 ──
    M_aniso = pr.transform_matrix_full(0.0, 1.6, 0.7)
    m = _check_static("非均勻 scale diag(1.6,0.7)", pts, O, P, M_aniso, require_aniso=True)
    # 正對照:均勻 scale diag(1.6,1.6) → 距離比離散度應 ~0(相似成立)
    M_iso = pr.transform_matrix_full(0.0, 1.6, 1.6)
    m_iso = _check_static("均勻 scale diag(1.6,1.6)〔正對照〕", pts, O, P, M_iso, require_aniso=False)

    results["AC1_fixed_point"] = m["fix"] < TOL_FIX
    results["AC2_negctrl"] = (m["neg"] >= MIN_NEG) and (m["neg"] > m["fix"] * NEG_RATIO)
    results["AC3_affine_preserved"] = m["aff"] < TOL_AFF
    # crux:非均勻離散度大(相似 FAIL)且仿射保形;均勻離散度 ~0(相似 PASS)→ 判別力
    results["AC4_similarity_breaks"] = (m["spread"] >= MIN_ANISO) and (m_iso["spread"] < TOL_ISO)

    # ── AC5:純 shear M=[[1,0.35],[0.2,1]] 繞 pivot(經 pivot_delta_matrix;兩非對角項皆非零)──
    M_shear = pr.shear_matrix(0.35, 0.2)
    ms = _check_static("純 shear [[1,0.35],[0.2,1]]", pts, O, P, M_shear, require_aniso=True)
    results["AC5_shear_preserved"] = (ms["fix"] < TOL_FIX) and (ms["aff"] < TOL_AFF) and \
        (ms["neg"] >= MIN_NEG) and (ms["neg"] > ms["fix"] * NEG_RATIO) and (ms["spread"] >= MIN_ANISO)

    # ── AC6:identity M=I → Δ=0、∀件點零位移 ──
    M_id = pr.transform_matrix_full(0.0, 1.0, 1.0)
    Delta_id = pr.pivot_delta_matrix(M_id, tuple(O), tuple(P))
    d_id = math.hypot(Delta_id[0], Delta_id[1])
    move_id = max(float(np.linalg.norm(_world_static(pts[k] - O, O, Delta_id,
                  np.eye(2)) - pts[k])) for k in range(len(pts)))
    print(f"\n[identity M=I]  Δ = {d_id:.2e}px  | ∀件點最大位移 = {move_id:.2e}px  (< {EPS})")
    results["AC6_identity"] = (d_id < EPS) and (move_id < EPS)

    # ── AC7:端到端 —— limb 非均勻 scale(sx≠sy)+rotate 經真實 apply_pivots(include_scale=True)──
    # (gen_animations 目前不產非均勻 scale;此為 pivot_channels_srt 在 sx≠sy 下的首次端到端驗證。)
    anim = {"bones": {"b_左手": {
        "rotate": [{"time": 0.0, "angle": 0.0}, {"time": 0.25, "angle": 20.0},
                   {"time": 0.5, "angle": 0.0}],
        "scale": [{"time": 0.0, "x": 1.0, "y": 1.0},
                  {"time": 0.25, "x": 1.55, "y": 0.75},   # sx≠sy:非均勻
                  {"time": 0.5, "x": 1.0, "y": 1.0}],
    }}}
    bone_origin = {"b_左手": (float(O[0]), float(O[1]))}
    pivots = {"b_左手": (float(P[0]), float(P[1]))}
    ell = P - O
    raw_rot = [dict(f) for f in anim["bones"]["b_左手"]["rotate"]]
    raw_sc = [dict(f) for f in anim["bones"]["b_左手"]["scale"]]
    conv = pr.apply_pivots(anim, bone_origin, pivots, include_scale=True)
    lh = anim["bones"]["b_左手"]
    rr, ss, tt = lh.get("rotate"), lh.get("scale"), lh.get("translate")
    finite = spine_anim.all_finite(anim)
    tsx = _dense_ts(tt)
    # (b) pivot 逐幀不動
    fix_e = max(float(np.linalg.norm(_world_anim(ell, O, rr, ss, tt, t) - P)) for t in tsx)
    # (c) 逐幀仿射保形:world(x)==M(t)(x−P)+P ∀件點(抽樣時間)
    aff_e = 0.0
    for t in tsx[::40]:
        ang = spine_anim._interp(rr, t, ["angle"])["angle"]
        sd = spine_anim._interp(ss, t, ["x", "y"])
        Mt = _M_np(ang, sd["x"], sd["y"])
        for k in range(0, len(pts), 3):
            w = _world_anim(pts[k] - O, O, rr, ss, tt, t)
            expect = Mt @ (pts[k] - P) + P
            aff_e = max(aff_e, float(np.linalg.norm(w - expect)))
    # (d) 負對照:未套用(繞件中心)pivot 位移
    neg_e = max(float(np.linalg.norm(_world_anim(ell, O, raw_rot, raw_sc, None, t) - P))
                for t in tsx)
    print(f"\n[端到端 apply_pivots(include_scale) 非均勻 scale+rotate]  converted = {conv}")
    print(f"  (a) finite                 = {finite}")
    print(f"  (b) 逐幀 pivot 殘差         = {fix_e:.4f}px  (< {TOL_FIX})")
    print(f"  (c) 逐幀仿射保形殘差        = {aff_e:.4f}px  (< {TOL_AFF})")
    print(f"  (d) 負對照未套用位移        = {neg_e:.2f}px   (>> (b))")
    results["AC7_end2end"] = finite and (fix_e < TOL_FIX) and (aff_e < TOL_AFF) and \
        (neg_e > fix_e * NEG_RATIO) and (neg_e >= 1.0)

    print("\n" + "-" * 74)
    for k, v in results.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    overall = all(results.values())
    print("-" * 74)
    print("OVERALL:", "PASS ✅" if overall else "FAIL ❌")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
