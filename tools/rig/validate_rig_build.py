#!/usr/bin/env python3
"""S5 端到端閘 —— 「接觸縫 pivot 推斷 → 寫入 build_spine 關節骨樹」的自我品質閘。

補上 `spine-rig-pivot` 區塊 `pivot_end2end`(原 L0)的空白:證明 pivot 不只是一個數字,
而是**真的被寫進可載入 Spine 的骨樹**,且該骨樹在 setup 不變、關節能正確帶動肢體。

流程:對 robot_parts.psd 跑 `build_spine --rig`(joint 骨置於接觸縫 pivot、render 骨掛其下、
attachment 相對件中心不動)+ 同資產非 rig build,再用 weighted_deform_eval 的 Spine 3.8 前向
運動學(FK)實算世界座標比對。

四道校驗(客觀、可機讀 pass/fail):
  AC-R1 setup 不變   —— 每件 render 骨 FK 世界位置 == 非 rig build 的件中心(d<0.5px);
                        意即 rig 化未擾動 setup pose,繼承非 rig build 已驗的 round-trip。
  AC-R2 joint 落 pivot —— 每 joint 骨 FK 世界位置 == 推斷的接觸縫 pivot(d<0.5px);emitter 自一致。
  AC-R3 關節帶動肢體  —— 轉 joint θ 後,子件 render 骨繞 pivot 旋轉 θ(半徑守恆、轉角==θ);
                        且父件(body)不受擾動 —— 證明骨樹真的『articulate』。
  AC-R4 pivot 非天真  —— 接觸縫 pivot 顯著異於件中心(med|pivot-center|/rig_scale>0.10),
                        且『繞 pivot』與『繞件中心』對肢體末梢造成顯著不同位移(證明 pivot 落點會改變運動,
                        放對才有意義)。絕對準度由 validate_pivots(同演算法、同美術真值)另行擔保。

誠實界定:本閘驗端到端 emitter 正確性 + 關節帶動語意;pivot 對美術真值的絕對準度由
`validate_pivots.py` 擔保(相同接觸縫演算法)。多 rig 泛化仍待第二個拆件 rig 真值資產(見 knowledge)。
"""
import sys, os, math, json, tempfile, argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "mesh_gen"))
sys.path.insert(0, os.path.join(HERE, "..", "analyzer"))
sys.path.insert(0, HERE)
import weighted_deform_eval as wde   # noqa: E402
import build_spine as bs             # noqa: E402
from infer_pivots import contact_seam_joint  # noqa: E402

TAU_POS = 0.5        # 位置一致性門檻(px)
TAU_ANG = 0.5        # 轉角一致性門檻(度)
THETA = 30.0         # AC-R3 測試旋轉角
MARGIN = 0.10        # AC-R4 pivot 離件中心的最小相對邊際


def fk(build_dir, pose=None):
    sk, bones, byname, order = wde.load_skeleton(os.path.join(build_dir, "skeleton.json"))
    world = wde.bone_world_transforms(bones, byname, order, pose or {})
    return sk, byname, {n: (world[n][4], world[n][5]) for n in world}, world


def bone_local(byname, name):
    b = byname[name]
    return (b.get("x", 0.0), b.get("y", 0.0), b.get("rotation", 0.0),
            b.get("scaleX", 1.0), b.get("scaleY", 1.0))


def evaluate(psd="assets/robot_parts.psd", verbose=True):
    tmp = tempfile.mkdtemp(prefix="rigval_")
    rig_dir = os.path.join(tmp, "rig")
    norig_dir = os.path.join(tmp, "norig")
    bs.build(psd, rig_dir, rig=True)
    bs.build(psd, norig_dir, rig=False)

    rig_meta = json.load(open(os.path.join(rig_dir, "rig_meta.json")))
    joints = rig_meta["joints"]           # child_safe -> {bone, pivot}
    tree = rig_meta["tree"]               # child_safe -> parent_safe
    root_bone = f"b_{rig_meta['root_part']}"

    _, byname, wr, world_r = fk(rig_dir)
    _, _, wn, _ = fk(norig_dir)

    # ---- AC-R1:setup 不變(render 骨世界 == 非 rig)----
    r1_d = {}
    for b in wr:
        if b.startswith("b_") and b in wn:
            r1_d[b] = math.hypot(wr[b][0] - wn[b][0], wr[b][1] - wn[b][1])
    ac1_max = max(r1_d.values())
    ac1 = ac1_max < TAU_POS

    # ---- AC-R2:joint 落 pivot ----
    r2_d = {}
    for c, j in joints.items():
        piv = j["pivot"]; jw = wr[j["bone"]]
        r2_d[c] = math.hypot(jw[0] - piv[0], jw[1] - piv[1])
    ac2_max = max(r2_d.values())
    ac2 = ac2_max < TAU_POS

    # ---- AC-R3:轉 joint θ,子件繞 pivot 旋轉 θ、父件不動 ----
    r3 = {}
    ac3 = True
    for c, j in joints.items():
        jb = j["bone"]; piv = np.array(j["pivot"])
        child_render = f"b_{c}"
        c0 = np.array(wr[child_render])                 # 旋轉前件中心世界
        x, y, rot, sx, sy = bone_local(byname, jb)
        _, _, wp, _ = fk(rig_dir, pose={jb: (x, y, rot + THETA, sx, sy)})
        c1 = np.array(wp[child_render])
        parent_bone = tree[c]                            # parent_safe(== root_part)
        pmoved = math.hypot(wp[f"b_{parent_bone}"][0] - wr[f"b_{parent_bone}"][0],
                            wp[f"b_{parent_bone}"][1] - wr[f"b_{parent_bone}"][1])
        r0 = np.linalg.norm(c0 - piv); r1 = np.linalg.norm(c1 - piv)
        v0 = c0 - piv; v1 = c1 - piv
        ang = math.degrees(math.atan2(v0[0] * v1[1] - v0[1] * v1[0], v0 @ v1))  # signed
        radius_ok = abs(r1 - r0) < TAU_POS
        angle_ok = abs(abs(ang) - THETA) < TAU_ANG
        parent_ok = pmoved < TAU_POS
        r3[c] = dict(radius_err=abs(r1 - r0), angle=ang, parent_moved=pmoved,
                     ok=radius_ok and angle_ok and parent_ok)
        ac3 = ac3 and r3[c]["ok"]

    # ---- AC-R4:pivot 非天真(離件中心)+ 繞 pivot vs 繞件中心對末梢有顯著不同位移 ----
    # rig_scale = body(父件)邊界對角線
    # body 邊界世界多邊形 → 對角線尺度(與 pivot gate 的 rig_scale 一致)
    body_poly = _part_world_poly(rig_dir, rig_meta["root_part"])
    scale = float(np.hypot(*(body_poly.max(0) - body_poly.min(0))))

    r4_center_gap, r4_tip_gap = {}, {}
    for c, j in joints.items():
        piv = np.array(j["pivot"])
        center = np.array(wr[f"b_{c}"])
        r4_center_gap[c] = float(np.linalg.norm(piv - center) / scale)
        # 子件末梢 = 邊界離 pivot 最遠點;比較繞 pivot 與繞件中心旋轉 θ 的落點差
        cpoly = _part_world_poly(rig_dir, c)
        tip = cpoly[np.argmax(np.linalg.norm(cpoly - piv, axis=1))]
        tip_by_pivot = _rot_about(tip, piv, THETA)
        tip_by_center = _rot_about(tip, center, THETA)
        r4_tip_gap[c] = float(np.linalg.norm(tip_by_pivot - tip_by_center) / scale)
    ac4_center = float(np.median(list(r4_center_gap.values()))) > MARGIN
    ac4_tip = float(np.median(list(r4_tip_gap.values()))) > MARGIN
    ac4 = ac4_center and ac4_tip

    if verbose:
        print(f"rig_scale(body diag) = {scale:.1f}px   θ_test={THETA}°")
        print(f"\nAC-R1 setup 不變      max d={ac1_max:.4f}px (<{TAU_POS}) -> {_p(ac1)}")
        for b, d in sorted(r1_d.items()):
            print(f"    {b:10} d={d:.4f}")
        print(f"\nAC-R2 joint 落 pivot  max d={ac2_max:.4f}px (<{TAU_POS}) -> {_p(ac2)}")
        for c, d in r2_d.items():
            print(f"    j_{c:8} d={d:.4f}")
        print(f"\nAC-R3 關節帶動肢體    (轉 joint {THETA}°) -> {_p(ac3)}")
        for c, v in r3.items():
            print(f"    {c:8} radius_err={v['radius_err']:.4f}px  轉角={v['angle']:.3f}°  "
                  f"父件位移={v['parent_moved']:.4f}px  {_p(v['ok'])}")
        print(f"\nAC-R4 pivot 非天真    med|pivot-center|/scale={np.median(list(r4_center_gap.values())):.3f} "
              f"(>{MARGIN}); med tip位移/scale={np.median(list(r4_tip_gap.values())):.3f} (>{MARGIN}) -> {_p(ac4)}")
        for c in joints:
            print(f"    {c:8} center_gap={r4_center_gap[c]:.3f}  tip_gap={r4_tip_gap[c]:.3f}")

    overall = ac1 and ac2 and ac3 and ac4
    return dict(ac1=ac1, ac2=ac2, ac3=ac3, ac4=ac4, overall=overall,
                ac1_max=ac1_max, ac2_max=ac2_max, scale=scale,
                r3=r3, center_gap=r4_center_gap, tip_gap=r4_tip_gap)


def _part_world_poly(build_dir, part_safe):
    """由 build 的 _parts png + manifest 取該件世界邊界多邊形(與 build_spine 同座標約定)。"""
    import cv2
    parts_dir = os.path.join(build_dir, "_parts")
    manifest = json.load(open(os.path.join(parts_dir, "manifest.json")))
    sk = json.load(open(os.path.join(build_dir, "skeleton.json")))
    H = sk["skeleton"]["height"]
    ent = None
    for e in manifest["parts"] if isinstance(manifest, dict) and "parts" in manifest else manifest:
        if bs.safe(e["name"]) == part_safe or e["name"] == part_safe:
            ent = e; break
    if ent is None:
        raise KeyError(part_safe)
    png = os.path.join(parts_dir, ent["file"])
    ox, oy = ent["offset"]
    world, _ = bs._boundary_world(png, ox, oy, H)
    return world


def _rot_about(p, c, deg):
    t = math.radians(deg); ca, sa = math.cos(t), math.sin(t)
    v = np.asarray(p) - np.asarray(c)
    return np.asarray(c) + np.array([ca * v[0] - sa * v[1], sa * v[0] + ca * v[1]])


def _p(b):
    return "PASS" if b else "FAIL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    print("=" * 70)
    print("S5 端到端閘 —— 接觸縫 pivot → build_spine 關節骨樹")
    print("=" * 70)
    r = evaluate(a.psd, verbose=True)
    print("\n" + "=" * 70)
    print(f"OVERALL: {'PASS ✅' if r['overall'] else 'FAIL ❌'}  "
          f"(R1={r['ac1']} R2={r['ac2']} R3={r['ac3']} R4={r['ac4']})")
    print("=" * 70)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, default=float, indent=2))
    return 0 if r["overall"] else 1


if __name__ == "__main__":
    sys.exit(main())
