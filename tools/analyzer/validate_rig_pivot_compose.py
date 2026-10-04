#!/usr/bin/env python3
"""candidate (G-1) 自我驗收閘 — `--rig`(S5 結構搬骨)× keyframe-pivot(S1 `--pivot-rotate`/`--scale-pivot`)
組合正確性(整合閘,純 CPU)。

背景(長期掛在 STATE「下一步」的 (G-1)):
  `build_spine` 對「件繞關節 pivot」有**兩條**機制,分屬兩個能力階段:
    - **S5 `--rig`**:把關節 limb 的 **bone 原點搬到接觸縫(關節)**,並以父子樹(limb 掛 body)結構性帶動。
      limb 的 rotate/scale 是 Spine bone 的自身變換,**本就繞 bone 原點** → bone 原點在關節 ⇒ **結構性繞關節**。
    - **S1 keyframe-pivot(`--pivot-rotate`/`--scale-pivot`)**:bone 原點仍在**件中心**,靠逐幀補償
      translate `Δ=(M−I)(O−P)`(O=件中心、P=關節)把旋轉/縮放的不動點從件中心移到關節 → **keyframe 繞關節**。
  兩者達成**同一幾何目標**(limb 繞關節動),機制不同(結構搬骨 vs 關鍵幀補償),故**不可疊加**
  —— 疊加會雙重補償。`build_spine.py` 以 `(pivot_rotate or scale_pivot or shear_pivot) and not rig`
  全域守衛**擇一**(rig 時跳過 keyframe 補償)。

  STATE (G-1) 原想的「per-bone 語意去重」(effect 件在 rig 下掛 root/body 仍可受惠 pivot-rotate)經本閘查證
  **為非議題**:effect 件(光暈)無接觸縫 → `rlay[nm]["joint"]==False` → **不在** `pivot_of`/`rig_joints`
  **任一機制**的關節集合 → **兩機制都不對它做 pivot 補償**(它恆繞件中心)。故無「per-bone 路由」可做;
  (G-1) 的真正內容 = 把這條組合正確性釘成**回歸閘**(呼應 (G-2) 整合閘精神、RULES「每能力必配評估器」)。

本閘產**三版**真實 `build_spine --animate` robot 骨架:
    RIG   = `--rig`        (結構搬骨;limb bone 原點在關節、無補償 translate)
    PIVOT = `--scale-pivot`(keyframe 補償;繞關節,= (G-2) comp 版)
    NAIVE = 無 pivot 旗標   (繞件中心,負對照基線)
並驗:兩機制各自把 limb 旋轉中心落在**同一關節**(等價)、**疊加會雙重補償**(守衛必要)、
非關節件在兩機制下**一致不受 pivot 補償**(honest 解答 G-1 原議題)。

世界變換模型(PIVOT 版,Spine root 子 bone):world(ℓ,t)=(O+T(t))+R(θ)·diag(sx,sy)·ℓ;繞 pivot 後 world(P−O,t)≡P。
RIG 版 limb 為 body 子;其自身 rotate/scale 繞 bone 原點,原點(setup 世界)== 關節 → 結構性繞關節
(本閘以「bone 原點世界==關節 且 無 translate 通道」釘此結構事實,不需密集取樣)。

AC(客觀、可量測):
  R1 present + joint-set 一致 + routing : 三版 build 皆成功;RIG `rig_joints` 鍵 == PIVOT `pivot_joints` 鍵
                                        (同一 S5 幾何推得同組關節 limb)且世界座標一致(≤TOL_JOINT);非關節件
                                        (光暈/身體)**不在**任一關節集合;每個旋轉/縮放主秀節拍(hit/combo/
                                        charge/burst/cascade)在 RIG 與 PIVOT 兩版皆動 ≥1 關節 limb。
  R2 crux — 機制等價(皆繞關節)        : (rig 側)每關節 limb bone parent==b_身體(結構鏈非 root)、世界 bone
                                        原點==關節(≤TOL_JOINT)、且**無 translate 通道**(自身變換繞原點=繞關節);
                                        (pivot 側)每(主秀節拍×關節 limb)補償後關節不動點殘差 <TOL_FIX(重算 (G-2))。
                                        ⇒ 兩機制皆把 limb 旋轉中心落在關節 → 冗餘 → 擇一正確。
  R3 crux neg-control — 疊加雙重補償    : 對 RIG 動畫副本跑 `apply_pivots`(餵件中心 O + 關節 P)→ 對關節 limb
                                        注入**假** translate(max|Δ| ≥ MIN_DOUBLE px);其在 body-local 把關節點
                                        推離 P(殘差 == 該 |Δ|)→ 證疊加**真的**破壞不動點、守衛(`not rig`)必要;
                                        且真實 RIG(未疊加)關節 limb **無** translate(守衛在產線確實成立)。
  R4 isolation — 非關節件兩機制一致      : 非關節件(光暈=effect/身體=root-ish body)在 RIG 為 joint==False
                                        (bone 在件中心、掛 body/root、無 pivot)、在 PIVOT 不在 pivot_joints
                                        (無 keyframe 補償)→ **兩機制皆不對其做 pivot 補償**(恆繞件中心)。
                                        honest 證 (G-1) 原想的「effect 在 rig 受惠 pivot」不適用(無關節 pivot 可繞)。

用法:
  python3 validate_rig_pivot_compose.py            # 摘要
  python3 validate_rig_pivot_compose.py --json     # 完整 JSON
"""
import argparse, copy, json, math, os, sys, tempfile

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rig"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim
import build_spine
from pivot_rotation import apply_pivots
from gen_animations import beat_category
from tier_variants import MAIN_SHOW_CATS, SHEAR_CATS

ROT_SCALE_MAIN = MAIN_SHOW_CATS - SHEAR_CATS      # hit/combo/charge/burst/cascade(shear 節拍另由他閘覆蓋)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"

TOL_JOINT = 0.2     # px,兩機制關節世界座標 / rig bone 原點==關節 容忍
TOL_FIX = 0.5       # px,pivot 版繞關節不動點逐幀殘差上限(同 (G-2))
MIN_DOUBLE = 8.0    # px,疊加注入的假 translate 下限(證雙重補償量級明顯)
NON_JOINT = ("b_光暈", "b_身體")   # 非關節件(effect / body;無接觸縫)


def _psd():
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (PSD, os.path.join(here, "..", "..", PSD)):
        if os.path.exists(cand):
            return cand
    raise FileNotFoundError(PSD)


def _build(**kw):
    out = tempfile.mkdtemp(prefix="rpc_")
    summary = build_spine.build(_psd(), out, genre=GENRE, animate=True, **kw)
    skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    return skel, summary


def _R(deg):
    r = math.radians(deg); c, s = math.cos(r), math.sin(r)
    return np.array([[c, -s], [s, c]])


def _world(local, O, rot, sc, tr, t):
    """PIVOT 版(root 子 bone)世界變換,同 (G-2) `validate_pivot_main_show._world`。"""
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
    return [n for n in skel.get("animations", {}) if beat_category(n) in ROT_SCALE_MAIN]


def _bone_map(skel):
    return {b["name"]: b for b in skel["bones"]}


def _world_origin(bmap, name):
    """沿父鏈累加 setup bone 原點(setup rot0/scale1 → 僅平移鏈,給 rig limb 的關節世界座標)。"""
    w = np.zeros(2)
    while name:
        b = bmap.get(name)
        if b is None:
            break
        w = w + np.array([b.get("x") or 0.0, b.get("y") or 0.0])
        name = b.get("parent")
    return w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results, detail = {}, {}
    print("=" * 74)
    print("candidate (G-1) — rig × keyframe-pivot 組合正確性 整合閘")
    print("=" * 74)

    rig, rsum = _build(rig=True)
    comp, csum = _build(scale_pivot=True)
    naive, _ = _build()                      # 無 pivot 旗標(負對照基線,供 routing 對照)

    rig_joints = {b: tuple(v) for b, v in rsum.get("rig_joints", {}).items()}
    piv_joints = {b: tuple(v) for b, v in csum.get("pivot_joints", {}).items()}
    centers = {b: tuple(v) for b, v in csum.get("pivot_centers", {}).items()}
    beats = _mainshow_beats(comp)
    rbmap = _bone_map(rig)
    print(f"\nrig_joints={list(rig_joints)}  pivot_joints={list(piv_joints)}")
    print(f"旋轉/縮放主秀節拍(cat∈MAIN_SHOW−SHEAR)= {beats}")
    detail["rig_joints"] = {b: list(v) for b, v in rig_joints.items()}
    detail["pivot_joints"] = {b: list(v) for b, v in piv_joints.items()}
    detail["beats"] = beats

    # ---------- R1 present + joint-set 一致 + routing ----------
    set_match = set(rig_joints) == set(piv_joints) and bool(rig_joints)
    coord_match = all(
        b in rig_joints and math.hypot(rig_joints[b][0] - piv_joints[b][0],
                                       rig_joints[b][1] - piv_joints[b][1]) <= TOL_JOINT
        for b in piv_joints)
    non_joint_excluded = all(b not in rig_joints and b not in piv_joints for b in NON_JOINT)
    per_beat_routed = True
    for beat in beats:
        rb = rig["animations"].get(beat, {}).get("bones", {})
        cb = comp["animations"].get(beat, {}).get("bones", {})
        rig_hit = any((rb.get(b, {}).get("rotate") or rb.get(b, {}).get("scale")) for b in rig_joints)
        piv_hit = any((cb.get(b, {}).get("rotate") or cb.get(b, {}).get("scale")) for b in piv_joints)
        per_beat_routed &= (rig_hit and piv_hit)
    r1 = bool(beats) and set_match and coord_match and non_joint_excluded and per_beat_routed
    results["R1_present_jointset_routing"] = r1
    print(f"\n[R1] joint-set 一致={set_match} 座標一致={coord_match} 非關節件排除={non_joint_excluded} "
          f"每主秀節拍兩版皆動 limb={per_beat_routed} → {r1}")

    # ---------- R2 crux 機制等價(皆繞關節)----------
    # rig 側:結構搬骨——parent==body、世界 bone 原點==關節、無 translate 通道。
    rig_struct_ok = True
    rig_rows = []
    for b, P in rig_joints.items():
        bone = rbmap.get(b, {})
        parent_ok = bone.get("parent") == "b_身體"
        worg = _world_origin(rbmap, b)
        org_ok = math.hypot(worg[0] - P[0], worg[1] - P[1]) <= TOL_JOINT
        no_tr = all("translate" not in rig["animations"][beat]["bones"].get(b, {})
                    for beat in beats if b in rig["animations"][beat]["bones"])
        rig_struct_ok &= (parent_ok and org_ok and no_tr)
        rig_rows.append(dict(bone=b, parent=bone.get("parent"),
                             origin_world=[round(worg[0], 2), round(worg[1], 2)],
                             joint=list(P), origin_eq_joint=org_ok, no_translate=no_tr))
    detail["rig_structural"] = rig_rows
    # pivot 側:重算 (G-2) 補償後繞關節不動點殘差 <TOL_FIX。
    worst_fix = 0.0
    piv_rows = []
    for beat in beats:
        cb = comp["animations"][beat]["bones"]
        for b, P in piv_joints.items():
            if b not in centers:
                continue
            ch = cb.get(b, {})
            if not (ch.get("rotate") or ch.get("scale")):
                continue
            O = np.array(centers[b]); Pv = np.array(P)
            ell = Pv - O
            t0, t1 = _tspan(ch)
            ts = _dense(t0, t1)
            rot, sc, tr = ch.get("rotate"), ch.get("scale"), ch.get("translate")
            fix = max(np.linalg.norm(_world(ell, O, rot, sc, tr, t) - Pv) for t in ts)
            worst_fix = max(worst_fix, fix)
            piv_rows.append(dict(beat=beat, bone=b, fix=round(fix, 4)))
    detail["pivot_residual"] = piv_rows
    r2 = rig_struct_ok and (worst_fix < TOL_FIX) and bool(piv_rows)
    results["R2_mechanism_equivalence"] = r2
    print(f"[R2] rig 結構繞關節(parent/origin==joint/no-translate)={rig_struct_ok}  "
          f"pivot 補償最差殘差={worst_fix:.4f}px (< {TOL_FIX}) → {r2}")

    # ---------- R3 crux neg-control 疊加雙重補償 ----------
    # 真實 RIG 關節 limb 無 translate(守衛在產線成立);對 RIG 副本跑 apply_pivots → 注入假 translate。
    real_rig_no_tr = all(
        all("translate" not in rig["animations"][beat]["bones"].get(b, {})
            for beat in beats if b in rig["animations"][beat]["bones"])
        for b in rig_joints)
    worst_double = 0.0
    dbl_rows = []
    bone_origin = {b: centers[b] for b in centers}           # apply_pivots 以為 bone 在件中心 O
    pivot_of = {b: piv_joints[b] for b in piv_joints}         # 關節 P
    for beat in beats:
        stacked = copy.deepcopy(rig["animations"][beat])
        apply_pivots(stacked, bone_origin, pivot_of, include_scale=True)
        for b in rig_joints:
            tr = stacked["bones"].get(b, {}).get("translate")
            maxtr = max((math.hypot(k["x"], k["y"]) for k in tr), default=0.0) if tr else 0.0
            worst_double = max(worst_double, maxtr)
            if tr:
                dbl_rows.append(dict(beat=beat, bone=b, injected=round(maxtr, 2)))
    detail["double_comp"] = dbl_rows
    r3 = real_rig_no_tr and (worst_double >= MIN_DOUBLE)
    results["R3_negctrl_double_comp"] = r3
    print(f"[R3] 真實 rig 無 translate(守衛成立)={real_rig_no_tr}  "
          f"疊加注入假 translate max={worst_double:.1f}px (≥ {MIN_DOUBLE}) → {r3}")

    # ---------- R4 isolation 非關節件兩機制一致(皆不做 pivot 補償)----------
    iso_ok = True
    iso_rows = []
    rig_meta = json.load(open(os.path.join(rsum["out"], "build_meta.json"), encoding="utf-8"))
    for b in NON_JOINT:
        nm = b[2:]                                   # "b_光暈" → "光暈"
        rig_is_joint = bool(rig_meta.get(nm, {}).get("joint", False))   # rig 側:非關節
        piv_has_pivot = b in piv_joints                                 # pivot 側:無 keyframe 補償
        ok = (not rig_is_joint) and (not piv_has_pivot)
        iso_ok &= ok
        iso_rows.append(dict(bone=b, rig_joint=rig_is_joint, pivot_compensated=piv_has_pivot, ok=ok))
    detail["isolation"] = iso_rows
    r4 = iso_ok and bool(iso_rows)
    results["R4_nonjoint_parity"] = r4
    print(f"[R4] 非關節件兩機制皆不做 pivot 補償={iso_ok} → {r4}")

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
