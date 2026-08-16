#!/usr/bin/env python3
"""S3 v3 — 輪廓貼合 + 規則內部格點 mesh 生成器(緊湊凸形件適用)。

動機(2026-08-16,由 validate_psd_to_award 端到端對照 Award 藝術家 mesh 發現):
  - v1(Canny 散點 Delaunay):覆蓋率高但拓樸不規則,強變形下自交(左手 10 self-int)。
  - v2(strip 掃描線格):變形乾淨,但多邊形上下蓋只用單列取樣,曲面 blob 覆蓋率封頂
    ~0.93(光暈/身體 < 藝術家 0.98)。
  兩者對「緊湊凸形生產件(機器人光暈/身體/左手)」都不足。

v3 策略(=藝術家實際做法,亦即 SpriteToMesh):
  1. cv2.findContours 取最大外輪廓 → approxPolyDP 貼合成 ~target_hull 點的 hull(貼合曲面邊界)。
  2. 內部佈規則格點(lattice,只留在輪廓內且離邊界 >= margin 者)。
  3. 以 hull 為 PSLG 邊界做約束 Delaunay(triangle 'pYY',不加 Steiner 點,保留輸入頂點)。
  → hull 貼合邊界 → 高覆蓋率;內部規則格 → 變形穩健(規則格比散點耐拉扯)。

hull 排在 vertices 最前(Spine 格式)。輸出格式同 v2.to_spine。
"""
import argparse, json
import numpy as np
import cv2
import triangle as tr


def load_mask(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"無法讀取: {path}")
    if img.ndim == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3]
    else:
        g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        alpha = (g > 0).astype(np.uint8) * 255
    return (alpha > 8).astype(np.uint8) * 255, img.shape[1], img.shape[0]


def contour_hull(mask, target_hull=40):
    """取最大外輪廓,approxPolyDP 逼近至約 target_hull 點(二分 epsilon)。"""
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        raise SystemExit("找不到輪廓")
    c = max(cnts, key=cv2.contourArea)
    peri = cv2.arcLength(c, True)
    lo, hi = 0.001, 0.05
    best = None
    for _ in range(24):
        eps = (lo + hi) / 2 * peri
        ap = cv2.approxPolyDP(c, eps, True).reshape(-1, 2)
        n = len(ap)
        if best is None or abs(n - target_hull) < abs(len(best) - target_hull):
            best = ap
        if n > target_hull:
            lo = (lo + hi) / 2
        else:
            hi = (lo + hi) / 2
    return best.astype(np.float64)


def interior_grid(mask, hull, step, margin):
    """規則格點,保留在輪廓內且離輪廓 >= margin(避免貼邊細長三角)。"""
    cnt = hull.reshape(-1, 1, 2).astype(np.float32)
    ys = np.where(mask.any(axis=1))[0]; xs = np.where(mask.any(axis=0))[0]
    y0, y1, x0, x1 = ys[0], ys[-1], xs[0], xs[-1]
    pts = []
    y = y0 + step / 2.0
    while y < y1:
        x = x0 + step / 2.0
        while x < x1:
            if cv2.pointPolygonTest(cnt, (float(x), float(y)), True) >= margin:
                pts.append((x, y))
            x += step
        y += step
    return np.array(pts, dtype=np.float64).reshape(-1, 2)


def to_spine(pts, tris, n_hull, W, H):
    verts, uvs = [], []
    for (x, y) in pts:
        verts += [round(float(x) - W / 2.0, 3), round(H / 2.0 - float(y), 3)]
        uvs += [round(float(x) / W, 5), round(float(y) / H, 5)]
    return {"type": "mesh", "vertices": verts, "uvs": uvs,
            "triangles": [int(i) for t in tris for i in t],
            "hull": int(n_hull), "width": int(W), "height": int(H), "_mode": "contour-grid-v3"}


def generate(path, target_hull=40, grid_step=None, margin=None):
    mask, W, H = load_mask(path)
    hull = contour_hull(mask, target_hull)
    n_hull = len(hull)
    diag = (W ** 2 + H ** 2) ** 0.5
    if grid_step is None:
        grid_step = max(diag / 9.0, 12.0)      # 內部格距 ~ 邊界對角的 1/9
    if margin is None:
        margin = grid_step * 0.35
    inner = interior_grid(mask, hull, grid_step, margin)
    pts = np.vstack([hull, inner]) if len(inner) else hull
    seg = np.array([[i, (i + 1) % n_hull] for i in range(n_hull)], dtype=np.int32)
    t = tr.triangulate({"vertices": pts, "segments": seg}, "pYY")
    if len(t["vertices"]) != len(pts):
        # 理論上 pYY 不加點;若加了(退化),截回並重編(保守)
        pts = np.array(t["vertices"], dtype=np.float64)
    tris = t["triangles"]
    return to_spine(pts, tris, n_hull, W, H)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--hull", type=int, default=40)
    ap.add_argument("--step", type=float, default=None)
    a = ap.parse_args()
    m = generate(a.image, a.hull, a.step)
    out = a.out or (a.image.rsplit(".", 1)[0] + "_mesh_v3.json")
    json.dump(m, open(out, "w"), ensure_ascii=False)
    print(f"[{m['_mode']}] {out}: 頂點 {len(m['uvs'])//2} (hull {m['hull']}), 三角 {len(m['triangles'])//3}")


if __name__ == "__main__":
    main()
