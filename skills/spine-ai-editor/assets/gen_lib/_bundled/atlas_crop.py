#!/usr/bin/env python3
"""解析 Spine/libgdx .atlas 並裁出指定 region(處理多頁 page + rotate 旗標)。

libgdx atlas:xy = region 在 sheet 的左上角(y 從頂部算);size = 原始 w,h;
rotate:true 表示在 sheet 中旋轉 90° 存放(占用 h×w)。

⚠️ derotate 方向(2026-06-26 以真實 PSD 外部真值校正):還原旋轉件要用 **CW**
   (`ROTATE_90_CLOCKWISE`)。先前用 CCW 是錯的,但被 evaluate_slicing 的 extract↔repack
   round-trip 自洽掩蓋(方向一起反仍 MAE=0)。Award 機器人件對照 PSD 切件:CCW IoU 0.4–0.57、
   CW IoU 0.92–0.98 → 確認 CW。詳見 knowledge/s4-psd-to-spine-real.md。

多頁:每個 region 記錄所屬 page;extract 自動從 atlas 同目錄找該 page 的 png。
"""
import os
import cv2
import numpy as np


def parse_atlas(path):
    """回傳 {region_name: {attrs..., 'page': page_png}}。正確跳過 page 屬性行(不誤收 page 為 region)。"""
    regions = {}
    cur_page = None
    cur_reg = None
    lines = open(path, encoding="utf-8").read().splitlines()
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        if ln.strip() == "":
            cur_reg = None
            i += 1
            continue
        # page 行(頂格、以 .png 結尾)
        if not ln.startswith(" ") and ln.rstrip().endswith(".png"):
            cur_page = ln.strip()
            cur_reg = None
            i += 1
            # 消化 page 屬性(連續含 ':' 的行:size/format/filter/repeat),停在第一個 region 行
            while i < n and lines[i].strip() != "" and ":" in lines[i]:
                i += 1
            continue
        # region 行(頂格、不含 ':')
        if not ln.startswith(" ") and ":" not in ln:
            cur_reg = ln.strip()
            regions[cur_reg] = {"page": cur_page}
            i += 1
            continue
        # region 屬性
        if cur_reg is not None and ":" in ln:
            k, v = ln.strip().split(":", 1)
            regions[cur_reg][k.strip()] = v.strip()
        i += 1
    return regions


def crop_region(sheet, region):
    x, y = [int(t) for t in region["xy"].split(",")]
    w, h = [int(t) for t in region["size"].split(",")]
    rot = region.get("rotate", "false") in ("true", "90")
    if rot:
        sub = sheet[y:y + w, x:x + h]                 # 旋轉存放:占用 h(寬)×w(高)
        sub = cv2.rotate(sub, cv2.ROTATE_90_CLOCKWISE)  # CW 還原(經 PSD 真值校正)
    else:
        sub = sheet[y:y + h, x:x + w]
    return sub


def extract(atlas_path, sheet_path, name):
    """裁出 region。多頁時自動用 region 所屬 page(atlas 同目錄);
    單頁或找不到 page 檔時退回傳入的 sheet_path(向後相容)。"""
    regions = parse_atlas(atlas_path)
    if name not in regions:
        raise SystemExit(f"region 不存在: {name}; 可用: {list(regions)[:8]}...")
    r = regions[name]
    page = r.get("page")
    cand = os.path.join(os.path.dirname(atlas_path), page) if page else None
    sheet_file = cand if (cand and os.path.exists(cand)) else sheet_path
    sheet = cv2.imread(sheet_file, cv2.IMREAD_UNCHANGED)
    if sheet is None:
        raise SystemExit(f"無法讀取貼圖頁: {sheet_file}")
    return crop_region(sheet, r)


if __name__ == "__main__":
    import sys
    atlas, sheet, name = sys.argv[1], sys.argv[2], sys.argv[3]
    out = sys.argv[4] if len(sys.argv) > 4 else "region.png"
    sub = extract(atlas, sheet, name)
    cv2.imwrite(out, sub)
    print(f"{name}: {sub.shape[1]}x{sub.shape[0]} → {out}")
