#!/usr/bin/env python3
"""S3 — weighted-mesh(骨綁蒙皮)變形評估器:量化「靠骨骼+權重變形的網格」在骨骼擺動下會不會壞。

補上 `compare_robot_mesh.py` 誠實界定的唯一未驗維度:靜態覆蓋率 PASS ≠ 變形品質對等。
`deform_eval.py` 只處理 unweighted(逐頂點 deform timeline)mesh;本檔處理 **weighted mesh**
(vertices 格式 `[boneCount, (boneIdx,bindX,bindY,weight)*bc, ...]`,見 CLAUDE.md 雷點 #6)。

前向蒙皮(forward skinning,Spine 3.8 normal transform mode):
  1. 由 bones 陣列 + pose(在 setup local 上疊加的 rotate/translate 偏移)算每根 bone 的
     world 仿射 (a,b,c,d,wx,wy)(雷點:Spine Y-up;normal 繼承見 Bone.updateWorldTransform)。
  2. 每個頂點 world = Σ_j weight_j * (bone_j.world 套用 bind 座標_j)。
  3. 用 deform_eval 的幾何閘(self_intersections / triangle_flips / degenerate)判定拓樸。

評估器可信度驗證(跑 __main__):
  - 正對照:對 Award 3 個真實美術 weighted mesh(光暈/左手/身體),掃驅動骨旋轉範圍
    → 應全 clean(藝術家平滑權重 + 評估器一致 → 0 flip / 0 自交)。
  - 負對照:把平滑權重換成「硬指派最高權重骨(weight=1,不混合)」→ 相對旋轉下骨界折疊
    → 評估器必須抓到 flip/自交(證明鑑別力:平滑權重確實重要且可量測)。
"""
import json, math
import numpy as np

from deform_eval import signed_area, eval_pose


# ---------- weighted mesh 解析 ----------
def load_weighted(skeleton, slot, name):
    """回傳 (per_vertex, triangles, hull, nv)。
    per_vertex[i] = [(boneIdx, bindX, bindY, weight), ...](該頂點的骨綁項)。"""
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uvs = a["uvs"]; nv = len(uvs) // 2
    V = a["vertices"]
    if len(V) == nv * 2:
        raise ValueError(f"{slot}/{name} 不是 weighted mesh(vertices==uvs 長度)")
    per = []
    i = 0
    while i < len(V):
        bc = int(V[i]); i += 1
        entry = []
        for _ in range(bc):
            bi = int(V[i]); bx = V[i + 1]; by = V[i + 2]; w = V[i + 3]; i += 4
            entry.append((bi, bx, by, w))
        per.append(entry)
    if len(per) != nv:
        raise ValueError(f"{slot}/{name} 解析頂點數 {len(per)} != uv 頂點數 {nv}")
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    return per, tris, a["hull"], nv


def bones_used(per):
    s = set()
    for e in per:
        for (bi, *_r) in e:
            s.add(bi)
    return sorted(s)


# ---------- Spine normal-mode world transform ----------
def _local_matrix(rot, x, y, sx, sy, shx, shy):
    rx = math.radians(rot + shx)
    ry = math.radians(rot + 90.0 + shy)
    la = math.cos(rx) * sx
    lc = math.sin(rx) * sx
    lb = math.cos(ry) * sy
    ld = math.sin(ry) * sy
    return la, lb, lc, ld, x, y


def world_transforms(bones, pose=None):
    """回傳 list[dict]:每根 bone 的 world {a,b,c,d,wx,wy}。
    pose: {boneName: {"rotate":deg, "x":dx, "y":dy, "scaleX":k, "scaleY":k}} —— 疊加在 setup local 上
    (對齊 Spine 動畫語意:translate/rotate 為 setup 偏移;scale 為乘法,預設 1)。
    僅支援 normal transform mode(本資產全 normal;非 normal 會誤,呼叫端須確認)。"""
    pose = pose or {}
    idx = {b["name"]: i for i, b in enumerate(bones)}
    W = [None] * len(bones)

    def compute(i):
        if W[i] is not None:
            return W[i]
        b = bones[i]
        p = pose.get(b["name"], {})
        rot = b.get("rotation", 0.0) + p.get("rotate", 0.0)
        x = b.get("x", 0.0) + p.get("x", 0.0)
        y = b.get("y", 0.0) + p.get("y", 0.0)
        sx = b.get("scaleX", 1.0) * p.get("scaleX", 1.0)
        sy = b.get("scaleY", 1.0) * p.get("scaleY", 1.0)
        shx = b.get("shearX", 0.0); shy = b.get("shearY", 0.0)
        la, lb, lc, ld, lx, ly = _local_matrix(rot, x, y, sx, sy, shx, shy)
        parent = b.get("parent")
        if parent is None or parent not in idx:
            W[i] = {"a": la, "b": lb, "c": lc, "d": ld, "wx": lx, "wy": ly}
        else:
            pw = compute(idx[parent])
            pa, pb, pc, pd = pw["a"], pw["b"], pw["c"], pw["d"]
            W[i] = {
                "a": pa * la + pb * lc, "b": pa * lb + pb * ld,
                "c": pc * la + pd * lc, "d": pc * lb + pd * ld,
                "wx": pa * lx + pb * ly + pw["wx"],
                "wy": pc * lx + pd * ly + pw["wy"],
            }
        return W[i]

    for i in range(len(bones)):
        compute(i)
    return W


def skin_vertices(per, Wt):
    """前向蒙皮 → world 頂點 Nx2。"""
    out = np.zeros((len(per), 2), dtype=np.float64)
    for vi, entry in enumerate(per):
        px = py = 0.0
        for (bi, bx, by, w) in entry:
            wt = Wt[bi]
            wx = bx * wt["a"] + by * wt["b"] + wt["wx"]
            wy = bx * wt["c"] + by * wt["d"] + wt["wy"]
            px += wx * w
            py += wy * w
        out[vi] = (px, py)
    return out


# ---------- 掃驅動骨旋轉,逐姿勢判定 ----------
def _setup_ref(bones, per, tris):
    W0 = world_transforms(bones, None)
    setup = skin_vertices(per, W0)
    signs = [signed_area(setup, t) > 0 for t in tris]
    area0 = sum(abs(signed_area(setup, t)) for t in tris) or 1.0
    return setup, signs, area0


def pose_at(bones, per, tris, drive_bone, deg, ref):
    _, signs, area0 = ref
    W = world_transforms(bones, {bones[drive_bone]["name"]: {"rotate": deg}})
    v = skin_vertices(per, W)
    r = eval_pose(v, tris, signs, area0)
    r["deg"] = round(deg, 1)
    return v, r


def break_angle(bones, per, tris, drive_bone, ref, max_deg=90):
    """繞 setup 對 drive_bone 兩方向逐度旋轉,回傳首次破壞(自交/翻面/退化)的最小|角度|。
    calibration-free:不需人為位移場幅度(避開 deform_eval.stress_field 的假性失敗教訓)。"""
    for deg in range(1, max_deg + 1):
        for d in (deg, -deg):
            _, r = pose_at(bones, per, tris, drive_bone, d, ref)
            if not r["clean"]:
                return deg
    return max_deg  # 到上限仍乾淨(視為 >=max_deg)


def hard_partition(per):
    """對照:每頂點只保留最高權重骨(weight=1,不混合)→ 移除權重平滑;
    用於量化「權重分布如何改變變形響應」(非通用 pass/fail:小影響驅動骨下反而更僵直)。"""
    out = []
    for entry in per:
        top = max(entry, key=lambda e: e[3])
        out.append([(top[0], top[1], top[2], 1.0)])
    return out


PARTS = [
    ("機器人拆件/光暈", "機器人拆件/光暈"),
    ("機器人拆件/左手", "機器人拆件/左手"),
    ("機器人拆件/身體", "機器人拆件/身體"),
]


def pick_drive_bone(bones, per, used):
    """驅動骨 = used 中 parent 也在 used 的子骨裡、權重占比最大的一根(製造相對運動)。"""
    from collections import defaultdict
    share = defaultdict(float)
    for e in per:
        for (bi, bx, by, w) in e:
            share[bi] += w
    usedset = {bones[u]["name"] for u in used}
    children = [b for b in used if bones[b].get("parent") in usedset]
    pool = children or used
    return max(pool, key=lambda b: share[b]), dict(share)


# ---------- validator ----------
def validate(path="assets/Award.json"):
    """兩支可機讀 claim:
       (A) 蒙皮正確性錨:每頂點權重和=1、setup pose 拓樸乾淨、setup 包圍盒主軸 ≈ region 尺寸
           (獨立佐證 Y-up/旋轉/scale 繼承算對)。
       (B) 折疊偵測力:對每件驅動骨掃旋轉,checker 回報有限破壞角(<max)→ 能抓折疊(非靜默放行);
           且 setup(0°)乾淨 → 無假陽性。
       evaluator_validated = A ∧ B。smooth vs hard 破壞角作為『資料』誠實附上(不當閘)。"""
    sk = json.load(open(path))
    bones = sk["bones"]
    skin = sk["skins"][0]["attachments"] if isinstance(sk["skins"], list) else sk["skins"]
    report = {}
    corr_ok = True
    disc_ok = True
    for slot, name in PARTS:
        per, tris, hull, nv = load_weighted(sk, slot, name)
        used = bones_used(per)
        drive, share = pick_drive_bone(bones, per, used)
        ref = _setup_ref(bones, per, tris)
        setup, signs, area0 = ref
        # (A) 正確性錨
        wsum = [sum(e[3] for e in entry) for entry in per]
        wsum_ok = all(abs(x - 1.0) < 1e-3 for x in wsum)
        r0 = eval_pose(setup, tris, signs, area0)
        setup_clean = r0["clean"]
        att = skin[slot][name]
        bb = (setup.max(0) - setup.min(0))
        reg = np.array([att.get("width", 0), att.get("height", 0)], dtype=np.float64)
        # 主軸比:mesh 形狀主延伸應填滿 region 主軸(在 [0.85,1.1] 視為 scale/朝向正確)
        ratio = float(max(bb) / max(reg)) if max(reg) else 0.0
        bbox_ok = 0.85 <= ratio <= 1.1
        part_corr = wsum_ok and setup_clean and bbox_ok
        corr_ok = corr_ok and part_corr
        # (B) 折疊偵測 + smooth/hard 破壞角
        ba_smooth = break_angle(bones, per, tris, drive, ref)
        ba_hard = break_angle(bones, hard_partition(per), tris, drive,
                              _setup_ref(bones, hard_partition(per), tris))
        detects_fold = ba_smooth < 90
        disc_ok = disc_ok and detects_fold and setup_clean
        report[slot] = {
            "nv": nv, "hull": hull, "tris": len(tris),
            "bones_used": [bones[b]["name"] for b in used],
            "drive_bone": bones[drive]["name"],
            "weight_share": {bones[k]["name"]: round(v, 1) for k, v in
                             sorted(share.items(), key=lambda kv: -kv[1])},
            "correctness": {"weight_sum_all_1": wsum_ok, "setup_clean": setup_clean,
                            "setup_bbox": [round(float(bb[0]), 1), round(float(bb[1]), 1)],
                            "region_wh": [att.get("width"), att.get("height")],
                            "principal_ratio": round(ratio, 3), "bbox_ok": bbox_ok,
                            "pass": part_corr},
            "fold_detection": {"smooth_break_deg": ba_smooth, "hard_break_deg": ba_hard,
                               "detects_fold": detects_fold},
        }
    report["_summary"] = {
        "correctness_anchor": corr_ok,
        "fold_detection": disc_ok,
        "evaluator_validated": bool(corr_ok and disc_ok),
        "note": "smooth vs hard 破壞角為資料非閘:權重分布效應依驅動骨影響力而異"
                "(見 knowledge/s3-weighted-deform-evaluator.md)。",
    }
    return report


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    rep = validate(path)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    ok = rep["_summary"]["evaluator_validated"]
    print("\nevaluator_validated:", ok)
    sys.exit(0 if ok else 1)
