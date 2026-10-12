#!/usr/bin/env python3
"""候選15 對照圖:production estimate_alpha_taper vs 候選D(estimate_combined)。
挑「候選D 修好的最嚴重案例」與「候選D 新弄壞的案例」各 N 個,每案一列:
  真值 alpha | 挖洞後 | production 估計 | 候選D 估計(皆只在洞內替換,其餘用已知像素)
用法(從 repo 根): python3 tools/mesh_gen/s4_taper_compare_montage.py -o OUT.png [-n 4]
"""
import argparse, os, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from s4_alpha_taper_candidate14 import (load_materials, sweep, estimate_combined, mae_in_mask)
from inpaint_eval import punch_hole, estimate_alpha_taper


def crop_box(mask, pad=24):
    ys, xs = np.nonzero(mask)
    return max(0, ys.min() - pad), ys.max() + pad, max(0, xs.min() - pad), xs.max() + pad


def render(alpha, mask, box, scale=None, tint=None):
    y0, y1, x0, x1 = box
    a = np.clip(alpha[y0:y1, x0:x1], 0, 255).astype(np.uint8)
    rgb = np.stack([a] * 3, -1)
    m = mask[y0:y1, x0:x1]
    if tint:  # 洞邊界標紅線
        from scipy import ndimage
        edge = m & ~ndimage.binary_erosion(m)
        rgb[edge] = (255, 60, 60)
    scale = max(1, round(320 / max(1, x1 - x0)))
    im = Image.fromarray(rgb).resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.NEAREST)
    return im


EN = {"光暈": "halo", "右手": "right_hand", "頭": "head", "身體": "body", "左手": "left_hand", "底": "base",
      "框": "frame", "臉部陰影": "face_shadow", "墨鏡": "sunglasses"}


def en(name):
    for k, v in EN.items():
        name = name.replace(k, v)
    return name


def row(materials, key, old_mae, new_mae, tag):
    mat, mode, shape, frac, aspect, angle, seed = key
    gt = materials[mat]
    holed, mask = punch_hole(gt, mode=mode, frac=frac, seed=seed, shape=shape,
                             aspect=aspect, angle=angle if angle is not None else None)
    ah = holed[..., 3].astype(np.float64)
    box = crop_box(mask)
    outs = []
    for est_fn in (lambda a, m: estimate_alpha_taper(a, m, method='median'), estimate_alpha_taper):
        est = est_fn(holed[..., 3], mask)
        a = ah.copy(); a[mask] = est[mask]
        outs.append(a)
    gta = gt[..., 3].astype(np.float64)
    ims = [render(gta, mask, box, tint=True), render(ah, mask, box, tint=True),
           render(outs[0], mask, box, tint=True), render(outs[1], mask, box, tint=True)]
    labels = ["ground truth (red=hole)", "holed", f"old(median) MAE={old_mae:.1f}", f"new(default) MAE={new_mae:.1f}"]
    w = sum(i.width for i in ims) + 10 * 5
    h = max(i.height for i in ims) + 44
    canvas = Image.new("RGB", (w, h), (24, 24, 28))
    d = ImageDraw.Draw(canvas)
    d.text((10, 4), f"[{tag}] {en(mat)} {mode} {shape} frac={frac} seed={seed}", fill=(255, 220, 120))
    x = 10
    for im, lb in zip(ims, labels):
        d.text((x, 22), lb, fill=(200, 210, 230))
        canvas.paste(im, (x, 40)); x += im.width + 10
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("-n", type=int, default=4)
    a = ap.parse_args()
    materials = load_materials()
    old = sweep(materials, lambda a, m: estimate_alpha_taper(a, m, method='median'))
    new = sweep(materials, estimate_alpha_taper)
    def uniq(keys):
        seen, out = set(), []
        for k in keys:
            t = (k[0], k[1], k[2])
            if t not in seen:
                seen.add(t); out.append(k)
        return out[:a.n]
    fixed = uniq(sorted([k for k in old if old[k] > 20 and new[k] <= 20], key=lambda k: -old[k]))
    broken = uniq(sorted([k for k in old if old[k] <= 20 and new[k] > 20], key=lambda k: -new[k]))
    print(f"n={len(old)} fixed={sum(1 for k in old if old[k]>20 and new[k]<=20)} "
          f"broken={sum(1 for k in old if old[k]<=20 and new[k]>20)}")
    rows = [row(materials, k, old[k], new[k], "FIXED by D") for k in fixed] + \
           [row(materials, k, old[k], new[k], "NEWLY BROKEN by D") for k in broken]
    W = max(r.width for r in rows); H = sum(r.height for r in rows)
    sheet = Image.new("RGB", (W, H), (24, 24, 28)); y = 0
    for r in rows:
        sheet.paste(r, (0, y)); y += r.height
    sheet.save(a.out); print("saved", a.out, sheet.size)


if __name__ == "__main__":
    main()
