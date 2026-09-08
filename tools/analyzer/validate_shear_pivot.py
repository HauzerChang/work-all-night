#!/usr/bin/env python3
"""candidate 0i/G-3 延伸(**G-4**)驗收 — 「件繞關節 pivot 的**一般仿射**變換」keyframe 生成閘。

0i 讓件繞 pivot **轉**(M=R);G-3 推廣到繞 pivot **縮放**(M=R·S,均勻 scale = 相似變換,
`|world(x)−P|=s|x−P|`)。本閘(G-4)再推廣到**非均勻 scale(sx≠sy)與 shear** —— 此時 M 是
**一般仿射**、**不再是相似變換**,但補償公式 `Δ=(M−I)(O−P)` 仍讓 pivot P 為**精確不動點**,
且對任意附著點 x 精確滿足 **world(x)−P = M·(x−P)**(仿射保形)。矩陣改用**真實 Spine 3.8
bone local**(含 shear):M=(cos(θ+shx)·sx, cos(θ+90+shy)·sy, sin(θ+shx)·sx, sin(θ+90+shy)·sy)。

**crux = 相似性「應該壞掉」**:G-3 的 AC5 靠 `|world(x)−P|=s|x−P|` 成立來證繞 pivot 等比縮放;
非均勻 scale / shear 下該等式**必然不成立**(各方向拉伸比不同)。若 G-4 仍只驗相似性就會假陰性。
本閘改驗**更弱但更一般**的仿射保形(world(x)−P=M(x−P) 精確),並用**各向異性**
(anisotropy = max_d|M·d̂| − min_d|M·d̂|,= M 的奇異值差)作鑑別子:均勻 scale→0(相似)、
非均勻 scale / shear→顯著 >0(真正非相似)→ 證此閘測的是一般仿射、非 G-3 的相似特例。

真值來源同 0i/G-3:真實 Award 機器人左手件世界輪廓 + `infer_pivots` 接觸縫肩 pivot(|O−P|≈117px)。
純 Python 模擬,密集網格逐點量測(不靠肉眼、不需瀏覽器)。

AC(客觀、可量測):
  AC1 非均勻 scale 不動點: sx≠sy 補償版下 pivot 附著點世界座標 == P(幀間殘差 < TOL_FIX)。
  AC2 shear 不動點       : shearX≠0 補償版下 pivot 殘差 < TOL_FIX(仿射保形不需 M 是相似)。
  AC3 仿射保形(精確)   : 在**關鍵幀**(Δ 精確)下,∀件點 world(x)−P == M·(x−P),最壞偏差 < TOL_EXACT。
  AC4 相似性壞掉(鑑別) : 均勻 scale anisotropy≈0(相似);非均勻 scale 與 shear anisotropy ≥ MIN_ANISO
                          (真正非相似)→ 證閘測一般仿射,非 G-3 相似特例。
  AC5 identity 介面      : 首尾 identity 幀(θ=0,s=1,shear=0)Δ=0(< EPS)→ 無縫不被破壞。
  AC6 矩陣正確性         : (a) transform_matrix_full(θ,sx,sy,0,0) 逐位元 == transform_matrix(θ,sx,sy)
                          (0i/G-3 無回歸);(b) pure shearX φ 的 det == cos φ(**真實 Spine shear**,
                          非天真 unit-shear det=1);(c) shear=None 的仿射路徑 == G-3 的 srt 路徑(退化)。
  AC7 端到端整合         : 一支帶 rotate+scale+**shear** 通道的節拍 → `apply_pivots(include_shear=True)` →
                          (a)有限;(b)各通道端點相等(無縫);(c)生成節拍上 pivot 不動;(d)內建負對照
                          =未套用(繞件中心含 shear)pivot 會動。
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

TOL_FIX = 0.5       # px,pivot 不動點幀間最大殘差上限
TOL_EXACT = 2e-3    # px,關鍵幀仿射保形 world(x)−P=M(x−P) 偏差上限。數學上精確為 0,實測殘差
                    # 純由**關鍵幀量化**(角度/shear 存檔捨入 4dp≈5e-5°,經件點偏移 ~350px 放大到
                    # ~4e-4px)決定,非公式限制;仍比 0.5px 不動點門檻緊 250×。
MIN_ANISO = 0.10    # anisotropy 下限(非均勻/ shear 相似性壞掉的最小可辨量)
SIM_EPS = 1e-6      # 均勻 scale anisotropy 上限(相似→各向同性)
MIN_NEG = 10.0      # px,負對照 pivot 位移下限
EPS = 1e-6
NEG_RATIO = 20.0    # 負對照/不動點 位移比下限


def _M_spine(deg, sx, sy, shx=0.0, shy=0.0):
    """真實 Spine 3.8 bone local 2×2(獨立於 pivot_rotation 的轉錄,供交叉驗證)。"""
    rx = math.radians(deg + shx)
    ry = math.radians(deg + 90.0 + shy)
    return np.array([[math.cos(rx) * sx, math.cos(ry) * sy],
                     [math.sin(rx) * sx, math.sin(ry) * sy]])


def _world(local, O, rot_f, sc_f, sh_f, tr_f, t):
    """bone(root 子、setup identity)加 rotate/scale/shear/translate 對局部點 local 的世界座標。"""
    ang = spine_anim._interp(rot_f, t, ["angle"])["angle"] if rot_f else 0.0
    if sc_f:
        sd = spine_anim._interp(sc_f, t, ["x", "y"]); sx, sy = sd["x"], sd["y"]
    else:
        sx = sy = 1.0
    if sh_f:
        shd = spine_anim._interp(sh_f, t, ["x", "y"]); shx, shy = shd["x"], shd["y"]
    else:
        shx = shy = 0.0
    if tr_f:
        td = spine_anim._interp(tr_f, t, ["x", "y"]); tx, ty = td["x"], td["y"]
    else:
        tx = ty = 0.0
    O = np.asarray(O, float)
    return (O + np.array([tx, ty])) + _M_spine(ang, sx, sy, shx, shy) @ np.asarray(local, float)


def _dense_ts(frames, n=400):
    t0, t1 = frames[0]["time"], frames[-1]["time"]
    return [t0 + (t1 - t0) * i / n for i in range(n + 1)]


def _nu_scale_swing(px=1.6, py=1.2):
    """非均勻 scale 擺動(首尾 identity,峰 sx=px, sy=py,px≠py)。"""
    return [{"time": 0.0, "x": 1.0, "y": 1.0},
            {"time": 0.25, "x": px, "y": py},
            {"time": 0.5, "x": 1.0, "y": 1.0}]


def _shear_swing(phx=25.0, phy=0.0):
    """shear 擺動(首尾 identity,峰 shearX=phx, shearY=phy 度)。"""
    return [{"time": 0.0, "x": 0.0, "y": 0.0},
            {"time": 0.25, "x": phx, "y": phy},
            {"time": 0.5, "x": 0.0, "y": 0.0}]


def _rot_swing(peak=24.0):
    return [{"time": 0.0, "angle": 0.0}, {"time": 0.25, "angle": peak},
            {"time": 0.5, "angle": 0.0}]


def _anisotropy(m_tuple, ndir=180):
    """各向異性 = max_d̂|M·d̂| − min_d̂|M·d̂|(繞單位圓);相似變換=0,非均勻/ shear >0。"""
    m00, m01, m10, m11 = m_tuple
    M = np.array([[m00, m01], [m10, m11]])
    rs = []
    for k in range(ndir):
        a = 2 * math.pi * k / ndir
        d = np.array([math.cos(a), math.sin(a)])
        rs.append(np.linalg.norm(M @ d))
    return max(rs) - min(rs)


def _load_real():
    parts, truth, tree, fid = ip.load_award_robot(use_alpha=True)
    inf = ip.infer_pivots(parts, tree)
    slot = "機器人拆件/左手"
    pts = np.asarray(parts[slot], float)
    O = pts.mean(axis=0)
    P = np.asarray(inf[slot], float)
    return pts, O, P, fid.get(slot, "?")


def main():
    results = {}
    print("=" * 70)
    print("candidate G-4 — 件繞關節 pivot 一般仿射(非均勻 scale / shear)保形閘")
    print("=" * 70)

    pts, O, P, fid = _load_real()
    armlen = float(np.linalg.norm(O - P))
    ell_P = P - O
    print(f"\n真值:左手 [{fid}] verts={len(pts)}  O=({O[0]:.1f},{O[1]:.1f})  "
          f"P=({P[0]:.1f},{P[1]:.1f})  |O-P|={armlen:.1f}px")

    # ---- AC1:非均勻 scale 不動點 ----
    nu = _nu_scale_swing(1.6, 1.2)
    _, sc_d, _, tr_d = pr.pivot_channels_affine(None, nu, None, tuple(O), tuple(P))
    ts = _dense_ts(sc_d)
    fix1 = max(np.linalg.norm(_world(ell_P, O, None, sc_d, None, tr_d, t) - P) for t in ts)
    neg1 = max(np.linalg.norm(_world(ell_P, O, None, nu, None, None, t) - P) for t in ts)
    print(f"\n[非均勻 scale (1.6,1.2)]  dense keys={len(sc_d)}")
    print(f"  AC1 pivot 不動點殘差 max = {fix1:.4f}px  (< {TOL_FIX}) | 負對照 {neg1:.1f}px")
    results["AC1_nonuniform_fixed"] = fix1 < TOL_FIX and neg1 > fix1 * NEG_RATIO and neg1 >= MIN_NEG

    # ---- AC2:shear 不動點 ----
    sh = _shear_swing(25.0, 0.0)
    _, _, sh_d, tr_d2 = pr.pivot_channels_affine(None, None, sh, tuple(O), tuple(P))
    ts2 = _dense_ts(sh_d)
    fix2 = max(np.linalg.norm(_world(ell_P, O, None, None, sh_d, tr_d2, t) - P) for t in ts2)
    neg2 = max(np.linalg.norm(_world(ell_P, O, None, None, sh, None, t) - P) for t in ts2)
    print(f"\n[shear 25°]  dense keys={len(sh_d)}")
    print(f"  AC2 pivot 不動點殘差 max = {fix2:.4f}px  (< {TOL_FIX}) | 負對照 {neg2:.1f}px")
    results["AC2_shear_fixed"] = fix2 < TOL_FIX and neg2 > fix2 * NEG_RATIO and neg2 >= MIN_NEG

    # ---- AC3:仿射保形(關鍵幀精確)world(x)−P == M·(x−P) ----
    rot = _rot_swing(24.0); nu2 = _nu_scale_swing(1.5, 1.25); sh2 = _shear_swing(20.0, 10.0)
    rot_d, sc_d3, sh_d3, tr_d3 = pr.pivot_channels_affine(rot, nu2, sh2, tuple(O), tuple(P))
    worst_aff = 0.0
    for f in tr_d3:  # 逐關鍵幀(Δ 在此精確 = (M−I)(O−P))
        t = f["time"]
        ang = spine_anim._interp(rot_d, t, ["angle"])["angle"]
        sd = spine_anim._interp(sc_d3, t, ["x", "y"])
        shd = spine_anim._interp(sh_d3, t, ["x", "y"])
        M = _M_spine(ang, sd["x"], sd["y"], shd["x"], shd["y"])
        for k in range(len(pts)):
            w = _world(pts[k] - O, O, rot_d, sc_d3, sh_d3, tr_d3, t)
            lhs = w - P
            rhs = M @ (pts[k] - P)
            worst_aff = max(worst_aff, float(np.linalg.norm(lhs - rhs)))
    print(f"\n[rot24+scale(1.5,1.25)+shear(20,10) 關鍵幀]  keys={len(tr_d3)}")
    print(f"  AC3 仿射保形 world(x)-P=M(x-P) 最壞偏差 = {worst_aff:.2e}px  (< {TOL_EXACT})")
    results["AC3_affine_exact"] = worst_aff < TOL_EXACT

    # ---- AC4:相似性壞掉(anisotropy 鑑別)----
    a_uni = _anisotropy(pr.transform_matrix_full(0.0, 1.4, 1.4, 0.0, 0.0))
    a_nu = _anisotropy(pr.transform_matrix_full(0.0, 1.6, 1.2, 0.0, 0.0))
    a_sh = _anisotropy(pr.transform_matrix_full(0.0, 1.0, 1.0, 25.0, 0.0))
    print(f"\n[anisotropy = max|Md|-min|Md|]")
    print(f"  均勻 scale 1.4 = {a_uni:.2e}  (相似,< {SIM_EPS})")
    print(f"  非均勻 (1.6,1.2) = {a_nu:.3f}  (非相似,≥ {MIN_ANISO})")
    print(f"  shear 25°        = {a_sh:.3f}  (非相似,≥ {MIN_ANISO})")
    results["AC4_similarity_breaks"] = a_uni < SIM_EPS and a_nu >= MIN_ANISO and a_sh >= MIN_ANISO

    # ---- AC5:identity 介面(首尾幀 Δ=0)----
    d_t0 = math.hypot(tr_d3[0]["x"], tr_d3[0]["y"])
    d_tN = math.hypot(tr_d3[-1]["x"], tr_d3[-1]["y"])
    print(f"\n  AC5 identity Δ@t0/tN = {d_t0:.2e}/{d_tN:.2e}px  (< {EPS})")
    results["AC5_identity"] = d_t0 < EPS and d_tN < EPS

    # ---- AC6:矩陣正確性 ----
    # (a) shear=0 逐位元退化回 transform_matrix
    worst_bc = 0.0
    for deg in (-40, 0, 17, 90, 133, 250):
        for sx in (0.5, 1.0, 1.7):
            for sy in (0.4, 1.0, 1.3):
                a = pr.transform_matrix_full(deg, sx, sy, 0.0, 0.0)
                b = pr.transform_matrix(deg, sx, sy)
                worst_bc = max(worst_bc, max(abs(a[i] - b[i]) for i in range(4)))
    # (b) pure shearX φ 的 det == cos φ(真實 Spine shear,非天真 unit-shear det=1)
    worst_det = 0.0
    naive_det_gap = 0.0
    for phi in (5, 15, 25, 40, 60):
        m00, m01, m10, m11 = pr.transform_matrix_full(0.0, 1.0, 1.0, float(phi), 0.0)
        det = m00 * m11 - m01 * m10
        worst_det = max(worst_det, abs(det - math.cos(math.radians(phi))))
        naive_det_gap = max(naive_det_gap, abs(1.0 - math.cos(math.radians(phi))))  # 天真 unit-shear
    # (c) shear=None 仿射路徑 == G-3 srt 路徑(退化一致)
    r_s, s_s, t_s = pr.pivot_channels_srt(rot, nu2, tuple(O), tuple(P))
    r_a, s_a, sh_a, t_a = pr.pivot_channels_affine(rot, nu2, None, tuple(O), tuple(P))
    degrade_ok = (sh_a is None and len(r_s) == len(r_a) and
                  all(abs(r_s[i]["angle"] - r_a[i]["angle"]) < 1e-9 for i in range(len(r_s))) and
                  all(abs(s_s[i]["x"] - s_a[i]["x"]) < 1e-9 and abs(s_s[i]["y"] - s_a[i]["y"]) < 1e-9
                      for i in range(len(s_s))) and
                  all(abs(t_s[i]["x"] - t_a[i]["x"]) < 1e-9 and abs(t_s[i]["y"] - t_a[i]["y"]) < 1e-9
                      for i in range(len(t_s))))
    print(f"\n  AC6(a) shear=0 退化 vs transform_matrix 最壞差 = {worst_bc:.2e}  (< {EPS})")
    print(f"  AC6(b) pure shearX det==cosφ 最壞差 = {worst_det:.2e}  (天真 unit-shear 差 {naive_det_gap:.3f})")
    print(f"  AC6(c) shear=None 仿射路徑 == srt 路徑 = {degrade_ok}")
    results["AC6_matrix_correct"] = (worst_bc < EPS and worst_det < 1e-9
                                     and naive_det_gap >= MIN_ANISO and degrade_ok)

    # ---- AC7:端到端 apply_pivots(include_shear=True),帶 rotate+scale+shear ----
    bone = "b_左手"
    O7 = (250.0, 300.0); P7 = (350.0, 350.0)   # 合成肩 pivot
    anim = {"bones": {bone: {
        "rotate": _rot_swing(18.0),
        "scale": _nu_scale_swing(1.4, 1.15),
        "shear": _shear_swing(22.0, 8.0),
    }}}
    raw = {ch: [dict(f) for f in anim["bones"][bone][ch]] for ch in ("rotate", "scale", "shear")}
    conv = pr.apply_pivots(anim, {bone: O7}, {bone: P7}, include_shear=True)
    lh = anim["bones"][bone]
    finite = spine_anim.all_finite(anim)
    seamless = True
    for ch, keys in (("rotate", ["angle"]), ("scale", ["x", "y"]),
                     ("shear", ["x", "y"]), ("translate", ["x", "y"])):
        fr = lh.get(ch)
        if not fr:
            continue
        for kk in keys:
            seamless &= abs(fr[0][kk] - fr[-1][kk]) < 1e-6
    ell7 = np.array(P7) - np.array(O7)
    tt = lh["translate"]; ts7 = _dense_ts(tt)
    fix7 = max(np.linalg.norm(_world(ell7, O7, lh.get("rotate"), lh.get("scale"),
                                     lh.get("shear"), tt, t) - np.array(P7)) for t in ts7)
    neg7 = max(np.linalg.norm(_world(ell7, O7, raw["rotate"], raw["scale"],
                                     raw["shear"], None, t) - np.array(P7)) for t in ts7)
    print(f"\n[端到端 apply_pivots(include_shear=True)]  converted = {conv}")
    print(f"  (a) finite = {finite}")
    print(f"  (b) 端點相等(無縫) = {seamless}")
    print(f"  (c) 生成節拍 pivot 殘差 = {fix7:.4f}px  (< {TOL_FIX})")
    print(f"  (d) 負對照未套用位移    = {neg7:.2f}px   (>> (c))")
    results["AC7_end2end"] = (finite and seamless and fix7 < TOL_FIX
                              and neg7 > fix7 * NEG_RATIO and neg7 >= 1.0)

    print("\n" + "-" * 70)
    for k, v in results.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    overall = all(results.values())
    print("-" * 70)
    print("OVERALL:", "PASS ✅" if overall else "FAIL ❌")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
