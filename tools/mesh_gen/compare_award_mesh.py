#!/usr/bin/env python3
"""端到端驗收:PSD 切件 → S3 生成 mesh → 對照 Award 真實生產 mesh。

背景(見 knowledge/s4-psd-to-spine-real.md):Award(big win)spine 裡「機器人拆件」有 3 個
mesh 件 —— 光暈 / 身體 / 左手 —— 對應 robot_parts.psd 的同名圖層。這 3 件在 Award 是
**weighted mesh 且無 deform timeline**(靠骨骼權重變形,非逐頂點 deform),故本比對是
**靜態覆蓋率 + 拓樸經濟度**的驗收,不是 deform 穩健度(明確界定範圍,誠實)。

流程(每件):
  1. 來源 mask = PSD 切件 alpha(psd_slice 產出)。
  2. 我方 mesh = generate_mesh_v2(auto) —— 這 3 件長寬比 <1.2 → 回退 v1 Delaunay。
  3. 我方 IoU(mesh 填滿 vs PSD alpha)。
  4. 藝術家 baseline IoU:用 Award attachment 的 uvs 重建覆蓋,對 PSD alpha 求 IoU。
     ⚠️ uv 方向未知(光暈/身體在 atlas 旋轉打包)→ **以 PSD alpha 為外部真值,窮舉 8 種
     方向變換取最高 IoU**(RULES:round-trip 自洽 ≠ 絕對方向,需外部真值校驗)。
  5. 我方 mesh 靜態幾何閘(evaluate_mesh:格式/重心/退化/孤兒)。
  6. 拓樸經濟度:我方頂點數 vs 藝術家頂點數。

AC(可機讀):
  - AC_coverage:我方 IoU ≥ 藝術家 baseline IoU − margin(覆蓋不輸藝術家)。
  - AC_valid   :靜態幾何閘全過(合法 spine mesh)。
  - AC_economy :我方頂點數 ≤ 藝術家頂點數(至少不更複雜)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask as eval_load_mask


# uv → 像素座標的 8 種方向候選(對應旋轉/翻轉打包的未知性)
ORIENTS = {
    "id":      lambda u, v: (u, v),
    "flipU":   lambda u, v: (1 - u, v),
    "flipV":   lambda u, v: (u, 1 - v),
    "flipUV":  lambda u, v: (1 - u, 1 - v),
    "swap":    lambda u, v: (v, u),
    "swap_fU": lambda u, v: (1 - v, u),
    "swap_fV": lambda u, v: (v, 1 - u),
    "swap_fUV":lambda u, v: (1 - v, 1 - u),
}


def load_alpha(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"讀不到 {path}")
    if img.ndim == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3]
    else:
        g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        alpha = (g > 0).astype(np.uint8) * 255
    return (alpha > 8).astype(np.uint8)


def get_attachment(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[slot][name]


def coverage_from_uvs(uvs2, tris, W, H, transform):
    """用 uvs(套 transform)重建三角覆蓋的二值圖。"""
    recon = np.zeros((H, W), np.uint8)
    pix = np.empty_like(uvs2)
    for i, (u, v) in enumerate(uvs2):
        uu, vv = transform(u, v)
        pix[i] = (uu * W, vv * H)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pix[t]).astype(np.int32), 1)
    return recon, pix


def artist_best(att, mask):
    """窮舉方向,回傳對 PSD alpha 最貼合的藝術家覆蓋(外部真值定向)。"""
    uvs2 = np.array(att["uvs"]).reshape(-1, 2)
    tris = np.array(att["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    best = None
    for oname, f in ORIENTS.items():
        recon, pix = coverage_from_uvs(uvs2, tris, W, H, f)
        inter = np.logical_and(recon, mask).sum()
        union = np.logical_or(recon, mask).sum()
        iou = float(inter / union) if union else 0.0
        if best is None or iou > best[1]:
            best = (oname, iou, recon, pix)
    return {"orient": best[0], "iou": round(best[1], 4),
            "recon": best[2], "pix": best[3],
            "verts": len(uvs2), "hull": att.get("hull"),
            "tris": len(tris)}


def my_pixel_coords(mesh):
    W, H = mesh["width"], mesh["height"]
    v = mesh["vertices"]
    return np.array([(v[i] + W / 2.0, H / 2.0 - v[i + 1])
                     for i in range(0, len(v), 2)]), W, H


def overlay(path, mask, my_pix, my_tris, ar_pix, ar_tris):
    H, W = mask.shape
    img = np.zeros((H, W, 3), np.uint8)
    img[mask > 0] = (60, 60, 60)
    for t in ar_tris:
        cv2.polylines(img, [np.round(ar_pix[t]).astype(np.int32)], True, (0, 120, 255), 1)
    for t in my_tris:
        cv2.polylines(img, [np.round(my_pix[t]).astype(np.int32)], True, (0, 255, 90), 1)
    cv2.imwrite(path, img)


def compare(piece_png, sk, slot, name, fig_path=None):
    mask = load_alpha(piece_png)
    att = get_attachment(sk, slot, name)
    ar = artist_best(att, mask)

    mesh = gen_v2(piece_png, mode="auto")
    ev = evaluate(mesh, eval_load_mask(piece_png))
    my_iou = ev["criteria"]["AC1_iou"]["value"] if "criteria" in ev else ev["AC1_iou"]["value"]
    my_nv = len(mesh["uvs"]) // 2
    my_pix, _, _ = my_pixel_coords(mesh)
    my_tris = np.array(mesh["triangles"]).reshape(-1, 3)

    valid = all(ev["criteria"][k]["pass"] if "criteria" in ev else ev[k]["pass"]
                for k in (ev["criteria"] if "criteria" in ev else ev)
                if k not in ("AC1_iou",))  # IoU 分開判(對齊藝術家而非絕對 0.95)

    if fig_path:
        overlay(fig_path, mask, my_pix, my_tris, ar["pix"],
                np.array(att["triangles"]).reshape(-1, 3))

    margin = 0.02
    return {
        "piece": os.path.basename(piece_png), "slot": slot,
        "my": {"mode": mesh.get("_mode"), "verts": my_nv, "hull": mesh["hull"],
               "tris": len(my_tris), "iou": my_iou},
        "artist": {"verts": ar["verts"], "hull": ar["hull"], "tris": ar["tris"],
                   "iou": ar["iou"], "orient": ar["orient"]},
        "AC_coverage": {"pass": my_iou >= ar["iou"] - margin,
                        "my_iou": my_iou, "artist_iou": ar["iou"], "margin": margin},
        "AC_valid": {"pass": bool(valid)},
        "AC_economy": {"pass": my_nv <= ar["verts"], "my": my_nv, "artist": ar["verts"]},
    }


PIECES = [
    ("00_光暈.png", "機器人拆件/光暈"),
    ("03_身體.png", "機器人拆件/身體"),
    ("04_左手.png", "機器人拆件/左手"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pieces-dir", default="/tmp/robot_pieces")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--figs", default=None, help="輸出 overlay 圖的目錄")
    a = ap.parse_args()
    sk = json.load(open(a.award))
    if a.figs:
        os.makedirs(a.figs, exist_ok=True)
    reports = []
    for fn, slot in PIECES:
        p = os.path.join(a.pieces_dir, fn)
        fig = os.path.join(a.figs, slot.replace("/", "_") + ".png") if a.figs else None
        rep = compare(p, sk, slot, slot, fig)
        rep["overall_pass"] = rep["AC_coverage"]["pass"] and rep["AC_valid"]["pass"] and rep["AC_economy"]["pass"]
        reports.append(rep)
    allpass = all(r["overall_pass"] for r in reports)
    print(json.dumps({"reports": reports, "all_pass": allpass}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
