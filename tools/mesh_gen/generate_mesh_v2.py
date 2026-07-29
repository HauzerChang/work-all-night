#!/usr/bin/env python3
"""S3 v2 — deform-aware mesh 生成器。

來自里程碑發現(knowledge/s3-real-asset-finding.md):Canny 散點內部佈局靜態 IoU 高,
但大單向拉伸下自交。藝術家對窗簾用「直條(vertical strip)」拓樸 → 變形時各帶平滑滑動。

本版加入 strip 模式:對高瘦、row-convex(每條掃描線為單一 alpha 區段)的件,
用「掃描線格點」—— 每列取 alpha 左右邊界放點(+ 可選中欄),三角化成規則梯狀。
- 邊界點為主、順著拉伸軸 → 耐變形。
- 頂點數 = rows×cols,可控,接近藝術家精簡度。
- hull(外周)排在 vertices 最前(Spine 格式)。

mode=auto:長寬比高且 row-convex → strip;否則回退 v1(Delaunay,見 generate_mesh.py)。

參數調校發現(2026-06-26,4mesh 全驗):**IoU 由 rows(邊界取樣密度)決定,cols 只加內部
頂點不影響覆蓋率**。rows=8 對窗簾覆蓋率略低於藝術家基準(0.911 < ~0.916);**rows=10
(cols=3,30 頂點)對全部 4 mesh 都過 IoU 基準且真實 deform 乾淨** → 設為預設。
"""
import argparse, json
import numpy as np
import cv2


def load_mask(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"無法讀取: {path}")
    if img.ndim == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3]
    else:
        g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        alpha = (g > 0).astype(np.uint8) * 255
    return (alpha > 8).astype(np.uint8), img.shape[1], img.shape[0]


def row_span(mask, y):
    xs = np.where(mask[y] > 0)[0]
    return (int(xs[0]), int(xs[-1])) if len(xs) else None


def is_row_convex(mask, rows=24, hole_tol=2):
    """每條掃描線是否大致單一連續區段(strip 適用性)。"""
    h = mask.shape[0]
    ok = 0; tot = 0
    for i in range(rows):
        y = int((i + 0.5) * h / rows)
        xs = np.where(mask[y] > 0)[0]
        if not len(xs):
            continue
        tot += 1
        gaps = np.where(np.diff(xs) > 1)[0]
        if len(gaps) <= hole_tol:
            ok += 1
    return tot > 0 and ok / tot >= 0.9


def gen_strip(mask, W, H, rows, cols, inset=0.0):
    ys = np.where(mask.any(axis=1))[0]
    y0, y1 = int(ys[0]), int(ys[-1])
    grid = {}            # (i,j) -> point
    for i in range(rows):
        y = int(round(y0 + (y1 - y0) * i / (rows - 1)))
        y = min(max(y, y0), y1)
        sp = row_span(mask, y)
        if sp is None:
            # 往內找最近有效列
            for dy in range(1, H):
                for yy in (y - dy, y + dy):
                    if 0 <= yy < H and row_span(mask, yy):
                        sp = row_span(mask, yy); break
                if sp: break
        xl, xr = sp
        for j in range(cols):
            t = j / (cols - 1)
            x = xl + (xr - xl) * t
            # 邊界欄微內縮以避免落在羽化邊外(可選)
            if inset and j in (0, cols - 1):
                x += (inset if j == 0 else -inset) * (xr - xl)
            grid[(i, j)] = (float(x), float(y))

    # hull(外周)順時針 loop:top → right → bottom(逆) → left(上)
    hull_ij = []
    hull_ij += [(0, j) for j in range(cols)]
    hull_ij += [(i, cols - 1) for i in range(1, rows)]
    hull_ij += [(rows - 1, j) for j in range(cols - 2, -1, -1)]
    hull_ij += [(i, 0) for i in range(rows - 2, 0, -1)]
    interior_ij = [(i, j) for i in range(1, rows - 1) for j in range(1, cols - 1)]

    order = hull_ij + interior_ij
    idx = {ij: k for k, ij in enumerate(order)}
    pts = [grid[ij] for ij in order]

    # 規則梯狀三角(一致 winding)
    tris = []
    for i in range(rows - 1):
        for j in range(cols - 1):
            a, b = idx[(i, j)], idx[(i, j + 1)]
            c, d = idx[(i + 1, j)], idx[(i + 1, j + 1)]
            tris.append([a, b, d]); tris.append([a, d, c])
    return pts, tris, len(hull_ij)


def to_spine(pts, tris, n_hull, W, H):
    verts, uvs = [], []
    for (x, y) in pts:
        verts += [round(x - W / 2.0, 3), round(H / 2.0 - y, 3)]
        uvs += [round(x / W, 5), round(y / H, 5)]
    return {"type": "mesh", "vertices": verts, "uvs": uvs,
            "triangles": [int(i) for t in tris for i in t],
            "hull": int(n_hull), "width": int(W), "height": int(H)}


def generate(path, rows=10, cols=3, mode="auto", eps=0.004):
    mask, W, H = load_mask(path)
    aspect = H / max(W, 1)
    use_strip = (mode == "strip") or (mode == "auto" and aspect >= 1.2 and is_row_convex(mask))
    if not use_strip:
        # Delaunay 回退(blobby/圓件)。覆蓋率由**邊界取樣密度**決定(內部點不影響),
        # 與 strip 的「IoU 由 rows 決定」同理。對 atlas 縮放(~0.70)+ 羽化邊的真實件,
        # 預設 0.008 太粗 → 用 0.004 貼合輪廓(對 Award 光暈/身體/左手實測達藝術家水準)。
        # 見 knowledge/s3-psd-to-award-mesh.md。
        from generate_mesh import generate as gen_v1
        m, _ = gen_v1(path, epsilon_frac=eps)
        m["_mode"] = "delaunay-v1"
        return m
    pts, tris, n_hull = gen_strip(mask, W, H, rows, cols)
    m = to_spine(pts, tris, n_hull, W, H)
    m["_mode"] = "strip"
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--mode", choices=["auto", "strip", "delaunay"], default="auto")
    a = ap.parse_args()
    m = generate(a.image, a.rows, a.cols, a.mode)
    out = a.out or (a.image.rsplit(".", 1)[0] + "_mesh_v2.json")
    json.dump(m, open(out, "w"), ensure_ascii=False)
    print(f"[{m.get('_mode')}] {out}: 頂點 {len(m['uvs'])//2} (hull {m['hull']}), 三角 {len(m['triangles'])//3}")


if __name__ == "__main__":
    main()
