#!/usr/bin/env python3
"""端到端驗收:PSD件 → S3 generate_mesh_v2 → 對照 Award 真實(藝術家)mesh。

這是 S3+S4 的端到端閘,對**真實生產標的**(Award spine 的機器人拆件 mesh)驗收。
方法論沿用「藝術家真值自一致性」:先確認我方對齊/量測正確(用藝術家 mesh 自身覆蓋率
當基準),再判定生成 mesh 是否達標。純 CPU,不需外部 CDN,可自驅。

座標框統一在「atlas region derotate 後的局部像素」:
  1. 取 atlas region alpha(atlas_crop.crop_region,經 PSD 外部真值校正的 CW derotate)。
  2. Award 真實 mesh 的 uvs 是 atlas page 正規化座標 → 轉 page 像素 → 於 page 空間光柵化
     三角覆蓋 → 用**同一個** crop_region 變形到局部框(與 alpha 同框,免手推旋轉數學)。
  3. generate_mesh_v2 跑在 (1) 的 alpha crop 上 → 生成 mesh 於同框。
  4. 兩者對同一 alpha 算覆蓋 IoU + 頂點/三角/hull;逐條 AC 判定。

AC(見本檔 build_report):
  E1 對齊自洽:藝術家 mesh 覆蓋 IoU vs 其 atlas alpha ≥ 0.85(否則是我方 UV 對映錯,先修這)。
  E2 生成覆蓋:generated IoU ≥ artist IoU − 0.03(生成覆蓋不遜於藝術家)。
  E3 頂點預算:generated nv ≤ artist nv(不比藝術家複雜)。
  E4 生成 mesh 靜態品質:evaluate_mesh overall_pass(格式/無孤兒/無退化/重心在內)。
"""
import argparse, json, os, sys
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from atlas_crop import parse_atlas, crop_region          # noqa: E402
from generate_mesh_v2 import generate as gen_v2           # noqa: E402
from evaluate_mesh import evaluate as eval_mesh           # noqa: E402

# 機器人拆件中真正是 mesh 的三件(見 knowledge/s4-psd-to-spine-real.md)
MESH_SLOTS = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def page_size(atlas_path, page_png):
    """從 atlas header 讀該 page 的 size:w,h。"""
    cur = None
    for ln in open(atlas_path, encoding="utf-8"):
        s = ln.rstrip()
        if s.endswith(".png"):
            cur = s.strip()
        elif cur == page_png and s.strip().startswith("size:"):
            w, h = s.split(":", 1)[1].split(",")
            return int(w), int(h)
    raise SystemExit(f"找不到 page size: {page_png}")


def award_mesh(award_json, slot):
    d = json.load(open(award_json, encoding="utf-8"))
    return d["skins"][0]["attachments"][slot][slot]


def rasterize_tris(pts, tris, H, W):
    """把三角形填滿為 0/1 覆蓋圖(pts: Nx2 像素座標)。"""
    cov = np.zeros((H, W), np.uint8)
    for t in tris:
        poly = np.round(pts[t]).astype(np.int32)
        cv2.fillConvexPoly(cov, poly, 1)
    return cov


def artist_coverage_local(mesh, alpha_shape, flip_v=False):
    """Award mesh 的 uvs 是 region-local 正規化([0,1] over 該 region 的邏輯 w,h);
    直接映到 derotate 後的局部 crop(W×H)。經自洽 IoU 閘挑正確 flip。"""
    H, W = alpha_shape
    uvs = np.array(mesh["uvs"], dtype=np.float64).reshape(-1, 2)
    lx = uvs[:, 0] * W
    ly = (1.0 - uvs[:, 1]) * H if flip_v else uvs[:, 1] * H
    pts = np.stack([lx, ly], axis=1)
    tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    cov = rasterize_tris(pts, tris, H, W)
    return cov, len(uvs), len(tris), mesh.get("hull", 0)


def iou(a, b):
    a = a > 0; b = b > 0
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum()) / u if u else 0.0


def eval_one(atlas_path, award_json, slot, rows, cols, workdir):
    regions = parse_atlas(atlas_path)
    region = regions[slot]
    page = region["page"]
    page_path = os.path.join(os.path.dirname(atlas_path), page)
    sheet = cv2.imread(page_path, cv2.IMREAD_UNCHANGED)
    alpha_crop = crop_region(sheet, region)                     # BGRA local crop
    alpha = (alpha_crop[:, :, 3] > 8).astype(np.uint8)
    H, W = alpha.shape

    # 存 alpha crop 給 generator(它讀檔)
    os.makedirs(workdir, exist_ok=True)
    safe = slot.replace("/", "__")
    crop_png = os.path.join(workdir, f"{safe}.png")
    cv2.imwrite(crop_png, alpha_crop)

    # 生成 mesh
    gen = gen_v2(crop_png, rows=rows, cols=cols, mode="auto")
    gen_report = eval_mesh(gen, alpha, vertex_budget=128)
    # 生成 mesh 覆蓋(用 evaluate 內同法自算,取 AC1 值)
    gen_iou = gen_report["criteria"]["AC1_iou"]["value"]
    gen_nv = gen_report["vertices"]

    # 藝術家 mesh — 先試不翻,再試翻 v,取自洽 IoU 較高者
    amesh = award_mesh(award_json, slot)
    best = None
    for flip in (False, True):
        cov, nv, nt, hull = artist_coverage_local(amesh, (H, W), flip_v=flip)
        art_iou = iou(cov, alpha)
        if best is None or art_iou > best["art_iou"]:
            best = {"art_iou": round(art_iou, 4), "art_nv": nv, "art_nt": nt,
                    "art_hull": hull, "flip_v": flip}

    e1 = bool(best["art_iou"] >= 0.85)
    e2 = bool(gen_iou >= best["art_iou"] - 0.03)
    e3 = bool(gen_nv <= best["art_nv"])
    e4 = bool(gen_report["overall_pass"])
    return {
        "slot": slot, "local_wh": [W, H],
        "artist": best,
        "generated": {"iou": gen_iou, "nv": gen_nv,
                      "nt": gen_report["triangles"], "hull": gen["hull"],
                      "mode": gen.get("_mode")},
        "AC": {
            "E1_align_selfconsistent(art_iou>=0.85)": e1,
            "E2_gen_coverage(gen>=art-0.03)": e2,
            "E3_vertex_budget(gen_nv<=art_nv)": e3,
            "E4_gen_static_quality(evaluate_mesh)": e4,
        },
        "pass": e1 and e2 and e3 and e4,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--json", default="assets/Award.json")
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--workdir", default="/tmp/award_mesh_cmp")
    a = ap.parse_args()
    reports = [eval_one(a.atlas, a.json, s, a.rows, a.cols, a.workdir) for s in MESH_SLOTS]
    overall = all(r["pass"] for r in reports)
    out = {"overall_pass": overall, "parts": reports}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
