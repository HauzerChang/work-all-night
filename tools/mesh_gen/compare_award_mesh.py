#!/usr/bin/env python3
"""端到端驗收:PSD 切件 → S3 generate_mesh_v2 → 對照 Award 真實生產 mesh。

有真值可比的最高優先驗收(STATE 候選 1):用 robot_parts.psd 的 mesh 件
(光暈 / 身體 / 左手,在 Award 中皆為 mesh),跑生成器,與 Award 真實 mesh
做「同一張 alpha、同一 fill 方式」的覆蓋 IoU 對比 + 頂點數對比。

真實 mesh 覆蓋以 uvs 還原 setup 貼圖佈局(uvs 為 region 局部 0..1,填三角)。
Award mesh 為 weighted(骨骼驅動、無 deform timeline)→ 這裡只比「靜態覆蓋保真」
與「頂點經濟性」,不比 deform(這些件本就不逐頂點變形)。

用法:
  python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot
  python3 tools/mesh_gen/compare_award_mesh.py --slices /tmp/robot --award assets/Award.json
"""
import os, sys, json, argparse
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_mesh_v2 import generate as gen_v2

# PSD 切件檔名 -> Award slot(來自 knowledge/s4-psd-to-spine-real.md 逐件對應)
PIECES = {
    "00_光暈.png": "機器人拆件/光暈",
    "03_身體.png": "機器人拆件/身體",
    "04_左手.png": "機器人拆件/左手",
}


def att_of(award):
    sk = award['skins']
    return sk[0]['attachments'] if isinstance(sk, list) else sk['default']


def load_alpha(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    a = img[:, :, 3] if (img.ndim == 3 and img.shape[2] == 4) else \
        (cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img)
    return (a > 8).astype(np.uint8)


def fill_mesh(pts, tris, H, W):
    m = np.zeros((H, W), np.uint8)
    for t in tris.reshape(-1, 3):
        cv2.fillConvexPoly(m, np.round(pts[t]).astype(np.int32), 1)
    return m


def iou(a, b):
    uni = int(np.logical_or(a, b).sum())
    return int(np.logical_and(a, b).sum()) / uni if uni else 0.0


def recall(mesh_mask, alpha):
    return int(np.logical_and(mesh_mask, alpha).sum()) / max(int(alpha.sum()), 1)


def real_mask(att, slot, H, W, flip):
    a = list(att[slot].values())[0]
    uvs = np.array(a['uvs']).reshape(-1, 2)
    tris = np.array(a['triangles'], np.int32)
    px = uvs[:, 0] * W
    py = (1 - uvs[:, 1]) * H if flip else uvs[:, 1] * H
    return fill_mesh(np.stack([px, py], 1), tris, H, W), len(uvs)


def gen_mask(mesh, H, W):
    v = mesh['vertices']
    pts = np.array([(v[i] + W / 2.0, H / 2.0 - v[i + 1]) for i in range(0, len(v), 2)])
    return fill_mesh(pts, np.array(mesh['triangles'], np.int32), H, W), len(mesh['uvs']) // 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slices", default="/tmp/robot")
    ap.add_argument("--award", default="assets/Award.json")
    # 光暈這類軟邊發光件:多邊形 mesh 無法達 0.95 靜態 IoU(真值也不能)。
    # 判定改用「≥ 藝術家真實 mesh IoU − margin」。
    ap.add_argument("--margin", type=float, default=0.03)
    a = ap.parse_args()
    att = att_of(json.load(open(a.award)))

    print(f"{'件':<6}{'W×H':<11}{'real_v':>7}{'real_IoU':>10}{'real_rec':>9}"
          f"  {'gen_mode':<12}{'gen_v':>6}{'gen_IoU':>9}{'gen_rec':>9}{'verdict':>9}")
    print("-" * 100)
    rows = []
    all_pass = True
    for fn, slot in PIECES.items():
        alpha = load_alpha(os.path.join(a.slices, fn))
        H, W = alpha.shape
        # 校準貼圖 v 慣例:選 flip 讓真實 mesh IoU 最大(差距懸殊即明確)
        cand = []
        for flip in (True, False):
            rm, rv = real_mask(att, slot, H, W, flip)
            cand.append((iou(rm, alpha), rm, rv, flip))
        real_iou, rm, real_v, flip = max(cand, key=lambda t: t[0])
        real_rec = recall(rm, alpha)
        mesh = gen_v2(os.path.join(a.slices, fn))
        gm, gen_v = gen_mask(mesh, H, W)
        g_iou, g_rec = iou(gm, alpha), recall(gm, alpha)
        ok = g_iou >= real_iou - a.margin
        all_pass &= ok
        name = slot.split('/')[-1]
        print(f"{name:<6}{f'{W}x{H}':<11}{real_v:>7}{real_iou:>10.3f}{real_rec:>9.3f}"
              f"  {mesh.get('_mode'):<12}{gen_v:>6}{g_iou:>9.3f}{g_rec:>9.3f}"
              f"{'PASS' if ok else 'FAIL':>9}")
        rows.append(dict(name=name, W=W, H=H, real_v=real_v, real_iou=round(real_iou, 4),
                         real_rec=round(real_rec, 4), gen_mode=mesh.get('_mode'),
                         gen_v=gen_v, gen_iou=round(g_iou, 4), gen_rec=round(g_rec, 4),
                         flip=flip, verdict="PASS" if ok else "FAIL"))
    print("-" * 100)
    print(f"overall: {'PASS' if all_pass else 'FAIL'}  "
          f"(判準:生成 IoU ≥ 藝術家真值 IoU − {a.margin};頂點數見表)")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
