#!/usr/bin/env python3
"""S3 — weighted-mesh deform 評估器(Linear Blend Skinning / 骨骼驅動變形)。

補上 `deform_eval.py` 的空白:那支只處理 **unweighted**(逐頂點 offset)mesh。
真實生產的角色 mesh(Award 機器人光暈/左手/身體、OMG/mega/super 角色)是
**weighted mesh** — 沒有 deform timeline,靠 **骨骼 world transform + 每頂點權重**變形。
要量化「生成的 weighted mesh 在骨骼拉扯下變形品質是否對等美術」,必須先能:
  1) 從 skeleton + animation 算出**任一時刻的 bone world transform**(Spine 3.8 pose 引擎);
  2) 用 LBS 把 weighted 頂點變形到世界座標;
  3) 對變形後拓樸下幾何品質閘(自交/翻面/退化)+ 量化平滑度指標。

### Spine 3.8 weighted vertex 格式(CLAUDE.md 雷點 #6)
`vertices = [n, boneIdx, bindX, bindY, weight, ...(重複 n 次), ...(下一頂點)]`
其中 (bindX,bindY) 是該頂點在 **該 bone 局部空間**、bind(setup) 時的座標;weight 每頂點和=1。
world_vertex = Σ_i weight_i · (boneWorld_i ⊗ (bindX_i, bindY_i))

### Pose 引擎(對照 Spine runtime updateWorldTransform,normal transform mode)
local:  la=cosDeg(rot+shearX)·sx  lb=cosDeg(rot+90+shearY)·sy
        lc=sinDeg(rot+shearX)·sx  ld=sinDeg(rot+90+shearY)·sy
world:  a=pa·la+pb·lc  b=pa·lb+pb·ld  c=pc·la+pd·lc  d=pc·lb+pd·ld
        wx=pa·x+pb·y+p.wx           wy=pc·x+pd·y+p.wy
animation 疊加:rot+=rotate.angle  x+=translate.x  y+=translate.y  sx*=scale.x  sy*=scale.y

### 取樣(誠實界定)
在 **keyframe 時刻**變形精確(bezier 只重參數化「時間→進度」,不改端點值);相鄰 keyframe 間
以**線性內插 bone 參數**細分取樣。線性內插的參數值必落在兩端 keyframe 的凸包內,故涵蓋
與真實 bezier 相同的值域 → 對「拓樸是否撐得住」這個幾何閘足夠(不需精確重現緩動曲線)。

自我驗證:美術真值 weighted mesh 在**真實動畫骨骼序列**下必須全乾淨(self-consistency),
且負對照(擾動權重/破壞綁定)必須被抓到 → 才證明此閘可信。
"""
import json, math
import numpy as np

# 重用 deform_eval 的幾何檢查(自交/翻面/退化/面積)
from deform_eval import signed_area, check, eval_pose  # noqa: E402

DEG = math.pi / 180.0


# ---------------- Spine pose 引擎 ----------------
class Skel:
    def __init__(self, skeleton):
        self.sk = skeleton
        self.bones = skeleton["bones"]
        self.n = len(self.bones)
        self.name2idx = {b["name"]: i for i, b in enumerate(self.bones)}
        self.parent = [None] * self.n
        for i, b in enumerate(self.bones):
            p = b.get("parent")
            self.parent[i] = self.name2idx[p] if p is not None else None
        # setup 局部值(None → 預設)
        def g(b, k, d):
            v = b.get(k)
            return d if v is None else v
        self.setup = [dict(x=g(b, "x", 0.0), y=g(b, "y", 0.0), rot=g(b, "rotation", 0.0),
                           sx=g(b, "scaleX", 1.0), sy=g(b, "scaleY", 1.0),
                           shx=g(b, "shearX", 0.0), shy=g(b, "shearY", 0.0))
                      for b in self.bones]
        # 拓樸序(父先於子)— bones 陣列在 Spine 已保證,但保險做一次
        self.order = self._topo()

    def _topo(self):
        order, seen = [], set()
        def visit(i):
            if i in seen: return
            p = self.parent[i]
            if p is not None: visit(p)
            seen.add(i); order.append(i)
        for i in range(self.n): visit(i)
        return order

    def world(self, local):
        """local: list of dict(x,y,rot,sx,sy,shx,shy) → 回傳每骨 world matrix (a,b,c,d,wx,wy)。"""
        W = [None] * self.n
        for i in self.order:
            l = local[i]
            rot = l["rot"];
            la = math.cos((rot + l["shx"]) * DEG) * l["sx"]
            lc = math.sin((rot + l["shx"]) * DEG) * l["sx"]
            lb = math.cos((rot + 90.0 + l["shy"]) * DEG) * l["sy"]
            ld = math.sin((rot + 90.0 + l["shy"]) * DEG) * l["sy"]
            p = self.parent[i]
            if p is None:
                W[i] = (la, lb, lc, ld, l["x"], l["y"])
            else:
                pa, pb, pc, pd, pwx, pwy = W[p]
                a = pa * la + pb * lc
                b = pa * lb + pb * ld
                c = pc * la + pd * lc
                d = pc * lb + pd * ld
                wx = pa * l["x"] + pb * l["y"] + pwx
                wy = pc * l["x"] + pd * l["y"] + pwy
                W[i] = (a, b, c, d, wx, wy)
        return W

    # ---- animation ----
    def _kf_value(self, frames, t, keys, defaults):
        """線性內插 timeline(dict per keyframe)在時間 t 的值。keys/defaults 對齊。"""
        if not frames:
            return list(defaults)
        times = [f.get("time", 0.0) for f in frames]
        if t <= times[0]:
            f = frames[0]
        elif t >= times[-1]:
            f = frames[-1]
        else:
            i = 0
            while i + 1 < len(times) and times[i + 1] < t:
                i += 1
            f0, f1 = frames[i], frames[i + 1]
            t0, t1 = times[i], times[i + 1]
            a = (t - t0) / (t1 - t0) if t1 > t0 else 0.0  # 線性(見檔頭誠實界定)
            return [f0.get(k, dv) * (1 - a) + f1.get(k, dv) * a for k, dv in zip(keys, defaults)]
        return [f.get(k, dv) for k, dv in zip(keys, defaults)]

    def pose_local(self, anim_name, t):
        """回傳套用動畫後的 local(copy of setup + timeline)。"""
        local = [dict(s) for s in self.setup]
        anim = self.sk["animations"].get(anim_name, {})
        for bname, ch in anim.get("bones", {}).items():
            i = self.name2idx[bname]
            if "rotate" in ch:
                (ang,) = self._kf_value(ch["rotate"], t, ["angle"], [0.0])
                local[i]["rot"] += ang
            if "translate" in ch:
                dx, dy = self._kf_value(ch["translate"], t, ["x", "y"], [0.0, 0.0])
                local[i]["x"] += dx; local[i]["y"] += dy
            if "scale" in ch:
                sx, sy = self._kf_value(ch["scale"], t, ["x", "y"], [1.0, 1.0])
                local[i]["sx"] *= sx; local[i]["sy"] *= sy
            if "shear" in ch:
                hx, hy = self._kf_value(ch["shear"], t, ["x", "y"], [0.0, 0.0])
                local[i]["shx"] += hx; local[i]["shy"] += hy
        return local

    def anim_keytimes(self, anim_name, bone_filter=None):
        """收集動畫中(可選限定某些骨)所有 keyframe 時刻。"""
        ts = set([0.0])
        anim = self.sk["animations"].get(anim_name, {})
        for bname, ch in anim.get("bones", {}).items():
            if bone_filter and bname not in bone_filter:
                continue
            for chan, frames in ch.items():
                for f in frames:
                    ts.add(round(f.get("time", 0.0), 4))
        return sorted(ts)


# ---------------- weighted mesh LBS ----------------
def parse_weighted(vertices):
    """→ list[ list[(boneIdx,bx,by,w)] ]。"""
    out = []; i = 0; V = vertices
    while i < len(V):
        n = int(V[i]); i += 1
        e = []
        for _ in range(n):
            e.append((int(V[i]), V[i + 1], V[i + 2], V[i + 3])); i += 4
        out.append(e)
    return out


def get_mesh(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    return atts[slot][name]


def skin_deform(skel, weighted_verts, W):
    """LBS:回傳 Nx2 世界座標。W = skel.world(...) 的 bone matrices。"""
    N = len(weighted_verts)
    out = np.zeros((N, 2), dtype=np.float64)
    for vi, e in enumerate(weighted_verts):
        wx = wy = 0.0
        for (bi, bx, by, w) in e:
            a, b, c, d, tx, ty = W[bi]
            wx += (a * bx + b * by + tx) * w
            wy += (c * bx + d * by + ty) * w
        out[vi, 0] = wx; out[vi, 1] = wy
    return out


def smoothness(verts, tris):
    """變形平滑度代理指標:相鄰三角面積比的離散度(越小越平滑;僵硬/撕裂會拉高)。
    以邊長變異也可,但面積比對「局部拉伸不均」更敏感。回傳 (edge_len_cv, area_cv)。"""
    areas = np.array([abs(signed_area(verts, t)) for t in tris])
    areas = areas[areas > 1e-9]
    # 邊長變異
    es = set()
    for t in tris:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            es.add((min(a, b), max(a, b)))
    el = np.array([np.hypot(*(verts[a] - verts[b])) for a, b in es])
    el = el[el > 1e-9]
    ecv = float(el.std() / el.mean()) if len(el) else 0.0
    acv = float(areas.std() / areas.mean()) if len(areas) else 0.0
    return round(ecv, 4), round(acv, 4)


# ---------------- 評估 runner ----------------
def eval_weighted_mesh(skel, slot, name, anims=None, substeps=4):
    """對真實/生成 weighted mesh 逐動畫逐幀 LBS 評估。回傳 per-anim 聚合。"""
    a = get_mesh(skel.sk, slot, name)
    wv = parse_weighted(a["vertices"])
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    bone_names = set(bn for e in wv for (bi, *_ ) in e for bn in [skel.bones[bi]["name"]])
    # setup pose 世界頂點(作為 flip 參考 + 面積基準)
    W0 = skel.world(skel.setup)
    v0 = skin_deform(skel, wv, W0)
    setup_signs = [signed_area(v0, t) > 0 for t in tris]
    setup_area = sum(abs(signed_area(v0, t)) for t in tris)
    all_anims = anims if anims else list(skel.sk["animations"].keys())
    per = {}
    for anim in all_anims:
        # 只取真的驅動到此 mesh 骨的動畫
        keyts = skel.anim_keytimes(anim, bone_filter=bone_names)
        if len(keyts) <= 1:  # 沒 keyframe 驅動 → 略過
            continue
        # keyframe + 相鄰細分
        times = []
        for i, t in enumerate(keyts):
            times.append(t)
            if i + 1 < len(keyts):
                for s in range(1, substeps):
                    times.append(t + (keyts[i + 1] - t) * s / substeps)
        results = []
        for t in times:
            local = skel.pose_local(anim, t)
            W = skel.world(local)
            v = skin_deform(skel, wv, W)
            r = eval_pose(v, tris, setup_signs, setup_area)
            ecv, acv = smoothness(v, tris)
            r["edge_cv"] = ecv; r["area_cv"] = acv
            results.append(r)
        per[anim] = {
            "frames": len(results),
            "max_self_intersections": max(r["self_intersections"] for r in results),
            "max_triangle_flips": max(r["triangle_flips"] for r in results),
            "max_degenerate": max(r["degenerate"] for r in results),
            "area_ratio_range": [min(r["area_ratio"] for r in results),
                                 max(r["area_ratio"] for r in results)],
            "max_edge_cv": max(r["edge_cv"] for r in results),
            "max_area_cv": max(r["area_cv"] for r in results),
            "all_clean": all(r["clean"] for r in results),
        }
    return {"nv": len(wv), "tris": len(tris), "bones": sorted(bone_names), "anims": per}


def all_weighted_pieces(sk):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    return [(slot, nm) for slot, o in atts.items() for nm, at in o.items()
            if at.get("type") == "mesh" and len(at["vertices"]) != len(at["uvs"])]


def benchmark_artist(path, pieces=None):
    """對真實美術 weighted mesh 逐件逐動畫聚合原始指標(作為**校準基準線**,非絕對零閘)。"""
    sk = json.load(open(path)); skel = Skel(sk)
    if pieces is None:
        pieces = all_weighted_pieces(sk)
    report = {}
    for slot, nm in pieces:
        report[f"{slot}/{nm}"] = eval_weighted_mesh(skel, slot, nm)
    return report


# ---------------- 校準式相對閘(calibrated gate) ----------------
# ⚠️ 為何不用絕對 si==0 & flips==0(2026-08-26 校準教訓):
#   實測 Award 7 個美術 weighted mesh,其中 2 件在**真實動畫下**就非零:
#     - 機器人拆件/光暈:軟邊發光 mesh,被展開的骨拉扯必然自重疊(additive 混色,視覺無破)。
#     - superwin_角色:(a) Super_In t=0 有 scale.x=0.396 蓄力擠壓(area_ratio→0.14,微小不可見)
#                       (b) idle loop 有一撮 sliver 三角(setup 面積 −12~−18,摺疊細節區)會翻面。
#   這些都**出貨且視覺正常**。故絕對零閘對 weighted 角色 mesh **miscalibrated**(會誤殺美術真值)。
#   正解:對照該件**美術基準線**判定(生成 mesh 的變形品質「不劣於美術 + margin」),
#   與專案既有哲學一致(compare_robot_mesh 用 IoU 美術基準 −0.03 margin;deform_eval 用自一致性)。
DEFAULT_MARGINS = {"self_intersections": 0, "triangle_flips": 0,
                   "edge_cv": 0.15, "area_cv": 0.30, "area_ratio": 0.10}


def piece_baseline(skel, slot, name):
    """回傳該件逐動畫的基準指標(供生成 mesh 對照)。"""
    return eval_weighted_mesh(skel, slot, name)["anims"]


def gate_against_baseline(gen_anims, base_anims, margins=None):
    """生成 mesh 的 per-anim 指標 vs 美術基準線。回傳 (passed, reasons[])。
    判準(每個共同動畫):
      max_self_intersections <= base + margin[si]
      max_triangle_flips     <= base + margin[flips]
      max_edge_cv            <= base·(1+margin) (變形不更僵/更不均)
      max_area_cv            <= base·(1+margin)
      area_ratio 範圍不超出美術包絡外 margin[area_ratio]
    """
    m = dict(DEFAULT_MARGINS); m.update(margins or {})
    reasons = []; ok = True
    for anim, base in base_anims.items():
        g = gen_anims.get(anim)
        if g is None:
            continue  # 生成 mesh 也許沒綁到該動畫的骨 → 略過
        if g["max_self_intersections"] > base["max_self_intersections"] + m["self_intersections"]:
            ok = False; reasons.append(f"{anim}: si {g['max_self_intersections']}>{base['max_self_intersections']}+{m['self_intersections']}")
        if g["max_triangle_flips"] > base["max_triangle_flips"] + m["triangle_flips"]:
            ok = False; reasons.append(f"{anim}: flips {g['max_triangle_flips']}>{base['max_triangle_flips']}+{m['triangle_flips']}")
        if g["max_edge_cv"] > base["max_edge_cv"] * (1 + m["edge_cv"]) + 1e-6:
            ok = False; reasons.append(f"{anim}: edge_cv {g['max_edge_cv']}>{base['max_edge_cv']}·{1+m['edge_cv']}")
        if g["max_area_cv"] > base["max_area_cv"] * (1 + m["area_cv"]) + 1e-6:
            ok = False; reasons.append(f"{anim}: area_cv {g['max_area_cv']}>{base['max_area_cv']}·{1+m['area_cv']}")
        blo, bhi = base["area_ratio_range"]; glo, ghi = g["area_ratio_range"]
        if glo < blo - m["area_ratio"] or ghi > bhi + m["area_ratio"]:
            ok = False; reasons.append(f"{anim}: area_ratio {[glo,ghi]} outside {[blo,bhi]}±{m['area_ratio']}")
    return ok, reasons


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    rep = benchmark_artist(path)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
