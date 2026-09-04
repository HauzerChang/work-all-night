# 拆解流程重新分階段(2026-09-04,chunk 43)

> 分支 `claude/spine-s4-inpainting`。承接 chunk 42 的翅膀失敗案例——使用者裁示把「拆解」
> 從「AI 一鍵重繪整張圖」改成明確分階段的流程,把 AI(生成式)限縮到它已驗證可靠的用法
> (局部遮罩修補),語意判斷交給 Claude,邊界決策交給使用者。

## 六階段設計(使用者原話,逐條記錄)

1. 先由 Claude 執行(善用 GenieLabs `spine-animation-ai` 知識)分析圖片。
2. 列出認知好的部件,或提供使用者框選範圍(目的是提供使用者判斷何處需要切)。
3. 執行拆解,提供結果預覽及 PSD 轉換。
4. 修飾階段,此時才讓 GPT 參與進來,針對平圖切割後的各項邊緣破損進行維修。
5. viewer 先移除切片/拆解/需求精靈功能,僅保留補圖介面。
6. 製作輔助拆圖的 viewer(使用者做完決策後,產生對應檔案——輔助 AI 找到拆解點,再將檔案
   丟回 Claude 進行實際拆解)。

## 為什麼這個設計比舊版(chunk 39 一鍵重繪)合理

舊版「拆解」讓 gpt-image-2 對整張圖有 100% 自由重繪權(`allEditableMaskCanvas`,見
chunk 42),結果翅膀輸入生出完全不相干的人形部件——**生成式模型在「沒有局部錨定」的情況
下不可靠**,這是 chunk 42 用真實案例證實的。新設計把三件事分開,各自交給擅長的角色:

- **語意理解「這裡有什麼部件」**:交給 Claude(vision 理解,不是圖像生成,不需要重繪
  就能看懂圖片內容)。
- **邊界該切在哪裡的最終決定**:交給使用者(尤其是像九尾焰蓮那種同色重疊、AI/CPU
  都無法可靠判斷的困難案例,見 `s4-highcomplexity-charsheet-jiuweiyanlian.md`)。
- **切完之後邊緣的破損/毛邊修補**:交給 GPT,但**只用局部遮罩**(呼應候選17目前唯一
  驗證過相對可靠的用法——chunk 35 補圖案例,大部分原圖保留、只修一小塊,而不是 chunk 42
  那種整張圖自由重繪)。

## 進度:第5點已完成

`tools/mesh_gen/s4_ai_viewer.html` 已移除切片/拆解/需求精靈,只留補圖介面(檔案載入
含 .psd/manifest+PNG/單張PNG、composite 偽列、遮罩繪製、OpenAI 呼叫、套用/下載、用量
記錄)。Playwright 驗證:確認三項功能的 DOM 元素都已移除、既有補圖流程(含真實 PSD 載入)
無回歸,零 JS 錯誤。

## 第1/2點:現場示範(用九尾焰蓮案例,尚未取得使用者對格式的確認)

用 Claude 自己的視覺理解(不呼叫任何 API,零成本)分析 `assets/jiuwei_yanlian_char_crop.png`
(460×898),套用 GenieLabs 知識裡「先辨識自然部件,再決定拆分方式」的思路,產出結構化
part list。**這只是格式示範,座標是視覺估計的百分比,不是像素精確值**——如果使用者確認
這個格式方向可行,第6點的輔助 viewer 會需要更精確的框選/調整介面,不能只靠這種粗略估計。

```json
{
  "source_image": "assets/jiuwei_yanlian_char_crop.png",
  "image_size": [460, 898],
  "subject_type": "humanoid_character_with_nonhuman_features",
  "subject_notes": "狐耳半人半妖角色,九尾,長髮,半透明寬袖服裝",
  "parts": [
    {"id": "head", "label": "頭部(含五官)", "confidence": "high",
     "bbox_pct": [25, 3, 65, 18], "notes": "邊界清楚"},
    {"id": "fox_ears", "label": "狐耳(雙耳)", "confidence": "high",
     "bbox_pct": [30, 0, 75, 8], "notes": "與頭部相鄰但形狀獨立,可拆成單獨 slot 做耳朵擺動"},
    {"id": "hair_front", "label": "瀏海/額前髮絲", "confidence": "medium",
     "bbox_pct": [28, 5, 62, 15], "notes": "與頭部/髮量主體邊界略模糊"},
    {"id": "hair_main", "label": "長髮主體(後方+兩側)", "confidence": "medium",
     "bbox_pct": [0, 5, 55, 55], "notes": "⚠️ 與九尾狐尾在左下方大範圍重疊,顏色都偏白/粉,\n      邊界需使用者確認,不建議完全信任自動判定"},
    {"id": "earrings", "label": "耳環(雙耳)", "confidence": "high",
     "bbox_pct": [58, 15, 70, 21], "notes": "小型獨立配件"},
    {"id": "choker", "label": "頸飾(紅色蝴蝶結+墜飾)", "confidence": "high",
     "bbox_pct": [46, 19, 58, 25]},
    {"id": "bodice", "label": "上半身胸衣(紅色)", "confidence": "high",
     "bbox_pct": [33, 22, 70, 40]},
    {"id": "sleeve_left", "label": "左側白紗寬袖", "confidence": "medium",
     "bbox_pct": [13, 27, 40, 56], "notes": "半透明材質,邊界柔和不銳利,傳統像素分割不可靠"},
    {"id": "sleeve_right", "label": "右側白紗寬袖", "confidence": "medium",
     "bbox_pct": [60, 27, 86, 51], "notes": "同左袖,半透明"},
    {"id": "hand_left", "label": "左手", "confidence": "high",
     "bbox_pct": [13, 50, 26, 59]},
    {"id": "hand_right", "label": "右手", "confidence": "high",
     "bbox_pct": [75, 47, 89, 57]},
    {"id": "wrist_wraps", "label": "紅色護腕纏繞(雙手)", "confidence": "high",
     "bbox_pct": [null, null, null, null], "notes": "兩處小面積,各自在雙手手腕位置,座標略"},
    {"id": "belt", "label": "黑色腰帶+金色扣環", "confidence": "high",
     "bbox_pct": [38, 37, 71, 45]},
    {"id": "skirt", "label": "裙擺(紅色短裙主體)", "confidence": "high",
     "bbox_pct": [34, 40, 71, 61]},
    {"id": "tag_pendant", "label": "垂墜符紙標籤", "confidence": "high",
     "bbox_pct": [57, 44, 69, 59]},
    {"id": "sash_train", "label": "流蘇/披帛長下擺(拖尾)", "confidence": "low",
     "bbox_pct": [28, 55, 76, 96], "notes": "⚠️ 大範圍飄逸拖尾,末端跟尾巴/地面陰影交疊,\n      邊界高度不確定"},
    {"id": "leg_left", "label": "左腿(大腿露出部分)", "confidence": "high",
     "bbox_pct": [27, 57, 46, 73]},
    {"id": "leg_right", "label": "右腿", "confidence": "high",
     "bbox_pct": [54, 54, 73, 71]},
    {"id": "boot_left", "label": "左靴(過膝黑靴)", "confidence": "high",
     "bbox_pct": [27, 67, 49, 99]},
    {"id": "boot_right", "label": "右靴", "confidence": "high",
     "bbox_pct": [49, 67, 73, 99]},
    {"id": "tails_mass", "label": "九尾狐尾(整體,無法個別拆分)", "confidence": "low",
     "bbox_pct": [0, 30, 58, 100],
     "notes": "⚠️⚠️ 九條尾巴顏色高度相近(白到粉漸層皆有)、彼此重疊、部分繞到身體前後,\n      這是 CLAUDE.md 記載的『同材質語意召回0』教科書案例——Claude 自己用視覺理解\n      也只能框出『尾巴整體佔據的範圍』,無法可靠指出『第1條尾巴在哪、第2條在哪』的個別\n      邊界。這格必須由使用者人工決定要不要拆、怎麼拆(例如簡化成2-3叢而非精確9條),\n      這正是第2步『提供使用者框選範圍』存在的理由。"}
  ],
  "ambiguous_flags": [
    "hair_main 與 tails_mass 在左下方(約 x:0-40%, y:45-70%)重疊,自動判定不可信",
    "sash_train 尾端與 tails_mass/地面陰影交疊,邊界不確定",
    "tails_mass 內部無法個別拆出 9 條尾巴,只能給整體範圍"
  ]
}
```

## 這次示範揭露的方法論意義

1. **Claude 視覺理解對「清楚部件」(頭/軀幹/四肢/配件)判斷相對可信**,座標粗估即可,不需要
   生成式 AI 介入。這驗證了先前提過的「用 Claude vision 定位取代生成式重繪」的方向可行。
2. **對「困難部件」(九尾、半透明袖子、飄逸拖尾),Claude 誠實回報低信心 + 說明原因**,不會
   假裝有答案——這正是設計要的行為:**讓使用者知道哪裡真的需要人工決策,而不是在難的地方
   悄悄給一個不可靠的猜測**。
3. `bbox_pct` 目前是視覺估計,不是像素精確——第6點的輔助 viewer 如果要真的可用,應該讓
   Claude 產出的框當**初始草稿/建議**,由使用者在畫布上直接拖曳調整,而不是要求 Claude
   一次到位。

## 尚未解決的技術問題(留給後續 chunk,建的順序需要使用者確認)

1. **第6點輔助 viewer 的畫面設計**:載入圖片 → 疊上 Claude 給的建議框(如上面 JSON)→
   使用者可拖曳調整/新增/刪除/命名區域 → 匯出決策檔(JSON,格式待定,可以是上面這份
   `parts` 陣列的最終確認版)。
2. **第3點「PSD 轉換」的技術路徑未定**:現有 Python pipeline(`psd_slice.py` 等)是讀
   PSD,沒有「從一堆裁切區域組出新 PSD」的寫入能力。候選:(a) 找支援寫入的 Python 函式庫
   (如 `pytoshop`,需另外調研,`psd-tools` 本身寫入能力有限);(b) 沿用瀏覽器端 ag-psd
   (它同時支援 `readPsd`/`writePsd`),在輔助 viewer 裡直接組 PSD 下載,不用另外找
   Python 函式庫。**傾向 (b)**,因為已經在用 ag-psd,但 `writePsd` 尚未實際測試過。
3. **第4點「GPT 邊緣修補」的 mask 設計**:每個裁出的部件,邊緣可能因為裁切位置跟原始
   輪廓不完全貼合而有破損/毛邊,需要一個「只沿著裁切邊界一圈」的局部 mask(呼應
   `s4-gptfill-plugin-knowledge.md` §1 的 8px 融合邊界慣例),不是整張圖重繪——這部分
   可以直接複用簡化後的 `s4_ai_viewer.html`(補圖介面本來就是這個用法),不需要另外做。

## 下一步

等使用者確認以上格式/方向後,依序:
1. 調研 ag-psd 的 `writePsd` 能力(第3點的技術基礎)。
2. 設計並實作第6點的輔助 viewer(載入圖片→顯示/調整建議框→匯出決策檔)。
3. 實測一次完整流程:Claude 分析(示範已做)→使用者用輔助 viewer 確認邊界→拆出部件+
   組 PSD→用簡化後的補圖 viewer 修邊緣。

## 檔案

- 更新 `tools/mesh_gen/s4_ai_viewer.html`(移除切片/拆解/需求精靈,僅留補圖,見上方
  「進度:第5點已完成」)。
- 新增本檔(六階段規劃 + 第1/2點格式示範)。
