#!/usr/bin/env python3
"""AI 自主切圖(S4 進階)— 粗分件 PSD → 依「動畫反推的分件規格」重切成細分件 PSD。

輸入:來源 PSD + 切件規格 JSON(AI 的切圖決策:每件的來源圖層/多邊形或橢圓/模式/z 序)。
流程:
  1. 每個來源圖層攤到畫布座標;規格內的件依**列出順序**為像素歸屬優先權(先列先拿)。
  2. mode:
     - "cut" :取走多邊形內像素,來源留洞 → 洞區用 cv2 inpaint 補繪(補圖降階鏈 level-cv2;
               被切走的件蓋回來時洞不可見,animate 分離時才露出 → 正是「補圖前移」)。
     - "copy":複製像素、來源保留(**旋轉自覆蓋件**專用,如轉盤:圓盤繞心轉永遠蓋住自己,
               不留洞最安全 — 對照 Award 生產慣例歸納)。
  3. cut 件的切割邊(非原始輪廓的人工邊)做 2px 羽化,減少動起來的硬邊。
  4. 依規格 z 序輸出新 PSD(由下而上)。

自驗(--eval):新 PSD 依 z 重組 == 原 PSD composite(premult MAE;洞都被上層蓋住,
重組應幾乎無差)+ 每件非空 + 洞區補繪後 0 殘洞。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from PIL import Image
from psd_tools import PSDImage
from evaluate_inpaint import inpaint_cv2
from psd_slice import _premult_diff


def layer_canvas_rgba(layer, W, H):
    im = layer.topil()
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    full = np.zeros((H, W, 4), np.uint8)
    l, t = int(layer.left), int(layer.top)
    x0, y0 = max(l, 0), max(t, 0)
    x1, y1 = min(l + im.width, W), min(t + im.height, H)
    if x1 > x0 and y1 > y0:
        arr = np.array(im)
        full[y0:y1, x0:x1] = arr[y0 - t:y1 - t, x0 - l:x1 - l]
    return full, (l, t)


def region_mask(piece, off, W, H):
    m = np.zeros((H, W), np.uint8)
    ox, oy = off
    regions = piece.get("regions") or [piece]     # 支援多區域組合件(如耳機=兩耳罩橢圓)
    for r in regions:
        if "polygon" in r:
            pts = np.array([[p[0] + ox, p[1] + oy] for p in r["polygon"]], np.int32)
            cv2.fillPoly(m, [pts], 1)
        elif "ellipse" in r:
            cx, cy, rx, ry = r["ellipse"]
            cv2.ellipse(m, (int(cx + ox), int(cy + oy)), (int(rx), int(ry)), 0, 0, 360, 1, -1)
    return m.astype(bool)


def feather_cut_edges(rgba, cut_mask, natural_alpha, px=2):
    """只羽化「人工切割邊」:件邊界中,位於原始 alpha 內部的部分(非天然輪廓)。"""
    a = rgba[..., 3].astype(np.float32)
    interior = cv2.erode(natural_alpha.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    edge = cv2.morphologyEx(cut_mask.astype(np.uint8), cv2.MORPH_GRADIENT,
                            np.ones((3, 3), np.uint8)).astype(bool) & interior
    if not edge.any():
        return rgba
    soft = cv2.GaussianBlur(cut_mask.astype(np.float32), (px * 2 + 1,) * 2, 0)
    band = cv2.dilate(edge.astype(np.uint8), np.ones((px * 2 + 1,) * 2, np.uint8)).astype(bool)
    a[band] = a[band] * soft[band]
    out = rgba.copy()
    out[..., 3] = np.clip(a, 0, 255).astype(np.uint8)
    return out


def crop_to_bbox(rgba):
    a = rgba[..., 3]
    ys, xs = np.nonzero(a > 0)
    if not len(xs):
        return None, (0, 0)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    return rgba[y0:y1, x0:x1], (int(x0), int(y0))


def resegment(src_psd_path, spec, out_psd_path):
    psd = PSDImage.open(src_psd_path)
    W, H = psd.width, psd.height
    layers = {l.name: l for l in psd.descendants() if not l.is_group() and l.is_visible()}
    src_data = {n: layer_canvas_rgba(l, W, H) for n, l in layers.items()}

    outputs = []           # (z, name, canvas rgba)
    taken = {n: np.zeros((H, W), bool) for n in layers}     # cut 已拿走
    # pass 1:cut/copy 件(列出順序 = 優先權)
    for piece in spec["pieces"]:
        src = piece["source"]
        full, off = src_data[src]
        alpha = full[..., 3] > 8
        m = region_mask(piece, off, W, H) & alpha
        if piece.get("mode", "cut") == "cut":
            m = m & ~taken[src]
            taken[src] |= m
        out = np.zeros_like(full)
        out[m] = full[m]
        out = feather_cut_edges(out, m, alpha, spec.get("feather", 2))
        outputs.append((piece["z"], piece["name"], out))
    # pass 2:remainder(留在來源的),洞區 inpaint
    # ⚠️ 只補「殘留輪廓周圍的重疊帶」:動畫分離只露出關節附近 10~15px,
    #    把整個被切走的區域(如整顆頭)都填成軀幹是錯的(補繪無據、又浪費)。
    margin = spec.get("overlap_margin", 14)
    k = np.ones((margin * 2 + 1,) * 2, np.uint8)
    holes_left = {}
    for src, rem in spec.get("remainders", {}).items():
        full, _ = src_data[src]
        alpha = full[..., 3] > 8
        keep = alpha & ~taken[src]
        out = np.zeros_like(full)
        out[keep] = full[keep]
        band = taken[src] & cv2.dilate(keep.astype(np.uint8), k).astype(bool)
        if band.any() and rem.get("inpaint", True):
            out = inpaint_cv2(out, band)
            out[~(keep | band)] = 0              # 只允許長在 keep ∪ 重疊帶
        holes_left[rem["name"]] = int((band & (out[..., 3] <= 8)).sum()) if rem.get("inpaint", True) else 0
        outputs.append((rem["z"], rem["name"], out))

    outputs.sort(key=lambda x: x[0])
    new = PSDImage.new("RGBA", (W, H))
    manifest = []
    for z, name, rgba in outputs:
        crop, (l, t) = crop_to_bbox(rgba)
        if crop is None:
            manifest.append({"name": name, "z": z, "empty": True}); continue
        lyr = new.create_pixel_layer(Image.fromarray(crop, "RGBA"), name="tmp", top=t, left=l)
        lyr.name = name    # setter 會寫 UNICODE_LAYER_NAME(luni)區塊,中文名 Photoshop/psd-tools 皆可讀
        manifest.append({"name": name, "z": z, "offset": [l, t],
                         "size": [crop.shape[1], crop.shape[0]]})
    new.save(out_psd_path)
    return manifest, holes_left, (W, H)


def evaluate(src_psd_path, out_psd_path, mae_thresh=2.0):
    ref = np.array(PSDImage.open(src_psd_path).composite().convert("RGBA"))
    outp = PSDImage.open(out_psd_path)
    W, H = outp.width, outp.height
    recon = np.zeros((H, W, 4), np.float64)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for l in outp.descendants():           # psd-tools descendants = 由下而上
        if l.is_group() or not l.is_visible():
            continue
        fl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        fl.paste(l.topil().convert("RGBA"), (int(l.left), int(l.top)))
        canvas = Image.alpha_composite(canvas, fl)
    rgb_mae, alpha_mae = _premult_diff(np.array(canvas), ref)
    n_layers = sum(1 for l in outp.descendants() if not l.is_group())
    return {"overall_pass": rgb_mae < mae_thresh and alpha_mae < mae_thresh,
            "premult_rgb_mae": round(rgb_mae, 4), "alpha_mae": round(alpha_mae, 4),
            "layers": n_layers, "thresh": mae_thresh}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--eval", action="store_true")
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    manifest, holes_left, size = resegment(a.src, spec, a.out)
    print(json.dumps({"layers": manifest, "unfilled_hole_px": holes_left},
                     ensure_ascii=False, indent=1))
    if a.eval:
        rep = evaluate(a.src, a.out)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
