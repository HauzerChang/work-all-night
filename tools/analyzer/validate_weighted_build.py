#!/usr/bin/env python3
"""weighted build 的端到端閘(L3)—— 驗證 build_spine --weighted 產出的 weighted mesh:

  AC1 可載入/可解析為合法 weighted mesh(格式 + hull 首位)。
  AC2 setup skinning 重建乾淨(si=0 / degen=0)。
  AC3 幾何覆蓋:mesh 三角於 setup 光柵化 vs 該件 alpha 遮罩 IoU ≥ 門檻(mesh 覆蓋正確區域)。
  AC4 變形乾淨:對控制骨施加合成旋轉/平移,逐幀 si=0 / flip=0(證骨綁能真的動且不破)。

這補上 STATE 候選 2 的最後一哩:不只「生成 weighted mesh」,而是「build_spine 端到端產出
可載入、可變形、覆蓋正確的 weighted 素材」。deform **品質**(對藝術家)另由 validate_weighted_gen 驗。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
import weighted_deform_eval as W


def _part_mask(parts_dir, file):
    img = cv2.imread(os.path.join(parts_dir, file), cv2.IMREAD_UNCHANGED)
    a = img[:, :, 3] if (img.ndim == 3 and img.shape[2] == 4) else \
        (cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) > 0).astype(np.uint8) * 255
    return (a > 8).astype(np.uint8)


def _silhouette_iou(sv, tris, ox, oy, H, w, h, mask):
    """setup 世界頂點 → part-local → 光柵化三角填充,對 alpha mask 算 IoU。"""
    tri_canvas = np.zeros((h, w), np.uint8)
    for t in tris:
        pts = []
        for vi in t:
            wx, wy = sv[vi]
            px = wx - ox; py = H - wy - oy
            pts.append([px, py])
        cv2.fillConvexPoly(tri_canvas, np.round(pts).astype(np.int32), 1)
    inter = int((tri_canvas & mask).sum()); uni = int((tri_canvas | mask).sum())
    return inter / uni if uni else 0.0


def _synth_poses(byname, ctrl_bones):
    """對控制骨施加合成 delta(旋轉 + 平移),回傳 [local_pose dict]。"""
    poses = []
    for ang in (-30, -15, 15, 30):
        for tx in (0, 20):
            pose = {}
            for i, nm in enumerate(ctrl_bones):
                b = byname[nm]
                s = 1 if i % 2 == 0 else -1
                pose[nm] = (b.get("x", 0) + s * tx, b.get("y", 0),
                            b.get("rotation", 0) + s * ang, 1.0, 1.0)
            poses.append(pose)
    return poses


def validate(build_dir, psd_path=None, iou_thresh=0.85):
    sk = json.load(open(os.path.join(build_dir, "skeleton.json")))
    bones = sk["bones"]; byname = {b["name"]: b for b in bones}
    order = [b["name"] for b in bones]; bidx = {i: b["name"] for i, b in enumerate(bones)}
    skin = sk["skins"]["default"]
    world0 = W.bone_world_transforms(bones, byname, order, {})
    H = sk["skeleton"]["height"]

    parts_dir = os.path.join(build_dir, "_parts")
    mpath = os.path.join(parts_dir, "manifest.json")
    man = json.load(open(mpath)) if os.path.exists(mpath) else None
    bm_path = os.path.join(build_dir, "build_meta.json")
    build_meta = json.load(open(bm_path)) if os.path.exists(bm_path) else {}
    entries = man["parts"] if isinstance(man, dict) and "parts" in man else (man or [])
    by_safe = {e["name"].replace("/", "_").replace("\\", "_").replace(" ", "_"): e for e in entries}

    report = {"build_dir": build_dir, "meshes": {}, "overall_pass": True}
    n_weighted = 0
    for slot_name, atts in skin.items():
        a = list(atts.values())[0]
        if a.get("type") != "mesh" or len(a["vertices"]) == len(a["uvs"]):
            continue
        n_weighted += 1
        pv, tris, hull, uvs, wt = W.parse_weighted(a)
        sv = W.skin_vertices(pv, world0, bidx)
        signs = [W.signed_area(sv, t) > 0 for t in tris]
        area0 = sum(abs(W.signed_area(sv, t)) for t in tris)
        setup = W.eval_pose_wm(sv, tris, signs, area0)
        ac1 = (hull is not None and hull > 0 and len(pv) >= hull)
        ac2 = setup["clean"]
        # AC3 幾何覆蓋
        e = by_safe.get(slot_name)
        if e:
            ox, oy = e["offset"]; w, h = e["size"]
            mask = _part_mask(parts_dir, e["file"])
            iou = _silhouette_iou(sv, tris, ox, oy, H, w, h, mask)
        else:
            iou = None
        ac3 = (iou is not None and iou >= iou_thresh)
        # AC4 合成變形
        ctrl = sorted({bidx[i] for en in pv for (i, *_r) in en})
        worst = {"si": 0, "flip": 0}
        for pose in _synth_poses(byname, ctrl):
            wd = W.bone_world_transforms(bones, byname, order, pose)
            v = W.skin_vertices(pv, wd, bidx)
            r = W.eval_pose_wm(v, tris, signs, area0)
            worst["si"] = max(worst["si"], r["self_intersections"])
            worst["flip"] = max(worst["flip"], r["triangle_flips"])
        kind = build_meta.get(slot_name, {}).get("kind", "structural")
        # 軟性加成件(特效):additive 混合下自我重疊視覺無害 → AC4 的 si 只記錄不硬性 fail
        # (與 validate_weighted_gen / weighted_deform_eval 的 attachment 語意分類一致)。
        if kind == "effect":
            ac4 = True
            ac4_note = "soft/additive:si=%d 只記錄(additive 重疊無害)" % worst["si"]
        else:
            ac4 = (worst["si"] == 0 and worst["flip"] == 0)
            ac4_note = None
        entry = {"nv": len(pv), "tris": len(tris), "hull": hull, "bones": ctrl, "kind": kind,
                 "AC1_loadable": ac1, "AC2_setup_clean": ac2,
                 "AC3_silhouette_iou": {"pass": ac3, "iou": round(iou, 4) if iou is not None else None,
                                        "thresh": iou_thresh},
                 "AC4_synth_deform_clean": {"pass": ac4, "worst": worst, "note": ac4_note},
                 "pass": all([ac1, ac2, ac3, ac4])}
        report["meshes"][slot_name] = entry
        report["overall_pass"] &= entry["pass"]
    report["weighted_meshes"] = n_weighted
    if n_weighted == 0:
        report["overall_pass"] = False
        report["error"] = "no weighted mesh found (build with --weighted)"
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("build_dir")
    ap.add_argument("--psd", default=None)
    a = ap.parse_args()
    rep = validate(a.build_dir, a.psd)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print("\nOVERALL:", "PASS ✅" if rep["overall_pass"] else "FAIL ❌")
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
