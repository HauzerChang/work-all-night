#!/usr/bin/env python3
"""S2/S3 — weighted-mesh deform 評估器:量化「綁骨(weighted)網格在骨骼動畫拉扯下會不會壞」。

補上先前唯一未驗維度(見 STATE / knowledge/s3-robot-mesh-vs-award.md):
`compare_robot_mesh` 只驗**靜態** IoU;weighted mesh 真正的價值是**骨骼變形平滑度**(linear
blend skinning 在動畫下不撕裂/不翻面)。unweighted 的 `deform_eval` 用逐頂點 offset 重現;
weighted 必須重現 **Spine 骨骼世界變換 + LBS**。

技術路徑(對照 CLAUDE.md 雷點 #4/#6):
  - 骨骼世界變換:normal transform mode,由 x,y,rotation,scaleX,scaleY(+parent 鏈)組出仿射
    (a,b,c,d,wx,wy)。Award 全 77 骨皆 normal、無 shear、parent-before-child → 可精確重現。
  - 動畫 timeline:rotate(加角度)/translate(加位移)/scale(乘縮放)。取 keyframe 時間點
    (extreme pose 落在 key 上)+ 相鄰線性內插取樣。
  - LBS:weighted vertex = Σ_j weight_j · boneWorld_j.localToWorld(bindX_j, bindY_j)。
  - 幾何閘沿用 deform_eval(self_intersections / triangle_flips / degenerate)。

驗證真相來源:Award.json 的 7 個真實 weighted mesh × 12 動畫,藝術家手做 → 應全乾淨
(`_checker_validated`,同 unweighted benchmark 的作法)。附負對照證明鑑別力。
"""
import json, math
import numpy as np


# ---------- 向量化幾何閘(拓樸固定 → 預計算,逐 pose 只重算座標) ----------
class MeshChecker:
    """對固定拓樸的 mesh 預計算 edge/pair,逐 pose 向量化檢查自交/翻面/退化。
    與 deform_eval 的純 Python 閘同義,但快數十倍,足以掃全動畫全 pose。"""

    def __init__(self, tris):
        self.tris = np.asarray(tris, dtype=np.int64).reshape(-1, 3)
        # 去重無向邊
        es = set()
        for t in self.tris:
            for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                es.add((int(min(a, b)), int(max(a, b))))
        E = np.array(sorted(es), dtype=np.int64)  # (M,2)
        self.E = E
        M = len(E)
        # 非相鄰邊對(不共頂點)
        iu, ju = np.triu_indices(M, k=1)
        a0, a1 = E[iu, 0], E[iu, 1]
        b0, b1 = E[ju, 0], E[ju, 1]
        share = (a0 == b0) | (a0 == b1) | (a1 == b0) | (a1 == b1)
        keep = ~share
        self.pair_i = iu[keep]
        self.pair_j = ju[keep]

    @staticmethod
    def _areas(p, tris):
        a = p[tris[:, 0]]; b = p[tris[:, 1]]; c = p[tris[:, 2]]
        return 0.5 * ((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1])
                      - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1]))

    def setup_signs(self, p):
        return self._areas(p, self.tris) > 0

    def check(self, p, setup_signs, setup_area):
        areas = self._areas(p, self.tris)
        degen = int(np.sum(np.abs(areas) < 1e-6))
        flips = int(np.sum((areas > 0) != setup_signs) - degen) if setup_signs is not None else 0
        flips = max(flips, 0)
        # 自交:非相鄰邊對的線段相交(嚴格,orientation 全非零且異號)
        E = self.E
        P1 = p[E[self.pair_i, 0]]; P2 = p[E[self.pair_i, 1]]
        P3 = p[E[self.pair_j, 0]]; P4 = p[E[self.pair_j, 1]]

        def orient(a, b, c):
            v = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
            s = np.zeros(len(v), dtype=np.int8)
            s[v > 1e-9] = 1; s[v < -1e-9] = -1
            return s
        d1 = orient(P3, P4, P1); d2 = orient(P3, P4, P2)
        d3 = orient(P1, P2, P3); d4 = orient(P1, P2, P4)
        cross = (d1 != d2) & (d3 != d4) & (d1 != 0) & (d2 != 0) & (d3 != 0) & (d4 != 0)
        xs = int(np.sum(cross))
        area = float(np.abs(areas).sum())
        mn = p.min(0); mx = p.max(0)
        return {"self_intersections": xs, "triangle_flips": flips, "degenerate": degen,
                "area_ratio": round(area / setup_area, 3) if setup_area else 0.0,
                "bbox": [round(float(mx[0] - mn[0]), 1), round(float(mx[1] - mn[1]), 1)],
                "clean": (xs == 0 and flips == 0 and degen == 0)}


def signed_area(p, t):
    a, b, c = p[t[0]], p[t[1]], p[t[2]]
    return ((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2.0


# ---------- 骨骼(setup local + world affine) ----------
def build_bones(skeleton):
    """回傳 bones:list of dict{name,parent_idx,x,y,rot,sx,sy},index 對齊 mesh 的 boneIdx。"""
    out = []
    name2idx = {}
    for i, b in enumerate(skeleton["bones"]):
        name2idx[b["name"]] = i
    for b in skeleton["bones"]:
        out.append({
            "name": b["name"],
            "parent": name2idx[b["parent"]] if "parent" in b else -1,
            "x": float(b.get("x", 0.0)), "y": float(b.get("y", 0.0)),
            "rot": float(b.get("rotation", 0.0)),
            "sx": float(b.get("scaleX", 1.0)), "sy": float(b.get("scaleY", 1.0)),
        })
    return out


def world_affines(bones, pose):
    """pose[i] = dict{x,y,rot,sx,sy}(已含動畫套用後的 local)。回傳 list of (a,b,c,d,wx,wy)。
    normal transform mode、無 shear;bones 已 parent-before-child。"""
    W = [None] * len(bones)
    for i, bn in enumerate(bones):
        p = pose[i]
        rot = math.radians(p["rot"])
        cos, sin = math.cos(rot), math.sin(rot)
        # 無 shear:la=cos*sx, lb=-sin*sy, lc=sin*sx, ld=cos*sy
        la = cos * p["sx"]; lb = -sin * p["sy"]
        lc = sin * p["sx"]; ld = cos * p["sy"]
        par = bn["parent"]
        if par < 0:
            W[i] = (la, lb, lc, ld, p["x"], p["y"])
        else:
            pa, pb, pc, pd, pwx, pwy = W[par]
            a = pa * la + pb * lc
            b = pa * lb + pb * ld
            c = pc * la + pd * lc
            d = pc * lb + pd * ld
            wx = pa * p["x"] + pb * p["y"] + pwx
            wy = pc * p["x"] + pd * p["y"] + pwy
            W[i] = (a, b, c, d, wx, wy)
    return W


# ---------- weighted mesh 解碼 + LBS ----------
def decode_weighted(att):
    """回傳 verts:list per-vertex [(boneIdx,bx,by,w),...]。要求 weighted(vertices!=uvs 長度)。"""
    v = att["vertices"]
    nv = len(att["uvs"]) // 2
    out = []
    k = 0
    for _ in range(nv):
        n = int(v[k]); k += 1
        entries = []
        for _j in range(n):
            bi = int(v[k]); bx = float(v[k + 1]); by = float(v[k + 2]); w = float(v[k + 3])
            entries.append((bi, bx, by, w)); k += 4
        out.append(entries)
    return out, nv


def skin(decoded, Waff):
    """LBS → Nx2 世界座標。"""
    pts = np.zeros((len(decoded), 2), dtype=np.float64)
    for vi, entries in enumerate(decoded):
        wx = wy = 0.0
        for (bi, bx, by, w) in entries:
            a, b, c, d, tx, ty = Waff[bi]
            wx += w * (bx * a + by * b + tx)
            wy += w * (bx * c + by * d + ty)
        pts[vi] = (wx, wy)
    return pts


# ---------- 動畫 timeline → 每骨 local pose ----------
def _interp(frames, t, keys, mul=False):
    """線性內插 timeline(rotate/translate/scale)在時間 t 的值。mul=scale(缺省 1)否則加(缺省 0)。
    回傳 dict{key:value}。curve/stepped 一律近似為線性(自一致 benchmark 取樣密;extreme 落 key 上)。"""
    base = 1.0 if mul else 0.0
    if not frames:
        return {k: base for k in keys}
    if t <= frames[0].get("time", 0.0):
        f = frames[0]; return {k: float(f.get(k, base)) for k in keys}
    if t >= frames[-1].get("time", 0.0):
        f = frames[-1]; return {k: float(f.get(k, base)) for k in keys}
    for i in range(len(frames) - 1):
        t0 = frames[i].get("time", 0.0); t1 = frames[i + 1].get("time", 0.0)
        if t0 <= t <= t1:
            r = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            out = {}
            for k in keys:
                v0 = float(frames[i].get(k, base)); v1 = float(frames[i + 1].get(k, base))
                out[k] = v0 * (1 - r) + v1 * r
            return out
    f = frames[-1]; return {k: float(f.get(k, base)) for k in keys}


def anim_times(skeleton, anim):
    """收集該動畫所有 bone timeline 的 keyframe 時間(排序去重)。"""
    ts = set([0.0])
    bones_tl = skeleton["animations"][anim].get("bones", {})
    for bn, ch in bones_tl.items():
        for kind, frames in ch.items():
            for f in frames:
                ts.add(float(f.get("time", 0.0)))
    return sorted(ts)


def pose_at(skeleton, bones, anim, t):
    """回傳 pose list:每骨在時間 t 的 local(setup + 動畫套用)。"""
    bones_tl = skeleton["animations"][anim].get("bones", {})
    name2idx = {b["name"]: i for i, b in enumerate(bones)}
    pose = []
    for i, bn in enumerate(bones):
        p = {"x": bn["x"], "y": bn["y"], "rot": bn["rot"], "sx": bn["sx"], "sy": bn["sy"]}
        ch = bones_tl.get(bn["name"])
        if ch:
            if "rotate" in ch:
                p["rot"] += _interp(ch["rotate"], t, ["angle"])["angle"]
            if "translate" in ch:
                d = _interp(ch["translate"], t, ["x", "y"])
                p["x"] += d["x"]; p["y"] += d["y"]
            if "scale" in ch:
                d = _interp(ch["scale"], t, ["x", "y"], mul=True)
                p["sx"] *= d["x"]; p["sy"] *= d["y"]
        pose.append(p)
    return pose


def _slot_setup_alpha(skeleton, slot):
    for s in skeleton.get("slots", []):
        if s.get("name") == slot:
            col = s.get("color", "ffffffff")
            return int(col[6:8], 16) / 255.0
    return 1.0


def slot_alpha_at(skeleton, slot, anim, t, setup_alpha):
    """slot 在時間 t 的 alpha(0..1);讀 color timeline(rrggbbaa)線性內插。無 timeline → setup。
    對照 CLAUDE.md 雷點 #3:mesh 只在可見(且 attachment active)時才需拓樸乾淨。"""
    sl = skeleton["animations"][anim].get("slots", {}).get(slot, {})
    frames = sl.get("color")
    if not frames:
        return setup_alpha
    def av(f):
        return int(f["color"][6:8], 16) / 255.0
    if t <= frames[0].get("time", 0.0):
        return av(frames[0])
    if t >= frames[-1].get("time", 0.0):
        return av(frames[-1])
    for i in range(len(frames) - 1):
        t0 = frames[i].get("time", 0.0); t1 = frames[i + 1].get("time", 0.0)
        if t0 <= t <= t1:
            r = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return av(frames[i]) * (1 - r) + av(frames[i + 1]) * r
    return av(frames[-1])


def slot_attachment_active(skeleton, slot, anim, t, mesh_name, setup_attachment):
    """slot 在時間 t 是否掛著此 mesh(attachment timeline gating)。"""
    sl = skeleton["animations"][anim].get("slots", {}).get(slot, {})
    frames = sl.get("attachment")
    if not frames:
        return setup_attachment == mesh_name
    cur = setup_attachment
    for f in frames:
        if f.get("time", 0.0) <= t + 1e-9:
            cur = f.get("name")
        else:
            break
    return cur == mesh_name


def sample_times(times, substeps=4):
    """在 keyframe 間插入 substeps-1 個中間取樣點。"""
    if len(times) <= 1:
        return times
    out = []
    for i in range(len(times) - 1):
        out.append(times[i])
        for s in range(1, substeps):
            out.append(times[i] + (times[i + 1] - times[i]) * s / substeps)
    out.append(times[-1])
    return out


# ---------- runner ----------
def _iter_meshes(skeleton):
    skin_ = skeleton["skins"]
    if isinstance(skin_, list):
        for entry in skin_:
            for slot, atts in entry.get("attachments", {}).items():
                for name, a in atts.items():
                    if a.get("type") == "mesh":
                        yield entry.get("name"), slot, name, a
    else:
        atts0 = skin_.get("attachments", skin_)
        for slot, atts in atts0.items():
            for name, a in atts.items():
                if a.get("type") == "mesh":
                    yield "default", slot, name, a


def eval_weighted_mesh(skeleton, bones, att, slot=None, name=None, mutate=None,
                       alpha_gate=1.0 / 255):
    """對單一 weighted mesh 跑全動畫,回傳 per-anim clean 報告 + setup 檢查。
    只評估 slot **可見**(alpha>alpha_gate 且 attachment active)的幀 — 對照 Spine 渲染語意
    (雷點 #3):alpha=0 的 fade-in / attachment 未掛 的幀不會被渲染,拓樸髒不影響畫面。
    mutate:可選 callable(decoded)→decoded,用於負對照。"""
    decoded, nv = decode_weighted(att)
    setup_alpha = _slot_setup_alpha(skeleton, slot) if slot else 1.0
    setup_attach = None
    for s in skeleton.get("slots", []):
        if s.get("name") == slot:
            setup_attach = s.get("attachment")
    if mutate:
        decoded = mutate([[list(t) for t in e] for e in decoded])  # deep-copy tuples→lists
    chk = MeshChecker(att["triangles"])
    tris = chk.tris

    # setup pose(無動畫)→ 基準符號 / 面積 / 自交
    setup_pose = [{"x": b["x"], "y": b["y"], "rot": b["rot"], "sx": b["sx"], "sy": b["sy"]} for b in bones]
    Ws = world_affines(bones, setup_pose)
    sverts = skin(decoded, Ws)
    setup_signs = chk.setup_signs(sverts)
    setup_area = float(np.abs(chk._areas(sverts, tris)).sum())
    setup_r = chk.check(sverts, setup_signs, setup_area)

    per_anim = {}
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    for anim in skeleton.get("animations", {}):
        ts = sample_times(anim_times(skeleton, anim))
        if len(ts) <= 1:
            continue
        res = []
        gated = 0
        for t in ts:
            if slot is not None:
                a = slot_alpha_at(skeleton, slot, anim, t, setup_alpha)
                vis = slot_attachment_active(skeleton, slot, anim, t, name, setup_attach)
                if a <= alpha_gate or not vis:
                    gated += 1
                    continue
            pose = pose_at(skeleton, bones, anim, t)
            W = world_affines(bones, pose)
            v = skin(decoded, W)
            res.append(chk.check(v, setup_signs, setup_area))
        if not res:
            continue  # 整段動畫該 mesh 都不可見
        agg = {
            "frames": len(res),
            "gated_invisible": gated,
            "max_self_intersections": max(r["self_intersections"] for r in res),
            "max_triangle_flips": max(r["triangle_flips"] for r in res),
            "max_degenerate": max(r["degenerate"] for r in res),
            "area_ratio_range": [min(r["area_ratio"] for r in res), max(r["area_ratio"] for r in res)],
            "all_clean": all(r["clean"] for r in res),
        }
        per_anim[anim] = agg
        for k in worst:
            worst[k] = max(worst[k], agg["max_" + k])
    return {"nv": nv, "tris": int(len(tris)),
            "setup": {"self_intersections": setup_r["self_intersections"],
                      "degenerate": setup_r["degenerate"],
                      "bbox": setup_r["bbox"]},
            "anims": per_anim, "worst": worst}


def benchmark_weighted(path):
    sk = json.load(open(path))
    bones = build_bones(sk)
    report = {}
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    setup_bad = 0
    for skname, slot, name, att in _iter_meshes(sk):
        if len(att["vertices"]) == len(att["uvs"]):
            continue  # unweighted → 交給 deform_eval
        r = eval_weighted_mesh(sk, bones, att, slot=slot, name=name)
        report[f"{slot}/{name}"] = r
        for k in worst:
            worst[k] = max(worst[k], r["worst"][k])
        if r["setup"]["self_intersections"] > 0 or r["setup"]["degenerate"] > 0:
            setup_bad += 1
    meshes = {k: v for k, v in report.items() if not k.startswith("_")}
    artist_clean = [k for k, v in meshes.items()
                    if all(a["all_clean"] for a in v["anims"].values())]
    report["_worst_across_all_visible"] = worst
    # 評估器可信度 = skinning 在 setup 全部重現為有效幾何(唯一真正的正確性自檢)。
    report["_setup_all_valid"] = (setup_bad == 0)
    # 藝術家真值觀察(非評估器正確性):有幾個 mesh 在可見幀全乾淨。
    report["_artist_clean_visible"] = {"clean": len(artist_clean), "total": len(meshes),
                                       "clean_meshes": artist_clean}
    # 誠實界定:並非所有生產 weighted mesh 都拓樸乾淨(hero/halo 在可見的擠壓/縮放會自交),
    # 故不存在「所有藝術 mesh worst==0」這種 checker gate;可信度看 _setup_all_valid + 負對照鑑別力。
    return report


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    rep = benchmark_weighted(path)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
