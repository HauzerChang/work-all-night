#!/usr/bin/env python3
"""S2 切圖評估器(自我品質閘) — 驗證「atlas 切圖 → 重組」的保真度。

對應 PLAN.md S4 完成條件「切圖重組還原原圖輪廓、0 孤兒像素」的**自評閘**(S2 樞紐)。
真值 = `main_draw.png`(atlas sheet 本身);切圖正確 ⇔ 重組 == 原 sheet。

端到端流程:
  對每個 region:atlas_crop.extract() 取「去旋轉後」子圖 → 依 xy/size/rotate 重組回空白畫布
  → 與原 sheet 在 region 覆蓋處逐像素比對。一次驗證全部 region 的 xy/size/rotate 解析,
  並回頭驗證 `atlas_crop.py` 的 rotate 方向是否正確。

AC(可機讀):
  AC1 解析完整 :過濾 page 行後,N region 全部成功切出非空。
  AC2 重組保真 :每 region 重組回原位 == sheet 對應區(rotate round-trip 正確);
                量化「完全一致 region 數」與「平均像素 MAE」。
  AC3 0 孤兒   :sheet alpha>0 像素被 region 覆蓋率 ≥ thresh(未覆蓋=孤兒)。
  AC4 0 重疊   :被 >1 region 寫入的像素數(atlas packer 不應重疊)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import parse_atlas, extract


def real_regions(atlas_path):
    """過濾掉 atlas page 行(無 xy/size 的條目,如 'main_draw.png')。"""
    regs = parse_atlas(atlas_path)
    return {n: r for n, r in regs.items() if "xy" in r and "size" in r}


def repack(sub, region):
    """把『去旋轉後』子圖轉回 packed 方向,回傳 (packed_img, y, x, ph, pw)。"""
    x, y = [int(t) for t in region["xy"].split(",")]
    rot = region.get("rotate", "false") == "true"
    if rot:
        packed = cv2.rotate(sub, cv2.ROTATE_90_CLOCKWISE)  # extract 用 CCW,這裡逆轉
    else:
        packed = sub
    ph, pw = packed.shape[:2]
    return packed, y, x, ph, pw


def evaluate(atlas_path, png_path, recon_mae_thresh=1.0, orphan_thresh=0.005):
    regs = real_regions(atlas_path)
    sheet = cv2.imread(png_path, cv2.IMREAD_UNCHANGED)
    H, W = sheet.shape[:2]
    C = sheet.shape[2] if sheet.ndim == 3 else 1

    canvas = np.zeros_like(sheet)
    cover = np.zeros((H, W), np.int32)        # 每像素被幾個 region 覆蓋
    parsed_ok = 0
    per_region_exact = 0
    mae_list = []
    failed = []

    for name, r in regs.items():
        try:
            sub = extract(atlas_path, png_path, name)
        except SystemExit:
            failed.append(name); continue
        if sub is None or sub.size == 0:
            failed.append(name); continue
        parsed_ok += 1
        packed, y, x, ph, pw = repack(sub, r)
        if y + ph > H or x + pw > W:
            failed.append(name); continue
        region_sheet = sheet[y:y + ph, x:x + pw]
        # 重組保真:重組塊 vs sheet 對應區
        diff = np.abs(packed.astype(np.int32) - region_sheet.astype(np.int32))
        mae = float(diff.mean())
        mae_list.append(mae)
        if mae < 1e-9:
            per_region_exact += 1
        canvas[y:y + ph, x:x + pw] = packed
        cover[y:y + ph, x:x + pw] += 1

    n = len(regs)
    # AC3 孤兒:sheet 有 alpha 但無 region 覆蓋
    if C == 4:
        sheet_content = sheet[:, :, 3] > 8
    else:
        sheet_content = (cv2.cvtColor(sheet, cv2.COLOR_BGR2GRAY) if sheet.ndim == 3 else sheet) > 8
    covered = cover > 0
    orphan = np.logical_and(sheet_content, ~covered)
    orphan_ratio = float(orphan.sum() / max(int(sheet_content.sum()), 1))
    # AC4 重疊
    overlap_px = int((cover > 1).sum())

    avg_mae = float(np.mean(mae_list)) if mae_list else 1e9
    results = {
        "AC1_parse_complete": {"pass": parsed_ok == n and not failed,
                               "value": f"{parsed_ok}/{n}", "failed": failed},
        "AC2_recon_fidelity": {"pass": avg_mae < recon_mae_thresh,
                               "avg_mae": round(avg_mae, 4),
                               "exact_regions": f"{per_region_exact}/{parsed_ok}",
                               "thresh": recon_mae_thresh},
        "AC3_no_orphan": {"pass": orphan_ratio <= orphan_thresh,
                          "orphan_ratio": round(orphan_ratio, 5), "thresh": orphan_thresh},
        "AC4_no_overlap": {"pass": overlap_px == 0, "overlap_px": overlap_px},
    }
    overall = all(v["pass"] for v in results.values())
    return {"overall_pass": overall, "regions": n, "rotated": sum(
        1 for r in regs.values() if r.get("rotate") == "true"),
        "sheet": [W, H], "criteria": results}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", default="assets/main_draw.atlas")
    ap.add_argument("--png", default="assets/main_draw.png")
    a = ap.parse_args()
    rep = evaluate(a.atlas, a.png)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
