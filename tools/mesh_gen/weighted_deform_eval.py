#!/usr/bin/env python3
"""S3 — weighted(骨綁) mesh 變形評估器:量化「骨骼驅動的 weighted mesh 在真實動畫下會不會壞」。

補上 `deform_eval.py` 的唯一缺口:那支只處理 unweighted mesh(靠 deform timeline 逐頂點加偏移);
真實生產角色(Award 機器人:光暈/左手/身體 …)是 **weighted mesh**,頂點綁在骨上、靠 bone 動畫變形。
要驗「內部取樣密度 + BBW 權重」是否服務骨骼變形平滑度(STATE 候選 2 的唯一未驗維度),先要這支閘。

Spine 3.8 weighted 變形數學(對照 CLAUDE.md 雷點 #4/#6):
  weighted vertices 攤平格式: [boneCount, (boneIdx, bindX, bindY, weight)*boneCount, ...]
  某頂點世界座標 = Σ_i weight_i · boneWorld_i.transformPoint(bindX_i, bindY_i)
  boneWorld 由 setup 局部姿勢 + 動畫 timeline(translate 加、rotate 加、scale 乘)沿 parent 鏈組成。
  本檔僅支援 transform="normal"(Award 全部骨皆 normal;遇到其他模式會 raise,不靜默出錯)。

幾何品質閘沿用 deform_eval:self_intersections / triangle_flips / degenerate / area_ratio。

驗證真相來源(評估器可信度):
  - 正:藝術家自己的 weighted mesh 用真實動畫驅動 → 全幀乾淨(si=0)。(≈ unweighted 的 _checker_validated)
  - 負:破壞綁定(打亂權重 / 換骨)→ 應偵測到自交/翻面(鑑別力)。
"""
import json, math, sys
import numpy as np

# 沿用既有幾何檢查,單一真相來源
from deform_eval import signed_area, eval_pose, check


def eval_pose_wm(verts, tris, setup_signs, setup_area):
    """weighted mesh 專用姿勢檢查:degeneracy 用**相對面積**判定,避免把
    big-win『整體 scale 從 0 彈入』(全 mesh 均勻縮到 0)誤判為拓樸缺陷。
    self_intersection / flip 本就 scale-invariant,沿用 check()。"""
    r = check(verts, tris, setup_signs)  # self_intersections / triangle_flips / degenerate(abs) / bbox
    areas = [abs(signed_area(verts, t)) for t in tris]
    total = sum(areas)
    mean = total / len(areas) if areas else 0.0
    # 相對 degeneracy:整體幾乎收合(global scale→0)時 mean≈0 → 判定 0(非缺陷);
    # 否則某三角相對於同姿勢平均面積趨零 = 真正局部塌陷(撕裂前兆)。
    if mean < 1e-9:
        rel_degen = 0
    else:
        rel_degen = sum(1 for a in areas if a < 1e-4 * mean)
    r["degenerate"] = rel_degen
    r["area_ratio"] = round(total / setup_area, 3) if setup_area else 0.0
    r["clean"] = (r["self_intersections"] == 0 and r["triangle_flips"] == 0 and rel_degen == 0)
    return r


# ---------- skeleton 讀取 ----------
def load_skeleton(path):
    sk = json.load(open(path))
    bones = sk["bones"]
    byname = {b["name"]: b for b in bones}
    order = [b["name"] for b in bones]  # Spine bones 陣列即為可安全逐一計算的順序(parent 先於 child)
    return sk, bones, byname, order


def get_skin_attachments(sk):
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)


def parse_weighted(att):
    """回傳 (per_vertex list of [(boneIdx,bindX,bindY,weight)...], tris, hull, uvs, weighted?)。"""
    verts = att["vertices"]
    uvs = att["uvs"]
    tris = np.array(att["triangles"], dtype=np.int32).reshape(-1, 3)
    nv = len(uvs) // 2
    weighted = len(verts) != len(uvs)
    if not weighted:
        # unweighted: 直接 (x,y);包成單骨(root)綁定,權重 1,bind 即座標(呼叫端可自行處理)
        pv = [[(None, verts[2 * i], verts[2 * i + 1], 1.0)] for i in range(nv)]
        return pv, tris, att.get("hull"), uvs, False
    pv = []
    i = 0
    while i < len(verts):
        bc = int(verts[i]); i += 1
        entries = []
        for _ in range(bc):
            bi = int(verts[i]); bx = verts[i + 1]; by = verts[i + 2]; w = verts[i + 3]
            entries.append((bi, bx, by, w)); i += 4
        pv.append(entries)
    assert len(pv) == nv, f"parsed {len(pv)} verts, expected {nv}"
    return pv, tris, att.get("hull"), uvs, True


# ---------- bone world transform (transform=normal) ----------
def _cosd(d): return math.cos(math.radians(d))
def _sind(d): return math.sin(math.radians(d))


def local_matrix(x, y, rot, sx, sy, shx=0.0, shy=0.0):
    """回傳 (a,b,c,d, x, y):2x2 仿射 + 平移(Spine world transform 慣例)。"""
    rotY = rot + 90 + shy
    a = _cosd(rot + shx) * sx
    b = _cosd(rotY) * sy
    c = _sind(rot + shx) * sx
    d = _sind(rotY) * sy
    return a, b, c, d, x, y


def compose(parent, local):
    """world = parent ∘ local(皆 (a,b,c,d,x,y))。"""
    pa, pb, pc, pd, px, py = parent
    la, lb, lc, ld, lx, ly = local
    a = pa * la + pb * lc
    b = pa * lb + pb * ld
    c = pc * la + pd * lc
    d = pc * lb + pd * ld
    x = pa * lx + pb * ly + px
    y = pc * lx + pd * ly + py
    return a, b, c, d, x, y


IDENT = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def bone_world_transforms(bones, byname, order, local_pose):
    """local_pose[name] = (x,y,rot,sx,sy) 覆寫;回傳 {name: world (a,b,c,d,x,y)}。"""
    world = {}
    for name in order:
        b = byname[name]
        if b.get("transform", "normal") != "normal":
            raise NotImplementedError(f"bone {name} transform={b['transform']} 未支援")
        lp = local_pose.get(name)
        if lp is None:
            x, y = b.get("x", 0.0), b.get("y", 0.0)
            rot = b.get("rotation", 0.0)
            sx, sy = b.get("scaleX", 1.0), b.get("scaleY", 1.0)
        else:
            x, y, rot, sx, sy = lp
        lm = local_matrix(x, y, rot, sx, sy, b.get("shearX", 0.0), b.get("shearY", 0.0))
        parent = b.get("parent")
        pw = world[parent] if parent else IDENT
        world[name] = compose(pw, lm)
    return world


def transform_point(w, px, py):
    a, b, c, d, x, y = w
    return (a * px + b * py + x, c * px + d * py + y)


def inverse_transform_point(w, px, py):
    """世界點 → 該骨局部座標(用於算 weighted mesh 的 bind 座標)。"""
    a, b, c, d, x, y = w
    det = a * d - b * c
    if abs(det) < 1e-12:
        return (0.0, 0.0)
    dx, dy = px - x, py - y
    return ((d * dx - b * dy) / det, (-c * dx + a * dy) / det)


def edge_length_cv(verts, tris):
    """所有邊長的變異係數(std/mean)—— 變形平滑度指標之一(邊長分布越穩越平滑)。"""
    seen = set(); L = []
    for t in tris:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            e = (min(a, b), max(a, b))
            if e in seen:
                continue
            seen.add(e)
            L.append(float(np.hypot(*(verts[a] - verts[b]))))
    L = np.array(L)
    m = L.mean()
    return float(L.std() / m) if m > 1e-9 else 0.0


# ---------- 動畫 timeline 取樣 ----------
def _curve_interp(kf, nkf, t):
    """回傳 [0,1] 的內插比例 alpha(對應時間段 kf.time..nkf.time)。
    支援 Spine 3.8 緊湊 bezier {curve:cx1,c2:cy1,c3:cx2,c4:cy2}、"stepped"、預設 linear。"""
    t0 = kf.get("time", 0.0); t1 = nkf.get("time", 0.0)
    span = t1 - t0
    p = 0.0 if span <= 0 else (t - t0) / span
    curve = kf.get("curve")
    if curve is None:
        return p  # linear
    if curve == "stepped":
        return 0.0
    # curve == 數值 → bezier;預設 c2=0, c4=1
    cx1 = float(curve); cy1 = float(kf.get("c2", 0.0))
    cx2 = float(kf.get("c3", 1.0)); cy2 = float(kf.get("c4", 1.0))
    # 以 x=p 反解 bezier 參數 s,再取 y。Newton + bisection 混合。
    def bez(s, a, b):  # a,b 為兩個控制點座標(端點 0,1)
        u = 1 - s
        return 3 * u * u * s * a + 3 * u * s * s * b + s * s * s
    lo, hi = 0.0, 1.0
    for _ in range(30):
        mid = (lo + hi) / 2
        x = bez(mid, cx1, cx2)
        if x < p: lo = mid
        else: hi = mid
    s = (lo + hi) / 2
    return bez(s, cy1, cy2)


def sample_timeline(frames, t, key, default=0.0):
    """在時間 t 取 timeline 值(單值 rotate:'angle';雙值 translate/scale:'x','y')。
    ⚠️ Spine 匯出會省略 == 預設值的 channel:translate/rotate 預設 0、**scale 預設 1**。
    呼叫端須傳對的 default(scale 傳 1.0),否則缺 channel 會被當 0 → mesh 塌陷(踩過)。
    回傳 dict of channel→value。"""
    if not frames:
        return {}
    if t <= frames[0].get("time", 0.0):
        kf = frames[0]
        return {k: kf.get(k, default) for k in key}
    if t >= frames[-1].get("time", 0.0):
        kf = frames[-1]
        return {k: kf.get(k, default) for k in key}
    for i in range(len(frames) - 1):
        if frames[i].get("time", 0.0) <= t <= frames[i + 1].get("time", 0.0):
            a, b = frames[i], frames[i + 1]
            alpha = _curve_interp(a, b, t)
            return {k: a.get(k, default) + (b.get(k, default) - a.get(k, default)) * alpha for k in key}
    return {k: frames[0].get(k, default) for k in key}


def anim_local_pose(sk, anim, byname, affected, amplify=1.0):
    """回傳 function(t)->local_pose dict,只覆寫該動畫有 timeline 的骨。
    amplify>1:把 timeline 相對 setup 的 delta 放大(壓力測試用,測綁定品質裕度;
    amplify=1 為忠實重現真實動畫)。"""
    bt = sk["animations"][anim].get("bones", {})

    def at(t):
        pose = {}
        for name in affected:
            b = byname[name]
            x0, y0 = b.get("x", 0.0), b.get("y", 0.0)
            r0 = b.get("rotation", 0.0)
            sx0, sy0 = b.get("scaleX", 1.0), b.get("scaleY", 1.0)
            ch = bt.get(name, {})
            tr = sample_timeline(ch.get("translate", []), t, ("x", "y"), default=0.0)
            ro = sample_timeline(ch.get("rotate", []), t, ("angle",), default=0.0)
            sc = sample_timeline(ch.get("scale", []), t, ("x", "y"), default=1.0)
            x = x0 + amplify * tr.get("x", 0.0); y = y0 + amplify * tr.get("y", 0.0)
            r = r0 + amplify * ro.get("angle", 0.0)
            sx = sx0 * (1.0 + amplify * (sc.get("x", 1.0) - 1.0)) if sc else sx0
            sy = sy0 * (1.0 + amplify * (sc.get("y", 1.0) - 1.0)) if sc else sy0
            pose[name] = (x, y, r, sx, sy)
        return pose
    return at


# ---------- skinning ----------
def skin_vertices(pv, world, bidx_to_name):
    """回傳 Nx2 世界座標(y 不翻轉,純幾何拓樸用)。"""
    out = np.zeros((len(pv), 2), dtype=np.float64)
    for vi, entries in enumerate(pv):
        wx = wy = 0.0
        for (bi, bx, by, w) in entries:
            name = bidx_to_name[bi] if bi is not None else None
            wt = world[name] if name is not None else IDENT
            px, py = transform_point(wt, bx, by)
            wx += px * w; wy += py * w
        out[vi] = (wx, wy)
    return out


# ---------- 主評估 ----------
def anim_duration(sk, anim):
    d = 0.0
    a = sk["animations"][anim]
    for grp in a.values():
        if isinstance(grp, dict):
            for ch in grp.values():
                if isinstance(ch, dict):
                    for frames in ch.values():
                        if isinstance(frames, list):
                            for f in frames:
                                if isinstance(f, dict):
                                    d = max(d, f.get("time", 0.0))
    return d


def affected_bones(sk, anim, mesh_bones, byname):
    """該動畫中,會影響 mesh 綁定骨(含其祖先鏈)的所有骨名。"""
    bt = sk["animations"][anim].get("bones", {})
    need = set()
    for mb in mesh_bones:
        n = mb
        while n:
            need.add(n); n = byname[n].get("parent")
    # 只保留動畫實際有 timeline 的(其餘用 setup);但祖先仍要在 order 中計算,故回傳全鏈
    return need, set(bt.keys()) & need


def eval_pv(sk, bones, byname, order, bidx_to_name, pv, tris, mesh_bone_names,
            anims=None, substeps=6, amplify=1.0):
    """核心:對已解析的 (pv, tris) + 骨架 context 逐動畫逐幀評估(JSON 路徑與生成 mesh 共用)。
    同時輸出變形平滑度指標(area_ratio 波動 std、edge-length CV 相對 setup 的增幅)。"""
    world0 = bone_world_transforms(bones, byname, order, {})
    setup_v = skin_vertices(pv, world0, bidx_to_name)
    setup_signs = [signed_area(setup_v, t) > 0 for t in tris]
    setup_area = sum(abs(signed_area(setup_v, t)) for t in tris)
    setup_check = eval_pose_wm(setup_v, tris, setup_signs, setup_area)
    setup_cv = edge_length_cv(setup_v, tris)

    all_anims = anims or list(sk.get("animations", {}))
    per_anim = {}
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    ar_all, cvinc_all = [], []
    for anim in all_anims:
        chain_all, driven = affected_bones(sk, anim, mesh_bone_names, byname)
        if not driven:
            continue
        dur = anim_duration(sk, anim)
        posef = anim_local_pose(sk, anim, byname, chain_all, amplify=amplify)
        npts = max(8, int(math.ceil(dur / 0.2)) * substeps)
        results = []
        for s in range(npts + 1):
            t = dur * s / npts
            world = bone_world_transforms(bones, byname, order, posef(t))
            v = skin_vertices(pv, world, bidx_to_name)
            r = eval_pose_wm(v, tris, setup_signs, setup_area)
            r["_cv_inc"] = edge_length_cv(v, tris) - setup_cv  # 平滑度:邊長變異相對 setup 的增幅
            results.append(r)
        ars = [r["area_ratio"] for r in results]
        cvs = [r["_cv_inc"] for r in results]
        ar_all += ars; cvinc_all += cvs
        agg = {
            "driven_bones": sorted(driven), "duration": round(dur, 3),
            "frames_sampled": len(results),
            "max_self_intersections": max(r["self_intersections"] for r in results),
            "max_triangle_flips": max(r["triangle_flips"] for r in results),
            "max_degenerate": max(r["degenerate"] for r in results),
            "area_ratio_range": [min(ars), max(ars)],
            "all_clean": all(r["clean"] for r in results),
        }
        per_anim[anim] = agg
        for k in worst:
            worst[k] = max(worst[k], agg["max_" + k])

    smooth = {
        "edge_cv_setup": round(setup_cv, 4),
        "edge_cv_increase_max": round(max(cvinc_all), 4) if cvinc_all else 0.0,
        "area_ratio_std": round(float(np.std(ar_all)), 4) if ar_all else 0.0,
        "area_ratio_span": [round(min(ar_all), 3), round(max(ar_all), 3)] if ar_all else [1.0, 1.0],
    }
    return {
        "nv": len(pv), "tris": len(tris), "bones": mesh_bone_names,
        "setup": setup_check, "anims": per_anim, "worst": worst, "smoothness": smooth,
        "checker_validated": (worst["self_intersections"] == 0 and worst["triangle_flips"] == 0
                              and worst["degenerate"] == 0 and setup_check["clean"]),
    }


def evaluate_weighted_mesh(path, slot, name=None, substeps=6, anims=None, mutate=None, amplify=1.0):
    """對單一 weighted mesh 逐動畫逐幀評估。mutate: 可選 (pv->pv) 破壞綁定做負對照。
    amplify>1:放大骨動畫 delta 做壓力測試(測綁定品質裕度)。"""
    sk, bones, byname, order = load_skeleton(path)
    atts = get_skin_attachments(sk)
    if name is None:
        name = next(iter(atts[slot]))
    att = atts[slot][name]
    pv, tris, hull, uvs, weighted = parse_weighted(att)
    bidx_to_name = {i: b["name"] for i, b in enumerate(bones)}
    mesh_bones = sorted({e[0] for entries in pv for e in entries if e[0] is not None})
    mesh_bone_names = [bidx_to_name[i] for i in mesh_bones]
    if mutate:
        pv = mutate(pv, bidx_to_name)
    r = eval_pv(sk, bones, byname, order, bidx_to_name, pv, tris, mesh_bone_names,
                anims=anims, substeps=substeps, amplify=amplify)
    r.update({"slot": slot, "name": name, "weighted": weighted, "hull": hull})
    return r


# ---------- 負對照 mutators ----------
def mutate_scramble_weights(pv, bidx_to_name):
    """把每頂點的權重循環錯位(仍和=1,但綁錯骨)→ 應造成撕裂。"""
    out = []
    for entries in pv:
        if len(entries) >= 2:
            ws = [e[3] for e in entries]
            ws = ws[-1:] + ws[:-1]  # 循環位移
            out.append([(entries[k][0], entries[k][1], entries[k][2], ws[k]) for k in range(len(entries))])
        else:
            out.append(entries)
    return out


def mutate_rebind_far(pv, bidx_to_name):
    """把單骨頂點的 bind 座標整體平移(模擬綁到錯位骨),測鑑別力。"""
    out = []
    for entries in pv:
        out.append([(bi, bx + 400.0, by - 400.0, w) for (bi, bx, by, w) in entries])
    return out


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    slot = sys.argv[2] if len(sys.argv) > 2 else "機器人拆件/身體"
    rep = evaluate_weighted_mesh(path, slot)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
