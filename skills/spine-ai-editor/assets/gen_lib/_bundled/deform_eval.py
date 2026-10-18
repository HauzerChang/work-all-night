#!/usr/bin/env python3
"""S2/S3 — deform-aware mesh 評估器:量化「會變形的網格在動畫拉扯下會不會壞」。

對 unweighted mesh:
  deformed_local[i] = setup_vertices[i] + deform_offset[i]   (offset 段補零對齊)
  (對照 CLAUDE.md 雷點 #3/#4:deform 直接逐頂點加偏移;此為 attachment-local 空間,
   足以判定拓樸正確性 — 自交/翻面/面積,不受控制骨的仿射變換影響。)

幾何品質閘(可機讀):
  - self_intersections:非相鄰邊是否真交叉(三角彼此穿插 → 撕裂/破圖)
  - triangle_flips    :三角 signed-area 相對 setup 變號(翻面 → 貼圖鏡射撕裂)
  - degenerate        :面積≈0 的三角
  - area_ratio / bbox :變形幅度量化

提供兩種用法:
  1) benchmark_real():對真實 main_draw 的 4 mesh × 各動畫逐幀評估(建立 ground-truth)。
  2) stress_test(mesh, mag):對任一 mesh 施加空間位移場(校準自真實 deform 最大幅度),
     檢查其拓樸是否耐變形 → 作為 S3 生成器的閘。
"""
import json, math
import numpy as np


# ---------- Spine deform ----------
def load_mesh(skeleton, slot, name):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    a = atts[slot][name]
    nv = len(a["uvs"]) // 2
    setup = np.array(a["vertices"], dtype=np.float64).reshape(nv, 2)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    return setup, tris, a["hull"], nv


def deform_frames(skeleton, anim, slot, name):
    """回傳 [(time, full_offset_vec(2*nv,))]，已把 sparse offset 段補成全長。"""
    dfm = skeleton["animations"][anim].get("deform")
    if not dfm:
        return []
    out = []
    for skinname, slots in dfm.items():
        if slot in slots and name in slots[slot]:
            frames = slots[slot][name]
            nv2 = None
            for f in frames:
                off = f.get("offset", 0)
                dv = f.get("vertices", [])
                out.append((f.get("time", 0.0), off, np.array(dv, dtype=np.float64)))
            return out
    return out


def apply_deform(setup, off, dv):
    flat = setup.reshape(-1).copy()
    if len(dv):
        flat[off:off + len(dv)] += dv
    return flat.reshape(-1, 2)


def sample_poses(setup, frames, substeps=4):
    """逐 keyframe + 相鄰幀線性內插取樣，回傳 [(label, verts)]。"""
    if not frames:
        return [("setup", setup.copy())]
    full = []
    for (t, off, dv) in frames:
        full.append((t, apply_deform(setup, off, dv)))
    poses = []
    for i, (t, v) in enumerate(full):
        poses.append((f"t={t:.3f}", v))
        if i + 1 < len(full):
            v2 = full[i + 1][1]
            for s in range(1, substeps):
                a = s / substeps
                poses.append((f"t={t:.3f}+{a:.2f}", v * (1 - a) + v2 * a))
    return poses


# ---------- geometry checks ----------
def signed_area(p, t):
    a, b, c = p[t[0]], p[t[1]], p[t[2]]
    return ((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2.0


def _seg_cross(p1, p2, p3, p4):
    def o(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)
    d1, d2, d3, d4 = o(p3, p4, p1), o(p3, p4, p2), o(p1, p2, p3), o(p1, p2, p4)
    return d1 != d2 and d3 != d4 and d1 != 0 and d2 != 0 and d3 != 0 and d4 != 0


def tri_edges(tris):
    es = set()
    for t in tris:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            es.add((min(a, b), max(a, b)))
    return list(es)


def check(verts, tris, setup_signs):
    flips = 0
    degen = 0
    for i, t in enumerate(tris):
        a = signed_area(verts, t)
        if abs(a) < 1e-6:
            degen += 1
        elif setup_signs is not None and (a > 0) != setup_signs[i]:
            flips += 1
    edges = tri_edges(tris)
    xs = 0
    for i in range(len(edges)):
        e1 = edges[i]
        for j in range(i + 1, len(edges)):
            e2 = edges[j]
            if e1[0] in e2 or e1[1] in e2:
                continue
            if _seg_cross(verts[e1[0]], verts[e1[1]], verts[e2[0]], verts[e2[1]]):
                xs += 1
    mn = verts.min(0); mx = verts.max(0)
    return {"self_intersections": xs, "triangle_flips": flips, "degenerate": degen,
            "bbox": [round(float(mx[0] - mn[0]), 1), round(float(mx[1] - mn[1]), 1)]}


def eval_pose(verts, tris, setup_signs, setup_area):
    r = check(verts, tris, setup_signs)
    area = sum(abs(signed_area(verts, t)) for t in tris)
    r["area_ratio"] = round(area / setup_area, 3) if setup_area else 0.0
    r["clean"] = (r["self_intersections"] == 0 and r["triangle_flips"] == 0 and r["degenerate"] == 0)
    return r


# ---------- runners ----------
def benchmark_real(path):
    sk = json.load(open(path))
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    meshes = [(s, n) for s, o in atts.items() for n, a in o.items() if a.get("type") == "mesh"]
    report = {}
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    for slot, name in meshes:
        setup, tris, hull, nv = load_mesh(sk, slot, name)
        setup_signs = [signed_area(setup, t) > 0 for t in tris]
        setup_area = sum(abs(signed_area(setup, t)) for t in tris)
        per_anim = {}
        for anim in sk.get("animations", {}):
            frames = deform_frames(sk, anim, slot, name)
            if not frames:
                continue
            poses = sample_poses(setup, frames)
            res = [eval_pose(v, tris, setup_signs, setup_area) for _, v in poses]
            agg = {
                "frames_sampled": len(res),
                "max_self_intersections": max(r["self_intersections"] for r in res),
                "max_triangle_flips": max(r["triangle_flips"] for r in res),
                "max_degenerate": max(r["degenerate"] for r in res),
                "area_ratio_range": [min(r["area_ratio"] for r in res), max(r["area_ratio"] for r in res)],
                "all_clean": all(r["clean"] for r in res),
            }
            per_anim[anim] = agg
            for k in worst:
                worst[k] = max(worst[k], agg["max_" + k])
        report[f"{slot}/{name}"] = {"nv": nv, "hull": hull, "tris": len(tris), "anims": per_anim}
    report["_worst_across_all"] = worst
    report["_checker_validated"] = (worst["self_intersections"] == 0 and worst["triangle_flips"] == 0
                                    and worst["degenerate"] == 0)
    return report


def max_deform_magnitude(path):
    sk = json.load(open(path)); mx = 0.0
    for anim in sk.get("animations", {}):
        dfm = sk["animations"][anim].get("deform") or {}
        for _, slots in dfm.items():
            for _, attd in slots.items():
                for _, frames in attd.items():
                    for f in frames:
                        dv = f.get("vertices", [])
                        for k in range(0, len(dv) - 1, 2):
                            mx = max(mx, math.hypot(dv[k], dv[k + 1]))
    return mx


def stress_field(verts, mag):
    """⚠️ 合成位移場 — 僅供「最壞情況裕度探測」,**不可當 pass/fail 閘**。
    教訓(2026-06-24):mag=315 時面積比達 2.0,遠超真實 deform 的 1.13,造成假性失敗。
    正式閘請用 transfer_deform_check()(真實位移場轉移)。"""
    mn = verts.min(0); mx = verts.max(0); h = max(mx[1] - mn[1], 1e-6); w = max(mx[0] - mn[0], 1e-6)
    out = verts.copy()
    for i, (x, y) in enumerate(verts):
        fy = (mx[1] - y) / h
        fx = (x - mn[0]) / w - 0.5
        out[i, 0] = x + mag * fy * (1.6 * fx)
        out[i, 1] = y + mag * 0.25 * math.sin(fx * math.pi * 3) * fy
    return out


# ---------- 真實位移場轉移(正式 deform 閘)----------
def real_deform_field(skeleton, slot, name):
    """回傳 (uvs Nx2, field Nx2):該 mesh 在所有動畫中『總位移最大幀』的逐頂點位移(local,y-up)。
    以 UV 為座標,讓位移場可轉移到任一拓樸的 mesh。"""
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uvs = np.array(a["uvs"], dtype=np.float64).reshape(-1, 2)
    setup = np.array(a["vertices"], dtype=np.float64).reshape(-1, 2)
    best = None
    for anim in skeleton.get("animations", {}):
        for (t, off, dv) in deform_frames(skeleton, anim, slot, name):
            d = apply_deform(setup, off, dv)
            tot = float(np.abs(d - setup).sum())
            if best is None or tot > best[0]:
                best = (tot, anim, d)
    field = (best[2] - setup) if best else np.zeros_like(setup)
    return uvs, field, (best[1] if best else None)


def transfer_deform_check(mesh, uvs_src, field):
    """把真實位移場(uvs_src 座標、y-up)內插到 mesh 的頂點並套用,檢查幾何。
    sign 約定:mesh.vertices 已 y-up,field 為 y-up local → 直接相加(經自一致性驗證)。"""
    from scipy.interpolate import griddata
    v = mesh["vertices"]
    s = np.column_stack([v[0::2], v[1::2]])
    mu = np.array(mesh["uvs"], dtype=np.float64).reshape(-1, 2)
    dx = griddata(uvs_src, field[:, 0], mu, "linear")
    dy = griddata(uvs_src, field[:, 1], mu, "linear")
    nx = griddata(uvs_src, field[:, 0], mu, "nearest")
    ny = griddata(uvs_src, field[:, 1], mu, "nearest")
    dx = np.where(np.isnan(dx), nx, dx); dy = np.where(np.isnan(dy), ny, dy)
    sd = s + np.column_stack([dx, dy])
    t = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    signs = [signed_area(s, x) > 0 for x in t]
    area = sum(abs(signed_area(s, x)) for x in t)
    return eval_pose(sd, t, signs, area)


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/main_draw.json"
    rep = benchmark_real(path)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print("\nmax_deform_magnitude:", round(max_deform_magnitude(path), 2))
