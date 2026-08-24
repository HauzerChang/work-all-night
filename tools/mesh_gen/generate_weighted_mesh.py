#!/usr/bin/env python3
"""S3 — weighted mesh 生成器(拓樸 + 內部取樣密度控制 + 骨綁權重)。

補上 compare_robot_mesh 的限制:靜態 IoU PASS ≠ 骨骼變形平滑度對等。
本檔對「同一件的 setup 世界形狀 + 同一組驅動骨」生成 **我方拓樸 + 權重**,
再用 `weighted_deform_eval` 在**真實動畫骨骼 pose** 下量化變形品質,和美術對照。

流程(純 CPU,確定性,不學美術決定 — 對照 RULES):
  1. 取美術件 setup 世界頂點 → 邊界多邊形(hull-first 序)。
  2. 在同多邊形內以 `interior_spacing` 控制**內部取樣密度**;邊界重採樣 → 約束 Delaunay(triangle)。
  3. 骨綁權重(BBW 代理):對每頂點取到各骨「線段」的距離,inverse-distance^2、
     取 top-K、正規化(和=1)→ 平滑、確定性、可機讀。
  4. 世界頂點 → 各影響骨的 bind 局部座標(反 setup 世界矩陣)→ 組 Spine weighted 頂點。

限制(誠實):骨「集合」沿用美術真值(該件用哪些骨),本工具驗的是**權重+拓樸生成**,
非骨骼選擇(骨選擇屬 S1/S5)。權重為 inverse-distance BBW 代理,非解拉普拉斯的真 BBW。
"""
import json, math, sys
import numpy as np
import triangle as tr

import spine_skeleton as ss


# ---------- 幾何工具 ----------
def polygon_from_hull(setup_world, hull_n):
    """weighted mesh 頂點序中,前 hull_n 個為邊界(hull-first;雷點 #6)。"""
    return setup_world[:hull_n].copy()


def point_in_poly(pt, poly):
    x, y = pt; inside = False; n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]; xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def sample_interior(poly, spacing):
    mn = poly.min(0); mx = poly.max(0)
    pts = []
    ys = np.arange(mn[1] + spacing * 0.5, mx[1], spacing)
    xs = np.arange(mn[0] + spacing * 0.5, mx[0], spacing)
    for y in ys:
        for x in xs:
            if point_in_poly((x, y), poly):
                pts.append((x, y))
    return np.array(pts, dtype=np.float64).reshape(-1, 2)


def resample_boundary(poly, step):
    """沿邊界等弧長重採樣,回傳新邊界點(封閉)。"""
    out = []
    n = len(poly)
    for i in range(n):
        a = poly[i]; b = poly[(i + 1) % n]
        seg = b - a; L = np.hypot(*seg)
        k = max(1, int(round(L / step)))
        for s in range(k):
            out.append(a + seg * (s / k))
    return np.array(out, dtype=np.float64).reshape(-1, 2)


def triangulate(boundary, interior):
    """約束 Delaunay:邊界為 segment,內部點為 holes-free 點集。"""
    nb = len(boundary)
    pts = np.vstack([boundary, interior]) if len(interior) else boundary
    segs = [[i, (i + 1) % nb] for i in range(nb)]
    A = {"vertices": pts, "segments": np.array(segs, dtype=np.int32)}
    B = tr.triangulate(A, "p")  # 'p' = planar straight-line graph,只保多邊形內三角
    V = B["vertices"]; T = B["triangles"]
    # 過濾重心在多邊形外的三角(triangle 'p' 已大致處理,保險)
    keep = []
    for t in T:
        c = V[t].mean(0)
        if point_in_poly(c, boundary):
            keep.append(t)
    return V, np.array(keep, dtype=np.int32)


# ---------- 骨綁權重(BBW 代理)----------
def bone_segments(sk, bone_names_subset):
    """回傳 {bone_name: (origin(2,), tip(2,))}(setup 世界)。"""
    W = sk.world_transforms()
    segs = {}
    for name in bone_names_subset:
        a, b, c, d, tx, ty = W[name]
        length = sk.byname[name].get("length", 0.0)
        origin = np.array([tx, ty])
        tip = np.array([a * length + tx, c * length + ty])
        segs[name] = (origin, tip)
    return segs, W


def dist_point_seg(p, a, b):
    ab = b - a; t = 0.0
    denom = float(ab @ ab)
    if denom > 1e-9:
        t = float((p - a) @ ab) / denom
        t = max(0.0, min(1.0, t))
    proj = a + t * ab
    return float(np.hypot(*(p - proj)))


def compute_weights(verts, segs, topk=2, power=2.0):
    names = list(segs.keys())
    out = []
    for p in verts:
        ds = np.array([dist_point_seg(p, *segs[n]) for n in names])
        ds = np.maximum(ds, 1e-3)
        w = 1.0 / ds ** power
        # top-K
        idx = np.argsort(-w)[:topk]
        wk = w[idx]; wk = wk / wk.sum()
        out.append([(names[idx[j]], float(wk[j])) for j in range(len(idx))])
    return out


def world_to_bind(p, boneW):
    """世界點 → 骨局部 bind 座標(反仿射)。boneW=(a,b,c,d,tx,ty)。"""
    a, b, c, d, tx, ty = boneW
    det = a * d - b * c
    if abs(det) < 1e-9:
        return 0.0, 0.0
    dx = p[0] - tx; dy = p[1] - ty
    lx = (d * dx - b * dy) / det
    ly = (-c * dx + a * dy) / det
    return lx, ly


def build_weighted_vertices(verts, weights, bone_names_all, W):
    """組 Spine weighted 攤平陣列。"""
    name2idx = {n: i for i, n in enumerate(bone_names_all)}
    flat = []
    for p, wl in zip(verts, weights):
        flat.append(len(wl))
        for name, w in wl:
            bi = name2idx[name]
            lx, ly = world_to_bind(p, W[name])
            flat += [bi, lx, ly, w]
    return flat


# ---------- 端到端:生成一件的 weighted mesh ----------
def generate_part(sk, slot, interior_spacing=28.0, boundary_step=26.0, topk=2):
    from weighted_deform_eval import load_part
    vw_art, tris_art, hull, name = load_part(sk.data, slot)
    bone_names = sk.order
    W0 = sk.world_transforms()
    art_world = ss.skin_vertices(vw_art, bone_names, W0)

    # 該件用到的骨(真值)
    used = []
    for e in vw_art:
        for bi, *_ in e:
            if bone_names[bi] not in used:
                used.append(bone_names[bi])

    poly = polygon_from_hull(art_world, hull)
    boundary = resample_boundary(poly, boundary_step)
    interior = sample_interior(poly, interior_spacing)
    V, T = triangulate(boundary, interior)

    segs, W = bone_segments(sk, used)
    weights = compute_weights(V, segs, topk=topk)
    flat = build_weighted_vertices(V, weights, bone_names, W)

    return {
        "name": name, "used_bones": used,
        "gen_nv": len(V), "gen_tris": len(T),
        "art_nv": len(vw_art), "art_tris": len(tris_art),
        "vertices": flat, "triangles": T.reshape(-1).tolist(),
        "world_setup": V,
    }


if __name__ == "__main__":
    sk = ss.load("assets/Award.json")
    for slot in ["機器人拆件/左手", "機器人拆件/身體", "機器人拆件/光暈"]:
        g = generate_part(sk, slot)
        print(f"{slot}: gen {g['gen_nv']}v/{g['gen_tris']}t  (art {g['art_nv']}v/{g['art_tris']}t)  "
              f"bones={g['used_bones']}")
