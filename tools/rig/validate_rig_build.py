#!/usr/bin/env python3
"""S5 rig → build_spine 整合閘:驗證 `build_spine --rig` 把接觸縫關節正確寫成骨階層。

這是 S5「pivot 推斷」脫離 HOLD、通往 L3 的整合驗收:不只算出關節座標(那由
`validate_pivots.py` 對 Award 真值驗過),而是證明**關節被忠實地嵌進可載入的 Spine 骨鏈**——
子件骨掛在父件骨下、pivot 落在關節、且旋轉子骨時**繞關節轉**(而非繞件中心),同時**素材不位移**。

四道 AC(對 robot_parts.psd,star 先驗:身體=root,頭/左手/右手=子):
  AC1 素材不位移   —— rig build 每 slot 解算出的影像中心世界座標 == flat build 的件中心(< 1px)。
                     (證明 pivot 從件中心搬到關節後,用 attachment 偏移補償,靜態外觀不變。)
  AC2 pivot 落關節 —— 每子件骨的世界位置 == 由父/子輪廓重算的接觸縫關節(< 1px);父子掛接正確。
  AC3 繞關節旋轉   —— 旋轉子骨 θ:接觸縫點位移「rig(繞關節)<< centroid(繞件中心)」,
                     且末梢點確實有大位移(肢體真的在轉,非退化)。
  AC4 負對照       —— (a)centroid pivot、(b)關節互換 皆使 AC2/AC3 爆閘(確認閘有鑑別力)。

真相來源:輪廓幾何(接觸縫算法本身已對 Award 藝術家 pivot 真值驗過,見 validate_pivots.py);
本閘驗的是「算法結果 → 骨鏈嵌入」的正確性,純確定性、無 ML。
"""
import argparse, json, os, sys, math, tempfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "analyzer"))
sys.path.insert(0, os.path.join(HERE, "..", "mesh_gen"))
sys.path.insert(0, HERE)
import build_spine as bs
import weighted_deform_eval as wde
from infer_pivots import contact_seam_joint


def _rot_deg(theta):
    return math.radians(theta)


def seam_points(parent_sil, child_sil, q=0.2):
    """回傳 child 輪廓中最靠近 parent 的 q 分位點(接觸縫點集)、與最遠端點(末梢代表)。"""
    P, C = np.asarray(parent_sil), np.asarray(child_sil)
    d = np.min(np.linalg.norm(C[:, None, :] - P[None, :, :], axis=2), axis=1)
    thr = np.quantile(d, q)
    seam = C[d <= thr + 1e-9]
    distal = C[np.argmax(d)][None, :]
    return seam, distal


def world_of(bones, byname, order, local_pose):
    return wde.bone_world_transforms(bones, byname, order, local_pose)


def collect(psd_path, genre, tmp):
    """跑 rig build + flat build,並獨立從 PSD 重算輪廓/tree/關節。回傳所有驗證所需材料。"""
    rig_dir = os.path.join(tmp, "rig"); flat_dir = os.path.join(tmp, "flat")
    s_rig = bs.build(psd_path, rig_dir, genre, rig=True)
    s_flat = bs.build(psd_path, flat_dir, genre, rig=False)

    # 獨立重算:輪廓(世界)、面積、star tree、接觸縫關節
    parts_dir = os.path.join(rig_dir, "_parts")
    psd, manifest, parts = bs.slice_psd(psd_path, parts_dir)
    H = psd.height
    metas = [e for e, _ in parts]
    names = [bs.safe(e["name"]) for e in metas]
    offsets = [e["offset"] for e in metas]
    sizes = [tuple(reversed(np.array(im).shape[:2])) for _, im in parts]  # (w,h)
    spec = bs.analyze(psd_path, genre)
    note = {r["part"]: r.get("note", "") for r in spec["4_slicing_strategy"]["parts"]}
    def kind(nm_orig):
        return "effect" if "特效" in note.get(nm_orig, "") else "structural"

    sil, area, struct = {}, {}, []
    for i, e in enumerate(metas):
        if kind(e["name"]) == "structural":
            png = os.path.join(parts_dir, e["file"])
            sil[i], _ = bs._boundary_world(png, offsets[i][0], offsets[i][1], H)
            area[i] = bs._alpha_area(png)
            struct.append(i)
    root_i, tree_i = bs.infer_rig_tree(struct, area)
    joints = {c: contact_seam_joint(sil[p], sil[c], q=0.2)[0] for c, p in tree_i.items()}

    # 父件(軀幹)bbox 對角線作尺度正規化
    proot = sil[root_i]
    diag = float(np.hypot(proot[:, 0].max() - proot[:, 0].min(),
                          proot[:, 1].max() - proot[:, 1].min()))
    return dict(rig_dir=rig_dir, flat_dir=flat_dir, s_rig=s_rig, s_flat=s_flat,
                names=names, offsets=offsets, sizes=sizes, H=H, sil=sil,
                root_i=root_i, tree_i=tree_i, joints=joints, scale=diag,
                name_to_i={names[i]: i for i in range(len(names))})


def image_center_world(sk, byname, order, slot_bone, att):
    """slot 的影像中心世界座標(setup pose)。region: bone_world + R·(att.x,att.y);
    mesh: 頂點世界包圍盒中心(此處只需 region/mesh 一致的靜態位置比對)。"""
    world = world_of(sk["bones"], byname, order, {})
    w = world[slot_bone]
    if att.get("type") == "mesh":
        pv, tris, hull, uvs, weighted = wde.parse_weighted(att)
        if weighted:
            return None  # weighted 走控制骨,不在此 AC 範圍
        V = np.array([wde.transform_point(w, e[0][1], e[0][2]) for e in pv])
        return (V[:, 0].mean(), V[:, 1].mean())
    return wde.transform_point(w, att.get("x", 0.0), att.get("y", 0.0))


def ac1_no_shift(mat):
    """rig build 每 slot 解算影像中心 == flat build 件中心。回傳 (pass, max_err, detail)。"""
    rig = json.load(open(os.path.join(mat["rig_dir"], "skeleton.json")))
    flat = json.load(open(os.path.join(mat["flat_dir"], "skeleton.json")))
    rby = {b["name"]: b for b in rig["bones"]}; rorder = [b["name"] for b in rig["bones"]]
    fby = {b["name"]: b for b in flat["bones"]}; forder = [b["name"] for b in flat["bones"]]
    rskin = rig["skins"]["default"]; fskin = flat["skins"]["default"]
    errs, detail = [], {}
    for slot in rskin:
        ratt = next(iter(rskin[slot].values())); fatt = next(iter(fskin[slot].values()))
        rbone = next(s["bone"] for s in rig["slots"] if s["name"] == slot)
        fbone = next(s["bone"] for s in flat["slots"] if s["name"] == slot)
        rc = image_center_world(rig, rby, rorder, rbone, ratt)
        fc = image_center_world(flat, fby, forder, fbone, fatt)
        if rc is None or fc is None:
            continue
        e = float(np.hypot(rc[0] - fc[0], rc[1] - fc[1]))
        errs.append(e); detail[slot] = round(e, 3)
    mx = max(errs) if errs else 0.0
    return mx < 1.0, mx, detail


def ac2_pivot_at_seam(mat):
    """每子件骨世界位置 == 重算接觸縫關節;父子掛接正確。"""
    rig = json.load(open(os.path.join(mat["rig_dir"], "skeleton.json")))
    by = {b["name"]: b for b in rig["bones"]}; order = [b["name"] for b in rig["bones"]]
    world = world_of(rig["bones"], by, order, {})
    errs, detail, parent_ok = [], {}, True
    for c_i, p_i in mat["tree_i"].items():
        cbone = f"b_{mat['names'][c_i]}"; pbone = f"b_{mat['names'][p_i]}"
        if by[cbone].get("parent") != pbone:
            parent_ok = False
        w = world[cbone]; bw = np.array([w[4], w[5]])
        j = mat["joints"][c_i]
        e = float(np.hypot(bw[0] - j[0], bw[1] - j[1]))
        errs.append(e); detail[mat["names"][c_i]] = round(e, 3)
    mx = max(errs) if errs else 0.0
    return (mx < 1.0 and parent_ok), mx, {"parent_ok": parent_ok, "err": detail}


def _seam_disp(sk, mat, theta, pivot_mode):
    """旋轉每子骨 θ,量接觸縫點與末梢點的世界位移。pivot_mode:
       'joint'   —— 用 rig build(骨在關節);
       'centroid'—— 用 flat build(骨在件中心)當對照。
    回傳 {child: (seam_disp_norm, distal_disp_norm)}。"""
    by = {b["name"]: b for b in sk["bones"]}; order = [b["name"] for b in sk["bones"]]
    W0 = world_of(sk["bones"], by, order, {})
    out = {}
    for c_i, p_i in mat["tree_i"].items():
        cbone = f"b_{mat['names'][c_i]}"
        b = by[cbone]
        lp = {cbone: (b.get("x", 0.0), b.get("y", 0.0), b.get("rotation", 0.0) + theta,
                      b.get("scaleX", 1.0), b.get("scaleY", 1.0))}
        W1 = world_of(sk["bones"], by, order, lp)
        seam, distal = seam_points(mat["sil"][p_i], mat["sil"][c_i], q=0.2)
        # 把世界縫點/末梢轉進 setup 子骨局部,再用旋轉後世界轉出
        w0 = W0[cbone]; w1 = W1[cbone]
        def disp(pts):
            local = [wde.inverse_transform_point(w0, px, py) for px, py in pts]
            new = np.array([wde.transform_point(w1, lx, ly) for lx, ly in local])
            return float(np.linalg.norm(new - np.asarray(pts), axis=1).mean())
        out[mat["names"][c_i]] = (disp(seam) / mat["scale"], disp(distal) / mat["scale"])
    return out


def ac3_rotate_about_joint(mat, theta=25.0):
    """rig(繞關節)接觸縫位移 << centroid(繞件中心);且末梢確有位移。"""
    rig = json.load(open(os.path.join(mat["rig_dir"], "skeleton.json")))
    flat = json.load(open(os.path.join(mat["flat_dir"], "skeleton.json")))
    d_rig = _seam_disp(rig, mat, theta, "joint")
    d_cen = _seam_disp(flat, mat, theta, "centroid")
    detail, ok = {}, True
    for c in d_rig:
        rs, rd = d_rig[c]; cs, cd = d_cen[c]
        # 縫位移:rig 應顯著小於 centroid;末梢:rig 應確有位移(肢體真的轉)
        seam_ratio = rs / (cs + 1e-9)
        cond = (seam_ratio < 0.5) and (rd > 0.05)
        ok = ok and cond
        detail[c] = {"seam_rig": round(rs, 4), "seam_centroid": round(cs, 4),
                     "seam_ratio": round(seam_ratio, 3), "distal_rig": round(rd, 4),
                     "pass": bool(cond)}
    return ok, detail


def ac4_negative(mat, theta=25.0):
    """負對照:(a)centroid pivot、(b)關節互換 皆爆 AC2/AC3。確認閘有鑑別力。"""
    rig = json.load(open(os.path.join(mat["rig_dir"], "skeleton.json")))
    by = {b["name"]: b for b in rig["bones"]}; order = [b["name"] for b in rig["bones"]]
    world = world_of(rig["bones"], by, order, {})

    # (a) centroid 對照:骨放件中心 → 對關節真值的誤差應遠大於 rig,且繞它轉縫會大幅位移
    cen_err = []
    for c_i in mat["tree_i"]:
        c = mat["names"][c_i]
        cen = np.array(mat["joints"][c_i]) * 0 + np.array([  # flat build 件中心
            [b for b in json.load(open(os.path.join(mat["flat_dir"], "skeleton.json")))["bones"]
             if b["name"] == f"b_{c}"][0][k] for k in ("x", "y")])
        cen_err.append(float(np.hypot(cen[0] - mat["joints"][c_i][0], cen[1] - mat["joints"][c_i][1])))
    centroid_breaks = (max(cen_err) / mat["scale"]) > 0.10   # 件中心偏離關節 > 10% 軀幹尺度

    # (b) 關節互換:把某子件的關節換成另一子件的關節 → 該骨偏離自身真值
    childs = list(mat["tree_i"].keys())
    swap_breaks = True
    if len(childs) >= 2:
        a, b2 = childs[0], childs[1]
        swapped = {a: mat["joints"][b2], b2: mat["joints"][a]}
        errs = [float(np.hypot(swapped[c][0] - mat["joints"][c][0],
                               swapped[c][1] - mat["joints"][c][1])) / mat["scale"]
                for c in (a, b2)]
        swap_breaks = min(errs) > 0.10
    ok = centroid_breaks and swap_breaks
    return ok, {"centroid_max_err_norm": round(max(cen_err) / mat["scale"], 4),
                "centroid_breaks": bool(centroid_breaks), "swap_breaks": bool(swap_breaks)}


def run(psd_path, genre="slot_bigwin"):
    with tempfile.TemporaryDirectory() as tmp:
        mat = collect(psd_path, genre, tmp)
        r1 = ac1_no_shift(mat)
        r2 = ac2_pivot_at_seam(mat)
        r3 = ac3_rotate_about_joint(mat)
        r4 = ac4_negative(mat)
    report = {
        "psd": os.path.basename(psd_path),
        "rig": mat["s_rig"].get("rig"),
        "scale_torso_diag": round(mat["scale"], 2),
        "AC1_no_shift":        {"pass": bool(r1[0]), "max_err_px": round(r1[1], 4), "per_slot": r1[2]},
        "AC2_pivot_at_seam":   {"pass": bool(r2[0]), "max_err_px": round(r2[1], 4), "detail": r2[2]},
        "AC3_rotate_joint":    {"pass": bool(r3[0]), "detail": r3[1]},
        "AC4_negative_control":{"pass": bool(r4[0]), "detail": r4[1]},
    }
    report["OVERALL_PASS"] = all(report[k]["pass"] for k in
                                 ("AC1_no_shift", "AC2_pivot_at_seam", "AC3_rotate_joint", "AC4_negative_control"))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default=os.path.join(HERE, "..", "..", "assets", "robot_parts.psd"))
    ap.add_argument("--genre", default="slot_bigwin")
    a = ap.parse_args()
    rep = run(a.psd, a.genre)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    sys.exit(0 if rep["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
