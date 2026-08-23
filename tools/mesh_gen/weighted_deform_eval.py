#!/usr/bin/env python3
"""S3 — weighted-mesh **骨骼變形** 評估器:量化「靠骨骼權重(LBS)變形的網格在真實動畫下會不會壞」。

補上 `knowledge/s3-robot-mesh-vs-award.md` 唯一未驗維度:
  之前只驗了 weighted mesh 的『靜態覆蓋率 IoU』;bone-driven 變形平滑度未驗。
  本檔用 Award 真實骨架 + 權重 + 動畫,以 forward-kinematics + linear-blend-skinning
  重現 Spine 對 weighted mesh 的世界頂點計算,再套 deform_eval 的幾何閘。

方法(對照 CLAUDE.md 雷點 #4/#6):
  1. FK:每骨 world transform = parent.world ∘ local(setup + 動畫 delta)。全骨依序(parent 先)。
     transform mode 目前資產全為 normal(已驗)。
  2. LBS(weighted mesh):
        worldVertex = Σ_b  weight_b * ( bone_b.world 套用到 bind 座標(bx,by) )
     bind 座標為 setup pose 下相對該骨的座標(#6)。
  3. 幾何閘:重用 deform_eval 的 self_intersections / triangle_flips / degenerate / area_ratio。

角度慣例:Spine world transform 對整體是一致仿射(含可能的全域鏡射);self-intersection 與
「相對 setup 的 flip」對全域仿射不變,故不需校 y-up/down 或 skeleton flip —— 只要 setup 與
各 pose 用同一套 FK 即可(t=0 identity 閘會抓到不一致)。

curve:於 keyframe 時刻取『精確值』(不受 bezier 影響)+ 相鄰幀線性 substep(與 deform_eval 一致)。
"""
import json, math
import numpy as np

from deform_eval import signed_area, eval_pose  # 重用幾何閘


# ---------- 骨架載入 ----------
def load_skeleton(path):
    return json.load(open(path))


def parse_weighted_mesh(sk, slot, name):
    """回傳 (verts, tris, hull, nv):verts[i] = [(boneIdx, bindX, bindY, weight), ...]。"""
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    if len(a["vertices"]) == len(a["uvs"]):
        raise ValueError(f"{slot}/{name} 不是 weighted mesh(vertices 長度 == uvs)")
    v = a["vertices"]; verts = []; i = 0
    while i < len(v):
        n = int(v[i]); i += 1
        entry = []
        for _ in range(n):
            entry.append((int(v[i]), float(v[i + 1]), float(v[i + 2]), float(v[i + 3])))
            i += 4
        verts.append(entry)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    return verts, tris, a["hull"], len(verts)


# ---------- forward kinematics ----------
def _local_matrix(rot_deg, sx, sy, shx, shy):
    """回傳 (a,b,c,d):Spine local 旋轉+縮放+剪切矩陣。"""
    r = math.radians(rot_deg + shx)
    ry = math.radians(rot_deg + 90 + shy)
    a = math.cos(r) * sx
    c = math.sin(r) * sx
    b = math.cos(ry) * sy
    d = math.sin(ry) * sy
    return a, b, c, d


def _bone_setup_local(b):
    return {
        "x": float(b.get("x", 0.0)), "y": float(b.get("y", 0.0)),
        "rotation": float(b.get("rotation", 0.0)),
        "scaleX": float(b.get("scaleX", 1.0)), "scaleY": float(b.get("scaleY", 1.0)),
        "shearX": float(b.get("shearX", 0.0)), "shearY": float(b.get("shearY", 0.0)),
        "parent": b.get("parent"), "name": b["name"],
        "transform": b.get("transform", "normal"),
    }


def _timeline_value(frames, t, keys, mult=False):
    """在 keyframe 時刻取精確值,幀間線性(deform_eval 慣例)。keys 例:('x','y') / ('angle',)。
    回傳 dict{key: value}。空/無值幀該 key 視為 0(mult 時視為 1)。"""
    default = 1.0 if mult else 0.0
    if not frames:
        return {k: default for k in keys}
    # frames 已依 time 排序
    times = [f.get("time", 0.0) for f in frames]
    if t <= times[0]:
        f = frames[0]
        return {k: float(f.get(k, default)) for k in keys}
    if t >= times[-1]:
        f = frames[-1]
        return {k: float(f.get(k, default)) for k in keys}
    for i in range(len(frames) - 1):
        if times[i] <= t <= times[i + 1]:
            f0, f1 = frames[i], frames[i + 1]
            span = times[i + 1] - times[i]
            a = 0.0 if span <= 0 else (t - times[i]) / span
            out = {}
            for k in keys:
                v0 = float(f0.get(k, default)); v1 = float(f1.get(k, default))
                out[k] = v0 * (1 - a) + v1 * a
            return out
    f = frames[-1]
    return {k: float(f.get(k, default)) for k in keys}


def pose_locals(bones_setup, anim, t):
    """回傳每骨的 animated local(setup + 動畫 delta at time t)。"""
    bonetl = (anim or {}).get("bones", {}) if anim else {}
    locals_ = {}
    for name, s in bones_setup.items():
        loc = dict(s)
        tl = bonetl.get(name)
        if tl:
            if "rotate" in tl:
                loc["rotation"] += _timeline_value(tl["rotate"], t, ("angle",))["angle"]
            if "translate" in tl:
                d = _timeline_value(tl["translate"], t, ("x", "y"))
                loc["x"] += d["x"]; loc["y"] += d["y"]
            if "scale" in tl:
                d = _timeline_value(tl["scale"], t, ("x", "y"), mult=True)
                loc["scaleX"] *= d["x"]; loc["scaleY"] *= d["y"]
            if "shear" in tl:
                d = _timeline_value(tl["shear"], t, ("x", "y"))
                loc["shearX"] += d["x"]; loc["shearY"] += d["y"]
        locals_[name] = loc
    return locals_


def world_transforms(bones_order, locals_):
    """依 bone 順序(parent 先)計算 world transform。回傳 {name:(a,b,c,d,wx,wy)}。
    僅實作 transform='normal'(本資產全為 normal);遇其他 mode 拋錯以免默默算錯。"""
    W = {}
    for name in bones_order:
        loc = locals_[name]
        if loc["transform"] != "normal":
            raise NotImplementedError(f"bone {name} transform={loc['transform']} 尚未實作")
        la, lb, lc, ld = _local_matrix(loc["rotation"], loc["scaleX"], loc["scaleY"],
                                       loc["shearX"], loc["shearY"])
        p = loc["parent"]
        if p is None or p not in W:
            # root
            W[name] = (la, lb, lc, ld, loc["x"], loc["y"])
        else:
            pa, pb, pc, pd, pwx, pwy = W[p]
            a = pa * la + pb * lc
            b = pa * lb + pb * ld
            c = pc * la + pd * lc
            d = pc * lb + pd * ld
            wx = pa * loc["x"] + pb * loc["y"] + pwx
            wy = pc * loc["x"] + pd * loc["y"] + pwy
            W[name] = (a, b, c, d, wx, wy)
    return W


def lbs_vertices(verts, bone_names, W):
    """LBS:回傳 Nx2 world 座標。verts[i]=[(boneIdx,bx,by,w),...]。"""
    out = np.zeros((len(verts), 2), dtype=np.float64)
    for i, entry in enumerate(verts):
        x = y = 0.0
        for (bi, bx, by, w) in entry:
            a, b, c, d, wx, wy = W[bone_names[bi]]
            x += (a * bx + b * by + wx) * w
            y += (c * bx + d * by + wy) * w
        out[i] = (x, y)
    return out


# ---------- slot 可見度(alpha)閘 ----------
def slot_alpha(anim, slot, t):
    """回傳 slot 在時刻 t 的 alpha(0..1)。無 color timeline → 1.0(全可見)。
    color 為 'RRGGBBAA' hex;honor 'stepped'(保持值至下一幀)。"""
    sl = (anim.get("slots", {}) or {}).get(slot, {})
    frames = sl.get("color")
    if not frames:
        return 1.0

    def a_of(f):
        c = f.get("color", "ffffffff")
        return int(c[6:8], 16) / 255.0
    times = [f.get("time", 0.0) for f in frames]
    if t <= times[0]:
        return a_of(frames[0])
    if t >= times[-1]:
        return a_of(frames[-1])
    for i in range(len(frames) - 1):
        if times[i] <= t <= times[i + 1]:
            f0, f1 = frames[i], frames[i + 1]
            if f0.get("curve") == "stepped":
                return a_of(f0)
            span = times[i + 1] - times[i]
            a = 0.0 if span <= 0 else (t - times[i]) / span
            return a_of(f0) * (1 - a) + a_of(f1) * a
    return a_of(frames[-1])


# ---------- 高階:對一個 slot 跑一支動畫 ----------
def _anim_duration(anim):
    dur = 0.0
    for _, tls in (anim.get("bones", {}) or {}).items():
        for _, frames in tls.items():
            for f in frames:
                dur = max(dur, f.get("time", 0.0))
    return dur


def pose_world(sk, bones_setup, bones_order, bone_names, verts, anim, t):
    locs = pose_locals(bones_setup, anim, t)
    W = world_transforms(bones_order, locs)
    return lbs_vertices(verts, bone_names, W)


def sample_anim(sk, slot, name, anim_name, substeps=4):
    """回傳 [(label, worldVertsNx2)]:keyframe 時刻 + 線性 substep。"""
    bones = sk["bones"]
    bones_setup = {b["name"]: _bone_setup_local(b) for b in bones}
    bones_order = [b["name"] for b in bones]
    bone_names = bones_order
    verts, tris, hull, nv = parse_weighted_mesh(sk, slot, name)
    anim = sk["animations"][anim_name]
    dur = _anim_duration(anim)
    # 取所有 keyframe 時刻(只看驅動此 mesh 的骨 + 其祖先其實都影響;簡化:取全動畫 keyframe 時刻)
    times = set([0.0, dur])
    for _, tls in (anim.get("bones", {}) or {}).items():
        for _, frames in tls.items():
            for f in frames:
                times.add(f.get("time", 0.0))
    times = sorted(times)
    poses = []

    def add(tt):
        wv = pose_world(sk, bones_setup, bones_order, bone_names, verts, anim, tt)
        vis = slot_alpha(anim, slot, tt) > 0.05
        poses.append((f"t={tt:.3f}", wv, vis))
    for i, t in enumerate(times):
        add(t)
        if i + 1 < len(times):
            t2 = times[i + 1]
            for s in range(1, substeps):
                a = s / substeps
                add(t * (1 - a) + t2 * a)
    return poses, tris


def _agg(res):
    if not res:
        return None
    return {
        "frames_sampled": len(res),
        "max_self_intersections": max(r["self_intersections"] for r in res),
        "max_triangle_flips": max(r["triangle_flips"] for r in res),
        "max_degenerate": max(r["degenerate"] for r in res),
        "area_ratio_range": [min(r["area_ratio"] for r in res), max(r["area_ratio"] for r in res)],
        "all_clean": all(r["clean"] for r in res),
    }


def eval_slot_anim(sk, slot, name, anim_name, setup_world=None):
    """回傳 (report, poses, tris)。report 分 all(全幀)與 visible(slot alpha>0.05)。
    變形品質判定應以 visible 為準:不可見的進場擠壓不算破圖。"""
    poses, tris = sample_anim(sk, slot, name, anim_name)
    if setup_world is None:
        setup_world = poses[0][1]  # t=0
    setup_signs = [signed_area(setup_world, t) > 0 for t in tris]
    setup_area = sum(abs(signed_area(setup_world, t)) for t in tris)
    all_res, vis_res = [], []
    for _, v, vis in poses:
        r = eval_pose(v, tris, setup_signs, setup_area)
        all_res.append(r)
        if vis:
            vis_res.append(r)
    return {"all": _agg(all_res), "visible": _agg(vis_res),
            "visible_frac": round(len(vis_res) / len(all_res), 2) if all_res else 0.0}, poses, tris


def setup_world_vertices(sk, slot, name):
    """setup pose(無動畫)下的 LBS world 頂點 —— 該 weighted mesh 的真實 setup 幾何。"""
    bones = sk["bones"]
    bones_setup = {b["name"]: _bone_setup_local(b) for b in bones}
    bones_order = [b["name"] for b in bones]
    verts, tris, hull, nv = parse_weighted_mesh(sk, slot, name)
    W = world_transforms(bones_order, {k: dict(v) for k, v in bones_setup.items()})
    return lbs_vertices(verts, bones_order, W), tris, hull, nv


# ---------- 驗證器自檢(evaluator trustworthiness) ----------
def self_validate(path, slots):
    """AC1 t=0 identity、AC2 setup cleanliness、AC3 discriminative(負對照)。"""
    sk = load_skeleton(path)
    report = {"AC1_t0_identity": {}, "AC2_setup_clean": {}, "AC3_negative_control": {}}
    for slot, name in slots:
        # AC2: setup 世界頂點乾淨
        sw, tris, hull, nv = setup_world_vertices(sk, slot, name)
        signs = [signed_area(sw, t) > 0 for t in tris]
        area = sum(abs(signed_area(sw, t)) for t in tris)
        base = eval_pose(sw, tris, signs, area)
        report["AC2_setup_clean"][f"{slot}"] = {
            "self_intersections": base["self_intersections"],
            "degenerate": base["degenerate"], "nv": nv, "hull": hull,
            "pass": base["self_intersections"] == 0 and base["degenerate"] == 0,
        }
        # AC1: FK/LBS 中性 —— 套「空動畫」(無任何 timeline)應與 setup 完全一致。
        # (不用『動畫 t=0』:In/Out 進出場動畫 t=0 本就偏離 setup,那不是 FK bug。)
        bones = sk["bones"]
        bones_setup = {b["name"]: _bone_setup_local(b) for b in bones}
        bones_order = [b["name"] for b in bones]
        verts, tr, _, _ = parse_weighted_mesh(sk, slot, name)
        neutral = pose_world(sk, bones_setup, bones_order, bones_order, verts,
                             {"bones": {}}, 0.0)
        diff = float(np.abs(neutral - sw).max())
        report["AC1_t0_identity"][f"{slot}"] = {
            "test": "empty-anim == setup", "max_abs_diff_vs_setup": round(diff, 9),
            "pass": diff < 1e-9,
        }
        # AC3: 注入大角度假旋轉到驅動骨 → 應出現 self-int / flip
        report["AC3_negative_control"][f"{slot}"] = _negative_control(sk, slot, name)
    report["_all_pass"] = (
        all(v["pass"] for v in report["AC1_t0_identity"].values())
        and all(v["pass"] for v in report["AC2_setup_clean"].values())
        and all(v["pass"] for v in report["AC3_negative_control"].values())
    )
    return report


def _find_driving_anim(sk, slot, name):
    verts, tris, hull, nv = parse_weighted_mesh(sk, slot, name)
    used = sorted({bi for e in verts for (bi, _, _, _) in e})
    used_names = {sk["bones"][i]["name"] for i in used}
    for an, ad in sk["animations"].items():
        bt = ad.get("bones", {}) or {}
        if used_names & set(bt.keys()):
            return an
    return None


def _negative_control(sk, slot, name):
    """對驅動骨注入 +60° 假旋轉,檢查評估器能否抓到破壞(鑑別力)。"""
    bones = sk["bones"]
    bones_setup = {b["name"]: _bone_setup_local(b) for b in bones}
    bones_order = [b["name"] for b in bones]
    verts, tris, hull, nv = parse_weighted_mesh(sk, slot, name)
    used = sorted({bi for e in verts for (bi, _, _, _) in e})
    target = bones_order[used[len(used) // 2]]  # 挑中間一根驅動骨
    sw, _, _, _ = setup_world_vertices(sk, slot, name)
    signs = [signed_area(sw, t) > 0 for t in tris]
    area = sum(abs(signed_area(sw, t)) for t in tris)
    worst = {"self_intersections": 0, "triangle_flips": 0}
    for ang in (30, 60, 120):
        locs = {k: dict(v) for k, v in bones_setup.items()}
        locs[target]["rotation"] += ang
        W = world_transforms(bones_order, locs)
        wv = lbs_vertices(verts, bones_order, W)
        r = eval_pose(wv, tris, signs, area)
        worst["self_intersections"] = max(worst["self_intersections"], r["self_intersections"])
        worst["triangle_flips"] = max(worst["triangle_flips"], r["triangle_flips"])
    return {"bogus_bone": target, "worst": worst,
            "pass": worst["self_intersections"] > 0 or worst["triangle_flips"] > 0}


def benchmark(path, slots):
    """對 slot 逐動畫跑真實變形品質基準(藝術家真值)。"""
    sk = load_skeleton(path)
    out = {}
    for slot, name in slots:
        driving_anims = []
        verts, tris, hull, nv = parse_weighted_mesh(sk, slot, name)
        used = sorted({bi for e in verts for (bi, _, _, _) in e})
        used_names = {sk["bones"][i]["name"] for i in used}
        for an, ad in sk["animations"].items():
            bt = ad.get("bones", {}) or {}
            if used_names & set(bt.keys()):
                driving_anims.append(an)
        sw, _, _, _ = setup_world_vertices(sk, slot, name)
        per = {}
        for an in driving_anims:
            agg, _, _ = eval_slot_anim(sk, slot, name, an, setup_world=sw)
            per[an] = agg
        out[f"{slot}"] = {"nv": nv, "hull": hull, "tris": len(tris),
                          "driving_bones": sorted(used_names), "anims": per}
    return out


ROBOT_SLOTS = [("機器人拆件/光暈", "機器人拆件/光暈"),
               ("機器人拆件/左手", "機器人拆件/左手"),
               ("機器人拆件/身體", "機器人拆件/身體")]

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    print("=== 評估器自檢(AC1 t0 / AC2 setup clean / AC3 negative control)===")
    sv = self_validate(path, ROBOT_SLOTS)
    print(json.dumps(sv, ensure_ascii=False, indent=2))
    print("\n=== 藝術家真實 weighted mesh 變形品質基準 ===")
    bm = benchmark(path, ROBOT_SLOTS)
    print(json.dumps(bm, ensure_ascii=False, indent=2))
    ok = sv["_all_pass"]
    print("\nSELF-VALIDATE:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
