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
    """移除三角過濾後不再被任何三角引用的『內部』孤兒頂點並重編索引。
    hull 頂點(0..n_hull-1)一律保留(定義邊界環,順序/數量不變);只丟 idx>=n_hull 的孤兒。
    修正 filter_triangles 對凹形/軟邊件可能孤立內部頂點 → Spine 格式非法(AC2c fail)。"""
    if len(tris) == 0:
        return pts, tris, n_hull
    used = set(int(i) for i in tris.flatten())
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


def _coverage_iou(mesh, mask):
    """三角形填滿 vs mask 的 IoU(不依賴 evaluate_mesh,避免循環 import)。"""
    W, H = mesh["width"], mesh["height"]
    v = mesh["vertices"]
    pts = np.array([(v[i] + W / 2.0, H / 2.0 - v[i + 1]) for i in range(0, len(v), 2)])
    recon = np.zeros((H, W), np.uint8)
    for t in np.array(mesh["triangles"]).reshape(-1, 3):
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    inter = int(np.logical_and(recon, m).sum())
    union = int(np.logical_or(recon, m).sum())
    return inter / union if union else 0.0


def generate(path, max_interior=40, epsilon_frac=0.008, min_dist=14, margin=6):
    mask, gray, W, H = load_mask(path)
    hull = boundary_points(mask, epsilon_frac)
    inter = interior_points(mask, gray, hull, max_interior, min_dist, margin)
    pts, tris, n_hull = triangulate(hull, inter)
    tris = filter_triangles(pts, tris, mask)
    pts, tris, n_hull = prune_orphans(pts, tris, n_hull)
    return to_spine(pts, tris, n_hull, W, H), mask


def generate_adaptive(path, target_iou=0.95, budget=64, eps0=0.008,
                      min_eps=0.0015, shrink=1.6, **kw):
    """自我驗證迴圈:從粗 epsilon 起,量測覆蓋 IoU,不足且預算未滿就加密邊界(縮小 eps)重試。
    - 硬邊件在粗 epsilon 即達標(頂點少)→ 早停;軟邊大 blob(如光暈)自動加密到達標或撞預算。
    - 回傳同時滿足 (iou>=target 且 nv<=budget) 的最精簡解;若無,回傳『達標且頂點最少』
      或退而求其次『IoU 最高且不超預算』的一版。不引入 per-shape 魔數。"""
    eps = eps0
    meeting = []   # (nv, mesh, mask) 達 target 且在預算內
    fallbacks = [] # (iou, nv, mesh, mask) 在預算內但未達 target
    for _ in range(8):
        mesh, mask = generate(path, epsilon_frac=eps, **kw)
        nv = len(mesh["uvs"]) // 2
        iou = _coverage_iou(mesh, mask)
        if nv <= budget:
            if iou >= target_iou:
                meeting.append((nv, mesh, mask))
                break  # eps 遞減使覆蓋單調上升,首達標即最精簡
            fallbacks.append((iou, nv, mesh, mask))
        if eps <= min_eps:
            break
        eps = max(min_eps, eps / shrink)
    if meeting:
        nv, mesh, mask = min(meeting, key=lambda x: x[0])
        return mesh, mask
    if fallbacks:
        _, _, mesh, mask = max(fallbacks, key=lambda x: x[0])
        return mesh, mask
    return generate(path, epsilon_frac=eps0, **kw)  # 極端退路


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
