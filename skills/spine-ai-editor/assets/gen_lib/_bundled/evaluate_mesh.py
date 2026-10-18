#!/usr/bin/env python3
"""S3 mesh 評估器(自我品質閘) — 對照 AC.md 逐條評分。

評估器是「鍛鍊五件套」的樞紐:能自評才能自主迭代收斂(見 Spine能力鍛鍊計畫.md 第二部分)。
輸入:Spine mesh attachment(generate_mesh 的輸出格式) + 來源 alpha 遮罩。
輸出:每條 AC 的 pass/fail + 量化值;可由 orchestrator 機讀後決定是否再迭代。
"""
import argparse, json
import numpy as np
import cv2


def mesh_pixel_coords(mesh):
    """還原成影像像素座標(generate 用 y 上翻+置中,這裡逆轉回去)以便與遮罩比對。"""
    W, H = mesh["width"], mesh["height"]
    v = mesh["vertices"]
    pts = []
    for i in range(0, len(v), 2):
        x = v[i] + W / 2.0
        y = H / 2.0 - v[i + 1]
        pts.append((x, y))
    return np.array(pts, dtype=np.float64), W, H


def tri_area(a, b, c):
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2.0


def evaluate(mesh, mask, vertex_budget=64,
             iou_thresh=0.95, centroid_thresh=0.99):
    pts, W, H = mesh_pixel_coords(mesh)
    tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    nv = len(pts)
    uvs = mesh["uvs"]
    verts = mesh["vertices"]
    results = {}

    # AC4 格式
    fmt = {
        "unweighted (len(vertices)==2*nv==len(uvs))": len(verts) == 2 * nv == len(uvs),
        "hull>0 且 ≤ nv": 0 < mesh["hull"] <= nv,
        "triangles 索引在範圍內": bool(tris.size) and int(tris.max()) < nv and int(tris.min()) >= 0,
    }
    results["AC4_format"] = {"pass": all(fmt.values()), "detail": fmt}

    # AC1 IoU(把三角形填滿 vs 來源遮罩)
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        poly = np.round(pts[t]).astype(np.int32)
        cv2.fillConvexPoly(recon, poly, 1)
    m = (mask > 0).astype(np.uint8)
    inter = int(np.logical_and(recon, m).sum())
    union = int(np.logical_or(recon, m).sum())
    iou = inter / union if union else 0.0
    results["AC1_iou"] = {"pass": iou >= iou_thresh, "value": round(iou, 4), "thresh": iou_thresh}

    # AC2a 三角形重心在 mask 內
    inside = 0
    for t in tris:
        c = pts[t].mean(axis=0)
        cx, cy = int(round(c[0])), int(round(c[1]))
        if 0 <= cy < H and 0 <= cx < W and m[cy, cx]:
            inside += 1
    ratio = inside / len(tris) if len(tris) else 0.0
    results["AC2a_centroid_in_mask"] = {
        "pass": ratio >= centroid_thresh, "value": round(ratio, 4), "thresh": centroid_thresh}

    # AC2b 退化三角形(面積≈0)
    degen = sum(1 for t in tris if tri_area(pts[t[0]], pts[t[1]], pts[t[2]]) < 1e-6)
    results["AC2b_degenerate"] = {"pass": degen == 0, "value": int(degen)}

    # AC2c 孤兒頂點
    used = set(int(i) for i in tris.flatten())
    orphans = [i for i in range(nv) if i not in used]
    results["AC2c_orphans"] = {"pass": len(orphans) == 0, "value": len(orphans)}

    # AC3 頂點預算
    results["AC3_vertex_budget"] = {"pass": nv <= vertex_budget, "value": nv, "budget": vertex_budget}

    overall = all(r["pass"] for r in results.values())
    return {"overall_pass": overall, "vertices": nv, "triangles": len(tris),
            "hull": mesh["hull"], "criteria": results}


def load_mask(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"無法讀取遮罩來源: {path}")
    if img.ndim == 3 and img.shape[2] == 4:
        return (img[:, :, 3] > 8).astype(np.uint8)
    gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return (gray > 8).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mesh_json")
    ap.add_argument("source_image")
    ap.add_argument("--budget", type=int, default=64)
    args = ap.parse_args()
    mesh = json.load(open(args.mesh_json))
    mask = load_mask(args.source_image)
    report = evaluate(mesh, mask, vertex_budget=args.budget)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
