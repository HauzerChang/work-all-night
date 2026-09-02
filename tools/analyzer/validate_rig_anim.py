#!/usr/bin/env python3
"""S1×S5 端到端閘 —— 證「**分鏡生成的 keyframe** 讓肢體繞 **S5 推得的接觸縫關節** 旋轉」。

背景(closed loop):
  - S1 (candidate 0d) `gen_animations`:把分鏡 role×beat 確定性轉成 bone rotate/translate/scale。
  - S5 `build_spine --rig`:把「關節=父子件接觸縫」寫成子骨世界原點(pivot→bone 樹)。
  兩者各自已驗(validate_anim / validate_rig_build),但**併用**(`--rig --animate`)從未被當作一個單元驗過:
  沒人證明**生成的動畫幀**真的讓肢體繞「推得的關節」轉(而非件中心)。本閘補這個缺口。

與 validate_rig_build 的差異(為何不是重複):
  validate_rig_build 用**手設 25°**測關節語意;本閘的旋轉角**一律取自 gen_animations 產出的真實
  keyframe**(經 spine_anim 取樣),並用**完整 Spine bone world transform 組合**(weighted_deform_eval)
  算動畫後世界點 —— 驗的是「S1 生成器 → S5 rig 骨 → 世界姿勢」這條**整條管線**,能抓 rig_build 的
  純幾何解析式抓不到的整合 bug(動畫掛錯骨、rig 骨原點與關節不符、取樣器與骨變換不一致)。

AC(對 Award 機器人 robot_parts;struct 子件=右手/左手/頭,皆 region+joint):
  AC1 動畫真的驅動關節肢體:`--rig --animate` 產出有限、well-formed 的 animations;每個結構肢體骨
      在某 beat 有非零 rotate(peak |θ|≥ 門檻)→ 生成器確有讓 rig 上的關節肢體旋轉。
  AC2 無縫介面在 rig build 上保持(回歸):每個 beat 的 setup 介面時刻(In 尾/Loop 首尾/Out 首),
      **組合世界點**≈ setup 世界點 → rig 沒破壞可無縫串接性。
  AC3 關節樞紐語意(核心,端到端組合變換):對每個結構肢體,取其 **Loop peak-rotate 幀**(純 rotate,
      無 translate/scale 混淆),追蹤「關節材質點 J」經各自 limb 骨的組合世界變換後,相對「隨 body 剛性
      帶動的關節位置 J_body」的**撕裂量**。rig(limb 骨原點=J、掛 body)→ J 隨 body 走、撕裂≈0;
      flat(limb 骨在件中心)→ J 甩離 body、撕裂大。要求 rig_tear<EPS 且 ratio=flat/rig>門檻。
  AC4 鑑別力/歸因:①在**零旋轉介面幀**(Loop t=0,θ=0)rig/flat 撕裂皆≈0 → AC3 撕裂確由生成 keyframe
      的旋轉造成,非固定偏移;②「若改用件中心當 pivot」的解析式撕裂 |J−C|·2sin(θ/2)(θ=取樣角、C=件
      中心)顯著 > rig_tear≈0 → 量化證明 rig 恰繞「推得的關節 J」轉而非件中心。

真相來源:build_spine 自身確定性 rig(接觸縫=infer_pivots,對藝術家真值已驗)+ gen_animations 自身
生成的 keyframe + Spine 3.8 bone world transform(weighted_deform_eval,對 Award 真值重現)。純 CPU。
一鍵:`python3 tools/analyzer/validate_rig_anim.py`(exit 0 = PASS)。
"""
import sys, os, json, argparse, tempfile, shutil
import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "mesh_gen"))
import weighted_deform_eval as wde   # noqa: E402
import build_spine as bs             # noqa: E402
import spine_anim as sa              # noqa: E402
from validate_rig_build import _slot_bone, _part_world_points, _load  # noqa: E402

EPS_IFACE = 0.5     # setup 介面世界點容差(px)
PEAK_MIN = 3.0      # AC1:結構肢體骨 peak |rotate| 至少(度)
EPS_TEAR = 0.5      # AC3:rig 的關節撕裂上限(px;理論=0)
MIN_TEAR = 2.0      # AC3:flat 撕裂 / 件中心 pivot 解析撕裂 至少(px,確保訊號有意義)
RATIO_MIN = 4.0     # AC3/AC4:flat(或件中心解析)撕裂 / rig 撕裂 比至少
EPS_ZERO = 0.2      # AC4:零旋轉介面幀撕裂上限(px)


def _animated_world(bones, byname, order, anim, t):
    """在時間 t 取樣 anim,把通道疊到 setup local 上,回傳組合後的 world transforms。"""
    pose = sa.sample(anim, t)["bones"]
    local_pose = {}
    for name in order:
        d = pose.get(name)
        if d is None:
            continue                              # 該骨無 timeline → 用 setup
        b = byname[name]
        x = b.get("x", 0.0) + d["x"]
        y = b.get("y", 0.0) + d["y"]
        rot = b.get("rotation", 0.0) + d["rotate"]
        sx = b.get("scaleX", 1.0) * d["scaleX"]
        sy = b.get("scaleY", 1.0) * d["scaleY"]
        local_pose[name] = (x, y, rot, sx, sy)
    return wde.bone_world_transforms(bones, byname, order, local_pose)


def _peak_rotate_time(anim, bone, n=200):
    """回傳 (peak_time, peak_angle):bone 在 anim 內 |rotate| 最大的時刻。"""
    dur = sa.duration(anim)
    best_t, best_a = 0.0, 0.0
    for i in range(n + 1):
        t = dur * i / n
        a = sa.sample(anim, t)["bones"].get(bone, {}).get("rotate", 0.0)
        if abs(a) > abs(best_a):
            best_a, best_t = a, t
    return best_t, best_a


def evaluate(psd="assets/robot_parts.psd", genre="slot_bigwin", verbose=True):
    tmp = tempfile.mkdtemp(prefix="riganim_")
    try:
        rig_dir = os.path.join(tmp, "rig")
        flat_dir = os.path.join(tmp, "flat")
        summ = bs.build(psd, rig_dir, genre, rig=True, animate=True)
        bs.build(psd, flat_dir, genre, rig=False, animate=True)   # 非 rig 對照(同 keyframe、骨在件中心)

        skR, bonesR, bynameR, orderR, attsR, worldR0, metaR = _load(rig_dir)
        skF, bonesF, bynameF, orderF, attsF, worldF0, metaF = _load(flat_dir)
        sbR, sbF = _slot_bone(skR), _slot_bone(skF)
        animsR, animsF = skR["animations"], skF["animations"]
        body = summ["rig_root"][2:]
        struct = [nm for nm in metaR if metaR[nm].get("joint")]     # 結構肢體(有關節)

        # ================= AC1 動畫驅動關節肢體 =================
        finite = all(sa.all_finite(a) for a in animsR.values()) and len(animsR) > 0
        # 每骨都指向存在的 bone
        bone_names = {b["name"] for b in bonesR}
        targets_ok = all(bn in bone_names for a in animsR.values() for bn in a.get("bones", {}))
        peaks = {}
        for nm in struct:
            bn = f"b_{nm}"
            mx = 0.0
            for a in animsR.values():
                _, ang = _peak_rotate_time(a, bn)
                if abs(ang) > abs(mx):
                    mx = ang
            peaks[nm] = mx
        ac1 = finite and targets_ok and all(abs(peaks[nm]) >= PEAK_MIN for nm in struct)

        # ================= AC2 無縫介面(rig build 上回歸)=================
        # 每 beat 的 setup 介面時刻。In→尾;Loop→首尾;Out→首;其餘(hold/pulse/hit/reveal)→首尾。
        iface = {}
        for name, a in animsR.items():
            dur = sa.duration(a)
            low = name.lower()
            if low in ("in",) or "intro" in low or low == "in":
                iface[name] = [dur]
            elif low in ("out",):
                iface[name] = [0.0]
            else:
                iface[name] = [0.0, dur]
        max_iface_dev = 0.0
        for name, times in iface.items():
            for t in times:
                w = _animated_world(bonesR, bynameR, orderR, animsR[name], t)
                for nm in [s["name"] for s in skR["slots"]]:
                    Pa = _part_world_points(skR, attsR, w, sbR, nm)
                    P0 = _part_world_points(skR, attsR, worldR0, sbR, nm)
                    max_iface_dev = max(max_iface_dev, float(np.max(np.linalg.norm(Pa - P0, axis=1))))
        ac2 = max_iface_dev < EPS_IFACE

        # ================= AC3 關節樞紐語意(核心,Loop 純 rotate 幀)=================
        # 追蹤「關節材質點 J」:rig limb 骨原點就在 J、掛 body → J 隨 body 剛性帶動(撕裂≈0);
        # flat limb 骨在件中心 C、掛 root → 繞 C 轉時 J 甩離 body(撕裂大)。以「隨 body 帶動的 J_body」
        # 為忠實參考,量兩版 limb 骨動畫後 J 相對 J_body 的偏差 = 接觸縫撕裂。
        loop_name = next((n for n in animsR if n.lower() in ("loop", "idle")), None)
        body_bone = f"b_{body}"
        rows = []
        for nm in struct:
            bn = f"b_{nm}"
            bf = sbF[nm]
            pt, ang = _peak_rotate_time(animsR[loop_name], bn)
            J = np.array([worldR0[bn][4], worldR0[bn][5]])                    # setup 關節世界點(=rig 骨原點)
            C = np.array([worldF0[bf][4], worldF0[bf][5]])                    # flat 骨原點=件中心
            Jb_local = wde.inverse_transform_point(worldR0[body_bone], J[0], J[1])   # J 於 body 局部
            Jf_local = wde.inverse_transform_point(worldF0[bf], J[0], J[1])          # J 於 flat limb 局部
            wR = _animated_world(bonesR, bynameR, orderR, animsR[loop_name], pt)
            wF = _animated_world(bonesF, bynameF, orderF, animsF[loop_name], pt)
            J_body = np.array(wde.transform_point(wR[body_bone], *Jb_local))  # 忠實:隨 body 帶動的關節
            J_rig = np.array([wR[bn][4], wR[bn][5]])                          # rig:limb 骨原點(=追蹤的 J)
            J_flat = np.array(wde.transform_point(wF[bf], *Jf_local))         # flat:limb 骨帶動的 J
            rig_tear = float(np.linalg.norm(J_rig - J_body))
            flat_tear = float(np.linalg.norm(J_flat - J_body))
            # 「若改用件中心 C 當 pivot」的解析撕裂(繞 C 轉 ang,J 甩動量)
            center_pred = float(np.linalg.norm(J - C) * 2.0 * np.sin(np.radians(abs(ang)) / 2.0))
            ratio = flat_tear / (rig_tear + 1e-9)
            rows.append(dict(nm=nm, ang=ang, rig_tear=rig_tear, flat_tear=flat_tear,
                             center_pred=center_pred, ratio=ratio, JminusC=float(np.linalg.norm(J - C))))
        ac3 = all(r["rig_tear"] < EPS_TEAR and r["flat_tear"] > MIN_TEAR
                  and r["ratio"] > RATIO_MIN for r in rows)

        # ================= AC4 鑑別力/歸因 =================
        # (a) 零旋轉介面幀(Loop t=0,θ=0)rig/flat 撕裂皆≈0
        zero_dev = 0.0
        for nm in struct:
            bn = f"b_{nm}"; bf = sbF[nm]
            J = np.array([worldR0[bn][4], worldR0[bn][5]])
            Jb_local = wde.inverse_transform_point(worldR0[body_bone], J[0], J[1])
            Jf_local = wde.inverse_transform_point(worldF0[bf], J[0], J[1])
            wR = _animated_world(bonesR, bynameR, orderR, animsR[loop_name], 0.0)
            wF = _animated_world(bonesF, bynameF, orderF, animsF[loop_name], 0.0)
            J_body = np.array(wde.transform_point(wR[body_bone], *Jb_local))
            J_rig = np.array([wR[bn][4], wR[bn][5]])
            J_flat = np.array(wde.transform_point(wF[bf], *Jf_local))
            zero_dev = max(zero_dev, float(np.linalg.norm(J_rig - J_body)),
                           float(np.linalg.norm(J_flat - J_body)))
        ac4a = zero_dev < EPS_ZERO
        # (b) 件中心 pivot 解析撕裂顯著 > rig_tear≈0(量化:rig 恰繞關節非件中心)
        ac4b = all(r["center_pred"] > MIN_TEAR and r["center_pred"] / (r["rig_tear"] + 1e-9) > RATIO_MIN
                   for r in rows)
        ac4 = ac4a and ac4b

        if verbose:
            print(f"rig_root = {summ['rig_root']}   結構肢體 = {struct}   loop='{loop_name}'")
            print(f"AC1 動畫驅動關節肢體  peaks(°)={ {k: round(v,1) for k,v in peaks.items()} } "
                  f"(each ≥{PEAK_MIN}, finite&targets_ok={finite and targets_ok}) -> {'PASS' if ac1 else 'FAIL'}")
            print(f"AC2 無縫介面(rig)  max_dev={max_iface_dev:.4f}px (<{EPS_IFACE}) -> {'PASS' if ac2 else 'FAIL'}")
            print(f"AC3 關節樞紐語意(Loop peak-rotate 純 rotate 幀,端到端組合變換,關節撕裂):")
            for r in rows:
                rs = ">1e6" if r["ratio"] > 1e6 else f"{r['ratio']:.0f}"
                print(f"    {r['nm']}: θ={r['ang']:+.1f}°  |J−C|={r['JminusC']:.0f}px  "
                      f"rig_tear={r['rig_tear']:.4f}px(<{EPS_TEAR})  flat_tear={r['flat_tear']:.2f}px(>{MIN_TEAR})  "
                      f"ratio(flat/rig)={rs}(>{RATIO_MIN})")
            print(f"    -> {'PASS' if ac3 else 'FAIL'}")
            print(f"AC4 鑑別力/歸因: (a)零旋轉幀撕裂 max={zero_dev:.4f}px(<{EPS_ZERO}) "
                  f"(b)件中心 pivot 解析撕裂={[round(r['center_pred'],1) for r in rows]}px ≫ rig_tear≈0 "
                  f"-> {'PASS' if ac4 else 'FAIL'}")

        overall = ac1 and ac2 and ac3 and ac4
        return dict(ac1=ac1, ac2=ac2, ac3=ac3, ac4=ac4, overall=overall,
                    peaks=peaks, max_iface_dev=max_iface_dev, zero_dev=zero_dev,
                    rows=rows, struct=struct, rig_root=summ["rig_root"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    print("=" * 74)
    print("S1×S5 端到端閘 —— 分鏡生成 keyframe × 推得接觸縫關節(build_spine --rig --animate)")
    print("=" * 74)
    r = evaluate(a.psd, a.genre, verbose=True)
    print("\n" + "=" * 74)
    print(f"OVERALL: {'PASS ✅' if r['overall'] else 'FAIL ❌'}  "
          f"(AC1={r['ac1']} AC2={r['ac2']} AC3={r['ac3']} AC4={r['ac4']})")
    print("=" * 74)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, default=float, indent=2))
    return 0 if r["overall"] else 1


if __name__ == "__main__":
    sys.exit(main())
