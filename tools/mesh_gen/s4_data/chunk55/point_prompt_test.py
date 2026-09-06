"""S4 chunk 55 — ad-hoc 測試:對 skirt(chunk54 新發現的靜默錯誤)測點提示。

沿用 chunk48 的做法(先在 Python 層直接驗證,不先蓋 UI):對 skirt 的框
(bbox_px=[156,359,327,548],來自 chunk53 decision_final.json)測試加正向/負向點
能否讓 MobileSAM 選中紅色裙擺布料主體而非皮膚(大腿/手)。

不修改任何 production 代碼(s4_sam_segment.py 維持不變),這是一次性驗證腳本。
"""
import sys, os, json
import numpy as np
from PIL import Image

sys.path.insert(0, "/tmp/mobilesam_src")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from mobile_sam import sam_model_registry, SamPredictor
from scipy import ndimage

CHECKPOINT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "models", "mobile_sam.pt")
IMG_PATH = "assets/jiuwei_yanlian_char_crop.png"
BOX = [156, 359, 327, 548]  # x0,y0,x1,y1

img = Image.open(IMG_PATH).convert("RGB")
rgb = np.array(img)

sam = sam_model_registry["vit_t"](checkpoint=CHECKPOINT)
sam.eval()
predictor = SamPredictor(sam)
predictor.set_image(rgb)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def eval_mask(mask, box):
    x0, y0, x1, y1 = box
    sub = mask[y0:y1, x0:x1]
    fg_ratio = float(sub.mean())
    labeled, n = ndimage.label(sub)
    if n > 0:
        sizes = ndimage.sum(sub, labeled, range(1, n + 1))
        largest_frac = float(sizes.max() / sizes.sum())
    else:
        largest_frac = 1.0
    return fg_ratio, n, largest_frac


def save_overlay(mask, box, name):
    x0, y0, x1, y1 = box
    pad = 10
    crop = rgb[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad].copy()
    m = mask[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
    overlay = crop.copy()
    overlay[m] = (overlay[m] * 0.4 + np.array([255, 0, 0]) * 0.6).astype(np.uint8)
    Image.fromarray(overlay).save(os.path.join(OUT_DIR, name))


def run_case(label, point_coords, point_labels):
    box = np.array(BOX)
    if point_coords is not None:
        masks, scores, _ = predictor.predict(
            box=box,
            point_coords=np.array(point_coords),
            point_labels=np.array(point_labels),
            multimask_output=True,
        )
    else:
        masks, scores, _ = predictor.predict(box=box, multimask_output=True)
    chosen = int(np.argmax(scores))
    mask = masks[chosen]
    fg_ratio, n, largest_frac = eval_mask(mask, BOX)
    fname = f"skirt_{label}.png"
    save_overlay(mask, BOX, fname)
    result = {
        "case": label,
        "scores": [round(float(s), 4) for s in scores],
        "chosen": chosen,
        "fg_ratio_in_box": round(fg_ratio, 4),
        "n_components": int(n),
        "largest_component_frac": round(largest_frac, 4),
        "overlay": fname,
    }
    print(json.dumps(result, ensure_ascii=False))
    return result


results = []
# baseline:純框(重現 chunk54 的失敗結果)
results.append(run_case("box_only", None, None))
# 正向點:紅色裙擺布料主體(兩點,放大格線確認過的座標)
results.append(run_case("pos_only", [[260, 395], [285, 430]], [1, 1]))
# 正向點 + 負向點(皮膚:大腿/手)
results.append(run_case(
    "pos_neg",
    [[260, 395], [285, 430], [250, 505], [180, 470]],
    [1, 1, 0, 0],
))

with open(os.path.join(OUT_DIR, "point_prompt_results.json"), "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
