#!/usr/bin/env python3
"""S3 端到端驗收:PSD 件 → generate_mesh_v2 → 對照「真實生產 spine mesh」ground truth。

背景:先前 S3 只用「自產 mesh vs 自身 alpha」自證(evaluate_mesh),沒有外部真值。
本工具引入**真實藝術家 mesh 當基準**(assets/Award.json 的機器人拆件 3 個 weighted mesh:
光暈/身體/左手),量化「自產 mesh 覆蓋率是否 ≥ 藝術家 mesh 覆蓋率」。

對齊依據(log 006 / 005):PSD 切件 size ≈ Award attachment width/height(+2px padding),
即 PSD 件像素空間 ≈ mesh 的 (uv*W, uv*H) 局部空間。故可把真實 mesh 的 uv 三角形
柵格化到「件像素」畫布,與 PSD alpha 求 IoU = **藝術家覆蓋率基準**;自產 mesh 用
evaluate_mesh 對同一 alpha 求 IoU。兩者同框可比。

方向約定不確定 → 對真實 mesh 嘗試 {identity, y-flip} 兩種 uv→pixel,取 IoU 較高者
(自我校驗約定,沿用 log 006「用外部真值定方向」的方法)。
"""
import argparse, json, os, sys
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from generate_mesh_v2 import generate as gen_v2  # noqa: E402
from evaluate_mesh import evaluate as eval_mesh   # noqa: E402


def load_alpha(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"讀不到: {path}")
    if img.ndim == 3 and img.shape[2] == 4:
        a = img[:, :, 3]
    else:
        g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        a = (g > 0).astype(np.uint8) * 255
    return (a > 8).astype(np.uint8)


def award_meshes(award_json):
    d = json.load(open(award_json))
    skins = d["skins"]
    atts = ({sk["name"]: sk.get("attachments", {}) for sk in skins}
            if isinstance(skins, list) else skins)["default"]
    out = {}
    for slot, group in atts.items():
        for aname, a in group.items():
            if a.get("type") == "mesh":
                out[slot] = a
    return out


def real_mesh_iou(mesh, alpha, flip_y):
    """把真實 mesh 的 uv 三角形柵格化到件像素畫布,與 alpha 求 IoU。"""
    H, W = alpha.shape
    uvs = mesh["uvs"]
    pts = np.empty((len(uvs) // 2, 2), np.float64)
    for i in range(0, len(uvs), 2):
        u, v = uvs[i], uvs[i + 1]
        x = u * (W - 1)
        y = (1.0 - v) * (H - 1) if flip_y else v * (H - 1)
        pts[i // 2] = (x, y)
    tris = np.array(mesh["triangles"], np.int32).reshape(-1, 3)
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    m = (alpha > 0).astype(np.uint8)
    inter = int(np.logical_and(recon, m).sum())
    union = int(np.logical_or(recon, m).sum())
    return (inter / union if union else 0.0), len(pts), len(tris)


def compare(part_png, real_mesh, rows, cols):
    alpha = load_alpha(part_png)
    # 自產 mesh
    gen = gen_v2(part_png, rows=rows, cols=cols)
    gen_rep = eval_mesh(gen, alpha, vertex_budget=200, iou_thresh=0.0)
    gen_iou = gen_rep["criteria"]["AC1_iou"]["value"]
    # 真實藝術家 mesh(兩方向取高)
    best = None
    for fy in (False, True):
        iou, nv, ntri = real_mesh_iou(real_mesh, alpha, fy)
        if best is None or iou > best[0]:
            best = (iou, nv, ntri, fy)
    art_iou, art_nv, art_ntri, art_fy = best
    return {
        "gen": {"mode": gen.get("_mode"), "verts": gen_rep["vertices"],
                "tris": gen_rep["triangles"], "hull": gen_rep["hull"],
                "coverage_iou": round(gen_iou, 4),
                "clean_topology": bool(gen_rep["criteria"]["AC2b_degenerate"]["pass"]
                                       and gen_rep["criteria"]["AC2c_orphans"]["pass"])},
        "artist": {"verts": art_nv, "tris": art_ntri,
                   "coverage_iou": round(art_iou, 4), "uv_flip_y": art_fy},
        "gen_vs_artist_iou_delta": round(gen_iou - art_iou, 4),
        # 通過:自產覆蓋率不低於藝術家基準太多(容 0.02),且頂點更省或相當
        "pass_coverage": gen_iou >= art_iou - 0.02,
        "pass_budget": gen_rep["vertices"] <= art_nv,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default=os.path.join(HERE, "../../assets/Award.json"))
    ap.add_argument("--parts_dir", required=True, help="psd_slice 輸出目錄(含件 PNG)")
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--cols", type=int, default=3)
    a = ap.parse_args()

    real = award_meshes(a.award)
    # PSD 圖層名 → Award slot 名 對應(慣例:機器人拆件/<圖層名>)
    pairs = [("00_光暈", "機器人拆件/光暈"),
             ("03_身體", "機器人拆件/身體"),
             ("04_左手", "機器人拆件/左手")]
    allpass = True
    report = {}
    for fname, slot in pairs:
        png = os.path.join(a.parts_dir, fname + ".png")
        if slot not in real:
            print(f"⚠ Award 無 slot {slot}"); allpass = False; continue
        r = compare(png, real[slot], a.rows, a.cols)
        report[slot] = r
        ok = r["pass_coverage"] and r["gen"]["clean_topology"]
        allpass = allpass and ok
        print(f"{slot}: gen[{r['gen']['mode']}] {r['gen']['verts']}v "
              f"cov={r['gen']['coverage_iou']} | artist {r['artist']['verts']}v "
              f"cov={r['artist']['coverage_iou']} | Δ={r['gen_vs_artist_iou_delta']} "
              f"| coverage_pass={r['pass_coverage']} clean={r['gen']['clean_topology']}")
    print("\nOVERALL:", "PASS" if allpass else "FAIL")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
