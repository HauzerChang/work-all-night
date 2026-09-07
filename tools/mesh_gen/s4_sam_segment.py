"""S4 拆解流程第3點 — box-prompted 語意分割(MobileSAM),取代純矩形裁切。

背景:使用者實測矩形裁切後明確反對(「只切出矩形 不符合我的需求」),要求在框選範圍內
精準找到部件的不規則輪廓。傳統色彩分割(OpenCV GrabCut)實測對這種插畫風格三個測試案例
(head/choker/earrings)全部失敗(見 knowledge/s4-sam-segment.md 的失敗記錄)——GrabCut
沒有語意理解,只看顏色統計,框裡如果有一大片視覺上更「顯著」的內容(臉、皮膚)會直接選
那個,不管標籤說的是什麼。改用有學過「物件」概念的模型:MobileSAM(Apache 2.0,CPU
可跑,~40MB,一次下載無持續費用)——Meta Segment Anything 的輕量版,同樣的
box-prompted 介面,但用 TinyViT 換掉笨重的 ViT-H encoder。

模型來源(不進 git,見 .gitignore;需要時用下方指令重新下載並核對 sha256):
  curl -sSL -o tools/mesh_gen/models/mobile_sam.pt \
    https://raw.githubusercontent.com/ChaoningZhang/MobileSAM/master/weights/mobile_sam.pt
  # sha256: 6dbb90523a35330fedd7f1d3dfc66f995213d81b29a5ca8108dbcdd4e37d6c2f
原始碼(mobile_sam python package,同倉庫 Apache 2.0)不在 PyPI,需另外取得,見同一份
knowledge 文件的重現步驟。
"""
import sys, os
import numpy as np
from scipy import ndimage

DEFAULT_CHECKPOINT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "mobile_sam.pt")
# 依實測(見 knowledge/s4-sam-segment.md 完整記錄)歸納出兩種不可信的失敗模式,各自需要
# 不同的偵測方式,任一觸發就標 low_confidence:
# 1. 框幾乎全部被判定前景(如 earrings)——通常代表框本身沒貼近目標物件,SAM 找不到
#    可信賴的內部邊界,只好把整個框當前景。
# 2. 前景被切成好幾塊不相連的小碎片,不是一塊連續形狀(如 bodice 實測結果)——即使
#    fg_ratio 數字看起來正常,視覺上明顯是雜訊而不是一個部件的輪廓。用最大連通元件占
#    全部前景像素的比例當判準:太低代表破碎。
# 這兩個 threshold 都是憑這次實測(20個部件)校準的經驗值,不是理論推導,未來遇到不同
# 美術風格素材可能需要重新校準——這裡誠實承認,不假裝是普適常數。
LOW_CONFIDENCE_FG_RATIO = 0.75
LOW_CONFIDENCE_LARGEST_COMPONENT_FRAC = 0.6


class SamSegmenter:
    def __init__(self, checkpoint=DEFAULT_CHECKPOINT, mobile_sam_src=None):
        if mobile_sam_src:
            sys.path.insert(0, mobile_sam_src)
        try:
            from mobile_sam import sam_model_registry, SamPredictor
        except ImportError as e:
            raise ImportError(
                "找不到 mobile_sam 套件。這不是 pip 套件,需要從 MobileSAM repo 原始碼載入,"
                "見 s4_sam_segment.py 檔頭說明的重現步驟(git clone 後把路徑傳給 "
                "mobile_sam_src 參數 / --sam-src CLI 參數)。"
            ) from e
        if not os.path.exists(checkpoint):
            raise FileNotFoundError(
                f"找不到 MobileSAM 權重 {checkpoint},見 s4_sam_segment.py 檔頭的下載指令。"
            )
        sam = sam_model_registry["vit_t"](checkpoint=checkpoint)
        sam.eval()
        self.predictor = SamPredictor(sam)
        self._image_set = False

    def set_image(self, rgb_array):
        self.predictor.set_image(rgb_array)
        self._image_set = True

    def segment(self, bbox_xyxy, points=None):
        """回傳 (mask_bool_fullsize, info)。info 含三個候選的 score/選中的是哪個/
        框內前景比例/是否 low_confidence(框內幾乎全被判定前景,代表框本身可能太鬆,
        SAM 找不到可信的內部邊界,不代表這個工具本身壞掉——見檔頭說明)。

        points(選填):`[(x, y, label), ...]` 列表,label 1=正向點(在目標物件內)、
        0=負向點(在要排除的鄰近物件內)。單純 box prompt 在「框正確但SAM選錯鄰居內容」
        的部分案例上會選錯候選(見 knowledge/s4-sam-point-prompt-investigation.md 的
        `bodice`/`sleeve_right` 負面結果),但不是所有這類案例都救不了——
        `knowledge/s4-sam-point-prompt-skirt.md` 驗證過對 `skirt` 這個案例有效,
        單一正向點就能讓 SAM 選中正確候選,結論是「逐案實測,不能一概而論」。"""
        if not self._image_set:
            raise RuntimeError("尚未呼叫 set_image()")
        x0, y0, x1, y1 = bbox_xyxy
        box = np.array([x0, y0, x1, y1])
        if points:
            point_coords = np.array([[p[0], p[1]] for p in points])
            point_labels = np.array([p[2] for p in points])
            masks, scores, _ = self.predictor.predict(
                box=box, point_coords=point_coords, point_labels=point_labels,
                multimask_output=True)
        else:
            masks, scores, _ = self.predictor.predict(box=box, multimask_output=True)

        stats = []
        for i in range(3):
            sub = masks[i][y0:y1, x0:x1]
            fg_ratio = float(sub.mean())
            labeled, n = ndimage.label(sub)
            if n > 0:
                sizes = ndimage.sum(sub, labeled, range(1, n + 1))
                largest_frac = float(sizes.max() / sizes.sum())
            else:
                largest_frac = 1.0  # 空 mask,不算破碎(是另一個問題,fg_ratio=0 會很明顯)
            stats.append({"fg_ratio": fg_ratio, "n": int(n), "largest_frac": largest_frac})

        chosen = int(np.argmax(scores))
        fg_ratio = stats[chosen]["fg_ratio"]
        n = stats[chosen]["n"]
        largest_frac = stats[chosen]["largest_frac"]
        too_much_fg = fg_ratio >= LOW_CONFIDENCE_FG_RATIO
        fragmented = n > 1 and largest_frac < LOW_CONFIDENCE_LARGEST_COMPONENT_FRAC

        # 候選重選(chunk 59,見 knowledge/s4-sam-candidate-reselect.md):argmax(scores)
        # 選中的候選破碎時,SAM 其餘 2 個候選裡有時已經有一個乾淨(未破碎、未過量前景)的
        # ——量化驗證過(head/sash_train 正面、bodice/sleeve_right/skirt 這三個「內容選錯」
        # 案例因為從未被判定 fragmented 而不受影響,零回歸風險)。只在原選擇破碎時才嘗試,
        # 不破碎就不改,維持既有行為。
        auto_reselected = False
        if fragmented and not too_much_fg:
            clean_alts = [
                i for i in range(3)
                if i != chosen and stats[i]["fg_ratio"] < LOW_CONFIDENCE_FG_RATIO
                and not (stats[i]["n"] > 1 and stats[i]["largest_frac"] < LOW_CONFIDENCE_LARGEST_COMPONENT_FRAC)
            ]
            if clean_alts:
                chosen = max(clean_alts, key=lambda i: stats[i]["largest_frac"])
                fg_ratio = stats[chosen]["fg_ratio"]
                n = stats[chosen]["n"]
                largest_frac = stats[chosen]["largest_frac"]
                too_much_fg = False
                fragmented = False
                auto_reselected = True

        mask = masks[chosen]
        info = {
            "method": "mobile_sam",
            "scores": [round(float(s), 4) for s in scores],
            "chosen_candidate": chosen,
            "fg_ratio_in_box": round(fg_ratio, 4),
            "n_components": int(n),
            "largest_component_frac": round(largest_frac, 4),
            "low_confidence": too_much_fg or fragmented,
            "low_confidence_reason": ("too_much_fg" if too_much_fg else "") +
                                      ("+" if too_much_fg and fragmented else "") +
                                      ("fragmented" if fragmented else ""),
            "n_points_used": len(points) if points else 0,
            "auto_reselected": auto_reselected,
        }
        return mask, info
