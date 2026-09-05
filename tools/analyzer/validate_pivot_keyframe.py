#!/usr/bin/env python3
"""candidate 0i 自我驗收閘 — 關節 pivot 感知 keyframe 是否讓件**繞關節不動點**旋轉(純 CPU)。

核心不動點性質:繞 pivot P 旋轉時,件上與 P 重合的點在**世界座標保持不動**(P 是不動點);
繞件中心 O 旋轉則 P 會被甩開 —— 這對「有補償 vs 無補償」構成**天然負對照**。

ACs:
  AC1 formula      : rotate_about_pivot_delta 對閉式解一致(繞 pivot 後 P 精確不動)。
  AC2 fixed_point  : 端到端(build --animate --pivot)Loop 肢體純旋轉段,pivot 世界點跨全幀
                     位移 ≤ 容差(繞關節)。
  AC3 neg_control  : 同 Loop 但**無補償**(build --animate)pivot 世界點顯著位移(繞件中心)
                     —— 且與 AC2 分離度足夠(補償有效)。
  AC4 still_rotates: 件遠端點(離 pivot 遠)確有位移 —— 補償沒把旋轉「凍結」成靜止。
  AC5 interface    : --pivot 產物仍通過 validate_anim 全 AC(In 尾歸位 / Loop 無縫 / Out 收合)
                     —— 補償未破壞既有介面契約。
  AC6 discriminative: (a) 隨機 pivot 補償 → 該隨機點不動但**真關節 P 會動**(P 專屬性);
                      (b) P==O 補償 → Δ≡0(退化為原行為,no-op)。

用法:python3 validate_pivot_keyframe.py [--psd assets/robot_parts.psd] [--genre slot_bigwin]
"""
import argparse, copy, json, math, os, sys, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import spine_anim as SA
import pivot_keyframe as PK
from gen_animations import beat_category, safe
import build_spine as BS
import validate_anim as VA

TOL_FIX = 1.0        # pivot 不動點容差(px)—— 補償後跨全幀位移上限
NEG_MIN = 5.0        # 負對照:無補償時 pivot 至少要動這麼多(px)才算「有鑑別力」
FAR_MIN = 3.0        # 件遠端點至少要動這麼多(px)才算「確有旋轉」


# ---------- 扁平骨架世界取樣(parent=root、root 單位、setup rot=0 scale=1) ----------
def _R(deg):
    th = math.radians(deg)
    c, s = math.cos(th), math.sin(th)
    return np.array([[c, -s], [s, c]])


def world_point(bone_setup_xy, sampled, local_pt):
    """bone 世界原點 O + 動畫通道 → local_pt(相對 bone 局部座標)的世界座標。
    world = (O + translate) + R(rotate)·diag(scaleX,scaleY)·local_pt。"""
    O = np.asarray(bone_setup_xy, float)
    t = np.array([sampled["x"], sampled["y"]])
    S = np.array([sampled["scaleX"] * local_pt[0], sampled["scaleY"] * local_pt[1]])
    return O + t + _R(sampled["rotate"]) @ S


def _bone_setup(sk):
    return {b["name"]: (b.get("x", 0.0), b.get("y", 0.0)) for b in sk["bones"] if b["name"] != "root"}


def _pivot_track(anim, bname, O, P, n=96):
    """回傳 pivot 世界點在 [0,dur] n+1 取樣的最大位移(相對靜止 P)。"""
    dur = SA.duration(anim)
    p_local = np.array([P[0] - O[0], P[1] - O[1]])
    mx = 0.0
    for i in range(n + 1):
        t = dur * i / n
        s = SA.sample(anim, t)["bones"].get(bname)
        if s is None:
            continue
        w = world_point(O, s, p_local)
        mx = max(mx, float(np.linalg.norm(w - np.asarray(P, float))))
    return mx


def _far_point_disp(anim, bname, O, P, n=96):
    """件遠端點(從 pivot 沿 O→遠 方向 200px 的假想點)在動畫中的最大位移(確認確有旋轉)。"""
    dur = SA.duration(anim)
    # 遠端點:pivot 反向延伸(離 pivot 遠)→ local = (O-P)方向 ×200,轉 bone-local
    v = np.array([O[0] - P[0], O[1] - P[1]], float)
    n2 = np.linalg.norm(v) or 1.0
    far_local = (v / n2) * 200.0     # 相對 bone 原點 O 的局部座標
    s0 = SA.sample(anim, 0.0)["bones"].get(bname)
    base = world_point(O, s0, far_local) if s0 else None
    mx = 0.0
    for i in range(n + 1):
        t = dur * i / n
        s = SA.sample(anim, t)["bones"].get(bname)
        if s is None or base is None:
            continue
        w = world_point(O, s, far_local)
        mx = max(mx, float(np.linalg.norm(w - base)))
    return mx


# ---------- AC1: formula ----------
def check_ac1():
    O, P = (100.0, 50.0), (30.0, 20.0)
    detail, ok = {}, True
    for theta in (0.0, 15.0, -25.0, 90.0, 179.0):
        dx, dy = PK.rotate_about_pivot_delta(O, P, theta)
        # 補償後 P 應為不動點:world = O + Δ + R(θ)(P-O) == P
        pl = np.array([P[0] - O[0], P[1] - O[1]])
        w = np.array([O[0] + dx, O[1] + dy]) + _R(theta) @ pl
        err = float(np.linalg.norm(w - np.asarray(P)))
        detail[f"theta={theta}"] = round(err, 9)
        ok = ok and err < 1e-9
    # θ=0 → Δ==0
    d0 = PK.rotate_about_pivot_delta(O, P, 0.0)
    detail["theta0_zero_delta"] = (abs(d0[0]) < 1e-12 and abs(d0[1]) < 1e-12)
    ok = ok and detail["theta0_zero_delta"]
    return ok, detail


# ---------- AC2/AC3/AC4: 端到端 Loop 肢體 ----------
def _loop_anim(sk):
    for name, a in sk["animations"].items():
        if beat_category(name) == "loop":
            return name, a
    return None, None


def _structural_limb_bones(meta):
    """有 pivot 記錄的結構子件 → bone 名。"""
    return {("b_" + nm): tuple(meta[nm]["pivot"]) for nm in meta if meta[nm].get("pivot")}


def _peak_abs_rotate(anim, bname, n=96):
    dur = SA.duration(anim)
    return max(abs(SA.sample(anim, dur * i / n)["bones"].get(bname, {"rotate": 0.0})["rotate"])
               for i in range(n + 1))


def check_ac2_ac3_ac4(sk_piv, meta_piv, sk_nopiv):
    """AC2 補償後 pivot 不動;AC3 無補償=繞件中心(位移吻合閉式 2|P-O|sin(θpk/2)且被補償壓掉,
    ≥1 肢體位移實質顯著);AC4 遠端仍旋轉。"""
    setup = _bone_setup(sk_piv)
    limbs = _structural_limb_bones(meta_piv)
    _, loop_p = _loop_anim(sk_piv)
    _, loop_n = _loop_anim(sk_nopiv)
    ac2, ac3, ac4 = {}, {}, {}
    ok2 = ok4 = True
    ac3_perbone_ok = True
    max_mov = 0.0
    if not limbs or loop_p is None:
        return (False, {"error": "no limb pivots / no loop"}), (False, {}), (False, {})
    for bname, P in limbs.items():
        if bname not in loop_p.get("bones", {}):
            continue
        O = setup[bname]
        fix = _pivot_track(loop_p, bname, O, P)          # 有補償:應近 0
        mov = _pivot_track(loop_n, bname, O, P)          # 無補償:應吻合繞件中心閉式
        far = _far_point_disp(loop_p, bname, O, P)        # 遠端仍動
        # 閉式:繞件中心 O 旋轉 θpk 時 pivot 位移 = 2|P-O|sin(θpk/2)
        r = math.hypot(P[0] - O[0], P[1] - O[1])
        thpk = _peak_abs_rotate(loop_n, bname)
        pred = 2.0 * r * math.sin(math.radians(thpk) / 2.0)
        model_ok = abs(mov - pred) <= max(0.5, 0.12 * pred)   # 無補償=繞中心(模型吻合)
        killed = fix <= TOL_FIX and fix <= 0.05 * max(mov, 1e-6)  # 補償壓掉 ≥20×
        ac2[bname] = {"pivot_disp_px": round(fix, 4), "pass": fix <= TOL_FIX}
        ac3[bname] = {"nopiv_disp_px": round(mov, 3), "predicted_px": round(pred, 3),
                      "peak_deg": round(thpk, 2), "radius_px": round(r, 1),
                      "model_match": model_ok, "compensated_away": killed,
                      "pass": model_ok and killed}
        ac4[bname] = {"far_disp_px": round(far, 3), "pass": far >= FAR_MIN}
        ok2 = ok2 and ac2[bname]["pass"]
        ok4 = ok4 and ac4[bname]["pass"]
        ac3_perbone_ok = ac3_perbone_ok and ac3[bname]["pass"]
        max_mov = max(max_mov, mov)
    ac3["_substantive"] = {"max_nopiv_disp_px": round(max_mov, 3), "min_required": NEG_MIN,
                           "pass": max_mov >= NEG_MIN}
    ok3 = ac3_perbone_ok and ac3["_substantive"]["pass"]
    return (ok2, ac2), (ok3, ac3), (ok4, ac4)


# ---------- AC5: 介面契約仍過 ----------
def check_ac5(sk_piv, storyboard):
    res = VA.run_all(sk_piv, storyboard)
    ok = all(v[0] for v in res.values())
    return ok, {k: v[0] for k, v in res.items()}


# ---------- AC6: 鑑別力(隨機 pivot / P==O) ----------
def check_ac6(sk_piv, meta_piv):
    setup = _bone_setup(sk_piv)
    limbs = _structural_limb_bones(meta_piv)
    _, loop = _loop_anim(sk_piv)
    detail, ok = {}, True
    # 取一根肢體的原始 rotate（未補償）重建 → 對「隨機 pivot」與「P==O」各自補償
    bname, P = next(iter(limbs.items()))
    O = setup[bname]
    rot_frames = copy.deepcopy(loop["bones"][bname]["rotate"])

    # (a) 隨機 pivot Q:補償讓 Q 不動,但真關節 P 應**會動**(P 專屬)
    Q = (O[0] + 123.0, O[1] - 77.0)
    bQ = PK.compensate_bone({"rotate": copy.deepcopy(rot_frames)}, O, Q)
    animQ = {"bones": {bname: bQ}}
    q_fix = _pivot_track(animQ, bname, O, Q)              # Q 不動
    p_move = _pivot_track(animQ, bname, O, P)             # 但 P 會動
    detail["random_pivot"] = {"Q_disp": round(q_fix, 4), "trueP_disp": round(p_move, 3),
                              "pass": q_fix <= TOL_FIX and p_move >= NEG_MIN}
    ok = ok and detail["random_pivot"]["pass"]

    # (b) P==O:Δ 恆 0 → 補償後 translate 全 0(退化 no-op)
    bO = PK.compensate_bone({"rotate": copy.deepcopy(rot_frames)}, O, O)
    max_t = max((max(abs(f["x"]), abs(f["y"])) for f in bO.get("translate", [{"x": 0, "y": 0}])), default=0.0)
    detail["P_equals_O_noop"] = {"max_translate": round(max_t, 6), "pass": max_t < 1e-6}
    ok = ok and detail["P_equals_O_noop"]["pass"]
    return ok, detail


def run(psd, genre):
    from analyze_target import analyze
    sb = analyze(psd, genre)["3_motion_storyboard"]
    tmp = tempfile.mkdtemp(prefix="pivkf_")
    dp = os.path.join(tmp, "piv"); dn = os.path.join(tmp, "nopiv")
    BS.build(psd, dp, genre, animate=True, pivot=True)
    BS.build(psd, dn, genre, animate=True, pivot=False)
    sk_piv = json.load(open(os.path.join(dp, "skeleton.json")))
    meta_piv = json.load(open(os.path.join(dp, "build_meta.json")))
    sk_nopiv = json.load(open(os.path.join(dn, "skeleton.json")))

    res = {}
    res["AC1_formula"] = check_ac1()
    (ok2, d2), (ok3, d3), (ok4, d4) = check_ac2_ac3_ac4(sk_piv, meta_piv, sk_nopiv)
    res["AC2_fixed_point"] = (ok2, d2)
    res["AC3_neg_control"] = (ok3, d3)
    res["AC4_still_rotates"] = (ok4, d4)
    res["AC5_interface"] = check_ac5(sk_piv, sb)
    res["AC6_discriminative"] = check_ac6(sk_piv, meta_piv)
    return res, meta_piv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--genre", default="slot_bigwin")
    a = ap.parse_args()
    res, meta = run(a.psd, a.genre)
    overall = all(v[0] for v in res.values())
    report = {"overall_pass": overall,
              "limb_pivots": {nm: meta[nm]["pivot"] for nm in meta if meta[nm].get("pivot")},
              "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()}}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
