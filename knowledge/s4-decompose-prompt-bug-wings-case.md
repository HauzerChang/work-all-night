# 拆解功能真實使用失敗案例:預設 prompt 寫死人形假設(2026-09-04,chunk 42)

> 分支 `claude/spine-s4-inpainting`。使用者用 viewer 的「拆解」分頁,對一對機械翅膀素材
> (`assets/` 未收錄,使用者對話貼圖)實際跑了一次真實付費 API 呼叫,結果**輸出完全不相干**
> ——回傳的是一套黑色皮甲人形角色部件(臉/兜帽/胸甲/護臂/手套/靴子),跟輸入的翅膀毫無關係。

## 輸入/輸出(使用者實測,真實付費呼叫,已由使用者提供對照圖)

- 輸入:一對銀灰+金色+紅色的機械/天使風格翅膀,白底,1536×1024。
- 輸出:1024×1024,完全不同主體——黑髮男性角色的臉部正側面、兜帽披風、胸甲、雙臂護甲、
  手套(大小兩雙)、五雙靴子(不同角度)。**沒有任何一個部件跟翅膀有關**,連「風格相近但
  拆錯」都稱不上,是主體本身被整個換掉。

## 根因診斷(讀程式碼確認,不是猜測)

`s4_ai_viewer.html` 拆解分頁的**預設 prompt 寫死**:

```
Redraw this character as a fully deconstructed 2D game sprite atlas for Spine animation
rigging: separate the head, torso, arms, and legs/feet into individual isolated pieces...
```

這段文字**假設主體是人形角色**(明講 head/torso/arms/legs/feet)。使用者的輸入是翅膀,
沒有頭、沒有軀幹、沒有手臂腿——文字描述的內容跟實際圖片內容直接矛盾。加上拆解功能刻意用
`allEditableMaskCanvas()`(alpha 全 0,整張圖 100% 可編輯)給模型完全的重繪自由,模型在
「文字說有人形角色」vs「圖片是翅膀」兩個矛盾訊號之間,**選擇跟著文字走**,生出了一個通用
人形角色部件表,幾乎沒理會輸入圖的實際內容。

**這是我(Claude)寫的預設 prompt 只考慮了人形角色情境的責任**,不是「AI 本身不穩定」的
隨機失效——同一個 bug,只要輸入是任何非人形主體(道具、動物、翅膀、載具...)都會複現。

## 修正(已落地,尚未重新真實驗證)

1. **改寫預設 prompt 為主體無關的通用版本**,明確加入「錨定」語句(禁止模型替換主體):
   > "Take the EXACT subject shown in the reference image — do not invent, replace, or
   > substitute it with a different subject or character. ... separate its existing
   > natural parts (whatever they are — e.g. if it has limbs, separate limbs/torso/head;
   > if it is a pair of wings, separate each wing and its feather/segment clusters; if it
   > is an object, separate its natural sub-components)..."

   UI 上同時加了一段醒目提示,說明這次修正的背景,並提醒新版本**同樣尚未經真實付費呼叫
   驗證**,不要假設改了就一定有效。
2. **順帶修正一個可能的次要因素**:原本 size 下拉固定預設 `1024x1024`,使用者這次的翅膀
   輸入是 1536×1024(寬幅),若沿用預設方形尺寸送出,畫面會被硬塞進不合比例的正方形畫布、
   送出前可能已經變形——新增 `updateDecomposeSizeSuggestion()`,主素材變更時依長寬比
   自動建議最接近的 size 選項(比例>1.2 → 1536×1024;<1/1.2 → 1024×1536;其餘 →
   1024×1024),使用者仍可手動覆蓋。**這不是這次「主體完全被換掉」的主因**(尺寸不合比例
   頂多造成變形/裁切,不會無中生有換一個完全不同的主體),但一併修掉降低風險。

## 驗證(Playwright,mock API,未花真實費用)

1. 新 prompt 含 `"EXACT subject"` 錨定語句,不再含舊版的 `"head, torso, arms, and legs"`。
2. 三種長寬比輸入(寬幅 300×100/直幅 100×300/近方形 64×64)分別自動建議
   `1536x1024`/`1024x1536`/`1024x1024`,符合預期。
3. 修改後既有拆解流程(mock API 呼叫→顯示結果→用量記錄)仍正常運作,無 JS 錯誤。

**誠實限制**:上述驗證只確認「程式碼邏輯照預期運作」,**沒有驗證「新 prompt 真的能讓
gpt-image-2 忠實重繪翅膀」**——這需要真實付費呼叫才能知道,錨定語句能不能真的解決模型
「跟著文字走、忽略圖片」的傾向,目前是合理推測、不是已驗證結論。

## 對候選17/拆解功能的整體意義

這是候選17「拆解」子功能第一次遇到**真實、嚴重的失敗案例**(先前 chunk 35 的左手案例雖然
1a 分數 fail,但視覺上是可辨識的合理延續;這次是主體整個被替換,性質完全不同、嚴重得多)。
提醒:**候選17目前所有正面結果都只在「有 mask 挖洞、大部分原圖保留」的補圖情境下驗證過**,
「拆解」用的是完全不同的呼叫模式(整張圖可編輯、無局部錨定),兩者不能互相佐證可靠度——
拆解這條路線的可信度應該獨立評估,不能因為補圖那邊的 chunk 35 結果好就假設拆解也可靠。

## 下一步

- 建議使用者用修正後的 prompt,對同一張翅膀圖(或任何非人形素材)用 `quality=low` 低成本
  重跑一次,驗證錨定語句是否真的解決問題。
- 若重跑後依然主體跑偏,代表問題不只是 prompt 文字,可能是「整張圖可編輯」這個 mask 設計
  本身讓 gpt-image-2 的 img2img 條件約束太弱——那時候需要考慮換一種送法(例如保留畫布外圍
  一圈原圖不可編輯,強迫模型錨定風格/內容,但這會跟「拆解需要整張重新排版」的目標打架,
  需要另外設計)。
