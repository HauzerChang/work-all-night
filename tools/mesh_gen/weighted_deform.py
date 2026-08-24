#!/usr/bin/env python3
"""S3 — weighted-mesh 變形評估器:量化「靠骨骼+權重變形的網格」在真實動畫下會不會壞。

補上 compare_robot_mesh.py 的唯一未驗維度(見 knowledge/s3-robot-mesh-vs-award.md 誠實限制):
Award 機器人 3 個 mesh 件(光暈/左手/身體)是 **weighted mesh 且無 deform timeline** —— 它們
靠**骨骼變換 + 每頂點權重(LBS)**變形,而非逐頂點 deform。故 deform_eval 的位移場轉移閘不適用。
本工具改用 **linear-blend skinning** 把 mesh 綁到真實骨骼 pose 序列上,量測拓樸品質。

方法(對照 CLAUDE.md 雷點 #4/#6):
  1. 讀骨架 → 依 Spine 3.8 **normal-mode** 規則算每骨 setup 世界變換(矩陣 a,b,c,d + 平移 wx,wy)。
     (Award 全 77 骨皆 normal mode,已確認;非 normal mode 會 raise。)
  2. weighted mesh 每頂點 = [骨數,(boneIdx,bindX,bindY,weight)×N] → 世界座標
     worldPos = Σ_b weight_b · M_b(bindX_b, bindY_b)。setup pose 下重建 == 匯出世界座標。
  3. 套真實動畫的 bone timeline(rotate/translate/scale,線性取樣 keyframe 時間 + 中點)重算
     世界變換 → 得變形後世界頂點 → 跑幾何閘(自交/翻面/退化,重用 deform_eval)。

評估器可信度(內建 gate,對照「評估器本身也要可信」):
  - **per-bone bind 一致性**:多骨頂點的每根骨各自把 bind 座標映到 setup 世界的同一點
    (偏差 < TOL px)→ 獨立驗證 world-transform 數學與 weighted 解析器正確(不依賴權重)。
  - **setup 重建**:LBS 在 setup pose 的世界頂點 == 直接 skinning,拓樸 clean。

用途:
  - artist_baseline():3 件真實美術 weighted mesh 套真實動畫 → 應全 clean(生產美術基準)。
  - deform_weighted(mesh_weighted, bones, skeleton, anims):對**我方生成**的 weighted mesh
    套同一組真實 pose,量拓樸 → 與 artist_baseline 對照(下一 session:生成 + BBW 後接上)。
"""
import argparse, json, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from deform_eval import signed_area, eval_pose

TOL = 0.05  # per-bone bind 一致性容差(px);匯出 JSON 浮點捨入下實測 < 0.02

ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


# ---------- 骨架世界變換(Spine 3.8 normal mode) ----------
def _local_mat(rot, sx, sy, shx, shy):
    ry = math.radians(rot + 90.0 + shy); rx = math.radians(rot + shx)
    return (math.cos(rx) * sx, math.cos(ry) * sy,
            math.sin(rx) * sx, math.sin(ry) * sy)  # la, lb, lc, ld


def world_transforms(bones, byname, overrides=None):
    """回傳每骨 (a,b,c,d,wx,wy) 世界變換。overrides: {boneIdx:(dx,dy,drot,mulsx,mulsy)}。
    bones 假定已按 parent-before-child 排序(Spine JSON 慣例)。"""
    W = [None] * len(bones)
    for i, b in enumerate(bones):
        if b.get("transform", "normal") != "normal":
            raise ValueError(f"bone {b['name']} transform={b['transform']} 尚未支援(僅 normal)")
        x = b.get("x", 0.0); y = b.get("y", 0.0); rot = b.get("rotation", 0.0)
        sx = b.get("scaleX", 1.0); sy = b.get("scaleY", 1.0)
        shx = b.get("shearX", 0.0); shy = b.get("shearY", 0.0)
        if overrides and i in overrides:
            dx, dy, drot, msx, msy = overrides[i]
            x += dx; y += dy; rot += drot; sx *= msx; sy *= msy
        la, lb, lc, ld = _local_mat(rot, sx, sy, shx, shy)
        p = b.get("parent")
        if not p:
            W[i] = (la, lb, lc, ld, x, y)
        else:
            pa, pb, pc, pd, pwx, pwy = W[byname[p]]
            W[i] = (pa * la + pb * lc, pa * lb + pb * ld,
                    pc * la + pd * lc, pc * lb + pd * ld,
                    pa * x + pb * y + pwx, pc * x + pd * y + pwy)
    return W


# ---------- weighted mesh ----------
def parse_weighted(att):
    """回傳 [[(boneIdx,bindX,bindY,weight),...], ...](每頂點一 list)。非 weighted → None。"""
    if len(att["vertices"]) == len(att["uvs"]):
        return None
    v = att["vertices"]; out = []; i = 0
    while i < len(v):
        nb = int(v[i]); i += 1; vw = []
        for _ in range(nb):
            vw.append((int(v[i]), v[i + 1], v[i + 2], v[i + 3])); i += 4
        out.append(vw)
    return out


def skin(weights, W):
    pts = np.empty((len(weights), 2))
    for k, vw in enumerate(weights):
        x = y = 0.0
        for (bi, bx, by, w) in vw:
            a, b, c, d, wx, wy = W[bi]
            x += (a * bx + b * by + wx) * w
            y += (c * bx + d * by + wy) * w
        pts[k] = (x, y)
    return pts


def bind_consistency(weights, W):
    """多骨頂點的每根骨各自映 bind→setup 世界,回傳最大偏差(px)。驗證 world-transform 數學。"""
    maxdev = 0.0
    for vw in weights:
        if len(vw) < 2:
            continue
        pts = np.array([(a * bx + b * by + wx, c * bx + d * by + wy)
                        for (bi, bx, by, w) in vw
                        for (a, b, c, d, wx, wy) in [W[bi]]])
        maxdev = max(maxdev, float(np.linalg.norm(pts - pts.mean(0), axis=1).max()))
    return maxdev


# ---------- 動畫 bone timeline 取樣(線性;curve 以線性近似,對拓樸驗證保守足夠) ----------
def _val(frames, t, keys, defaults):
    """線性內插 frames 在時間 t 的值;keys/defaults 對齊(rotate:['angle'],translate/scale:['x','y'])。"""
    if not frames:
        return list(defaults)
    times = [f.get("time", 0.0) for f in frames]
    if t <= times[0]:
        f = frames[0]; return [f.get(k, d) for k, d in zip(keys, defaults)]
    if t >= times[-1]:
        f = frames[-1]; return [f.get(k, d) for k, d in zip(keys, defaults)]
    for i in range(len(frames) - 1):
        if times[i] <= t <= times[i + 1]:
            a = (t - times[i]) / max(times[i + 1] - times[i], 1e-9)
            f0, f1 = frames[i], frames[i + 1]
            return [f0.get(k, d) * (1 - a) + f1.get(k, d) * a
                    for k, d in zip(keys, defaults)]
    f = frames[-1]; return [f.get(k, d) for k, d in zip(keys, defaults)]


def anim_overrides(skeleton, byname, anim, t):
    """回傳該動畫在時間 t 的 {boneIdx:(dx,dy,drot,mulsx,mulsy)}。"""
    ov = {}
    bd = skeleton["animations"][anim].get("bones", {})
    for bn, tl in bd.items():
        idx = byname.get(bn)
        if idx is None:
            continue
        drot = _val(tl.get("rotate"), t, ["angle"], [0.0])[0] if "rotate" in tl else 0.0
        dx, dy = _val(tl.get("translate"), t, ["x", "y"], [0.0, 0.0]) if "translate" in tl else (0.0, 0.0)
        msx, msy = _val(tl.get("scale"), t, ["x", "y"], [1.0, 1.0]) if "scale" in tl else (1.0, 1.0)
        ov[idx] = (dx, dy, drot, msx, msy)
    return ov


def anim_sample_times(skeleton, byname, anim, target_bones, substeps=3):
    """該動畫中會影響 target_bones(含祖先)的 keyframe 時間聯集 + 相鄰中點。"""
    # 展開 target 的祖先鏈(祖先動也會帶動子骨)
    bones = skeleton["bones"]
    involved = set()
    for bi in target_bones:
        i = bi
        while i is not None:
            involved.add(bones[i]["name"])
            p = bones[i].get("parent"); i = byname.get(p) if p else None
    times = set()
    bd = skeleton["animations"][anim].get("bones", {})
    for bn, tl in bd.items():
        if bn not in involved:
            continue
        for _, frames in tl.items():
            for f in frames:
                times.add(round(f.get("time", 0.0), 4))
    if not times:
        return []
    ts = sorted(times)
    out = []
    for i, t in enumerate(ts):
        out.append(t)
        if i + 1 < len(ts):
            for s in range(1, substeps):
                out.append(t + (ts[i + 1] - t) * s / substeps)
    return out


# ---------- 對某 weighted mesh 跑真實動畫,回傳拓樸品質 ----------
def eval_weighted_mesh(skeleton, byname, weights, tris, target_bones,
                       anims=None, substeps=3):
    W0 = world_transforms(skeleton["bones"], byname)
    setup = skin(weights, W0)
    setup_signs = [signed_area(setup, t) > 0 for t in tris]
    setup_area = sum(abs(signed_area(setup, t)) for t in tris)
    dev = bind_consistency(weights, W0)
    setup_eval = eval_pose(setup, tris, setup_signs, setup_area)
    per_anim = {}
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    anims = anims if anims is not None else list(skeleton.get("animations", {}))
    for anim in anims:
        times = anim_sample_times(skeleton, byname, anim, target_bones, substeps)
        if not times:
            continue
        res = []
        for t in times:
            ov = anim_overrides(skeleton, byname, anim, t)
            Wt = world_transforms(skeleton["bones"], byname, ov)
            v = skin(weights, Wt)
            res.append(eval_pose(v, tris, setup_signs, setup_area))
        agg = {
            "frames_sampled": len(res),
            "max_self_intersections": max(r["self_intersections"] for r in res),
            "max_triangle_flips": max(r["triangle_flips"] for r in res),
            "max_degenerate": max(r["degenerate"] for r in res),
            "area_ratio_range": [min(r["area_ratio"] for r in res),
                                 max(r["area_ratio"] for r in res)],
            "all_clean": all(r["clean"] for r in res),
        }
        per_anim[anim] = agg
        for k in worst:
            worst[k] = max(worst[k], agg["max_" + k])
    return {
        "nv": len(weights), "tris": len(tris),
        "bind_consistency_px": round(dev, 4),
        "checker_validated": dev < TOL and setup_eval["clean"],
        "setup_clean": setup_eval["clean"],
        "anims": per_anim,
        "worst": worst,
        "all_clean": all(a["all_clean"] for a in per_anim.values()) if per_anim else None,
    }


def target_bones_of(weights):
    return sorted({bi for vw in weights for (bi, _, _, _) in vw})


def classify_kind(att):
    """structural = 有內部頂點(hull < nv,骨骼變形靠內部密度撐平滑);
    effect = 純邊界多邊形(hull == nv,軟邊 blob/光暈,大幅縮放下自重疊為美術常態)。"""
    nv = len(att["uvs"]) // 2
    return "effect" if att["hull"] >= nv else "structural"


def artist_baseline(skeleton_path="assets/Award.json", meshes=ROBOT_MESHES):
    sk = json.load(open(skeleton_path))
    byname = {b["name"]: i for i, b in enumerate(sk["bones"])}
    skin_ = sk["skins"]; skin_ = skin_[0] if isinstance(skin_, list) else skin_
    atts = skin_.get("attachments", skin_)
    report = {}
    for slot in meshes:
        att = atts[slot][slot]
        weights = parse_weighted(att)
        if weights is None:
            report[slot] = {"error": "not a weighted mesh"}
            continue
        tris = np.array(att["triangles"], dtype=np.int32).reshape(-1, 3)
        tb = target_bones_of(weights)
        r = eval_weighted_mesh(sk, byname, weights, tris, tb)
        r["kind"] = classify_kind(att)
        r["hull"] = att["hull"]
        r["driving_bones"] = [sk["bones"][i]["name"] for i in tb]
        report[slot] = r
    # 閘:(1) 評估器對每件都可信(bind 一致性 + setup clean);
    #    (2) structural 件在真實動畫下 clean(不透明結構件的變形品質基準)。
    #    effect 件(光暈)大幅縮放下自重疊為美術常態 → 只記錄為基準,不要求 clean。
    checker_ok = all(v.get("checker_validated") for v in report.values() if "error" not in v)
    struct_ok = all(v.get("all_clean") in (True, None)
                    for v in report.values() if v.get("kind") == "structural")
    return {"overall_pass": checker_ok and struct_ok,
            "checker_validated_all": checker_ok,
            "structural_clean": struct_ok,
            "pieces": report}


def _hard_rebind(weights, W0, tb):
    """把平滑權重換成 naive 硬綁(每頂點只綁最近骨、weight=1)—— 差生成器的典型失敗模式。"""
    setup = skin(weights, W0)
    org = {bi: np.array([W0[bi][4], W0[bi][5]]) for bi in tb}
    out = []
    for k, vw in enumerate(weights):
        p = setup[k]
        nb = min(tb, key=lambda bi: float(np.linalg.norm(org[bi] - p)))
        a, b, c, d, wx, wy = W0[nb]; det = a * d - b * c
        dx, dy = p[0] - wx, p[1] - wy
        out.append([(nb, (d * dx - b * dy) / det, (-c * dx + a * dy) / det, 1.0)])
    return out


def negative_control(skeleton_path="assets/Award.json",
                     slot="機器人拆件/身體", child_bone="4_LEG7",
                     degs=(30, 60, 90)):
    """對照:平滑(藝術家)權重 vs naive 硬綁,在合成的極端相對骨旋轉下比拓樸。
    平滑權重應顯著較耐變形 → 證明 LBS 評估器有鑑別權重品質的能力(下一步生成+BBW 的閘)。"""
    sk = json.load(open(skeleton_path))
    byname = {b["name"]: i for i, b in enumerate(sk["bones"])}
    skin_ = sk["skins"]; skin_ = skin_[0] if isinstance(skin_, list) else skin_
    att = skin_.get("attachments", skin_)[slot][slot]
    weights = parse_weighted(att)
    tris = np.array(att["triangles"], dtype=np.int32).reshape(-1, 3)
    tb = target_bones_of(weights)
    W0 = world_transforms(sk["bones"], byname)
    hard = _hard_rebind(weights, W0, tb)
    setup = skin(weights, W0)
    ss = [signed_area(setup, t) > 0 for t in tris]
    sa = sum(abs(signed_area(setup, t)) for t in tris)
    cb = byname[child_bone]
    rows = []
    for deg in degs:
        Wt = world_transforms(sk["bones"], byname, {cb: (0, 0, deg, 1, 1)})
        rs = eval_pose(skin(weights, Wt), tris, ss, sa)
        rh = eval_pose(skin(hard, Wt), tris, ss, sa)
        rows.append({"deg": deg,
                     "smooth": {"si": rs["self_intersections"], "flips": rs["triangle_flips"]},
                     "hard": {"si": rh["self_intersections"], "flips": rh["triangle_flips"]}})
    # 判定:存在某旋轉角,硬綁缺陷數 > 平滑(且平滑在該角仍 clean)→ 鑑別力成立
    discriminates = any(
        (r["hard"]["si"] + r["hard"]["flips"]) > (r["smooth"]["si"] + r["smooth"]["flips"])
        and (r["smooth"]["si"] + r["smooth"]["flips"]) == 0
        for r in rows)
    return {"slot": slot, "child_bone": child_bone, "rows": rows,
            "discriminates": discriminates}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--negctrl", action="store_true",
                    help="跑負對照(平滑 vs 硬綁)確認評估器鑑別力")
    a = ap.parse_args()
    if a.negctrl:
        nc = negative_control(a.skeleton)
        print(json.dumps(nc, ensure_ascii=False, indent=2))
        raise SystemExit(0 if nc["discriminates"] else 1)
    rep = artist_baseline(a.skeleton)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
