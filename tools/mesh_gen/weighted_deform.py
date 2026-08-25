#!/usr/bin/env python3
"""S2/S3 — weighted-mesh 骨骼變形評估器:量化「綁骨(BBW)的網格在動畫骨骼拉扯下會不會壞、平不平滑」。

與 deform_eval.py 的差別:
  - deform_eval 針對 **unweighted** mesh(main_draw 4 件),變形來自 `deform` timeline 的逐頂點 offset。
  - 本檔針對 **weighted** mesh(Award 機器人光暈/左手/身體),變形來自 **骨骼變換**:
        worldVertex = Σ_bone  weight * (boneWorldTransform ∘ bindLocal)
    骨骼世界變換由 bone 階層 SRT 組合、再疊加動畫 rotate/translate/scale timeline 得到。

補上 STATE 標記的「唯一未驗維度」:weighted mesh 骨骼變形平滑度。
真值:Award.json 內 7 個真實 weighted mesh 的權重 + 骨架 + 動畫(藝術家手綁)。

雷點對照(CLAUDE.md #4/#6):
  - 取變形後座標必須同步 re-pose(此處直接算世界變換,等價)。
  - weighted 格式 [numBones, (boneIdx,bindX,bindY,weight)*n];hull 頂點排最前;bind 為相對該骨座標;權重和=1。
  - 所有 Award bone 皆 transform=normal(標準 SRT),無 IK/constraint 介入這些骨 → 直接階層組合即可。

幾何品質閘沿用 deform_eval:self_intersections / triangle_flips / degenerate(+ 新增邊長應變平滑度)。
"""
import json, math, sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deform_eval import signed_area, eval_pose  # 復用幾何閘

DEG = math.pi / 180.0


# ---------- 讀取 ----------
def load_skeleton(path):
    with open(path) as f:
        return json.load(f)


def get_attachment(skel, slot, name):
    skin = skel["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    return atts[slot][name]


def parse_weighted(a):
    """回傳 (verts_w, tris, hull, nverts)。verts_w[i] = [(boneIdx,bindX,bindY,weight), ...]。
    若為 unweighted(vertices==2*uvs)則回傳 None(本評估器只處理 weighted)。"""
    uvs = a["uvs"]
    nv = len(uvs) // 2
    v = a["vertices"]
    if len(v) == len(uvs):
        return None  # unweighted
    verts_w = []
    i = 0
    while i < len(v):
        nb = int(v[i]); i += 1
        vw = []
        for _ in range(nb):
            bi = int(v[i]); bx = v[i + 1]; by = v[i + 2]; w = v[i + 3]; i += 4
            vw.append((bi, float(bx), float(by), float(w)))
        verts_w.append(vw)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    return verts_w, tris, a.get("hull"), nv


def mesh_bone_indices(verts_w):
    s = set()
    for vw in verts_w:
        for (bi, _, _, _) in vw:
            s.add(bi)
    return sorted(s)


# ---------- 動畫 timeline 取樣 ----------
def _sample(frames, t, key, default):
    """線性取樣(stepped 特判)。在確切 key time 會回傳精確值 → 只在 key times 評估時無插值誤差。"""
    if not frames:
        return default
    times = [f.get("time", 0.0) for f in frames]
    vals = [f.get(key, default) for f in frames]
    if t <= times[0]:
        return vals[0]
    if t >= times[-1]:
        return vals[-1]
    for i in range(1, len(times)):
        if t <= times[i] + 1e-9:
            prev = frames[i - 1]
            if prev.get("curve") == "stepped":
                return vals[i - 1]
            t0, t1 = times[i - 1], times[i]
            frac = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return vals[i - 1] + (vals[i] - vals[i - 1]) * frac
    return vals[-1]


def bone_local(bd, anim_bone, t):
    """回傳該骨在時間 t 的 local SRT(setup 疊加動畫)。"""
    x = bd.get("x") or 0.0
    y = bd.get("y") or 0.0
    rot = bd.get("rotation") or 0.0
    sx = bd.get("scaleX"); sx = 1.0 if sx is None else sx
    sy = bd.get("scaleY"); sy = 1.0 if sy is None else sy
    shx = bd.get("shearX") or 0.0
    shy = bd.get("shearY") or 0.0
    if anim_bone:
        if "rotate" in anim_bone:
            rot += _sample(anim_bone["rotate"], t, "angle", 0.0)
        if "translate" in anim_bone:
            x += _sample(anim_bone["translate"], t, "x", 0.0)
            y += _sample(anim_bone["translate"], t, "y", 0.0)
        if "scale" in anim_bone:
            sx *= _sample(anim_bone["scale"], t, "x", 1.0)
            sy *= _sample(anim_bone["scale"], t, "y", 1.0)
        if "shear" in anim_bone:
            shx += _sample(anim_bone["shear"], t, "x", 0.0)
            shy += _sample(anim_bone["shear"], t, "y", 0.0)
    return x, y, rot, sx, sy, shx, shy


def world_transforms(bones, anim_bones, t):
    """所有骨的世界變換 (a,b,c,d,wx,wy)。Spine 3.8 normal 模式;bones 陣列 parent 必在 child 前。"""
    name2idx = {b["name"]: i for i, b in enumerate(bones)}
    world = {}
    for idx, bd in enumerate(bones):
        x, y, rot, sx, sy, shx, shy = bone_local(bd, anim_bones.get(bd["name"]), t)
        rr = (rot + shx) * DEG
        ry = (rot + 90.0 + shy) * DEG
        la = math.cos(rr) * sx
        lc = math.sin(rr) * sx
        lb = math.cos(ry) * sy
        ld = math.sin(ry) * sy
        parent = bd.get("parent")
        pidx = name2idx.get(parent) if parent else None
        if pidx is None or pidx not in world:
            world[idx] = (la, lb, lc, ld, x, y)  # root(骨架 scale 視為 1)
        else:
            pa, pb, pc, pd, pwx, pwy = world[pidx]
            a = pa * la + pb * lc
            b = pa * lb + pb * ld
            c = pc * la + pd * lc
            d = pc * lb + pd * ld
            wx = pa * x + pb * y + pwx
            wy = pc * x + pd * y + pwy
            world[idx] = (a, b, c, d, wx, wy)
    return world


def skin(verts_w, world):
    """weighted 蒙皮:世界座標。"""
    out = np.zeros((len(verts_w), 2), dtype=np.float64)
    for vi, vw in enumerate(verts_w):
        px = py = 0.0
        for (bi, bx, by, w) in vw:
            a, b, c, d, wx, wy = world[bi]
            px += (a * bx + b * by + wx) * w
            py += (c * bx + d * by + wy) * w
        out[vi] = (px, py)
    return out


# ---------- 平滑度(邊長應變)----------
def edge_strain(setup, deformed, tris):
    """回傳 {max_strain, strain_std}:邊在變形前後的長度比 |len_def/len_setup - 1|。
    藝術家平滑權重 → 應變小且均勻;硬綁(nearest-bone)→ 骨界邊出現高應變尖峰。"""
    edges = set()
    for t in tris:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            edges.add((min(int(a), int(b)), max(int(a), int(b))))
    strains = []
    for (i, j) in edges:
        l0 = np.linalg.norm(setup[i] - setup[j])
        l1 = np.linalg.norm(deformed[i] - deformed[j])
        if l0 > 1e-6:
            strains.append(abs(l1 / l0 - 1.0))
    strains = np.array(strains) if strains else np.array([0.0])
    return {"max_strain": round(float(strains.max()), 4),
            "strain_std": round(float(strains.std()), 4),
            "strain_mean": round(float(strains.mean()), 4)}


# ---------- 負對照:硬綁(每頂點只留最大權重骨)----------
def hardify(verts_w):
    """把平滑權重塌成 nearest/最大權重單骨(weight=1)→ 剛體分割。用作評估器鑑別力的負對照。"""
    out = []
    for vw in verts_w:
        bi, bx, by, w = max(vw, key=lambda e: e[3])
        out.append([(bi, bx, by, 1.0)])
    return out


# ---------- 動畫關鍵時刻 ----------
def anim_keytimes(anim, bone_names):
    """收集動畫中這些骨所有 timeline 的 key times(聯集),含 t=0。極端姿勢多在 key times → 最易壞。"""
    ts = {0.0}
    bt = anim.get("bones", {})
    for bn in bone_names:
        for kind, frames in bt.get(bn, {}).items():
            for f in frames:
                ts.add(round(float(f.get("time", 0.0)), 4))
    return sorted(ts)


# ---------- 單一 mesh × 單一動畫評估 ----------
def eval_mesh_anim(skel, slot, name, anim_name, verts_w_override=None):
    bones = skel["bones"]
    a = get_attachment(skel, slot, name)
    parsed = parse_weighted(a)
    if parsed is None:
        return {"error": "not weighted"}
    verts_w, tris, hull, nv = parsed
    if verts_w_override is not None:
        verts_w = verts_w_override
    bone_names = [bones[bi]["name"] for bi in mesh_bone_indices(verts_w)]
    anim = skel["animations"][anim_name]

    # setup pose(無動畫)
    w0 = world_transforms(bones, {}, 0.0)
    setup = skin(verts_w, w0)
    setup_signs = [signed_area(setup, t) > 0 for t in tris]
    setup_area = sum(abs(signed_area(setup, t)) for t in tris) or 1.0

    frames = []
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0, "max_strain": 0.0}
    for t in anim_keytimes(anim, bone_names):
        wt = world_transforms(bones, anim.get("bones", {}), t)
        dv = skin(verts_w, wt)
        r = eval_pose(dv, tris, setup_signs, setup_area)
        st = edge_strain(setup, dv, tris)
        r.update(st)
        r["time"] = t
        frames.append(r)
        worst["self_intersections"] = max(worst["self_intersections"], r["self_intersections"])
        worst["triangle_flips"] = max(worst["triangle_flips"], r["triangle_flips"])
        worst["degenerate"] = max(worst["degenerate"], r["degenerate"])
        worst["max_strain"] = max(worst["max_strain"], r["max_strain"])
    clean = (worst["self_intersections"] == 0 and worst["triangle_flips"] == 0
             and worst["degenerate"] == 0)
    return {"slot": slot, "anim": anim_name, "nverts": nv, "ntris": len(tris),
            "bones": bone_names, "nframes": len(frames), "worst": worst,
            "clean": clean, "frames": frames}


def stress_break_point(skel, slot, name, anim_name, verts_w_override=None,
                       amps=(1, 1.5, 2, 3, 4, 6, 8, 12), ):
    """把動畫的骨骼偏移(相對 setup)放大 k 倍,找「首次出現自交/翻面」的 k。
    平滑權重(BBW/藝術家)應能撐過更大的 k 才壞 → 量化拓樸韌性,作為 foldover 閘的鑑別力。
    做法:對每根相關骨,取其動畫 timeline 在最大幅度 key 的偏移(相對 setup),
    以 k 倍施加為一個放大姿勢,重算世界變換 + 蒙皮 + 幾何閘。"""
    bones = skel["bones"]
    name2idx = {b["name"]: i for i, b in enumerate(bones)}
    a = get_attachment(skel, slot, name)
    verts_w, tris, hull, nv = parse_weighted(a)
    if verts_w_override is not None:
        verts_w = verts_w_override
    bidx = mesh_bone_indices(verts_w)
    bone_names = [bones[bi]["name"] for bi in bidx]
    anim = skel["animations"][anim_name]
    bt = anim.get("bones", {})

    # 取每根骨在整段動畫的「最大幅度」偏移(相對 setup)
    offs = {}
    for bn in bone_names:
        tl = bt.get(bn, {})
        drot = 0.0; dx = 0.0; dy = 0.0; ssx = 1.0; ssy = 1.0
        if "rotate" in tl:
            drot = max((f.get("angle", 0.0) for f in tl["rotate"]), key=abs, default=0.0)
        if "translate" in tl:
            dx = max((f.get("x", 0.0) for f in tl["translate"]), key=abs, default=0.0)
            dy = max((f.get("y", 0.0) for f in tl["translate"]), key=abs, default=0.0)
        if "scale" in tl:
            ssx = max((f.get("x", 1.0) for f in tl["scale"]), key=lambda v: abs(v - 1), default=1.0)
            ssy = max((f.get("y", 1.0) for f in tl["scale"]), key=lambda v: abs(v - 1), default=1.0)
        offs[bn] = (drot, dx, dy, ssx, ssy)

    w0 = world_transforms(bones, {}, 0.0)
    setup = skin(verts_w, w0)
    setup_signs = [signed_area(setup, t) > 0 for t in tris]
    setup_area = sum(abs(signed_area(setup, t)) for t in tris) or 1.0

    break_k = None
    trace = []
    for k in amps:
        # 建放大後的 local override:直接改 bones 的 setup 值(暫時),再算世界變換
        saved = {}
        for bn, (drot, dx, dy, ssx, ssy) in offs.items():
            bd = bones[name2idx[bn]]
            saved[bn] = {kk: bd.get(kk) for kk in ("rotation", "x", "y", "scaleX", "scaleY")}
            bd["rotation"] = (bd.get("rotation") or 0.0) + drot * k
            bd["x"] = (bd.get("x") or 0.0) + dx * k
            bd["y"] = (bd.get("y") or 0.0) + dy * k
            bd["scaleX"] = (bd.get("scaleX") if bd.get("scaleX") is not None else 1.0) * (1 + (ssx - 1) * k)
            bd["scaleY"] = (bd.get("scaleY") if bd.get("scaleY") is not None else 1.0) * (1 + (ssy - 1) * k)
        wk = world_transforms(bones, {}, 0.0)
        # 還原
        for bn, sv in saved.items():
            bones[name2idx[bn]].update(sv)
        dv = skin(verts_w, wk)
        r = eval_pose(dv, tris, setup_signs, setup_area)
        trace.append((k, r["self_intersections"], r["triangle_flips"], r["clean"]))
        if not r["clean"] and break_k is None:
            break_k = k
    return {"slot": slot, "anim": anim_name, "break_k": break_k, "trace": trace}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--skel", default="assets/Award.json")
    ap.add_argument("--slot", default="機器人拆件/身體")
    ap.add_argument("--anim", default="Award_Legend_Loop")
    ap.add_argument("--hard", action="store_true", help="負對照:硬綁單骨")
    args = ap.parse_args()
    skel = load_skeleton(args.skel)
    ov = None
    if args.hard:
        a = get_attachment(skel, args.slot, args.slot)
        ov = hardify(parse_weighted(a)[0])
    r = eval_mesh_anim(skel, args.slot, args.slot, args.anim, verts_w_override=ov)
    print(json.dumps({k: v for k, v in r.items() if k != "frames"}, ensure_ascii=False, indent=2))
