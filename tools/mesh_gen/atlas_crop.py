#!/usr/bin/env python3
"""解析 Spine/libgdx .atlas 並裁出指定 region(處理 rotate 旗標)。

libgdx atlas:xy = region 在 sheet 的左上角(y 從頂部算);size = 原始 w,h;
rotate:true 表示在 sheet 中順時針旋轉 90° 存放(占用 h×w),裁出後需轉回。
"""
import re
import cv2
import numpy as np


def parse_atlas(path):
    regions = {}
    cur = None
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        if not line.startswith(" ") and ":" not in line.split(" ")[0]:
            # region name line (no leading space, not a key:value)
            if not line.startswith(" ") and ":" not in line:
                cur = line.strip()
                regions[cur] = {}
                continue
        if cur and ":" in line:
            k, v = line.strip().split(":", 1)
            regions[cur][k.strip()] = v.strip()
    return regions


def crop_region(sheet, region):
    x, y = [int(t) for t in region["xy"].split(",")]
    w, h = [int(t) for t in region["size"].split(",")]
    rot = region.get("rotate", "false") == "true"
    if rot:
        sub = sheet[y:y + w, x:x + h]            # 旋轉存放:占用 h(寬)×w(高)
        sub = cv2.rotate(sub, cv2.ROTATE_90_COUNTERCLOCKWISE)
    else:
        sub = sheet[y:y + h, x:x + w]
    return sub


def extract(atlas_path, sheet_path, name):
    regions = parse_atlas(atlas_path)
    if name not in regions:
        raise SystemExit(f"region 不存在: {name}; 可用: {list(regions)[:8]}...")
    sheet = cv2.imread(sheet_path, cv2.IMREAD_UNCHANGED)
    return crop_region(sheet, regions[name])


if __name__ == "__main__":
    import sys
    atlas, sheet, name = sys.argv[1], sys.argv[2], sys.argv[3]
    out = sys.argv[4] if len(sys.argv) > 4 else "region.png"
    sub = extract(atlas, sheet, name)
    cv2.imwrite(out, sub)
    print(f"{name}: {sub.shape[1]}x{sub.shape[0]} → {out}")
