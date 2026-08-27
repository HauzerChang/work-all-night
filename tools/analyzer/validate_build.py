#!/usr/bin/env python3
"""build_spine 產出的 round-trip 驗證閘 —— 由生成的 json+atlas+png 重建 setup pose,
比對原 PSD composite。證明「規格→素材」的幾何/atlas 編碼正確(素材可用、位置對)。

方法(與 build_spine 座標約定一致):
  每 slot 依 z 序,讀 bone(x,y) → 影像中心 (x, H-y);由 atlas 取該件貼圖(此打包 rotate 全 false)
  → 貼到 (中心 - 半尺寸) → alpha-over 疊合 → 與 PSD composite 做 premultiplied MAE + 覆蓋率。

⚠️ 只驗**靜態幾何/貼圖編碼**(mesh 與 region 靜態擺放相同);mesh 的變形能力不在此驗。
"""
import argparse, json, os, sys
import numpy as np
import cv2
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
from atlas_crop import parse_atlas, extract
from psd_slice import slice_psd


def reconstruct(build_dir, W, H):
    sk = json.load(open(os.path.join(build_dir, "skeleton.json")))
    atlas = os.path.join(build_dir, "skeleton.atlas")
    png = os.path.join(build_dir, "skeleton.png")
    regions = parse_atlas(atlas)
    bone = {b["name"]: b for b in sk["bones"]}
    skin = sk["skins"]["default"]
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cover = np.zeros((H, W), np.int32)
    missing = []
    for slot in sk["slots"]:                       # slots 已按繪製順序(z 升序)
        nm = slot["attachment"]
        if nm not in regions:
            missing.append(nm); continue
        b = bone[slot["bone"]]
        bx, by = b.get("x", 0), b.get("y", 0)
        cx, cy = bx, H - by                         # 影像中心
        sub = extract(atlas, png, nm)               # BGRA crop
        sub_rgba = cv2.cvtColor(sub, cv2.COLOR_BGRA2RGBA)
        im = Image.fromarray(sub_rgba)
        w, h = im.size
        tlx, tly = int(round(cx - w / 2.0)), int(round(cy - h / 2.0))
        full = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        full.paste(im, (tlx, tly))
        canvas = Image.alpha_composite(canvas, full)
        a = np.array(im.split()[-1]) > 8
        y0 = max(tly, 0); x0 = max(tlx, 0)
        y1 = min(tly + h, H); x1 = min(tlx + w, W)
        if y1 > y0 and x1 > x0:
            cover[y0:y1, x0:x1] += a[y0 - tly:y1 - tly, x0 - tlx:x1 - tlx].astype(np.int32)
    return sk, canvas, cover, missing


def premult_mae(recon, ref):
    a = np.asarray(recon, np.float64); b = np.asarray(ref, np.float64)
    ap = a[..., :3] * a[..., 3:4] / 255.0
    bp = b[..., :3] * b[..., 3:4] / 255.0
    return float(np.abs(ap - bp).mean()), float(np.abs(a[..., 3] - b[..., 3]).mean())


def validate(psd_path, build_dir, mae_thresh=3.0, orphan_thresh=0.01):
    psd, _, _ = slice_psd(psd_path)
    W, H = psd.width, psd.height
    ref = psd.composite().convert("RGBA").resize((W, H))
    sk, recon, cover, missing = reconstruct(build_dir, W, H)
    rgb_mae, alpha_mae = premult_mae(recon, ref)
    content = np.asarray(ref.split()[-1]) > 8
    orphan = float(np.logical_and(content, cover == 0).sum() / max(int(content.sum()), 1))
    n_parts = len(sk["slots"])
    checks = {
        "AC1_parse_load": {"pass": len(sk["bones"]) >= n_parts + 1 and n_parts > 0,
                           "bones": len(sk["bones"]), "slots": n_parts,
                           "note": "≥ 每件一骨 + root(weighted 件會有額外控制骨)"},
        "AC2_all_attach_resolve": {"pass": len(missing) == 0, "missing": missing},
        "AC3_roundtrip_recon": {"pass": rgb_mae < mae_thresh and alpha_mae < mae_thresh,
                                "premult_rgb_mae": round(rgb_mae, 4),
                                "alpha_mae": round(alpha_mae, 4), "thresh": mae_thresh},
        "AC4_no_orphan": {"pass": orphan <= orphan_thresh,
                          "orphan_ratio": round(orphan, 5), "thresh": orphan_thresh},
    }
    overall = all(c["pass"] for c in checks.values())
    return {"overall_pass": overall, "source": os.path.basename(psd_path),
            "build_dir": build_dir, "criteria": checks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd")
    ap.add_argument("build_dir")
    a = ap.parse_args()
    rep = validate(a.psd, a.build_dir)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
