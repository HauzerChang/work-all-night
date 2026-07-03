#!/usr/bin/env python3
"""S4 下游:切件 → Spine/libgdx .atlas + 貼圖 sheet(AtlasPack)。

把 psd_slice 切出的各件 PNG 打包成單一貼圖頁 + 一份 .atlas,region 名 = skel_to_json 產出的
attachment 名(`<namespace>/<圖層名>`)→ 與 skeleton JSON 合起來就是**可載入的完整 Spine 資產**
(JSON + atlas + PNG)。

打包規則(對齊 libgdx atlas / atlas_crop.py 讀取假設):
  - 簡單 shelf(架式)打包:依高度遞減擺列、超寬換行;件間留 padding(避免 bilinear 邊緣滲色)。
  - **rotate: false**(不旋轉存放,最單純);region size = 件原始尺寸 → mesh/region 的正規化 uv 直接對應。
  - 每 region 寫 xy(左上)/ size / orig / offset:0,0 / index:-1,格式與真實 Spine atlas 一致。

驗收(--eval,純 CPU,不需 renderer):用**同一支** atlas_crop.extract(讀真實 Spine atlas 的程式碼)
從產出的 atlas+png 裁回每個 region → 對源切件比對 → MAE=0(打包無損、可被標準工具讀回)。
"""
import argparse, json, os, sys, math
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from PIL import Image
from psd_slice import slice_psd
from atlas_crop import extract as atlas_extract


def shelf_pack(sizes, padding=2, max_width=None):
    """sizes: [(name,w,h)]。回傳 (placements {name:(x,y,w,h)}, sheet_w, sheet_h)。"""
    total_area = sum((w + padding) * (h + padding) for _, w, h in sizes)
    if max_width is None:
        max_width = max(int(math.sqrt(total_area) * 1.1), max(w for _, w, _ in sizes) + padding)
    order = sorted(sizes, key=lambda s: -s[2])   # 高度遞減
    placements = {}
    x = y = row_h = 0
    sheet_w = 0
    for name, w, h in order:
        if x + w + padding > max_width and x > 0:   # 換行
            x = 0; y += row_h + padding; row_h = 0
        placements[name] = (x + padding, y + padding, w, h)
        x += w + padding
        row_h = max(row_h, h)
        sheet_w = max(sheet_w, x + padding)
    sheet_h = y + row_h + padding
    return placements, sheet_w, sheet_h


def build_atlas(psd_path, namespace, tmp_dir, png_name, padding=2):
    _, manifest, sliced = slice_psd(psd_path, tmp_dir)
    imgs = {f"{namespace}/{e['name']}": Image.open(os.path.join(tmp_dir, e["file"])).convert("RGBA")
            for e, _ in sliced}
    sizes = [(n, im.width, im.height) for n, im in imgs.items()]
    placements, W, H = shelf_pack(sizes, padding)
    sheet = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for name, (x, y, w, h) in placements.items():
        sheet.paste(imgs[name], (x, y))
    lines = ["", png_name, f"size: {W},{H}", "format: RGBA8888",
             "filter: Linear,Linear", "repeat: none"]
    for name, (x, y, w, h) in placements.items():
        lines += [name, "  rotate: false", f"  xy: {x}, {y}", f"  size: {w}, {h}",
                  f"  orig: {w}, {h}", "  offset: 0, 0", "  index: -1"]
    return sheet, "\n".join(lines) + "\n", placements, manifest


def evaluate(atlas_path, png_path, tmp_dir, namespace, manifest):
    """用 atlas_crop.extract 裁回每 region,對源切件比對(BGRA,cv2)。"""
    import cv2
    rows, worst = [], 0.0
    for e in manifest["parts"]:
        name = f"{namespace}/{e['name']}"
        src = cv2.imread(os.path.join(tmp_dir, e["file"]), cv2.IMREAD_UNCHANGED)
        got = atlas_extract(atlas_path, png_path, name)
        if got.shape != src.shape:
            rows.append({"region": name, "shape_mismatch": [list(got.shape), list(src.shape)]})
            worst = max(worst, 999); continue
        mae = float(np.abs(got.astype(np.float64) - src.astype(np.float64)).mean())
        worst = max(worst, mae)
        rows.append({"region": name, "size": f"{src.shape[1]}x{src.shape[0]}", "mae": round(mae, 5)})
    return {"overall_pass": worst < 0.001, "worst_mae": round(worst, 5), "regions": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--namespace", default="機器人拆件")
    ap.add_argument("--out-atlas", default="/tmp/robot_asset/robot.atlas")
    ap.add_argument("--out-png", default="/tmp/robot_asset/robot.png")
    ap.add_argument("--tmp", default="/tmp/robot_parts")
    ap.add_argument("--padding", type=int, default=2)
    ap.add_argument("--eval", action="store_true")
    a = ap.parse_args()
    png_name = os.path.basename(a.out_png)
    sheet, atlas_txt, placements, manifest = build_atlas(a.psd, a.namespace, a.tmp, png_name, a.padding)
    os.makedirs(os.path.dirname(a.out_atlas), exist_ok=True)
    sheet.save(a.out_png)
    open(a.out_atlas, "w", encoding="utf-8").write(atlas_txt)
    if a.eval:
        rep = evaluate(a.out_atlas, a.out_png, a.tmp, a.namespace, manifest)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        raise SystemExit(0 if rep["overall_pass"] else 1)
    print(json.dumps({"sheet": list(sheet.size), "regions": len(placements),
                      "atlas": a.out_atlas, "png": a.out_png}, ensure_ascii=False))


if __name__ == "__main__":
    main()
