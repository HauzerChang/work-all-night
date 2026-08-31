#!/usr/bin/env python3
"""S5 (d) 端到端閘 —— 驗 `build_spine --rig --weighted` 併用:weighted mesh 的控制骨
接進 rig 關節鏈,且 setup 不位移、能被關節articulate、變形仍乾淨。

此前 `--rig` 與 `--weighted` 互斥(併用直接 SystemExit)。本閘證明兩者可安全併用:

  AC1 結構:每個 weighted mesh 的**控制骨 parent == 該件關節骨 b_{nm}**(接進關節鏈,非掛 root);
       rig 父子樹本身完好(結構子件掛 body、body 掛 root);weighted 頂點的骨 index 皆合法。
  AC2 setup 不位移:rig×weighted 的 setup skinning 世界頂點 == weighted-only 版**逐頂點吻合**
       (證重掛關節骨 + 座標轉局部後,partition-of-unity 重建完全不變)。
  AC3 關節articulate(併用的收益):
       (a) 自articulate:轉某 weighted 件的關節骨 b_{nm} → rig 版件會動;weighted-only 版(控制骨掛 root,
           b_{nm} 只是 slot 骨、不驅動 weighted mesh)→ **件不動**。rig 位移 >> flat(≈0)。
       (b) 鏈帶動:轉 rig 根 b_body → rig 版**子件 weighted mesh(光暈)隨父件被帶動**;
           weighted-only 版光暈掛 root → **與 body 脫鉤不動**。證父→子關節鏈耦合。
  AC4 變形乾淨:上述關節旋轉下,結構 weighted 件逐幀 si=0 / flip=0(effect 件 additive → si 容忍)。

真相來源:build_spine 自身確定性組裝 + Spine 3.8 bone world transform(weighted_deform_eval,
已對 Award 真值重現)。純 CPU、無瀏覽器。一鍵:`python3 tools/analyzer/validate_rig_weighted_build.py`。
"""
import sys, os, json, argparse, tempfile, shutil
import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "mesh_gen"))
import weighted_deform_eval as W  # noqa: E402
import build_spine as bs          # noqa: E402

EPS_POSE = 0.05     # setup 逐頂點位移容差(px)
THETA = 25.0        # 關節測試旋轉角(度)
ARTIC_MIN = 5.0     # rig 版件被articulate的最小平均位移(px);weighted-only 應 ≈0
INERT_MAX = 1e-6    # weighted-only 版「不該動」的位移上界(px)


def _weighted_slots(sk):
    """回傳 [(slot_name, att)],只取 weighted mesh。"""
    out = []
    for slot, atts in sk["skins"]["default"].items():
        a = list(atts.values())[0]
        if a.get("type") == "mesh" and len(a["vertices"]) != len(a["uvs"]):
            out.append((slot, a))
    return out


def _load(out_dir):
    sk, bones, byname, order = W.load_skeleton(os.path.join(out_dir, "skeleton.json"))
    bidx = {i: b["name"] for i, b in enumerate(bones)}
    world0 = W.bone_world_transforms(bones, byname, order, {})
    meta = json.load(open(os.path.join(out_dir, "build_meta.json")))
    return sk, bones, byname, order, bidx, world0, meta


def _skin_setup(att, world, bidx):
    pv, tris, hull, uvs, wt = W.parse_weighted(att)
    return W.skin_vertices(pv, world, bidx), pv, tris


def _pose_rotate(bones, byname, order, bone_name, theta):
    """回傳把 bone_name 相對 setup 旋轉 theta 度後的 local_pose(其餘骨 setup)。"""
    b = byname[bone_name]
    pose = {bone_name: (b.get("x", 0.0), b.get("y", 0.0),
                        b.get("rotation", 0.0) + theta,
                        b.get("scaleX", 1.0), b.get("scaleY", 1.0))}
    return pose


def evaluate(psd="assets/robot_parts.psd", genre="slot_bigwin", verbose=True):
    tmp = tempfile.mkdtemp(prefix="rigwval_")
    try:
        rw_dir = os.path.join(tmp, "rw")     # rig × weighted
        wo_dir = os.path.join(tmp, "wo")     # weighted-only(對照)
        bs.build(psd, rw_dir, genre, rig=True, weighted=True)
        bs.build(psd, wo_dir, genre, rig=False, weighted=True)

        skR, bonesR, bynameR, orderR, bidxR, world0R, metaR = _load(rw_dir)
        skW, bonesW, bynameW, orderW, bidxW, world0W, metaW = _load(wo_dir)

        wslotsR = dict(_weighted_slots(skR))
        wslotsW = dict(_weighted_slots(skW))
        wnames = sorted(wslotsR.keys())

        # ---- AC1 結構:控制骨掛關節骨 + rig 樹完好 + index 合法 ----
        ac1 = len(wnames) > 0
        ac1_detail = {}
        # rig 樹:body 掛 root、結構子件掛 body
        body = None
        for nm, m in metaR.items():
            if m.get("role") == "body":
                body = nm
        ac1 = ac1 and (body is not None) and bynameR[f"b_{body}"].get("parent") == "root"
        for nm, m in metaR.items():
            if m.get("role") not in ("body", None) and f"b_{nm}" in bynameR:
                par = bynameR[f"b_{nm}"].get("parent")
                ac1 = ac1 and (par == f"b_{body}")
        # 每個 weighted 件的控制骨 parent == 該件關節骨 b_{nm}
        for nm in wnames:
            att = wslotsR[nm]
            v = att["vertices"]; i = 0; used = set()
            while i < len(v):
                bc = int(v[i]); i += 1
                for _ in range(bc):
                    used.add(int(v[i])); i += 4
            valid_idx = all(0 <= k < len(bonesR) for k in used)
            parents = {bidxR[k]: bonesR[k].get("parent") for k in used}
            joint_bone = f"b_{nm}"
            all_under_joint = all(p == joint_bone for p in parents.values())
            ac1 = ac1 and valid_idx and all_under_joint
            ac1_detail[nm] = {"control_bones": sorted(bidxR[k] for k in used),
                              "parents": sorted(set(parents.values())),
                              "joint_bone": joint_bone,
                              "under_joint": all_under_joint, "idx_valid": valid_idx}

        # ---- AC2 setup 不位移(rig×weighted vs weighted-only 逐頂點)----
        max_pose_dev = 0.0
        for nm in wnames:
            svR, _, _ = _skin_setup(wslotsR[nm], world0R, bidxR)
            svW, _, _ = _skin_setup(wslotsW[nm], world0W, bidxW)
            if svR.shape == svW.shape:
                max_pose_dev = max(max_pose_dev, float(np.max(np.linalg.norm(svR - svW, axis=1))))
            else:
                max_pose_dev = float("inf")  # 拓樸不一致 = 失敗
        ac2 = max_pose_dev < EPS_POSE

        # ---- AC3(a) 自articulate:轉 b_{nm} → rig 動、weighted-only 不動 ----
        artic = {}
        ac3a = True
        for nm in wnames:
            jb = f"b_{nm}"
            # rig 版
            svR0, pvR, _ = _skin_setup(wslotsR[nm], world0R, bidxR)
            wR = W.bone_world_transforms(bonesR, bynameR, orderR,
                                         _pose_rotate(bonesR, bynameR, orderR, jb, THETA))
            svR1 = W.skin_vertices(pvR, wR, bidxR)
            rd = float(np.mean(np.linalg.norm(svR1 - svR0, axis=1)))
            # weighted-only 版(jb 存在為 slot 骨,但不驅動 weighted mesh → 應不動)
            svW0, pvW, _ = _skin_setup(wslotsW[nm], world0W, bidxW)
            wW = W.bone_world_transforms(bonesW, bynameW, orderW,
                                         _pose_rotate(bonesW, bynameW, orderW, jb, THETA))
            svW1 = W.skin_vertices(pvW, wW, bidxW)
            fd = float(np.mean(np.linalg.norm(svW1 - svW0, axis=1)))
            artic[nm] = {"rig_disp": round(rd, 3), "flat_disp": round(fd, 6)}
            ac3a = ac3a and (rd > ARTIC_MIN) and (fd < INERT_MAX)

        # ---- AC3(b) 鏈帶動:轉 rig 根 b_body → 子 weighted 件(光暈)隨動;weighted-only 脫鉤 ----
        chain = {}
        child_w = [nm for nm in wnames if nm != body]  # body 以外的 weighted 件(此資產=光暈)
        ac3b = len(child_w) > 0
        rootb = f"b_{body}"
        for nm in child_w:
            svR0, pvR, _ = _skin_setup(wslotsR[nm], world0R, bidxR)
            wR = W.bone_world_transforms(bonesR, bynameR, orderR,
                                         _pose_rotate(bonesR, bynameR, orderR, rootb, THETA))
            svR1 = W.skin_vertices(pvR, wR, bidxR)
            rd = float(np.mean(np.linalg.norm(svR1 - svR0, axis=1)))
            svW0, pvW, _ = _skin_setup(wslotsW[nm], world0W, bidxW)
            # weighted-only 也有 b_body(slot 骨),轉它對掛 root 的光暈控制骨無效 → 脫鉤
            wW = W.bone_world_transforms(bonesW, bynameW, orderW,
                                         _pose_rotate(bonesW, bynameW, orderW, rootb, THETA))
            svW1 = W.skin_vertices(pvW, wW, bidxW)
            fd = float(np.mean(np.linalg.norm(svW1 - svW0, axis=1)))
            chain[nm] = {"rig_disp": round(rd, 3), "flat_disp": round(fd, 6)}
            ac3b = ac3b and (rd > ARTIC_MIN) and (fd < INERT_MAX)
        ac3 = ac3a and ac3b

        # ---- AC4 變形乾淨:關節旋轉下結構 weighted 件 si=0/flip=0(effect 容忍)----
        ac4 = True
        deform = {}
        for nm in wnames:
            jb = f"b_{nm}"
            pv, tris, hull, uvs, wt = W.parse_weighted(wslotsR[nm])
            sv0 = W.skin_vertices(pv, world0R, bidxR)
            signs = [W.signed_area(sv0, t) > 0 for t in tris]
            area0 = sum(abs(W.signed_area(sv0, t)) for t in tris)
            worst_si = worst_flip = 0
            for th in (-THETA, -THETA / 2, THETA / 2, THETA):
                for drive in (jb, rootb):  # 轉自身關節 + 轉 rig 根(鏈)
                    w = W.bone_world_transforms(bonesR, bynameR, orderR,
                                                _pose_rotate(bonesR, bynameR, orderR, drive, th))
                    v = W.skin_vertices(pv, w, bidxR)
                    r = W.eval_pose_wm(v, tris, signs, area0)
                    worst_si = max(worst_si, r["self_intersections"])
                    worst_flip = max(worst_flip, r["triangle_flips"])
            kind = metaR.get(nm, {}).get("kind", "structural")
            clean = (worst_si == 0 and worst_flip == 0)
            ok = True if kind == "effect" else clean
            deform[nm] = {"kind": kind, "worst_si": worst_si, "worst_flip": worst_flip, "pass": ok}
            ac4 = ac4 and ok

        if verbose:
            print(f"weighted 件 = {wnames}   rig 根 = b_{body}   子 weighted 件 = {child_w}")
            print(f"AC1 控制骨接進關節鏈 + rig 樹完好                 -> {'PASS' if ac1 else 'FAIL'}")
            for nm, d in ac1_detail.items():
                print(f"     {nm}: 控制骨{d['control_bones']} → parent {d['parents']} (應=[{d['joint_bone']}])")
            print(f"AC2 setup 不位移  max_dev={max_pose_dev:.4f}px (<{EPS_POSE}) -> {'PASS' if ac2 else 'FAIL'}")
            print(f"AC3a 自articulate@{THETA}°  rig vs weighted-only:")
            for nm, d in artic.items():
                print(f"     {nm}: rig={d['rig_disp']}px  flat={d['flat_disp']}px")
            print(f"     -> {'PASS' if ac3a else 'FAIL'} (rig>{ARTIC_MIN} 且 flat≈0)")
            print(f"AC3b 鏈帶動(轉 b_{body}→子件隨動)  rig vs weighted-only:")
            for nm, d in chain.items():
                print(f"     {nm}: rig={d['rig_disp']}px  flat={d['flat_disp']}px")
            print(f"     -> {'PASS' if ac3b else 'FAIL'}")
            print(f"AC4 變形乾淨(關節旋轉逐幀 si/flip):")
            for nm, d in deform.items():
                print(f"     {nm}({d['kind']}): si={d['worst_si']} flip={d['worst_flip']} -> {'PASS' if d['pass'] else 'FAIL'}")
            print(f"     -> {'PASS' if ac4 else 'FAIL'}")

        overall = ac1 and ac2 and ac3 and ac4
        return dict(ac1=ac1, ac2=ac2, ac3=ac3, ac3a=ac3a, ac3b=ac3b, ac4=ac4, overall=overall,
                    max_pose_dev=max_pose_dev, artic=artic, chain=chain,
                    ac1_detail=ac1_detail, deform=deform, weighted=wnames, body=body)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    print("=" * 74)
    print("S5 (d) 端到端閘 —— build_spine --rig --weighted 併用(weighted 控制骨接進關節鏈)")
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
