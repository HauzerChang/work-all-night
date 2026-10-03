#!/usr/bin/env python3
"""candidate (G-2) 自我驗收閘 — 主秀節拍下 limb 繞**關節 pivot** 旋轉+縮放(整合閘,純 CPU)。

背景(把兩條既有能力接起來驗):
  - candidate 0i(`pivot_rotation` / `--pivot-rotate`)讓件**繞關節 pivot 轉**而非件中心;
    G-3(`--scale-pivot`)再把 `scale` 也以 M=R·S 補償 → 件繞關節 pivot **旋轉+縮放**。
  - 但這兩者的端到端 AC(`validate_pivot_rotation` AC6 / `validate_scale_pivot` AC7)都只在
    **合成 skeleton + 合成單一 beat**(Loop / Win pulse)上驗機制。
  - 另一邊,主秀 beat(hit/combo/charge/burst/cascade)早已由 `genre_priors` → `build_spine --animate`
    直出,而 `build_spine` 的 pivot 補償迴圈(build_spine.py:`apply_pivots(beat, …)`)**逐一掃過所有
    animations**,故主秀 beat 的 limb rotate/scale 其實**已**被轉成繞關節版 —— 但**從未有 AC 驗過**
    「真實產線產的主秀節拍下,limb 真的繞關節而非件中心動」。

本閘補上這個缺口(STATE 建議 **(G-2)**):從 **genre 先驗庫** → **真實 `build_spine --animate --scale-pivot`
robot 骨架**(走完整產線,`apply_pivots` 在 build 內實跑)端到端量測 —— 對**每一個**旋轉/縮放主秀節拍
(cat ∈ MAIN_SHOW_CATS − SHEAR_CATS,即 hit/combo/charge/burst/cascade;shear 節拍 wobble/squash/twist
需 `--shear-pivot`,其繞關節性質已由 `validate_{twist,squash}_*` 的端到端 pivot 殘差 AC 覆蓋)×**每一個**有
關節的 limb/head bone,量其附著在關節 pivot 上的點世界座標是否**逐幀不動**(繞關節),並以**不補償版**
(`--animate` 無 pivot 旗標 → 繞件中心)做負對照。

真值界定:關節 pivot = S5 `infer_pivots` 由拆件接觸縫**確定性**推得(非美感);「limb 繞關節動」是
**可量化幾何事實**(不動點殘差 px),非主觀手感。閘以負對照(繞件中心明顯位移)+ 隔離(非關節件不受影響)
+ 正確轉換集合(只轉該轉的 bone)證鑑別力與可信。

世界變換模型(同 `validate_scale_pivot`,Spine root 子 bone、setup rot0/scale1):
  world(local, t) = (O + T(t)) + M(t)·local,  M = R(θ(t))·diag(sx(t), sy(t))
  關節附著局部點 ℓ_P = P − O;繞 pivot 補償後 world(ℓ_P, t) 應 ≡ P(∀t)。

AC(客觀、可量測):
  M1 present + routing + 零回歸 : 兩版 build 皆成功;summary 具 `pivot_centers`/`pivot_joints`;有關節的
                                limb/head bone 集合非空;**每個**旋轉/縮放主秀節拍皆有 ≥1 有關節 limb bone
                                帶 rotate/scale + translate(被補償);非關節件(光暈=特效/身體=root)不在
                                `pivot_joints`;scale-pivot 版的結構節拍(In/Loop/Out)仍 finite(無回歸)。
  M2 crux — 繞關節不動點      : **每個**(主秀節拍 × 有關節 limb bone),關節附著點世界座標逐幀殘差
                                max < TOL_FIX(繞關節);**且**件最遠點位移 ≥ MIN_MOVE(真的在動非凍住)。
  M3 neg-control(繞件中心)   : **每組** pair 在**不補償版**(繞件中心)下關節位移 ≥ NEG_RATIO × M2 殘差
                                (補償把關節運動砍 ≥20×,逐 pair 皆成立,主判準);**且**最差 pair 的繞件中心
                                位移量 ≥ MIN_NEG(量級上明顯大)→ 證「不動」來自補償,非節拍本身平凡。
  M4 identity 介面(保設定姿勢): pivot 補償**不在節拍本就靜止處引入不連續** —— 對每個(主秀節拍 × limb ×
                                首/尾端點),**若**不補償版該端點恰為 setup identity(rot≈0 ∧ scale≈1 ∧ tr≈0),
                                **則**補償版該端點亦須 setup identity(rot≈0 ∧ scale≈1 ∧ Δ≈0,< TOL_IDENT)。
                                故 hit/combo/charge/cascade 首尾、burst **尾**(靜止)皆須 identity → 仍可無縫插在
                                In/Loop/Out 之間;burst **首**(刻意塌陷登場,非 setup)不受此限,其關節仍由 M2
                                保證不動(補償在塌陷幀給出正確的 Δ=(M−I)(O−P))。
  M5 isolation + 正確轉換集合 : (a) 非關節件(光暈/身體)channels 在 comp 與 raw 兩版**逐位元相同**
                                (pivot 補償只動有關節的 limb,不外洩到特效/root);
                                (b) 兩版**有差異**(被補償)的 bone 集合 == **恰好**有關節 limb bone 集合
                                (該轉的都轉、不該轉的沒轉;無漏轉/多轉)。

用法:
  python3 validate_pivot_main_show.py            # 摘要
  python3 validate_pivot_main_show.py --json     # 完整 JSON
"""
import argparse, json, math, os, sys, tempfile

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rig"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim
import build_spine
from gen_animations import beat_category
from tier_variants import MAIN_SHOW_CATS, SHEAR_CATS

# 旋轉/縮放主秀節拍(可被 --scale-pivot 的 M=R·S 完整補償);shear 節拍需 --shear-pivot,已由他閘覆蓋。
ROT_SCALE_MAIN = MAIN_SHOW_CATS - SHEAR_CATS

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"

TOL_FIX = 0.5       # px,繞關節不動點逐幀殘差上限
MIN_MOVE = 8.0      # px,件最遠點位移下限(證 limb 真的在動)
MIN_NEG = 10.0      # px,負對照(繞件中心)關節位移下限
NEG_RATIO = 20.0    # 負對照 / M2 殘差比下限
TOL_IDENT = 1e-3    # 首尾 identity 容忍(rot 度 / scale 偏差 / translate px)
JOINT_MIN = 0.5     # 件中心與關節距離 ≥ 此值才算「有關節」(= apply_pivots 的補償門檻)
FAR = np.array([0.0, 240.0])   # 探針:離 bone 原點夠遠的局部點(量「最遠點位移」用)


def _psd():
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (PSD, os.path.join(here, "..", "..", PSD)):
        if os.path.exists(cand):
            return cand
    raise FileNotFoundError(PSD)


def _build(scale_pivot):
    """跑一次真實 build_spine 產線(animate),回傳 (skeleton_dict, summary)。
    scale_pivot=True → M=R·S 繞關節補償版;False → 不補償(繞件中心)負對照版。"""
    out = tempfile.mkdtemp(prefix="pms_")
    summary = build_spine.build(_psd(), out, genre=GENRE, animate=True, scale_pivot=scale_pivot)
    skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    return skel, summary


def _R(deg):
    r = math.radians(deg); c, s = math.cos(r), math.sin(r)
    return np.array([[c, -s], [s, c]])


def _world(local, O, rot, sc, tr, t):
    ang = spine_anim._interp(rot, t, ["angle"])["angle"] if rot else 0.0
    if sc:
        sd = spine_anim._interp(sc, t, ["x", "y"]); sx, sy = sd["x"], sd["y"]
    else:
        sx = sy = 1.0
    if tr:
        td = spine_anim._interp(tr, t, ["x", "y"]); tx, ty = td["x"], td["y"]
    else:
        tx = ty = 0.0
    O = np.asarray(O, float)
    M = _R(ang) @ np.diag([sx, sy])
    return (O + np.array([tx, ty])) + M @ np.asarray(local, float)


def _tspan(chans):
    """節拍中此 bone 任一通道的時間跨度。"""
    t0, t1 = None, None
    for ch in ("rotate", "scale", "translate"):
        fr = chans.get(ch)
        if fr:
            a, b = fr[0]["time"], fr[-1]["time"]
            t0 = a if t0 is None else min(t0, a)
            t1 = b if t1 is None else max(t1, b)
    return t0, t1


def _dense(t0, t1, n=200):
    return [t0 + (t1 - t0) * i / n for i in range(n + 1)]


def _mainshow_beats(skel):
    """skeleton 內 cat ∈ ROT_SCALE_MAIN 的主秀節拍名(端到端存在者)。"""
    out = []
    for name in skel.get("animations", {}):
        if beat_category(name) in ROT_SCALE_MAIN:
            out.append(name)
    return out


def _channels_equal(a, b):
    """兩個 bone channels dict 逐位元相等(JSON 正規化比對)。"""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results, detail = {}, {}
    print("=" * 74)
    print("candidate (G-2) — 主秀節拍下 limb 繞關節 pivot 旋轉+縮放 整合閘")
    print("=" * 74)

    comp, csum = _build(scale_pivot=True)
    raw, _ = _build(scale_pivot=False)

    centers = {b: tuple(v) for b, v in csum.get("pivot_centers", {}).items()}
    joints = {b: tuple(v) for b, v in csum.get("pivot_joints", {}).items()}
    # 有關節(中心≠關節)的 limb/head bone
    jointed = {b: (np.array(centers[b]), np.array(joints[b]))
               for b in joints
               if b in centers and math.hypot(centers[b][0] - joints[b][0],
                                              centers[b][1] - joints[b][1]) >= JOINT_MIN}
    beats = _mainshow_beats(comp)
    print(f"\npivot_centers={len(centers)}  pivot_joints={len(joints)}  有關節 limb/head={list(jointed)}")
    print(f"旋轉/縮放主秀節拍(cat∈MAIN_SHOW−SHEAR)= {beats}")
    detail["jointed"] = {b: {"O": centers[b], "P": joints[b]} for b in jointed}
    detail["beats"] = beats

    # ---------- M1 present + routing + 零回歸 ----------
    m1 = bool(centers) and bool(joints) and bool(jointed) and bool(beats)
    # 非關節件不在 pivot_joints(光暈=特效、身體=root 皆無接觸縫 → 不該有關節)
    non_joint_ok = ("b_光暈" not in joints) and ("b_身體" not in joints)
    # 每個主秀節拍皆有 ≥1 有關節 limb bone 帶 rotate/scale + 被補償(有 translate)
    per_beat_has_limb = True
    for beat in beats:
        bones = comp["animations"][beat]["bones"]
        hit_any = False
        for b in jointed:
            ch = bones.get(b, {})
            if (ch.get("rotate") or ch.get("scale")) and ch.get("translate"):
                hit_any = True
                break
        per_beat_has_limb &= hit_any
    # scale-pivot 版結構節拍仍 finite(無回歸)
    struct_finite = all(spine_anim.all_finite(comp["animations"][n])
                        for n in ("In", "Loop", "Out") if n in comp["animations"])
    m1 = m1 and non_joint_ok and per_beat_has_limb and struct_finite
    results["M1_present_routing"] = m1
    print(f"\n[M1] 有關節集合非空={bool(jointed)}  非關節件無關節={non_joint_ok}  "
          f"每主秀節拍有補償 limb={per_beat_has_limb}  結構節拍 finite={struct_finite}  → {m1}")

    # ---------- M2 crux 繞關節不動點 / M3 neg-control ----------
    worst_fix = 0.0
    worst_move_min = 1e9
    worst_neg_min = 1e9
    worst_ratio_min = 1e9
    pair_rows = []
    for beat in beats:
        cb = comp["animations"][beat]["bones"]
        rb = raw["animations"][beat]["bones"]
        for b, (O, P) in jointed.items():
            ch = cb.get(b, {})
            if not (ch.get("rotate") or ch.get("scale")):
                continue
            ell = P - O
            t0, t1 = _tspan(ch)
            ts = _dense(t0, t1)
            rot, sc, tr = ch.get("rotate"), ch.get("scale"), ch.get("translate")
            fix = max(np.linalg.norm(_world(ell, O, rot, sc, tr, t) - P) for t in ts)
            move = max(np.linalg.norm(_world(FAR, O, rot, sc, tr, t)
                                      - _world(FAR, O, rot, sc, tr, t0)) for t in ts)
            # 負對照:不補償版(繞件中心,無補償 translate)
            rch = rb.get(b, {})
            rrot, rsc, rtr = rch.get("rotate"), rch.get("scale"), rch.get("translate")
            neg = max(np.linalg.norm(_world(ell, O, rrot, rsc, rtr, t) - P) for t in ts)
            ratio = neg / fix if fix > 1e-9 else float("inf")
            worst_fix = max(worst_fix, fix)
            worst_move_min = min(worst_move_min, move)
            worst_neg_min = min(worst_neg_min, neg)
            worst_ratio_min = min(worst_ratio_min, ratio)
            pair_rows.append(dict(beat=beat, bone=b, fix=round(fix, 4),
                                  move=round(move, 2), neg=round(neg, 2),
                                  ratio=round(ratio, 1)))
    detail["pairs"] = pair_rows
    worst_neg_max = max((r["neg"] for r in pair_rows), default=0.0)
    m2 = (worst_fix < TOL_FIX) and (worst_move_min >= MIN_MOVE)
    # 主判準 = 逐 pair 比值(補償把關節運動砍 ≥20×,處處成立);量級floor只對最差 pair(明顯大)。
    m3 = (worst_ratio_min >= NEG_RATIO) and (worst_neg_max >= MIN_NEG)
    results["M2_about_joint_fixed"] = m2
    results["M3_negctrl_about_center"] = m3
    print(f"\n[M2] crux 繞關節: 最差不動點殘差={worst_fix:.4f}px (< {TOL_FIX})  "
          f"最小件位移={worst_move_min:.2f}px (≥ {MIN_MOVE})  → {m2}")
    print(f"[M3] 負對照繞件中心: 逐 pair 最小比值={worst_ratio_min:.1f}× (≥ {NEG_RATIO})  "
          f"最大位移={worst_neg_max:.2f}px (≥ {MIN_NEG})  → {m3}")
    print(f"     ({len(pair_rows)} 組 pair:主秀節拍 × 有關節 limb)")

    # ---------- M4 identity 介面(只在不補償版該端點本就 setup identity 時要求補償版亦 identity)----------
    _SPECS = (("rotate", 0.0, ("angle",)), ("scale", 1.0, ("x", "y")),
              ("translate", 0.0, ("x", "y")))

    def _endpoint_identity(bones, b, idx):
        """bone b 在端點 idx(0 或 -1)是否為 setup identity(所有出席通道該端點≈ident)。回 (is_ident, worst_dev)。"""
        ch = bones.get(b, {})
        worst = 0.0
        for key, ident, fields in _SPECS:
            fr = ch.get(key)
            if not fr:
                continue
            for f in fields:
                worst = max(worst, abs(fr[idx][f] - ident))
        return worst < TOL_IDENT, worst

    worst_ident = 0.0
    checked = 0
    for beat in beats:
        cb = comp["animations"][beat]["bones"]
        rb = raw["animations"][beat]["bones"]
        for b in jointed:
            for idx in (0, -1):
                raw_ident, _ = _endpoint_identity(rb, b, idx)
                if not raw_ident:
                    continue        # 節拍本就在此端點非 setup(如 burst 首塌陷)→ 不要求補償版 identity(M2 保證關節仍不動)
                comp_ident, dev = _endpoint_identity(cb, b, idx)
                worst_ident = max(worst_ident, dev)
                checked += 1
    m4 = (checked > 0) and (worst_ident < TOL_IDENT)
    results["M4_identity_interface"] = m4
    print(f"\n[M4] 保設定姿勢: {checked} 個靜止端點,補償後最差偏差={worst_ident:.2e} (< {TOL_IDENT})  → {m4}")

    # ---------- M5 isolation + 正確轉換集合 ----------
    # (a) 非關節件逐位元相同;(b) 兩版有差異的 bone 集合 == 恰好有關節 limb 集合
    iso_ok = True
    conv_correct = True
    non_joint_bones = {"b_光暈", "b_身體"}
    for beat in beats:
        cb = comp["animations"][beat]["bones"]
        rb = raw["animations"][beat]["bones"]
        for b in non_joint_bones:
            if b in cb or b in rb:
                if not _channels_equal(cb.get(b, {}), rb.get(b, {})):
                    iso_ok = False
        diff = {b for b in set(cb) | set(rb) if not _channels_equal(cb.get(b, {}), rb.get(b, {}))}
        expect = {b for b in jointed if (cb.get(b, {}).get("rotate") or cb.get(b, {}).get("scale"))}
        if diff != expect:
            conv_correct = False
            detail.setdefault("conv_mismatch", {})[beat] = {
                "diff": sorted(diff), "expect": sorted(expect)}
    m5 = iso_ok and conv_correct
    results["M5_isolation_scope"] = m5
    print(f"\n[M5] 非關節件逐位元相同={iso_ok}  有差異集合==有關節 limb 集合={conv_correct}  → {m5}")

    print("\n" + "-" * 74)
    for k, v in results.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    overall = all(results.values())
    print("-" * 74)
    print("OVERALL:", "PASS ✅" if overall else "FAIL ❌")
    if args.json:
        print(json.dumps({"results": results, "detail": detail}, ensure_ascii=False, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
