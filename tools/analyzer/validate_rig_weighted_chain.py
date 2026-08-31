#!/usr/bin/env python3
"""S5 (d') 端到端閘 —— 驗 `build_spine --rig --weighted` 在**多跳肢體鏈**上正確:
weighted mesh 當作鏈中段肢體(既是某件的子、又是另一件的父),旋轉某關節時
沿鏈**遞迴帶動所有後代 weighted 件**,而祖先/旁支不動。

動機(honest boundary,見 `knowledge/s5-rig-weighted-combo.md`):真實資產 robot_parts
的可拆肢體都是 region 件、且都直掛 body(星形/單跳);其 weighted mesh 只有 body(rig 根)
+ 光暈(effect)。因此「weighted mesh 當鏈中段肢體」在 robot_parts 無真實樣本。本閘用
合成多跳鏈 fixture(`make_limb_chain_psd`:body→arm→forearm→hand,arm/forearm 皆 weighted mesh)
補上此缺口。演算法早已支援(接觸縫遞迴 + 控制骨掛該件關節骨),本閘證明端到端確實成立。

AC(對照 rig×weighted vs weighted-only 內建負對照):
  AC1 鏈結構:bone 父鏈為**拓樸鏈**(b_hand→b_forearm→b_arm→b_body→root,非全掛 body 的星形);
       每個 weighted mesh 件的**控制骨 parent == 該件關節骨 b_{nm}**;骨 index 皆合法;鏈深 ≥ 3 跳。
  AC2 setup 不位移:rig×weighted 的 setup 世界頂點 == weighted-only 版逐頂點吻合(<0.05px)。
  AC3 遞迴帶動(多跳的收益):對每個驅動關節 jb(各件關節骨 + rig 根),
       (a) rig 版:**後代**(含自身)weighted 件位移 > 門檻;**非後代**(祖先/旁支)≈ 0;
       (b) weighted-only 版:所有 weighted 件位移 ≈ 0(控制骨掛 root → 與關節鏈脫鉤)= 負對照。
       特別驗**2 跳**:轉 rig 根 b_body → forearm(經 arm 隔一跳)確實隨動,weighted-only=0。
  AC3R region 葉件:轉 b_arm → 區域葉件 hand(掛 b_hand,arm 的後代)骨世界原點位移 > 門檻,
       轉更淺祖先無影響鏈方向(轉 b_forearm 動 hand、不動 arm)。
  AC4 變形乾淨:上述關節旋轉逐幀,結構 weighted 件 si=0/flip=0。

真相來源:build_spine 確定性組裝 + Spine 3.8 bone world transform(weighted_deform_eval,已對
Award 真值重現)。純 CPU、無瀏覽器。一鍵:`python3 tools/analyzer/validate_rig_weighted_chain.py`。
"""
import sys, os, tempfile, shutil, argparse
import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "mesh_gen"))
import weighted_deform_eval as W          # noqa: E402
import build_spine as bs                  # noqa: E402
import make_limb_chain_psd as mk          # noqa: E402
# 共用小工具(自 combo 閘):載入、取 weighted slot、skinning、旋轉 pose
from validate_rig_weighted_build import (  # noqa: E402
    _load, _weighted_slots, _skin_setup, _pose_rotate, EPS_POSE, THETA,
)

ARTIC_MIN = 5.0     # 「該動」的最小平均位移(px)
INERT_MAX = 1e-4    # 「不該動」的位移上界(px);純剛性換算,理論上 0


def _parent_map(bones):
    return {b["name"]: b.get("parent") for b in bones}


def _ancestors_or_self(bone, pmap):
    out, cur = set(), bone
    while cur is not None:
        out.add(cur)
        cur = pmap.get(cur)
    return out


def evaluate(verbose=True):
    tmp = tempfile.mkdtemp(prefix="rigwchain_")
    try:
        psd = os.path.join(tmp, "limb_chain.psd")
        mk.build(psd)
        rw_dir = os.path.join(tmp, "rw")     # rig × weighted
        wo_dir = os.path.join(tmp, "wo")     # weighted-only(對照)
        bs.build(psd, rw_dir, "slot_bigwin", rig=True, weighted=True)
        bs.build(psd, wo_dir, "slot_bigwin", rig=False, weighted=True)

        skR, bonesR, bynameR, orderR, bidxR, world0R, metaR = _load(rw_dir)
        skW, bonesW, bynameW, orderW, bidxW, world0W, metaW = _load(wo_dir)
        pmapR = _parent_map(bonesR)

        wslotsR = dict(_weighted_slots(skR))
        wslotsW = dict(_weighted_slots(skW))
        wnames = sorted(wslotsR.keys())
        body = next((nm for nm, m in metaR.items() if m.get("role") == "body"), None)

        # ---- AC1 鏈結構 ----
        ac1 = len(wnames) > 0 and body is not None
        ac1_detail = {}
        # (a) bone 父鏈為拓樸鏈:量鏈深(root 到最深關節骨的跳數)>= 3
        joint_bones = [f"b_{nm}" for nm in metaR if f"b_{nm}" in bynameR]
        max_depth = 0
        for jb in joint_bones:
            max_depth = max(max_depth, len(_ancestors_or_self(jb, pmapR)) - 1)  # 減 root 自身
        ac1_chain_depth = max_depth
        ac1 = ac1 and (max_depth >= 3)
        # (b) rig 樹非星形:存在關節骨其 parent 是另一個關節骨(非 body/root)
        non_star = any(pmapR.get(f"b_{nm}") not in ("root", f"b_{body}", None)
                       for nm in metaR if f"b_{nm}" in bynameR)
        ac1 = ac1 and non_star
        # (c) 每個 weighted 件控制骨 parent == 該件關節骨 b_{nm};index 合法
        for nm in wnames:
            att = wslotsR[nm]; v = att["vertices"]; i = 0; used = set()
            while i < len(v):
                bc = int(v[i]); i += 1
                for _ in range(bc):
                    used.add(int(v[i])); i += 4
            valid_idx = all(0 <= k < len(bonesR) for k in used)
            parents = {bonesR[k].get("parent") for k in used}
            joint_bone = f"b_{nm}"
            under_joint = parents == {joint_bone}
            ac1 = ac1 and valid_idx and under_joint
            ac1_detail[nm] = {"parents": sorted(parents), "joint": joint_bone,
                              "under_joint": under_joint, "idx_valid": valid_idx}

        # ---- AC2 setup 不位移 ----
        max_pose_dev = 0.0
        for nm in wnames:
            svR, _, _ = _skin_setup(wslotsR[nm], world0R, bidxR)
            svW, _, _ = _skin_setup(wslotsW[nm], world0W, bidxW)
            if svR.shape == svW.shape:
                max_pose_dev = max(max_pose_dev, float(np.max(np.linalg.norm(svR - svW, axis=1))))
            else:
                max_pose_dev = float("inf")
        ac2 = max_pose_dev < EPS_POSE

        # ---- AC3 遞迴帶動:對每個驅動關節,後代動、非後代不動;weighted-only 全脫鉤 ----
        # 預先算每個 weighted 件的 setup 頂點(rig / wo)
        setupR = {nm: _skin_setup(wslotsR[nm], world0R, bidxR) for nm in wnames}
        setupW = {nm: _skin_setup(wslotsW[nm], world0W, bidxW) for nm in wnames}
        drivers = [f"b_{nm}" for nm in metaR if f"b_{nm}" in bynameR]  # 各件關節骨(含 rig 根 b_body)
        ac3 = True
        ac3_detail = {}
        multi_hop_ok = False
        for jb in drivers:
            poseR = _pose_rotate(bonesR, bynameR, orderR, jb, THETA)
            wR = W.bone_world_transforms(bonesR, bynameR, orderR, poseR)
            poseW = _pose_rotate(bonesW, bynameW, orderW, jb, THETA)
            wW = W.bone_world_transforms(bonesW, bynameW, orderW, poseW)
            rows = {}
            for nm in wnames:
                svR0, pvR, _ = setupR[nm]
                rd = float(np.mean(np.linalg.norm(W.skin_vertices(pvR, wR, bidxR) - svR0, axis=1)))
                svW0, pvW, _ = setupW[nm]
                fd = float(np.mean(np.linalg.norm(W.skin_vertices(pvW, wW, bidxW) - svW0, axis=1)))
                is_desc = jb in _ancestors_or_self(f"b_{nm}", pmapR)  # jb 是 b_{nm} 的祖先或自身
                # rig:後代該動、非後代不動;weighted-only:一律不動(脫鉤負對照)
                exp_ok = ((rd > ARTIC_MIN) if is_desc else (rd < INERT_MAX)) and (fd < INERT_MAX)
                ac3 = ac3 and exp_ok
                rows[nm] = {"is_desc": is_desc, "rig": round(rd, 3), "wo": round(fd, 6), "ok": exp_ok}
            # 多跳亮點:轉 rig 根 b_body 時,離 body ≥2 跳的 weighted 件是否隨動(且 wo 脫鉤)
            if jb == f"b_{body}":
                for nm in wnames:
                    depth = len(_ancestors_or_self(f"b_{nm}", pmapR)) - 1  # 到 root 跳數
                    body_depth = len(_ancestors_or_self(f"b_{body}", pmapR)) - 1
                    hop_from_body = depth - body_depth
                    if hop_from_body >= 2 and rows[nm]["is_desc"]:
                        multi_hop_ok = multi_hop_ok or (rows[nm]["rig"] > ARTIC_MIN and rows[nm]["wo"] < INERT_MAX)
            ac3_detail[jb] = rows
        ac3 = ac3 and multi_hop_ok

        # ---- AC3R region 葉件隨鏈 + 鏈方向 ----
        # hand 是 region 葉件(掛 b_hand)。轉 b_arm(hand 的祖先)→ b_hand 世界原點動;
        # 轉 b_forearm → hand 動(forearm 是 hand 父);且轉任一關節不影響其祖先件的骨原點(方向性)。
        # 追蹤 region 葉件 attachment 的**世界代表點**(骨原點 + 旋轉後的局部偏移):
        # 轉其祖先或**自身**關節都會移動該件(自身旋轉→件繞骨原點轉,偏移點位移);非祖先/旁支不動。
        region_leaf = next((nm for nm, m in metaR.items()
                            if not m.get("mesh") and m.get("joint")), None)
        ac3r = region_leaf is not None
        ac3r_detail = {}
        if region_leaf:
            lb = f"b_{region_leaf}"
            latt = list(skR["skins"]["default"][region_leaf].values())[0]  # region attachment
            lx, ly = float(latt.get("x", 0.0)), float(latt.get("y", 0.0))  # 局部偏移(件中心)
            wt0 = W.bone_world_transforms(bonesR, bynameR, orderR, {})
            p0 = W.transform_point(wt0[lb], lx, ly)
            for jb in drivers:
                wtj = W.bone_world_transforms(bonesR, bynameR, orderR,
                                              _pose_rotate(bonesR, bynameR, orderR, jb, THETA))
                pj = W.transform_point(wtj[lb], lx, ly)
                d = float(np.hypot(pj[0] - p0[0], pj[1] - p0[1]))
                is_desc = jb in _ancestors_or_self(lb, pmapR)   # 祖先或自身 → 該動
                ok = (d > ARTIC_MIN) if is_desc else (d < INERT_MAX)
                ac3r = ac3r and ok
                ac3r_detail[jb] = {"drives_leaf": is_desc, "leaf_disp": round(d, 3), "ok": ok}

        # ---- AC4 變形乾淨 ----
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
                for drive in (jb, f"b_{body}"):
                    w = W.bone_world_transforms(bonesR, bynameR, orderR,
                                                _pose_rotate(bonesR, bynameR, orderR, drive, th))
                    r = W.eval_pose_wm(W.skin_vertices(pv, w, bidxR), tris, signs, area0)
                    worst_si = max(worst_si, r["self_intersections"])
                    worst_flip = max(worst_flip, r["triangle_flips"])
            kind = metaR.get(nm, {}).get("kind", "structural")
            ok = True if kind == "effect" else (worst_si == 0 and worst_flip == 0)
            deform[nm] = {"kind": kind, "si": worst_si, "flip": worst_flip, "ok": ok}
            ac4 = ac4 and ok

        if verbose:
            print(f"weighted mesh 件 = {wnames}   rig 根 = b_{body}   region 葉件 = {region_leaf}")
            print(f"bone 鏈:", " -> ".join(f"b_{nm}" for nm in [body] +
                  [n for n in metaR if metaR[n].get('joint')]))
            print(f"AC1 鏈結構(鏈深={ac1_chain_depth}≥3、非星形={non_star}、控制骨掛關節骨) -> {'PASS' if ac1 else 'FAIL'}")
            for nm, d in ac1_detail.items():
                print(f"     {nm}: 控制骨 parent {d['parents']} (應=[{d['joint']}]) idx_valid={d['idx_valid']}")
            print(f"AC2 setup 不位移  max_dev={max_pose_dev:.4f}px (<{EPS_POSE}) -> {'PASS' if ac2 else 'FAIL'}")
            print(f"AC3 遞迴帶動(後代動/祖先旁支不動;weighted-only 全脫鉤;多跳驗證={multi_hop_ok}):")
            for jb, rows in ac3_detail.items():
                seg = "  ".join(f"{nm.split('_')[-1]}[{'D' if r['is_desc'] else '.'}]"
                                f"rig={r['rig']}/wo={r['wo']}" for nm, r in rows.items())
                print(f"     轉 {jb}: {seg}")
            print(f"     -> {'PASS' if ac3 else 'FAIL'}")
            print(f"AC3R region 葉件 {region_leaf} 隨鏈(祖先/自身關節動它、旁支不動):")
            for jb, d in ac3r_detail.items():
                print(f"     轉 {jb}: 驅動={d['drives_leaf']} 葉件位移={d['leaf_disp']}px ok={d['ok']}")
            print(f"     -> {'PASS' if ac3r else 'FAIL'}")
            print(f"AC4 變形乾淨(關節旋轉逐幀 si/flip):")
            for nm, d in deform.items():
                print(f"     {nm}({d['kind']}): si={d['si']} flip={d['flip']} -> {'PASS' if d['ok'] else 'FAIL'}")
            print(f"     -> {'PASS' if ac4 else 'FAIL'}")

        overall = ac1 and ac2 and ac3 and ac3r and ac4
        if verbose:
            print(f"\nOVERALL -> {'PASS' if overall else 'FAIL'}")
        return dict(ac1=ac1, ac2=ac2, ac3=ac3, ac3r=ac3r, ac4=ac4, overall=overall,
                    chain_depth=ac1_chain_depth, max_pose_dev=max_pose_dev,
                    multi_hop=multi_hop_ok, weighted=wnames, body=body)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-q", "--quiet", action="store_true")
    a = ap.parse_args()
    r = evaluate(verbose=not a.quiet)
    sys.exit(0 if r["overall"] else 1)


if __name__ == "__main__":
    main()
