#!/usr/bin/env python3
"""端到端驗收:PSD件 → generate_mesh_v2 → 對照 Award 真實(藝術家)mesh 的靜態輪廓保真度。

背景 / 座標系關鍵發現
--------------------
Spine JSON 的 mesh `uvs` 是 **region-local 正規化 [0,1]**(runtime 由 AtlasAttachmentLoader
remap 進 atlas page),不是 page 正規化。所以藝術家 mesh 的 uv 已經直接等於「件圖正規化座標」
(u 向右、v 向下、[0,1] over 件),與 generate_mesh_v2 產出的 uv(x/W, y/H)同一個座標系 —
不需要任何 atlas region / 旋轉映射。

方法(每件)
-----------
1. psd_slice 切出的件 PNG → alpha 當真值輪廓。
2. generate_mesh_v2 產 mesh;hull uv 多邊形 rasterize → vs alpha 的 IoU(gen_hull∩alpha)。
3. 藝術家 mesh(Award.json)hull uv 多邊形 → vs alpha 的 IoU(art_hull∩alpha)。
4. 兩個 hull 多邊形互比 IoU(gen∩art),量「生成輪廓 ≈ 藝術家輪廓」。
5. 校準自證:對藝術家 uv 試 8 種 flip/transpose,確認 identity(不翻不轉)勝出 →
   證明兩者座標系真的對齊(不是靠搜尋硬湊)。

用法:python3 tools/mesh_gen/compare_to_award.py [--psd assets/robot_parts.psd]
需先能 import generate_mesh_v2 / psd_slice(PYTHONPATH=tools/mesh_gen)。
"""
import json, os, sys, argparse, tempfile
import numpy as np, cv2
from itertools import product

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_mesh_v2 as gmv2
import psd_slice

AWARD_JSON = 'assets/Award.json'
# PSD 圖層名 → Award slot 後綴(見 knowledge/s4-psd-to-spine-real.md)
ROBOT_MESH_PIECES = ['光暈', '身體', '左手']  # Award 中為 mesh 的 3 件


def award_meshes(path):
    d = json.load(open(path)); sk = d['skins']
    if isinstance(sk, dict):
        it = sk.get('default') or list(sk.values())[0]
    else:
        it = sk[0]['attachments']
    out = {}
    for slot, atts in it.items():
        for aname, a in atts.items():
            if a.get('type') == 'mesh':
                out[slot] = a
    return out


def hull_mask(poly_uv, H, W):
    pts = np.array([[u * W, v * H] for u, v in poly_uv], np.int32)
    m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [pts], 1)
    return m


def iou(a, b):
    return np.logical_and(a, b).sum() / max(np.logical_or(a, b).sum(), 1)


def calibrate(uv, hull, ref):
    """回傳 (best_iou, best_poly, best_mask, transform, discriminates)。
    discriminates = identity 是否明顯勝過其他候選(次高 + 0.1 內就算不明顯)。"""
    H, W = ref.shape
    results = {}
    for fu, fv, sw in product([0, 1], [0, 1], [0, 1]):
        u = uv[:, 0].copy(); v = uv[:, 1].copy()
        if sw: u, v = v, u
        if fu: u = 1 - u
        if fv: v = 1 - v
        poly = np.stack([u, v], 1)[:hull]
        mk = hull_mask(poly, H, W)
        results[(fu, fv, sw)] = (iou(mk, ref), poly, mk)
    ident = results[(0, 0, 0)][0]
    others = [v[0] for k, v in results.items() if k != (0, 0, 0)]
    best = max(results.items(), key=lambda kv: kv[1][0])
    io, poly, mk = best[1]
    return io, poly, mk, best[0], (best[0] == (0, 0, 0) and ident - max(others) > 0.1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--psd', default='assets/robot_parts.psd')
    ap.add_argument('--award', default=AWARD_JSON)
    ap.add_argument('--iou-thresh', type=float, default=0.85,
                    help='gen∩art hull IoU 通過門檻')
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix='cmp_award_')
    _psd, manifest, _parts = psd_slice.slice_psd(args.psd, out_dir=tmp)
    pmap = {p['name']: p for p in manifest['parts']}
    ameshes = award_meshes(args.award)

    print("piece | gen(v/hull/tri) | art(v/hull/tri) | gen∩alpha | art∩alpha | gen∩art | calib_ok")
    rows = []
    all_pass = True
    for cn in ROBOT_MESH_PIECES:
        slot = f'機器人拆件/{cn}'
        if cn not in pmap or slot not in ameshes:
            print(f"{cn}: 缺件或缺 Award mesh,跳過"); continue
        pfile = os.path.join(tmp, pmap[cn]['file'])
        img = cv2.imread(pfile, cv2.IMREAD_UNCHANGED)
        alpha = (img[:, :, 3] > 10).astype(np.uint8)
        H, W = alpha.shape; sc = 256 / max(H, W)
        ref = cv2.resize(alpha, (int(W * sc), int(H * sc)), interpolation=cv2.INTER_NEAREST)

        gm = gmv2.generate(pfile)
        guv = np.array(gm['uvs']).reshape(-1, 2)
        gmask = hull_mask(guv[:gm['hull']], *ref.shape)
        g_alpha = iou(gmask, ref)

        am = ameshes[slot]
        auv = np.array(am['uvs']).reshape(-1, 2)
        a_alpha, apoly, amask, xf, disc = calibrate(auv, am['hull'], ref)
        g_art = iou(gmask, amask)

        passed = (g_art >= args.iou_thresh) and disc
        all_pass = all_pass and passed
        print("%-4s | %d/%d/%d | %d/%d/%d | %.3f | %.3f | %.3f | %s%s" % (
            cn, len(guv), gm['hull'], len(gm['triangles']) // 3,
            len(auv), am['hull'], len(am['triangles']) // 3,
            g_alpha, a_alpha, g_art, 'yes' if disc else 'NO',
            '' if passed else '  <-- FAIL'))
        rows.append(dict(piece=cn, gen_v=len(guv), art_v=len(auv),
                         gen_alpha=g_alpha, art_alpha=a_alpha, gen_art=g_art,
                         calib_ok=disc, passed=passed))

    print("\nOVERALL:", "PASS" if all_pass else "FAIL",
          "— 生成 mesh 輪廓對照真實藝術家 mesh(gen∩art IoU >= %.2f 且座標校準自證)" % args.iou_thresh)
    return 0 if all_pass else 1


if __name__ == '__main__':
    sys.exit(main())
