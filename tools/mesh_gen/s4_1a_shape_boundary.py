#!/usr/bin/env python3
"""S4 補圖候選 10 — 光暈材質 1a 邊界再校準(見 STATE_S4.md 候選 10)。

背景:候選 1(`real_occlusion_eval.py`)發現「光暈(平滑漸層)CPU 補得動」這個候選 0 的
結論,是用小面積(12%)、圓形合成洞校準出來的;換成真實遮擋形狀後,面積更大的
`光暈←身體`(35.8%)反而 1a pass,面積較小的 `光暈←右手`(20.5%)/`光暈←左手`(16.8%)
卻 1a fail(`seam_grad_diff` 超標)——**非單調,代表洞面積不是決定因素,懷疑是洞的形狀
(狹長/不規則程度)在起作用**。

本檔:用 `punch_hole(shape="ellipse")`(新增,獨立控制面積與長寬比)在光暈上做參數掃描,
量化「形狀狹長度」(`mask_irregularity` = 輪廓周長/√面積,圓形理論最小值 2√π≈3.545)
與 `seam_grad_diff` 的關係,並用**同一把尺**量真實遮擋洞的狹長度,檢查是否能用一條
「狹長度門檻」解釋候選 1 觀察到的非單調 pass/fail。
"""
import argparse, json, os
import numpy as np
import cv2
from scipy import ndimage
from psd_tools import PSDImage

from psd_slice import leaf_layers
from inpaint_eval import punch_hole, run_with_mask
from real_occlusion_eval import layer_full_canvas, real_occlusion_mask, classify_mode

CANDIDATE_METHODS = ("nearest", "cv2_telea", "cv2_ns")


def mask_irregularity(mask):
    """輪廓周長(cv2.arcLength)/ sqrt(面積) —— 跟面積分開的獨立形狀變數。
    圓形理論最小值 = 2*sqrt(pi) ≈ 3.545;越狹長/邊界越崎嶇,值越大。"""
    m = mask.astype(np.uint8) * 255
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    perim = sum(cv2.arcLength(c, True) for c in contours)
    area = float(mask.sum())
    if area <= 0:
        return None
    return perim / np.sqrt(area)


def _rows_from_entry(entry, mask, extra):
    irregularity = mask_irregularity(mask)
    rows = []
    for name in CANDIDATE_METHODS:
        s = entry["methods"][name]
        rows.append({**extra, "method": name, "hole_px": entry["hole_px"],
                     "irregularity": round(irregularity, 3) if irregularity else None,
                     "seam_grad_diff": s["seam_grad_diff"], "ssim": s["ssim"],
                     "premult_mae": s["premult_mae"], "pass_1a": s["pass"]})
    return rows


def _fixed_center(gt):
    """洞心固定在內容的最大 margin 點(distance-transform argmax)——這是唯一能讓
    aspect 掃到夠寬範圍而不撞邊界 margin 檢查的位置,同時**固定位置**讓 aspect/frac
    的效應不會被『同一個 seed 在不同候選池選到不同位置』混進來(見 punch_hole 的
    `center` 參數說明)。"""
    content = gt[..., 3] > 8
    dist = ndimage.distance_transform_edt(content)
    return tuple(int(v) for v in np.unravel_index(np.argmax(dist), dist.shape))


def sweep_synthetic(gt, out_dir=None):
    """固定洞心,只變化 frac(面積)與 aspect(狹長度)/angle(朝向)—— 隔離『形狀』
    與『位置』兩個變數,才能單獨檢驗『狹長度是否決定 seam_grad_diff』這個假設。
    aspect/frac 網格受限於該固定點的實際 margin(見 STATE_S4.md 候選 10 量測:
    該點 margin=169px,margin 檢查用半長軸,較大 aspect×frac 組合會超出,直接
    skip 而非硬湊。"""
    center = _fixed_center(gt)
    rows = []
    for frac in (0.06, 0.08, 0.10, 0.12):
        for aspect in (1.0, 1.5, 2.0, 2.5, 3.0):
            try:
                _, mask = punch_hole(gt, mode="interior", frac=frac, seed=0,
                                      shape="ellipse", aspect=aspect, angle=0.0, center=center)
            except ValueError as e:
                rows.append({"frac": frac, "aspect": aspect, "angle": 0.0, "skipped": True,
                             "reason": str(e)})
                continue
            entry = run_with_mask(gt, mask, "interior", f"halo_synth_f{frac}_a{aspect}", out_dir)
            rows += _rows_from_entry(entry, mask, {"frac": frac, "aspect": aspect, "angle": 0.0})
    # 朝向子掃描(固定 frac/aspect,只轉角度):同一個狹長度數值,朝向不同(對到光暈
    # 放射梯度的角度不同)是否也會讓 seam_grad_diff 大幅變動——若會,代表『狹長度』
    # 這把尺本身不足以完全預測,材質內部結構(這裡是放射梯度)的朝向也是變數。
    frac, aspect = 0.08, 2.0
    for angle in (0.0, np.pi / 4, np.pi / 2, 3 * np.pi / 4):
        try:
            _, mask = punch_hole(gt, mode="interior", frac=frac, seed=0,
                                  shape="ellipse", aspect=aspect, angle=angle, center=center)
        except ValueError as e:
            rows.append({"frac": frac, "aspect": aspect, "angle": round(angle, 3),
                         "skipped": True, "reason": str(e)})
            continue
        entry = run_with_mask(gt, mask, "interior", f"halo_synth_angle_{angle:.3f}", out_dir)
        rows += _rows_from_entry(entry, mask, {"frac": frac, "aspect": aspect,
                                                "angle": round(angle, 3)})
    return rows


def real_occlusion_rows(psd_path, out_dir=None):
    psd = PSDImage.open(psd_path)
    layers = {l.name: l for l in leaf_layers(psd)}
    canvases = {name: layer_full_canvas(psd, l) for name, l in layers.items()}
    gt = canvases["光暈"]
    content = gt[..., 3] > 8
    rows = []
    dirs = {}
    for occluder in ("身體", "右手", "左手"):
        mask = real_occlusion_mask(gt, canvases[occluder])
        mode, touch_frac = classify_mode(content, mask)
        entry = run_with_mask(gt, mask, mode, f"光暈_occby_{occluder}", out_dir)
        area_frac = round(int(mask.sum()) / max(1, int(content.sum())), 4)
        rows += _rows_from_entry(entry, mask, {"case": f"光暈←{occluder}", "mode": mode,
                                                "area_frac": area_frac})
        ys, xs = np.where(mask)
        dirs[occluder] = (float(ys.mean()), float(xs.mean()))
    return rows, dirs


def sweep_position(gt, occluder_centroids, out_dir=None):
    """候選 10 延伸實驗:形狀掃描(見上)顯示同一固定位置下,狹長度在可行範圍內幾乎不影響
    seam_grad_diff(接近 0)——這推翻了『洞形狀狹長度本身決定 1a 邊界』的假設。剩下唯一
    的變數是『位置』:真實遮擋洞不像本檔的固定點掃描一樣落在光暈輻射梯度的對稱核心,
    而是落在核心某個方向的偏移處。這裡固定形狀(圓形、frac=0.08,margin 掃描已驗證此
    尺寸在下列位置皆可行),沿著『核心→真實遮擋洞質心』的方向線取樣多個距離,量測
    (a) gt 材質本身在該處的局部梯度強度(不靠 recon,是材質固有屬性)(b) 實際
    seam_grad_diff,檢驗『洞是否跨過核心陡峭區』是否比『洞多狹長』更能預測 1a 邊界。"""
    content = gt[..., 3] > 8
    dist = ndimage.distance_transform_edt(content)
    center = np.array(_fixed_center(gt), dtype=np.float64)
    frac = 0.08
    area = float(content.sum())
    r = max(3, int(np.sqrt(area * frac / np.pi)))

    def local_grad_mag(cy, cx, width=3):
        yy, xx = np.mgrid[0:gt.shape[0], 0:gt.shape[1]]
        ring = ((yy - cy) ** 2 + (xx - cx) ** 2 <= (r + width) ** 2) & \
               ((yy - cy) ** 2 + (xx - cx) ** 2 >= (r - width) ** 2) & content
        premult = gt[..., :3] * (gt[..., 3:4] / 255.0)
        gray = premult.mean(axis=2)
        gx = ndimage.sobel(gray, axis=1)
        gy = ndimage.sobel(gray, axis=0)
        gmag = np.sqrt(gx ** 2 + gy ** 2)
        return float(gmag[ring].mean()) if ring.sum() else None

    rows = []
    for occ_name, (oy, ox) in occluder_centroids.items():
        direction = np.array([oy, ox]) - center
        norm = np.linalg.norm(direction)
        if norm < 1:
            continue
        unit = direction / norm
        for t_frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            t = t_frac * norm
            cy, cx = center + unit * t
            cy, cx = int(round(cy)), int(round(cx))
            if not (0 <= cy < gt.shape[0] and 0 <= cx < gt.shape[1]):
                continue
            margin = dist[cy, cx] if content[cy, cx] else 0.0
            if margin < r * 1.15:
                rows.append({"toward": occ_name, "t_frac": t_frac, "skipped": True,
                             "reason": f"margin {margin:.1f}px < required {r * 1.15:.1f}px"})
                continue
            # circle 分支(既有程式碼路徑)不支援指定 center,直接手刻同尺寸圓形 mask
            # (半徑 r 與 punch_hole 用同一條公式:sqrt(面積*frac/pi))
            yy, xx = np.mgrid[0:gt.shape[0], 0:gt.shape[1]]
            mask = (((yy - cy) ** 2 + (xx - cx) ** 2) <= r * r) & content
            entry = run_with_mask(gt, mask, "interior", f"halo_pos_{occ_name}_{t_frac}", out_dir)
            grad = local_grad_mag(cy, cx)
            rows += [{**row, "toward": occ_name, "t_frac": t_frac, "local_grad_mag": round(grad, 3)
                     if grad else None} for row in _rows_from_entry(entry, mask, {})]
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()

    psd = PSDImage.open(a.psd)
    layers = {l.name: l for l in leaf_layers(psd)}
    canvases = {name: layer_full_canvas(psd, l) for name, l in layers.items()}
    gt = canvases["光暈"]

    real_rows, occ_dirs = real_occlusion_rows(a.psd, a.out)
    report = {
        "synthetic_shape": sweep_synthetic(gt, a.out),
        "synthetic_position": sweep_position(gt, occ_dirs, a.out),
        "real_occlusion": real_rows,
    }
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        json.dump(report, open(os.path.join(a.out, "shape_boundary_report.json"), "w"),
                  ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
