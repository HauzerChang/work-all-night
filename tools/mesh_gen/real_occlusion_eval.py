#!/usr/bin/env python3
"""S4 補圖閘候選 1 — 遮擋真值法(比合成挖洞更貼近實戰)。

背景(見 STATE_S4.md 候選 1 / handoff_S4.md §4):`inpaint_eval.py` 的洞是 `punch_hole`
自造的隨機圓,洞形狀/位置是人工的。這裡改用**真實**遮擋輪廓:機器人拆件 PSD 分層本就
每層各自畫全(即使被別的圖層蓋住),所以「圖層 A 的內容區 ∩ 疊在它上面的圖層 B 的內容區」
就是一個**真實會發生**的遮擋形狀,而該區域在 A 自己的圖層像素裡本來就有(未閹割的)真值。

拿這個真實形狀的洞去跑跟 `inpaint_eval.py` 完全同一套 baseline/指標/門檻/校準邏輯
(靠共用的 `run_with_mask()`),兩邊唯一的差異只有「洞從哪來」——藉此檢查合成挖洞閘的
pass/fail 判定,換成真實遮擋輪廓(不規則形狀、非人工挑選的位置)後是否依然一致。
"""
import argparse, json, os
import numpy as np
from scipy import ndimage
from psd_tools import PSDImage

from psd_slice import leaf_layers
from inpaint_eval import run_with_mask, calibration_check


def layer_full_canvas(psd, layer):
    """把單一圖層的像素貼回整張 PSD 畫布座標(而非切件裁到的 bbox 局部座標)——
    要用「圖層 A 的內容 ∩ 圖層 B 的內容」算真實遮擋,兩層必須在同一個座標系比較。"""
    W, H = psd.width, psd.height
    im = layer.topil()
    if im is None:
        return None
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    arr = np.array(im).astype(np.float64)
    canvas = np.zeros((H, W, 4), dtype=np.float64)
    l, t = int(layer.left), int(layer.top)
    canvas[t:t + arr.shape[0], l:l + arr.shape[1]] = arr
    return canvas


def classify_mode(content, mask, iters=3, edge_frac_thresh=0.15):
    """真實遮擋洞不像 punch_hole 保證落在 interior 或跨在 edge——它就是遮擋件的實際形狀,
    可能大半落在內部、邊緣沾一點。量測洞跟 target 自己內容邊界(背景膨脹 `iters` px)的
    重疊比例,決定要不要當 interior 套用(1b 只在 interior 校準過,見
    knowledge/s4-inpaint-1b-lenient-gate.md)。"""
    bg_dilated = ndimage.binary_dilation(~content, iterations=iters)
    touch = int((mask & bg_dilated).sum())
    frac = touch / max(1, int(mask.sum()))
    return ("interior" if frac < edge_frac_thresh else "edge"), round(frac, 4)


def real_occlusion_mask(target_canvas, occluder_canvas):
    t_alpha = target_canvas[..., 3] > 8
    o_alpha = occluder_canvas[..., 3] > 8
    return t_alpha & o_alpha


# 挑選依據(見 log 內的量測):光暈系列三對是純 interior(0% 沾邊界)且面積夠大(17~36%
# 內容面積),對照既有結論「光暈 CPU 補得動」;身體←左手面積較小(3.2%)且部分沾邊界,
# 對照既有結論「身體(機械紋理)1a 補不動、1b 可用」。
PAIRS = [
    ("光暈", "身體"),
    ("光暈", "右手"),
    ("光暈", "左手"),
    ("身體", "左手"),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("psd", nargs="?", default="assets/robot_parts.psd")
    ap.add_argument("-o", "--out", default=None, help="輸出補圖結果 PNG 的目錄(選填)")
    a = ap.parse_args()

    psd = PSDImage.open(a.psd)
    layers = {l.name: l for l in leaf_layers(psd)}
    canvases = {name: layer_full_canvas(psd, l) for name, l in layers.items()}

    report = {"source": os.path.basename(a.psd), "cases": {}}
    for target, occluder in PAIRS:
        if target not in canvases or occluder not in canvases:
            continue
        gt = canvases[target]
        mask = real_occlusion_mask(gt, canvases[occluder])
        if mask.sum() == 0:
            continue
        content = gt[..., 3] > 8
        mode, touch_frac = classify_mode(content, mask)
        key = f"{target}←{occluder}"
        base = f"{target}_occby_{occluder}"
        entry = run_with_mask(gt, mask, mode, base, a.out)
        entry["mode"] = mode
        entry["real_hole_boundary_touch_frac"] = touch_frac
        entry["hole_area_frac_of_target"] = round(int(mask.sum()) / max(1, int(content.sum())), 4)
        report["cases"][key] = entry

    calib_ok, calib_notes = calibration_check(report)
    report["calibration"] = {"pass": calib_ok, "notes": calib_notes}
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        json.dump(report, open(os.path.join(a.out, "manifest.json"), "w"),
                  ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if calib_ok else 1)


if __name__ == "__main__":
    main()
