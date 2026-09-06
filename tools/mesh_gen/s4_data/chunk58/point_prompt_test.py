"""S4 chunk 58 — ad-hoc 測試:對 `head`/`sash_train`(chunk47/54 記錄的 heuristic
正確攔截 fragmented 案例,尚未測過點提示)測點提示能否解決破碎問題。

沿用 chunk55 對 `skirt` 的方法論:先重現 baseline 失敗(fragmented),放大格線疊圖確認
座標,再測點提示組合,逐項視覺 + 量化複核。

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

BOXES = {
    "head": [184, 90, 359, 216],
    "sash_train": [129, 494, 350, 862],
}

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
    pad = 15
    x0p, y0p = max(0, x0 - pad), max(0, y0 - pad)
    x1p, y1p = min(rgb.shape[1], x1 + pad), min(rgb.shape[0], y1 + pad)
    crop = rgb[y0p:y1p, x0p:x1p].copy()
    m = mask[y0p:y1p, x0p:x1p]
    overlay = crop.copy()
    overlay[m] = (overlay[m] * 0.4 + np.array([255, 0, 0]) * 0.6).astype(np.uint8)
    Image.fromarray(overlay).save(os.path.join(OUT_DIR, name))


def run_case(part, label, point_coords, point_labels):
    box = np.array(BOXES[part])
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
    fg_ratio, n, largest_frac = eval_mask(mask, BOXES[part])
    fname = f"{part}_{label}.png"
    save_overlay(mask, BOXES[part], fname)
    result = {
        "part": part,
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

# ---- head ----
# baseline(重現 chunk47/54 的 fragmented 攔截)
results.append(run_case("head", "box_only", None, None))
# 正向點:臉部膚色核心區(額頭花鈿/鼻樑/嘴唇/下巴,格線疊圖確認座標)
results.append(run_case(
    "head", "pos_face",
    [[272, 120], [277, 158], [270, 178], [270, 198]],
    [1, 1, 1, 1],
))
# 正向點(同上)+ 負向點(左右兩側灰髮髮絲)
results.append(run_case(
    "head", "pos_face_neg_hair",
    [[272, 120], [277, 158], [270, 178], [270, 198], [210, 110], [335, 110]],
    [1, 1, 1, 1, 0, 0],
))

# ---- sash_train ----
# baseline(重現 chunk47 的 fragmented 攔截)
results.append(run_case("sash_train", "box_only", None, None))
# 正向點:紅色流蘇布料主體(格線疊圖確認座標,沿飄動方向分布)
results.append(run_case(
    "sash_train", "pos_fabric",
    [[210, 600], [220, 680], [210, 750]],
    [1, 1, 1],
))
# 正向點(同上)+ 負向點(黑色皮靴/膚色大腿,排除鄰居內容)
results.append(run_case(
    "sash_train", "pos_fabric_neg_neighbor",
    [[210, 600], [220, 680], [210, 750], [450, 650], [370, 540]],
    [1, 1, 1, 0, 0],
))

with open(os.path.join(OUT_DIR, "point_prompt_results.json"), "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
