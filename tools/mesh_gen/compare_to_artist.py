#!/usr/bin/env python3
"""S3 端到端驗收 — 把「PSD件→S3 生成 mesh」對照**真實生產 spine 的藝術家 mesh**。

情境(candidate #1,STATE):`robot_parts.psd` 的件在生產 spine `Award.json` 裡有對應的
藝術家手做 mesh(`機器人拆件/<圖層名>`)。這支工具做「同一件、同一張 alpha」上的**輪廓覆蓋對照**:

- S3 生成 mesh:填三角形 → IoU vs 件 alpha(即 evaluate_mesh 的 AC1,unweighted 直接用本地座標)。
- 藝術家 mesh:Award 的 mesh 為 **weighted**,JSON 不存 setup 世界座標;但 mesh 的 uvs 即
  「貼圖 → 幾何」的對映,在 setup pose 下與本地輪廓同形。故用 `uv*(width,height)` 還原藝術家
  輪廓多邊形(width/height = mesh 宣告的原圖尺寸,實測 ≈ PSD 件 bbox),填三角形 → IoU vs 同一件 alpha。
  以 8 種朝向(rot90×flip)取最佳,經驗證這批件最佳朝向皆 (0,0) → 確認 uv 直接對映本地座標、無旋轉。

⚠️ 為何沒有 deform 對照:`Award.json` **無任何 deform timeline**(`animations[*].deform` 皆空);
機器人 mesh 是 **weighted、靠骨骼蒙皮**變形,不是 main_draw 那種 deform-timeline 驅動。真實位移場
不存在,依 RULES「不要用未校準 stress_field」→ 本標的不做 deform 閘(deform 韌性由 main_draw 4mesh 負責)。

用法:
  python compare_to_artist.py --award assets/Award.json --parts scratch/robot_parts \\
      --map 光暈=00_光暈 身體=03_身體 左手=04_左手
"""
import argparse, json
import numpy as np
import cv2


def piece_alpha(png_path):
    im = cv2.imread(png_path, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise SystemExit(f"讀不到件: {png_path}")
    if im.ndim == 3 and im.shape[2] == 4:
        return (im[:, :, 3] > 8).astype(np.uint8)
    g = im if im.ndim == 2 else cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    return (g > 8).astype(np.uint8)


def iou(a, b):
    if b.shape != a.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_NEAREST)
    i = int(np.logical_and(a, b).sum()); u = int(np.logical_or(a, b).sum())
    return i / u if u else 0.0


def raster_local(pts, tris, W, H):
    canvas = np.zeros((int(round(H)), int(round(W))), np.uint8)
    T = np.array(tris, dtype=np.int32).reshape(-1, 3)
    for t in T:
        cv2.fillConvexPoly(canvas, np.round(pts[t]).astype(np.int32), 1)
    return canvas


def s3_coverage(mesh, alpha):
    """unweighted S3 mesh:本地像素座標(x+W/2, H/2-y)填三角 → IoU vs alpha。"""
    W, H = mesh["width"], mesh["height"]
    v = mesh["vertices"]
    pts = np.array([[v[i] + W / 2.0, H / 2.0 - v[i + 1]] for i in range(0, len(v), 2)])
    return iou(raster_local(pts, mesh["triangles"], W, H), alpha), len(pts)


def artist_coverage(att, alpha):
    """weighted 藝術家 mesh:uv*(W,H) 還原輪廓,取 8 朝向最佳 IoU。"""
    W, H = att["width"], att["height"]
    uvs = att["uvs"]
    u = np.array(uvs[0::2]) * W; vv = np.array(uvs[1::2]) * H
    base = np.stack([u, vv], 1)
    best = (-1.0, None)
    for k in range(4):
        for flip in (0, 1):
            pts = base.copy(); w, h = W, H
            if flip:
                pts[:, 1] = h - pts[:, 1]
            for _ in range(k):
                pts = np.stack([h - pts[:, 1], pts[:, 0]], 1); w, h = h, w
            cov = raster_local(pts, att["triangles"], w, h)
            val = iou(cov, alpha)
            if val > best[0]:
                best = (val, (k, flip))
    return best[0], len(uvs) // 2, att["hull"], best[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--parts", default="scratch/robot_parts")
    ap.add_argument("--map", nargs="+", required=True,
                    help="藝術家slot尾名=件檔名(不含.png),例 身體=03_身體")
    ap.add_argument("--slot-prefix", default="機器人拆件/")
    ap.add_argument("--gen-suffix", default="_mesh.json")
    ap.add_argument("--iou-thresh", type=float, default=0.95)
    args = ap.parse_args()

    d = json.load(open(args.award))
    atts = d["skins"][0]["attachments"] if isinstance(d["skins"], list) else d["skins"]["default"]

    rows = []
    for pair in args.map:
        part, stem = pair.split("=", 1)
        slot = args.slot_prefix + part
        att = atts[slot][slot]
        alpha = piece_alpha(f"{args.parts}/{stem}.png")
        mesh = json.load(open(f"{args.parts}/{stem}{args.gen_suffix}"))
        s3_iou, s3_v = s3_coverage(mesh, alpha)
        ar_iou, ar_v, ar_hull, orient = artist_coverage(att, alpha)
        rows.append({
            "part": part,
            "s3": {"verts": s3_v, "tris": len(mesh["triangles"]) // 3,
                   "mode": mesh.get("_mode"), "silhouette_iou": round(s3_iou, 4)},
            "artist": {"verts": ar_v, "hull": ar_hull, "tris": len(att["triangles"]) // 3,
                       "silhouette_iou": round(ar_iou, 4), "best_orient": orient},
            "s3_vs_artist_iou_delta": round(s3_iou - ar_iou, 4),
            "s3_reaches_artist": s3_iou >= ar_iou - 0.01,   # 達到藝術家水準(±0.01)
            "s3_verts_ratio": round(s3_v / ar_v, 3),
        })
    report = {"target": "PSD件→S3 mesh vs Award 藝術家 mesh(輪廓覆蓋)",
              "note": "Award 無 deform timeline;機器人 mesh 為 weighted 骨骼蒙皮,故不做 deform 閘",
              "parts": rows,
              "summary": {
                  "all_reach_artist_silhouette": all(r["s3_reaches_artist"] for r in rows),
                  "s3_avg_verts_ratio": round(sum(r["s3_verts_ratio"] for r in rows) / len(rows), 3),
              }}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["summary"]["all_reach_artist_silhouette"] else 1)


if __name__ == "__main__":
    main()
