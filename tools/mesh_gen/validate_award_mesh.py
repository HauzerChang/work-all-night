#!/usr/bin/env python3
"""端到端驗證:真實生產貼圖件 → S3 生成 mesh → 對照 Award 真實生產 mesh。

背景(knowledge/s4-psd-to-spine-real.md):`robot_parts.psd`(機器人拆件)的 5 件已對應
到生產 spine `Award` 的 slot `機器人拆件/<圖層名>`;其中 3 件是 mesh:光暈 / 身體 / 左手。
PSD 切件 ↔ atlas 切件 alpha-IoU 0.92–0.99 已確認同素材,故此處直接用 **Award atlas 切件**
當共同座標系(與 Award mesh 的 region-local UV 同框),對照最乾淨。

⚠️ 這 3 件在 Award 是 **weighted mesh 且無 deform timeline**(靠骨骼權重變形,非逐頂點 deform),
   我方 `generate_mesh_v2` 產 **unweighted** mesh。故本驗證是「**靜態拓樸/覆蓋率**」對照:
   - AC-cover:我方 mesh 覆蓋率 IoU ≥ 藝術家 mesh 自身覆蓋率(對齊真值基準,非武斷 0.95)
   - AC-budget:我方頂點數 ≤ 藝術家頂點數(精簡度不劣於人工)
   - AC-clean:我方 mesh setup 下 0 自交
   deform 穩健性因變形機制不同(權重 vs 逐頂點)在此不測,列為後續(見報告尾)。

用法:python3 tools/mesh_gen/validate_award_mesh.py [--gen v2|v1] [--outdir DIR]
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask

ASSET = os.path.join(os.path.dirname(__file__), "..", "..", "assets")
SLOTS = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def artist_mesh(skeleton, slot):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    return atts[slot][slot]


def poly_from_uv(uvs, tris, W, H):
    """把 region-local UV(0..1)映到 region 像素框,回傳 (points, triangles)。"""
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    return pts, tris


def iou_of(pts, tris, mask):
    H, W = mask.shape
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0


def seg_int(p1, p2, p3, p4):
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    d1, d2 = cross(p3, p4, p1), cross(p3, p4, p2)
    d3, d4 = cross(p1, p2, p3), cross(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def count_self_intersections(pts, tris):
    """統計三角化的邊自交數(共享頂點的邊不算)。setup 拓樸健檢。"""
    edges = set()
    for t in tris:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            edges.add((min(a, b), max(a, b)))
    edges = list(edges)
    n = 0
    for i in range(len(edges)):
        a, b = edges[i]
        for j in range(i + 1, len(edges)):
            c, d = edges[j]
            if len({a, b, c, d}) < 4:
                continue
            if seg_int(pts[a], pts[b], pts[c], pts[d]):
                n += 1
    return n


def run(gen_name, outdir):
    from generate_mesh_v2 import generate as gen_v2
    from generate_mesh import generate as gen_v1
    gen = (lambda p: gen_v2(p)) if gen_name == "v2" else (lambda p: gen_v1(p)[0])

    atlas = os.path.join(ASSET, "Award.atlas")
    png = os.path.join(ASSET, "Award.png")
    sk = json.load(open(os.path.join(ASSET, "Award.json")))
    os.makedirs(outdir, exist_ok=True)

    rows = []
    for slot in SLOTS:
        sub = extract(atlas, png, slot)               # 多頁自動選 page + CW derotate
        crop = os.path.join(outdir, slot.split("/")[-1] + "_region.png")
        cv2.imwrite(crop, sub)
        mask = load_mask(crop)
        if isinstance(mask, tuple):
            mask = mask[0]
        H, W = mask.shape

        # 我方 mesh
        mesh = gen(crop)
        if isinstance(mesh, tuple):
            mesh = mesh[0]
        my_nv = len(mesh["uvs"]) // 2
        my_tris_n = len(mesh["triangles"]) // 3
        my_iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
        my_uv = np.array(mesh["uvs"]).reshape(-1, 2)
        my_pts = np.column_stack([my_uv[:, 0] * W, my_uv[:, 1] * H])
        my_tris = np.array(mesh["triangles"]).reshape(-1, 3)
        my_si = count_self_intersections(my_pts, my_tris)

        # 藝術家 mesh(真值)
        a = artist_mesh(sk, slot)
        a_uv = np.array(a["uvs"]).reshape(-1, 2)
        a_tris = np.array(a["triangles"]).reshape(-1, 3)
        a_nv = len(a_uv)
        a_pts, _ = poly_from_uv(a_uv, a_tris, W, H)
        a_iou = iou_of(a_pts, a_tris, mask)
        a_si = count_self_intersections(a_pts, a_tris)
        weighted = (len(a["vertices"]) != len(a["uvs"]))

        cover_pass = my_iou >= a_iou - 0.01        # 覆蓋率不劣於真值(1% 容差)
        budget_pass = my_nv <= a_nv
        clean_pass = my_si == 0
        overall = cover_pass and budget_pass and clean_pass
        rows.append(dict(slot=slot, mode=mesh.get("_mode"), region=f"{W}x{H}",
                         my_iou=round(my_iou, 4), artist_iou=round(a_iou, 4),
                         my_nv=my_nv, artist_nv=a_nv, my_tris=my_tris_n,
                         artist_tris=len(a_tris), my_si=my_si, artist_si=a_si,
                         weighted=weighted, cover_pass=cover_pass,
                         budget_pass=budget_pass, clean_pass=clean_pass,
                         overall=overall))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", choices=["v1", "v2"], default="v2")
    ap.add_argument("--outdir", default="/tmp/award_mesh_val")
    a = ap.parse_args()
    rows = run(a.gen, a.outdir)
    print(f"\n=== S3 生成 mesh vs Award 真實 mesh(gen={a.gen})===")
    hdr = ["slot", "mode", "region", "my_iou", "artist_iou", "my_nv", "artist_nv",
           "my_si", "artist_si", "cover", "budget", "clean", "OVERALL"]
    print("  ".join(hdr))
    allpass = True
    for r in rows:
        allpass &= r["overall"]
        print(f'{r["slot"]:14} {str(r["mode"]):11} {r["region"]:9} {r["my_iou"]:.3f}   '
              f'{r["artist_iou"]:.3f}      {r["my_nv"]:3}    {r["artist_nv"]:3}    '
              f'{r["my_si"]:2}    {r["artist_si"]:2}   '
              f'{"P" if r["cover_pass"] else "F"}     {"P" if r["budget_pass"] else "F"}      '
              f'{"P" if r["clean_pass"] else "F"}     {"PASS" if r["overall"] else "FAIL"}')
    print(f'\n整體:{"ALL PASS" if allpass else "有 FAIL"}')
    print(json.dumps(rows, ensure_ascii=False))
    return 0 if allpass else 1


if __name__ == "__main__":
    sys.exit(main())
