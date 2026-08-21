# S3 weighted-mesh 變形評估器（補上唯一未驗維度）

- **結論**：補上 S3 之前唯一未驗維度 —— **weighted mesh 骨骼變形平滑度**。實作純 CPU 的
  「Spine 3.8 weighted-mesh 變形評估器」(`tools/mesh_gen/weighted_deform.py`)，並對 Award 3 個
  機器人真實美術 weighted mesh 做**評估器可信度驗收**(`validate_weighted_award.py`)，**4 道 AC 全 PASS**。
  這是「每能力必配評估器 / 評估器先行」的一環：**沒有可信的 weighted 變形度量，就無法評判之後 BBW 生成的 weighted mesh 品質**。現在有了。
- **依據/來源**：真值 = `assets/Award.json` 的 3 個機器人 weighted mesh(權重 + 骨架皆生產美術)。
  `python3 validate_weighted_award.py` → `overall_pass: true`。
- **信心程度**：高(FK 數學經剛體不變性硬檢查；負對照證明鑑別力；setup 重建 0 漂移)。
- **相關階段**：專案第 2 階段 / S3(mesh 生成器)+ S2(評估器套件)。

## 為什麼需要它

先前 `compare_robot_mesh.py` 只驗 weighted mesh 的**靜態**覆蓋率(setup pose IoU)。
但美術之所以用密集內部頂點 + 多骨權重，是為了**骨骼變形時的平滑度**——靜態 IoU 完全不涵蓋這維度。
`deform_eval.py` 只處理 unweighted mesh(deform timeline 直接位移頂點)。weighted mesh 的變形由
「骨的世界變換 + 每頂點 bind 座標/權重」驅動，需要另一套機制。本模組補上這個缺口。

## 模組能力(`weighted_deform.py`)

1. **骨骼 FK(normal 模式)**：由 `bones` 的 setup local transform + 姿勢覆寫 → 每骨世界矩陣。
   Award 全部 bone 都是 `transform:"normal"`(已核)，公式：
   `la=cos(rot+shx)*sx, lc=sin(rot+shx)*sx, lb=cos(rot+90+shy)*sy, ld=sin(rot+90+shy)*sy`，
   `world = parentWorld ∘ local`。
2. **weighted 頂點解碼**：`[nb, (boneIdx,bindX,bindY,weight)×nb, ...]` 攤平格式 → world 頂點
   `p = Σ_b w_b · boneWorld_b(bindX,bindY)`。
3. **平滑度度量**：三角翻面(setup 符號比對)、邊-邊自交、面積畸變比、**邊長拉伸 CV**
   (per-edge 拉伸比的變異係數 std/mean —— 低=變形平順鋪開，高=局部摺痕/pinch)。
   ⚠️ triangles 在 Spine JSON 是**攤平陣列**，要 reshape 成三元組(踩過)。

## 驗收 AC 與結果(全 PASS)

| AC | 檢查 | 結果 |
|---|---|---|
| AC1 setup 保真 | 由 weighted bind 重建 setup pose 是否 0 翻面/0 自交 | 3 件全乾淨 |
| AC2 **剛體不變性** | 旋轉「driver 骨集的共同祖先骨」→ 整 mesh 應純剛體移動(area_ratio==1、cv==0) | 3 件 area=1.0/cv=0 → **FK/weighting 數學正確** |
| AC3 關節彎折包絡 | 旋轉子骨(相對父骨)彎關節 → 藝術家 mesh 的最大乾淨角 + 拉伸 CV 簽章 | 身體 30°/cv0.21、左手 20°/cv0.14、光暈 5°/cv0.04 |
| AC4 **負對照鑑別力** | 同骨集但**隨機打亂權重**(setup 保持不變)→ 同角度應明顯更糟 | scramble break(flips+xs)=74/37/10 vs 藝術家 0；拉伸 CV 3~4× → **能區分好壞權重** |

- **AC2 關鍵修正**：rigid 探針必須是「driver 骨集的**共同祖先**」，不是「權重最大的骨」。
  光暈綁 4 根 sibling 骨(4_LEG3/4/5/6)，旋轉最重的葉骨 4_LEG6 是**相對變形**不是剛體；
  旋轉共同祖先 4_LEG3 才是整體剛體 → area=1/cv=0。`common_ancestor_driver()` 走 parent 鏈自動找。
- **AC4 關鍵設計**：負對照用「**隨機權重打亂**」而非「最近單骨硬權重」。硬權重對軟邊 blob(光暈)
  可能只是把子簇剛體旋轉、反而更少自交,鑑別不穩;隨機權重讓相鄰頂點不連貫移動 → 保證更糟,
  是任何可信平滑度度量都必須抓到的壞例。bind 座標重算使 setup pose 完全不變
  (`scramble_setup_drift_px=0.0`),把變數隔離在「權重品質」而非形狀。

## 重要發現

- **父骨帶動 = 剛體,子骨相對彎折才是真變形**：身體/左手綁「父骨(重) + 子骨」,旋轉父骨時子骨是
  它的 child → 整鏈剛體移動、mesh 不 flex(area=1.0)。要驗變形平滑度必須驅動**子骨相對父骨**
  (`pick_joint()`:選一根 parent 也在 driver 集裡的 driver 骨)。這對之後 BBW 設計關節測試至關重要。
- **各件變形容忍度差很多**：身體可乾淨彎到 30°、左手 20°、光暈只 5°(4 骨密集軟邊、單骨旋轉一大就自交)。
  → 未來評判 BBW mesh 要**逐件比對其藝術家簽章**,不是設單一絕對門檻。

## 下一步(直接可接)

有了可信評估器,下一個 bounded chunk 是 **S3 weighted mesh 生成(內部取樣密度 + BBW 權重)**:
對機器人某件(如身體,綁 4_LEG3/7/8)自動生成內部頂點 + 自動骨綁權重,用本評估器的
AC2/AC3/AC4 度量與**藝術家簽章逐件比對**(乾淨角包絡 ≥ 藝術家、拉伸 CV ≤ 藝術家×合理係數)。
BBW 較重(biharmonic + 不等式約束);可先用較輕的骨-熱/距離平滑權重取得 baseline,再視差距升級。
