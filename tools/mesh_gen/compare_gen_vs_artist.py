#!/usr/bin/env python3
"""端到端驗收:PSD/atlas 件 → S3 generate_mesh_v2 → 對照 Award 真實(藝術家)mesh。

背景(見 knowledge/s4-psd-to-spine-real.md):Award 生產 spine 中,機器人拆件的
光暈/身體/左手三件是 mesh(藝術家手做)。本工具把「同一張件輪廓」餵給我們的
S3 v2 生成器,再與藝術家 mesh 做**同一真值下**的覆蓋率(coverage IoU)與頂點預算比較,
回答:「S3 能否對真實生產標的產出品質相當的 mesh?」

單一真值來源:atlas region 的 alpha 輪廓(atlas_crop.extract 去旋轉回 orig 方向)。
  - 藝術家 mesh:JSON uvs 為 **region-local [0,1]**(Spine runtime 才套 atlas 旋轉/縮放),
    直接 (u*W, v*H) 落到該輪廓像素格 → 光柵化三角 → 對 alpha 算 IoU。
    v 方向由「取較高 IoU」自動決定(解 JSON 慣例;高 IoU 同時反證映射正確)。
  - 生成 mesh:把同一張 alpha 輪廓 PNG 餵給 generate_mesh_v2 → 對同一 alpha 算 IoU。

判定(每件):
  - gen 靜態格式/自交閘(借 evaluate_mesh)PASS。
  - gen coverage IoU >= 藝術家 coverage IoU - MARGIN(生成不遜於藝術家覆蓋)。
"""
import sys, os, json, argparse, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import cv2
import atlas_crop
import generate_mesh_v2
import evaluate_mesh

MESH_PIECES = ['機器人拆件/光暈', '機器人拆件/身體', '機器人拆件/左手']
MARGIN = 0.03  # 允許生成 IoU 比藝術家低這麼多仍算 PASS


def load_artist_mesh(award_json, name):
    d = json.load(open(award_json, encoding='utf-8'))
    sk = d['skins']
    att = sk[0]['attachments'] if isinstance(sk, list) else list(sk.values())[0]
    a = att[name][name]
    uvs = np.array(a['uvs'], dtype=np.float64).reshape(-1, 2)
    tris = np.array(a['triangles'], dtype=np.int32).reshape(-1, 3)
    return uvs, tris, len(uvs)


def raster_tris(pts, tris, H, W):
    """把三角面填滿成覆蓋遮罩(pts: Nx2 影像像素座標)。"""
    m = np.zeros((H, W), np.uint8)
    for t in tris:
        poly = np.round(pts[t]).astype(np.int32)
        cv2.fillConvexPoly(m, poly, 1)
    return m


def iou(a, b):
    a = (a > 0); b = (b > 0)
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def artist_coverage(uvs, tris, alpha):
    """藝術家 mesh 在 orig 輪廓上的覆蓋 IoU(自動解 v 方向)。回傳 (iou, recon, flip)。"""
    H, W = alpha.shape
    best = (-1.0, None, False)
    for flip in (False, True):
        v = (1.0 - uvs[:, 1]) if flip else uvs[:, 1]
        pts = np.stack([uvs[:, 0] * (W - 1), v * (H - 1)], axis=1)
        recon = raster_tris(pts, tris, H, W)
        val = iou(recon, alpha)
        if val > best[0]:
            best = (val, recon, flip)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--atlas', default='assets/Award.atlas')
    ap.add_argument('--sheet', default='assets/Award.png')
    ap.add_argument('--json', default='assets/Award.json')
    ap.add_argument('--rows', type=int, default=10)
    ap.add_argument('--cols', type=int, default=3)
    args = ap.parse_args()

    rows = []
    all_pass = True
    tmpdir = tempfile.mkdtemp(prefix='cmp_mesh_')
    for name in MESH_PIECES:
        # 1) 真值輪廓:atlas region alpha(去旋轉回 orig)
        sub = atlas_crop.extract(args.atlas, args.sheet, name)  # BGRA, orig 方向
        if sub.ndim != 3 or sub.shape[2] < 4:
            raise SystemExit(f"{name}: 無 alpha 通道,無法取輪廓")
        alpha = (sub[:, :, 3] > 8).astype(np.uint8)
        H, W = alpha.shape

        # 2) 藝術家 mesh 覆蓋
        uvs, tris, nv_art = load_artist_mesh(args.json, name)
        art_iou, _, flip = artist_coverage(uvs, tris, alpha)

        # 3) 把同一 alpha 輪廓存成 PNG 餵生成器
        png = os.path.join(tmpdir, name.split('/')[-1] + '.png')
        rgba = np.zeros((H, W, 4), np.uint8)
        rgba[:, :, 3] = alpha * 255
        rgba[:, :, :3] = 255  # 白色前景(僅供輪廓;generate 用 alpha)
        cv2.imwrite(png, rgba)

        gen = generate_mesh_v2.generate(png, rows=args.rows, cols=args.cols, mode='auto')
        nv_gen = len(gen['uvs']) // 2
        ev = evaluate_mesh.evaluate(gen, alpha, vertex_budget=64)
        crit = ev['criteria']
        gen_iou = crit['AC1_iou']['value']
        fmt_ok = crit['AC4_format']['pass']
        degen_ok = crit['AC2b_degenerate']['pass']       # 退化三角(面積≈0)
        orphan_ok = crit['AC2c_orphans']['pass']
        struct_ok = fmt_ok and degen_ok and orphan_ok    # 靜態結構健全

        gen_pass = (gen_iou >= art_iou - MARGIN) and struct_ok
        all_pass = all_pass and gen_pass
        rows.append(dict(piece=name, mode=gen.get('_mode'), vflip=flip,
                         nv_art=nv_art, nv_gen=nv_gen,
                         art_iou=round(art_iou, 4), gen_iou=round(gen_iou, 4),
                         struct_ok=bool(struct_ok), fmt_ok=bool(fmt_ok),
                         degen_ok=bool(degen_ok), orphan_ok=bool(orphan_ok),
                         gen_pass=bool(gen_pass)))

    # 報表
    print(f"{'piece':<22}{'mode':<9}{'nv_art':>6}{'nv_gen':>7}{'art_IoU':>9}{'gen_IoU':>9}{'struct':>7}{'PASS':>6}")
    for r in rows:
        print(f"{r['piece']:<22}{str(r['mode']):<9}{r['nv_art']:>6}{r['nv_gen']:>7}"
              f"{r['art_iou']:>9}{r['gen_iou']:>9}{str(r['struct_ok']):>7}{str(r['gen_pass']):>6}")
    print(f"\nMARGIN(gen_IoU 允許低於 art_IoU 上限) = {MARGIN}")
    print(f"\nOVERALL: {'PASS' if all_pass else 'FAIL'}")
    print(json.dumps(rows, ensure_ascii=False))
    sys.exit(0 if all_pass else 1)


if __name__ == '__main__':
    main()
