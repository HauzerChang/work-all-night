"""S5 — `build_spine --rig` 關節鏈的**自我品質閘**(端到端:PSD → 可載入 articulated Spine)。

驗證「把接觸縫 pivot 寫進 build_spine 的骨架」這件事做對了。與 `validate_pivots.py` 互補:
  - `validate_pivots`:接觸縫演算法 vs Award 藝術家真值(pivot 準度)。
  - 本閘:pivot 落進**實際產出的 rig 骨架**後,(1) 不動 setup pose、(2) 子骨真的繞關節轉、
          (3) 父子樹符合 struct_role。以**未 articulate 的同一份 build 當負對照**(繞件中心轉)。

四道校驗(客觀、可機讀 pass/fail):
  AC-R0 可載入/topo —— 骨架 JSON 可解析,且每根骨的 parent 排在它之前(Spine 可安全逐骨算 world)。
  AC-R1 setup 不變 —— 每件 setup pose 世界中心(articulated)== 未 articulate 版(< 0.5px)。
                      證明「加關節鏈」只改 rig 結構、不改素材外觀(round-trip 已由 validate_build 保證)。
  AC-R2 pivot=關節 —— 子骨旋轉 θ 時,關節(接觸縫)點應為不動點:
                      articulated 位移≈0;負對照(骨在件中心)關節點大幅甩開(有鑑別力)。
  AC-R3 父子樹符合語意 —— head/limb 掛 body、body/特效 掛 root,與分析器 struct_role 一致;
                        且確有 ≥2 條關節被建立(防「空樹默默通過」)。

一鍵驗證:`python3 tools/rig/validate_rig.py`(exit 0 = PASS)。
"""
import sys, os, json, math, argparse, tempfile
import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "analyzer"))
sys.path.insert(0, os.path.join(HERE, "..", "mesh_gen"))
import build_spine as bs                 # noqa: E402
import weighted_deform_eval as wde       # noqa: E402
from analyze_target import analyze       # noqa: E402

THETA = 30.0        # 測試旋轉角(度)
INVAR_TOL = 0.5     # AC-R1 setup 不變容差(px)
PIVOT_TOL = 1.0     # AC-R2 articulated 關節位移容差(px)


def _load(skeleton_path):
    sk, bones, byname, order = wde.load_skeleton(skeleton_path)
    skins = sk["skins"]
    if isinstance(skins, list):                     # 陣列式 skin
        skin = skins[0].get("attachments", skins[0])
    else:                                           # {"default": {...}} 式(build_spine 產出)
        skin = skins.get("default", next(iter(skins.values())))
    return sk, bones, byname, order, skin


def _att_local_center(att):
    """attachment 在其綁定骨局部座標系的幾何中心。"""
    if att.get("type") == "mesh":
        uvs = att["uvs"]
        v = att["vertices"]
        if len(v) == len(uvs):                      # unweighted:[x,y,...]
            xy = np.array(v, dtype=np.float64).reshape(-1, 2)
            return float(xy[:, 0].mean()), float(xy[:, 1].mean())
        # weighted:退回 (0,0)(本閘用未 weighted build,不會走到)
        return 0.0, 0.0
    return float(att.get("x", 0.0)), float(att.get("y", 0.0))


def _part_world_centers(skeleton_path):
    """回傳 {slot: (wx,wy)} 每件 setup pose 世界中心。"""
    sk, bones, byname, order, skin = _load(skeleton_path)
    world = wde.bone_world_transforms(bones, byname, order, {})
    out = {}
    for slot in sk["slots"]:
        nm = slot["attachment"]
        att = next(iter(skin[nm].values()))
        lx, ly = _att_local_center(att)
        out[slot["name"]] = wde.transform_point(world[slot["bone"]], lx, ly)
    return out


def _topo_ok(bones):
    seen = set()
    for b in bones:
        p = b.get("parent")
        if p is not None and p not in seen:
            return False
        seen.add(b["name"])
    return True


def _seam_displacement(skeleton_path, rig_meta, theta=THETA):
    """對每個關節子件:把接觸縫關節點表為子骨局部座標,旋轉子骨 θ,量關節點世界位移。
       articulated rig 骨原點=關節 → 位移≈0;負對照(骨在件中心)→ 大幅甩開。"""
    sk, bones, byname, order, skin = _load(skeleton_path)
    world0 = wde.bone_world_transforms(bones, byname, order, {})
    slot2bone = {s["name"]: s["bone"] for s in sk["slots"]}
    disp = {}
    for slot, meta in rig_meta.items():
        bone = slot2bone[slot]
        J = np.array(meta["joint_world"], dtype=np.float64)     # 真實接觸縫世界點
        w0 = world0[bone]
        lx, ly = wde.inverse_transform_point(w0, J[0], J[1])    # 關節點在子骨局部座標
        b = byname[bone]
        pose = {bone: (b.get("x", 0.0), b.get("y", 0.0), b.get("rotation", 0.0) + theta,
                       b.get("scaleX", 1.0), b.get("scaleY", 1.0))}
        wr = wde.bone_world_transforms(bones, byname, order, pose)
        Jr = np.array(wde.transform_point(wr[bone], lx, ly))
        J0 = np.array(wde.transform_point(w0, lx, ly))          # == J
        disp[slot] = float(np.linalg.norm(Jr - J0))
    return disp


def evaluate(psd="assets/robot_parts.psd", genre="slot_bigwin", verbose=True):
    tmp = tempfile.mkdtemp(prefix="rigval_")
    rig_dir = os.path.join(tmp, "rig")
    plain_dir = os.path.join(tmp, "plain")
    bs.build(psd, rig_dir, genre, articulate=True)      # 受測:articulated
    bs.build(psd, plain_dir, genre, articulate=False)   # 負對照:繞件中心

    rig_sk = json.load(open(os.path.join(rig_dir, "skeleton.json")))
    rig_meta = json.load(open(os.path.join(rig_dir, "rig_meta.json")))

    # AC-R0 可載入 / topo
    ac0 = _topo_ok(rig_sk["bones"])

    # AC-R1 setup 不變(articulated vs plain 每件世界中心)
    ca = _part_world_centers(os.path.join(rig_dir, "skeleton.json"))
    cp = _part_world_centers(os.path.join(plain_dir, "skeleton.json"))
    invar = {s: float(np.linalg.norm(np.array(ca[s]) - np.array(cp[s]))) for s in ca}
    max_invar = max(invar.values())
    ac1 = max_invar < INVAR_TOL

    # AC-R2 pivot=關節(articulated 位移≈0;plain 甩開)
    disp_rig = _seam_displacement(os.path.join(rig_dir, "skeleton.json"), rig_meta)
    disp_plain = _seam_displacement(os.path.join(plain_dir, "skeleton.json"), rig_meta)
    max_rig = max(disp_rig.values())
    min_plain = min(disp_plain.values())
    ac2 = (max_rig < PIVOT_TOL) and (min_plain > 10 * max(max_rig, 1e-6)) and (min_plain > 20.0)

    # AC-R3 父子樹符合 struct_role + 確有關節
    spec = analyze(psd, genre)
    role_of = {ef["name"]: ("effect" if ef.get("is_effect") else ef.get("struct_role"))
               for ef in spec["2_effects"]}
    body_part = next((nm for nm in role_of if role_of[nm] == "body"), None)
    body_bone = "b_" + bs.safe(body_part) if body_part else None
    parent_of = {b["name"]: b.get("parent") for b in rig_sk["bones"]}
    hier_ok = True
    hier_rows = []
    for part, role in role_of.items():
        bone = "b_" + bs.safe(part)
        if bone not in parent_of:
            continue
        exp = body_bone if role in ("head", "limb") and part != body_part else "root"
        ok = parent_of[bone] == exp
        hier_ok = hier_ok and ok
        hier_rows.append((part, role, parent_of[bone], exp, ok))
    n_joints = len(rig_meta)
    ac3 = hier_ok and n_joints >= 2

    if verbose:
        print(f"AC-R0 可載入/topo -> {'PASS' if ac0 else 'FAIL'}")
        print(f"AC-R1 setup 不變   max={max_invar:.4f}px (<{INVAR_TOL}) -> {'PASS' if ac1 else 'FAIL'}")
        for s in sorted(invar): print(f"        {s:<10} Δ={invar[s]:.4f}px")
        print(f"AC-R2 pivot=關節   θ={THETA}°  articulated max={max_rig:.3f}px  負對照(繞件心) min={min_plain:.1f}px -> {'PASS' if ac2 else 'FAIL'}")
        for s in sorted(disp_rig): print(f"        {s:<10} rig={disp_rig[s]:.3f}px  plain={disp_plain[s]:.1f}px")
        print(f"AC-R3 父子樹符合語意 joints={n_joints} -> {'PASS' if ac3 else 'FAIL'}")
        for (part, role, got, exp, ok) in hier_rows:
            print(f"        {part:<6}[{role}] parent={got:<8} expect={exp:<8} {'✓' if ok else '✗'}")

    overall = ac0 and ac1 and ac2 and ac3
    return dict(ac0=ac0, ac1=ac1, ac2=ac2, ac3=ac3, overall=overall,
                max_invar=max_invar, max_rig=max_rig, min_plain=min_plain,
                invar=invar, disp_rig=disp_rig, disp_plain=disp_plain,
                joints=n_joints, hier=hier_rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    print("=" * 70)
    print("S5 build_spine --rig 關節鏈自我品質閘(端到端 PSD→articulated Spine)")
    print("=" * 70)
    r = evaluate(a.psd, a.genre, verbose=True)
    print("\n" + "=" * 70)
    print(f"OVERALL: {'PASS ✅' if r['overall'] else 'FAIL ❌'}  "
          f"(R0={r['ac0']} R1={r['ac1']} R2={r['ac2']} R3={r['ac3']})")
    print("=" * 70)
    if a.json:
        print(json.dumps({k: v for k, v in r.items() if k != "hier"},
                         ensure_ascii=False, default=float, indent=2))
    return 0 if r["overall"] else 1


if __name__ == "__main__":
    sys.exit(main())
