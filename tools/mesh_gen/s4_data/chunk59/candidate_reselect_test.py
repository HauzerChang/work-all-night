"""S4 chunk 59:驗證候選「fragmented 時自動改選 largest_component_frac 最高的候選」
是否可行、是否能推廣到 bodice/sleeve_right(chunk58 提出但未實作,只驗證了 2 案)。

一次性驗證腳本,不改動任何 production 代碼(s4_sam_segment.py 維持 argmax(scores))。
對 5 個部件(head/sash_train/skirt——已知點提示可解;bodice/sleeve_right——已知點提示
4 次無效)用 box-only(不加點)跑 SAM,列出 3 個候選各自的 score/largest_component_frac,
比較「選 argmax(scores)」vs「選 argmax(largest_component_frac)」兩種策略選中的候選是否
不同、以及新策略選中的候選是否真的是乾淨/正確的內容(視覺複核決定,非只看數字)。
"""
import sys, os, json
sys.path.insert(0, "/tmp/mobilesam_src")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
import numpy as np
from scipy import ndimage
from PIL import Image
from mobile_sam import sam_model_registry, SamPredictor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
SRC_IMAGE = os.path.join(REPO, "assets", "jiuwei_yanlian_char_crop.png")
DECISION = os.path.join(REPO, "tools", "mesh_gen", "s4_data", "chunk58", "decision_final.json")
CHECKPOINT = os.path.join(REPO, "tools", "mesh_gen", "models", "mobile_sam.pt")

TEST_PARTS = ["head", "sash_train", "skirt", "bodice", "sleeve_right"]


def largest_frac(sub_mask):
    labeled, n = ndimage.label(sub_mask)
    if n == 0:
        return 1.0, 0
    sizes = ndimage.sum(sub_mask, labeled, range(1, n + 1))
    return float(sizes.max() / sizes.sum()), int(n)


def main():
    img = Image.open(SRC_IMAGE).convert("RGB")
    rgb = np.array(img)

    decision = json.load(open(DECISION))
    boxes = {p["id"]: p["bbox_px"] for p in decision["parts"] if p["id"] in TEST_PARTS}

    sam = sam_model_registry["vit_t"](checkpoint=CHECKPOINT)
    sam.eval()
    predictor = SamPredictor(sam)
    predictor.set_image(rgb)

    results = {}
    for part_id in TEST_PARTS:
        x0, y0, x1, y1 = boxes[part_id]
        box = np.array([x0, y0, x1, y1])
        masks, scores, _ = predictor.predict(box=box, multimask_output=True)

        cands = []
        for i in range(3):
            sub = masks[i][y0:y1, x0:x1]
            fg_ratio = float(sub.mean())
            lf, n = largest_frac(sub)
            cands.append({
                "idx": i,
                "score": round(float(scores[i]), 4),
                "fg_ratio_in_box": round(fg_ratio, 4),
                "n_components": n,
                "largest_component_frac": round(lf, 4),
            })

        by_score = int(np.argmax(scores))
        by_largest_frac = max(range(3), key=lambda i: cands[i]["largest_component_frac"])

        results[part_id] = {
            "box": boxes[part_id],
            "candidates": cands,
            "chosen_by_score": by_score,
            "chosen_by_largest_frac": by_largest_frac,
            "same_choice": by_score == by_largest_frac,
        }

        # 存每個候選的疊圖(RGB*mask,黑底),供視覺複核用
        for i in range(3):
            m = masks[i].astype(np.uint8) * 255
            overlay = rgb.copy()
            overlay[masks[i] == 0] = 0
            crop = overlay[y0:y1, x0:x1]
            Image.fromarray(crop).save(os.path.join(HERE, f"{part_id}_cand{i}.png"))

        print(f"== {part_id} ==")
        for c in cands:
            marker = ""
            if c["idx"] == by_score:
                marker += " <-score"
            if c["idx"] == by_largest_frac:
                marker += " <-largest_frac"
            print(f"  cand{c['idx']}: score={c['score']} fg_ratio={c['fg_ratio_in_box']} "
                  f"n={c['n_components']} largest_frac={c['largest_component_frac']}{marker}")
        print(f"  same_choice={results[part_id]['same_choice']}")

    with open(os.path.join(HERE, "candidate_reselect_results.json"), "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
