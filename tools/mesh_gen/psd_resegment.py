#!/usr/bin/env python3
"""AI 自主切圖(S4 進階)— 粗分件 PSD → 依「動畫反推的分件規格」重切成細分件 PSD。

輸入:來源 PSD + 切件規格 JSON(AI 的切圖決策:每件的來源圖層/多邊形或橢圓/模式/z 序)。

**v2 架構(W2,2026-07-03 美術版交叉比對後重寫)— 重疊切圖,廢互斥**:
  美術真值揭示:件=**完整物件**、件間大量重疊、被蓋處畫全(身體 96.5% 被蓋仍畫全、
  眼白 100% 藏在鏡片後仍完整)。互斥像素歸屬是架構級錯誤(頭被掏空 43%)。
  1. 每件宣告自己的**完整物件範圍 region**(polygon/ellipse/regions);region 可互相重疊。
  2. 可見像素歸屬:同來源圖層內,像素上「z 最高的宣告者」拿到**真實像素**
     (畫面上看到的就是最前面那件的顏色)。
  3. 其他宣告者在該處拿**補全像素**(cv2 inpaint「畫全」被蓋部分 — 補圖前移;
     大面積補全品質受 cv2 級上限,屬補圖降階鏈課題)。
  4. mode "copy":複製不參與歸屬(旋轉自覆蓋件:轉盤)。catch_all 件收該來源未被宣告的像素。
  5. 切割邊(非天然輪廓)2px 羽化;依 z 序輸出 PSD。

自驗(--eval):新 PSD 依 z 重組 == 原 PSD composite(premult MAE;補全區都被上層蓋住,
重組應幾乎無差)+ 每件非空。品質評分用 evaluate_reseg.py(對美術真值)。
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


def edge_snap(mask, rgba, natural_alpha, band=8):
    """W3:把宣告的 region 邊界吸附到影像的實際色界(GrabCut),位移上限 band px。
    人工切線(多邊形目測 ±4~8px)→ 沿真實部件輪廓;天然 alpha 輪廓不受影響
    (吸附結果與原 mask 都會被 natural_alpha 交集)。"""
    m = mask.astype(np.uint8)
    k = np.ones((band * 2 + 1,) * 2, np.uint8)
    inner = cv2.erode(m, k).astype(bool)
    outer = cv2.dilate(m, k).astype(bool)
    if not inner.any():          # 件太小,band 內縮成空 → 不吸附
        return mask
    gc = np.full(mask.shape, cv2.GC_BGD, np.uint8)
    gc[outer] = cv2.GC_PR_BGD
    gc[mask] = cv2.GC_PR_FGD
    gc[inner] = cv2.GC_FGD
    pm = np.clip(rgba[..., :3].astype(np.float64) * rgba[..., 3:4] / 255.0, 0, 255).astype(np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(pm, gc, None, bgd, fgd, 3, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        return mask
    snapped = (gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)
    # 位移上限:不出 outer、不小於 inner(防 GrabCut 跑飛/吃光)
    snapped = (snapped & outer) | inner
    return snapped & natural_alpha


def reassign_strays(owner, alpha, order_sorted, masks, max_px=400):
    """catch_all 之外的散件處理:小的未宣告連通塊 → 歸給邊界接觸最多的鄰件
    (帽頂小絮落到軀幹的視覺 bug 修正)。大塊仍回 catch_all(警告)。"""
    unclaimed = (owner == -1) & alpha
    if not unclaimed.any():
        return owner
    n, lab = cv2.connectedComponents(unclaimed.astype(np.uint8))
    k = np.ones((11, 11), np.uint8)
    for c in range(1, n):
        comp = lab == c
        if comp.sum() > max_px:
            continue
        ring = cv2.dilate(comp.astype(np.uint8), k).astype(bool) & ~comp
        best, best_n = -1, 0
        for i, p in enumerate(order_sorted):
            t = (ring & masks[p["name"]]).sum()
            if t > best_n:
                best, best_n = i, t
        if best >= 0:
            owner[comp] = best
    return owner


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
    holes_left = {}
    by_src = {}
    for piece in spec["pieces"]:
        by_src.setdefault(piece["source"], []).append(piece)

    for src, pieces in by_src.items():
        full, off = src_data[src]
        alpha = full[..., 3] > 8
        owners = [p for p in pieces if p.get("mode", "object") != "copy"]
        masks = {p["name"]: region_mask(p, off, W, H) & alpha for p in pieces}
        # W3 邊緣吸附:宣告邊界 → 沿實際色界(catch_all 全幅件不吸)
        if spec.get("edge_snap", False):
            for p in pieces:
                if p.get("catch_all") or p.get("snap", True) is False:
                    continue
                masks[p["name"]] = edge_snap(masks[p["name"]], full, alpha,
                                             band=spec.get("snap_band", 8))
        # 可見像素歸屬:z 最高的宣告者(owner map;-1=未宣告)
        owner = np.full((H, W), -1, np.int32)
        order_sorted = sorted(owners, key=lambda p: p["z"])
        for idx, p in enumerate(order_sorted):
            owner[masks[p["name"]]] = idx
        # 小散件 → 歸邊界接觸最多的鄰件;剩餘 → catch_all
        owner = reassign_strays(owner, alpha, order_sorted, masks)
        for p in order_sorted:
            if p.get("catch_all"):
                i = order_sorted.index(p)
                owner[(owner == -1) & alpha] = i
        unclaimed = int(((owner == -1) & alpha).sum())
        if unclaimed:
            holes_left[f"_unclaimed[{src}]"] = unclaimed
        for i, p in enumerate(order_sorted):
            m = masks[p["name"]]
            visible = m & (owner == i)
            hidden = m & (owner != i) & alpha        # 被更高 z 件蓋住 → 補全(畫全)
            out = np.zeros_like(full)
            out[visible] = full[visible]
            if hidden.any() and p.get("complete", True):
                out = inpaint_cv2(out, hidden)
                out[~(visible | hidden)] = 0
                holes_left[p["name"]] = int((hidden & (out[..., 3] <= 8)).sum())
            out = feather_cut_edges(out, m, alpha, spec.get("feather", 2))
            outputs.append((p["z"], p["name"], out))
        for p in pieces:                              # copy 件:複製不歸屬
            if p.get("mode") == "copy":
                m = masks[p["name"]]
                out = np.zeros_like(full)
                out[m] = full[m]
                out = feather_cut_edges(out, m, alpha, spec.get("feather", 2))
                outputs.append((p["z"], p["name"], out))

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
