#!/usr/bin/env python3
"""S5 rig 端到端閘 —— 驗 `build_spine --rig` 產出的骨骼父子樹「關節正確且素材不位移」。

S5 要脫離 HOLD → L3 的第二個要件(第一件是接觸縫 pivot 準度,見 validate_pivots.py):
把 pivot→bone 父子樹**寫進 build_spine**,並證明:
  (1) 骨樹結構正確(結構子件掛在 body 下、特效件亦然、body 掛 root);
  (2) setup pose 不因改骨原點而位移(art 與非 rig 版逐點吻合);
  (3) 接觸縫 pivot 忠實安裝成子骨世界原點(local↔parent 座標往返無誤差);
  (4) **關節語意正確**:轉動子骨會繞「接觸縫關節」旋轉,而非件中心/畫布原點
      —— 用 rig 版 vs 非 rig 版對「頸縫點」在同一旋轉下的位移差來鑑別(rig << 非 rig)。

真相來源:build_spine 自身的確定性 rig_layout(接觸縫 = infer_pivots,已對藝術家真值驗過)
+ Spine 3.8 bone world transform(weighted_deform_eval,已對 Award 真值重現)。純 CPU,無瀏覽器。
一鍵:`python3 tools/analyzer/validate_rig_build.py`(exit 0 = PASS)。
"""
import sys, os, json, argparse, tempfile, shutil
import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "mesh_gen"))
import weighted_deform_eval as wde  # noqa: E402
import build_spine as bs            # noqa: E402

EPS_POSE = 0.05     # setup pose 位移容差(px;bone/att 座標四捨五入到 2dp)
EPS_JOINT = 0.05    # pivot 安裝往返容差(px)
THETA = 25.0        # 關節測試旋轉角(度)


def _slot_bone(sk):
    return {s["name"]: s["bone"] for s in sk["slots"]}


def _part_world_points(sk, atts, world, slot_bone, slot):
    """該件在 setup pose 下的世界點雲(mesh→頂點;region→4 角)。"""
    att = next(iter(atts[slot].values()))
    bw = world[slot_bone[slot]]
    if att.get("type") == "mesh":
        pv, _, _, _, _ = wde.parse_weighted(att)   # unweighted: (None,x,y,1)
        pts = [wde.transform_point(bw, e[0][1], e[0][2]) for e in pv]
    else:
        x, y, w, h = att["x"], att["y"], att["width"], att["height"]
        corners = [(x - w / 2, y - h / 2), (x + w / 2, y - h / 2),
                   (x + w / 2, y + h / 2), (x - w / 2, y + h / 2)]
        pts = [wde.transform_point(bw, cx, cy) for cx, cy in corners]
    return np.array(pts, float)


def _load(out_dir):
    sk, bones, byname, order = wde.load_skeleton(os.path.join(out_dir, "skeleton.json"))
    atts = sk["skins"]["default"]              # build_spine 格式:{slot:{name:att}}
    world = wde.bone_world_transforms(bones, byname, order, {})
    meta = json.load(open(os.path.join(out_dir, "build_meta.json")))
    return sk, bones, byname, order, atts, world, meta


def evaluate(psd="assets/robot_parts.psd", genre="slot_bigwin", verbose=True):
    tmp = tempfile.mkdtemp(prefix="rigval_")
    try:
        rig_dir = os.path.join(tmp, "rig")
        flat_dir = os.path.join(tmp, "flat")
        summ = bs.build(psd, rig_dir, genre, rig=True)
        bs.build(psd, flat_dir, genre, rig=False)        # 非 rig 對照(art 應逐點相同)

        skR, bonesR, bynameR, orderR, attsR, worldR, metaR = _load(rig_dir)
        skF, _, _, _, attsF, worldF, _ = _load(flat_dir)
        sbR, sbF = _slot_bone(skR), _slot_bone(skF)
        parts = [s["name"] for s in skR["slots"]]
        body = summ["rig_root"][2:]                      # 去 "b_"

        # ---- AC1 骨樹結構 ----
        struct = []
        ac1 = bynameR[f"b_{body}"].get("parent") == "root"
        for nm in parts:
            if nm == body:
                continue
            par = bynameR[f"b_{nm}"].get("parent")
            ac1 = ac1 and (par == f"b_{body}")           # 所有件掛 body 下
            if metaR[nm].get("joint"):
                struct.append(nm)

        # ---- AC2 setup pose 不位移(rig vs 非 rig 逐件世界點)----
        max_pose_dev = 0.0
        for nm in parts:
            PR = _part_world_points(skR, attsR, worldR, sbR, nm)
            PF = _part_world_points(skF, attsF, worldF, sbF, nm)
            max_pose_dev = max(max_pose_dev, float(np.max(np.linalg.norm(PR - PF, axis=1))))
        ac2 = max_pose_dev < EPS_POSE

        # ---- AC3 接觸縫 pivot 忠實安裝成子骨世界原點 ----
        max_joint_dev = 0.0
        for bone, wj in summ["rig_joints"].items():
            wx, wy = worldR[bone][4], worldR[bone][5]
            max_joint_dev = max(max_joint_dev, float(np.hypot(wx - wj[0], wy - wj[1])))
        ac3 = max_joint_dev < EPS_JOINT

        # ---- AC4 關節語意:轉子骨繞「父子接觸縫」,而非件中心 ----
        # 用**真實 art 輪廓**(與 pivot 同一基底,避免 region bbox 粗糙代理)取每個結構子件
        # 與 body 的接觸縫點集,量該縫集在旋轉 THETA 下的位移。點 p 繞 pivot 轉 θ 的位移
        # = |p-pivot|·2sin(θ/2)。rig 版 pivot 在縫上(=縫集質心)→ 縫集位移小(縫不撕裂);
        # 非 rig 版 pivot=件中心 → 縫集遠 pivot → 位移大(骨繞件中心 → 縫撕裂)。ratio 應顯著。
        from psd_slice import slice_psd                       # noqa: E402
        sdir = os.path.join(tmp, "_sil")
        psd2, _, parts2 = slice_psd(psd, sdir)
        Hs = psd2.height
        sil = {}
        for e, _im in parts2:
            ws, _ = bs._boundary_world(os.path.join(sdir, e["file"]), e["offset"][0], e["offset"][1], Hs)
            sil[bs.safe(e["name"])] = ws
        body_sil = sil[body]
        krot = 2.0 * np.sin(np.radians(THETA) / 2.0)          # 位移係數(ratio 中會約掉)
        ratios, rig_disps, flat_disps = [], [], []
        for nm in struct:
            C = sil[nm]
            d = np.min(np.linalg.norm(C[:, None, :] - body_sil[None, :, :], axis=2), axis=1)
            seam = C[d <= np.quantile(d, 0.2) + 1e-9]
            rig_pivot = np.array([worldR[f"b_{nm}"][4], worldR[f"b_{nm}"][5]])   # rig 骨原點=接觸縫
            flat_pivot = np.array([worldF[sbF[nm]][4], worldF[sbF[nm]][5]])      # 非 rig 骨原點=件中心
            rd = float(np.mean(np.linalg.norm(seam - rig_pivot, axis=1))) * krot
            fd = float(np.mean(np.linalg.norm(seam - flat_pivot, axis=1))) * krot
            rig_disps.append(rd); flat_disps.append(fd)
            ratios.append(fd / rd if rd > 1e-9 else float("inf"))
        ac4 = min(ratios) > 2.0                                # 每關節接觸縫運動至少減半(rig << 非 rig)

        if verbose:
            print(f"rig_root = {summ['rig_root']}   結構子件 = {struct}")
            print(f"AC1 骨樹結構(子件掛 body、body 掛 root)         -> {'PASS' if ac1 else 'FAIL'}")
            print(f"AC2 setup 不位移  max_dev={max_pose_dev:.4f}px (<{EPS_POSE}) -> {'PASS' if ac2 else 'FAIL'}")
            print(f"AC3 pivot 安裝往返 max_dev={max_joint_dev:.4f}px (<{EPS_JOINT}) -> {'PASS' if ac3 else 'FAIL'}")
            print(f"AC4 關節語意  接觸縫位移@{THETA}°: rig={np.round(rig_disps,1).tolist()} "
                  f"非rig={np.round(flat_disps,1).tolist()}  min ratio={min(ratios):.1f}(>2.0) "
                  f"-> {'PASS' if ac4 else 'FAIL'}")

        overall = ac1 and ac2 and ac3 and ac4
        return dict(ac1=ac1, ac2=ac2, ac3=ac3, ac4=ac4, overall=overall,
                    max_pose_dev=max_pose_dev, max_joint_dev=max_joint_dev,
                    rig_disps=rig_disps, flat_disps=flat_disps, ratios=ratios,
                    struct=struct, rig_root=summ["rig_root"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    print("=" * 70)
    print("S5 rig 端到端閘 —— build_spine --rig(pivot→bone 父子樹)")
    print("=" * 70)
    r = evaluate(a.psd, a.genre, verbose=True)
    print("\n" + "=" * 70)
    print(f"OVERALL: {'PASS ✅' if r['overall'] else 'FAIL ❌'}  "
          f"(AC1={r['ac1']} AC2={r['ac2']} AC3={r['ac3']} AC4={r['ac4']})")
    print("=" * 70)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, default=float, indent=2))
    return 0 if r["overall"] else 1


if __name__ == "__main__":
    sys.exit(main())
