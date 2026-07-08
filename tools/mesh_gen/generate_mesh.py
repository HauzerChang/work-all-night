#!/usr/bin/env python3
"""S3 mesh 生成器(最小原型) — PNG(alpha) → unweighted Spine mesh attachment。

純 CPU pipeline(對應 Spine能力鍛鍊計畫.md 3.3):
  alpha mask → cv2.findContours → Douglas-Peucker 簡化(hull 邊界)
  → 多通道 Canny 抓內部視覺邊界放點 + 內部格點補點(去重/去太近邊界)
  → 約束 Delaunay(triangle 'p',不加 Steiner 點以保住頂點集與 hull-first 順序)
  → 以「三角形重心在 mask 內」過濾凹形外的三角

輸出 Spine JSON mesh attachment 格式:
  {"type":"mesh","vertices":[x,y,...],"uvs":[u,v,...],"triangles":[...],
   "hull":N,"width":W,"height":H}
  - unweighted:vertices = 頂點數×2(純座標),len(vertices)==len(uvs)
  - hull 頂點(邊界)必排在 vertices 最前(Spine 格式要求)
  - 座標 y 上翻(影像 y-down → Spine y-up),以影像中心為原點
"""
import argparse, json, sys
import numpy as np
import cv2
import triangle as tr


def load_mask(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"無法讀取影像: {path}")
    if img.ndim == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3]
        rgb = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
    else:
        gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        alpha = (gray > 0).astype(np.uint8) * 255
        rgb = gray
    mask = (alpha > 8).astype(np.uint8)
    return mask, rgb, img.shape[1], img.shape[0]


def boundary_points(mask, epsilon_frac):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        raise SystemExit("找不到輪廓(mask 全空?)")
    cnt = max(cnts, key=cv2.contourArea)
    peri = cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, epsilon_frac * peri, True)
    return approx.reshape(-1, 2).astype(np.float64)


def interior_points(mask, gray, hull_pts, max_interior, min_dist, margin):
    h, w = mask.shape
    eroded = cv2.erode(mask, np.ones((margin, margin), np.uint8))
    cands = []
    # (a) 多通道 Canny 內部視覺邊界 → 沿邊界取點(變形漂亮的關鍵)
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.bitwise_and(edges, edges, mask=eroded)
    ys, xs = np.where(edges > 0)
    if len(xs):
        idx = np.linspace(0, len(xs) - 1, min(len(xs), max_interior * 2)).astype(int)
        cands.extend(list(zip(xs[idx].astype(float), ys[idx].astype(float))))
    # (b) 內部格點補滿(平坦區沒有 Canny 邊時的後備)
    step = max(8, int(np.sqrt((w * h) / max(1, max_interior))))
    for yy in range(step, h, step):
        for xx in range(step, w, step):
            if eroded[yy, xx]:
                cands.append((float(xx), float(yy)))
    # 去重 / 去太近(含與 hull 太近)
    kept = []
    allpts = list(hull_pts)
    for p in cands:
        if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 >= min_dist ** 2 for q in allpts):
            kept.append(p); allpts.append(p)
        if len(kept) >= max_interior:
            break
    return np.array(kept, dtype=np.float64).reshape(-1, 2)


def triangulate(hull_pts, interior_pts):
    pts = np.vstack([hull_pts, interior_pts]) if len(interior_pts) else hull_pts.copy()
    n_hull = len(hull_pts)
    segs = np.array([[i, (i + 1) % n_hull] for i in range(n_hull)], dtype=np.int32)
    out = tr.triangulate({"vertices": pts, "segments": segs}, "p")  # constrained, no Steiner
    if "triangles" not in out or len(out["vertices"]) != len(pts):
        # 'p' 偶爾仍插點;退回未約束 Delaunay(保住頂點集)
        out = tr.triangulate({"vertices": pts}, "")
    return pts, out["triangles"], n_hull


def filter_triangles(pts, tris, mask):
    h, w = mask.shape
    keep = []
    for t in tris:
        c = pts[t].mean(axis=0)
        cx, cy = int(round(c[0])), int(round(c[1]))
        if 0 <= cy < h and 0 <= cx < w and mask[cy, cx]:
            keep.append(t)
    return np.array(keep, dtype=np.int32) if keep else np.zeros((0, 3), np.int32)


def prune_orphans(pts, tris, n_hull):
    """移除未被任何三角用到的『內部』頂點並重映射索引(AC2c)。

    只剪內部點(index >= n_hull);hull 頂點定義外周 loop、Spine 要求排最前且連續,
    即使某 hull 點暫無三角參照也保留,以維持 hull-first 不變量。
    內部孤兒來自 filter_triangles 把其周圍三角全濾掉(重心落在 mask 外),
    剪掉不影響覆蓋率(孤兒點不貢獻任何填滿)。
    """
    if not len(tris):
        return pts, tris, n_hull
    used = set(int(i) for t in tris for i in t)
    keep = [i for i in range(len(pts)) if i < n_hull or i in used]
    if len(keep) == len(pts):
        return pts, tris, n_hull
    remap = {old: new for new, old in enumerate(keep)}
    new_pts = pts[keep]
    new_tris = np.array([[remap[int(i)] for i in t] for t in tris], dtype=np.int32)
    return new_pts, new_tris, n_hull


def to_spine(pts, tris, n_hull, W, H):
    # y 上翻 + 置中(Spine y-up);uv 用影像座標正規化
    verts, uvs = [], []
    for (x, y) in pts:
        verts.extend([float(x - W / 2.0), float(H / 2.0 - y)])
        uvs.extend([float(x / W), float(y / H)])
    return {
        "type": "mesh",
        "vertices": [round(v, 3) for v in verts],
        "uvs": [round(u, 5) for u in uvs],
        "triangles": [int(i) for tt in tris for i in tt],
        "hull": int(n_hull),
        "width": int(W),
        "height": int(H),
    }


def generate(path, max_interior=40, epsilon_frac=0.008, min_dist=14, margin=6):
    mask, gray, W, H = load_mask(path)
    hull = boundary_points(mask, epsilon_frac)
    inter = interior_points(mask, gray, hull, max_interior, min_dist, margin)
    pts, tris, n_hull = triangulate(hull, inter)
    tris = filter_triangles(pts, tris, mask)
    pts, tris, n_hull = prune_orphans(pts, tris, n_hull)
    return to_spine(pts, tris, n_hull, W, H), mask


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--max-interior", type=int, default=40)
    ap.add_argument("--epsilon", type=float, default=0.008)
    ap.add_argument("--min-dist", type=float, default=14)
    args = ap.parse_args()
    mesh, _ = generate(args.image, args.max_interior, args.epsilon, args.min_dist)
    nv = len(mesh["uvs"]) // 2
    out = args.out or (args.image.rsplit(".", 1)[0] + "_mesh.json")
    with open(out, "w") as f:
        json.dump(mesh, f, ensure_ascii=False)
    print(f"寫出 {out}: 頂點 {nv} (hull {mesh['hull']}), 三角 {len(mesh['triangles'])//3}")


if __name__ == "__main__":
    main()
