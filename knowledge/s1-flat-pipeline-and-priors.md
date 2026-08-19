# S1 擴充 — 平圖(未分層)流程 + 分鏡先驗庫

- **結論**:依 STATE 候選 0 推進 S1 兩個子項並各配可驗證閘:
  (A) **平圖自動拆件 baseline**(純 CPU)+ 真值召回閘;(B) **分鏡先驗庫**擴充 + 真值覆蓋閘。
- **信心**:高(兩者皆對 repo 真實資產量化;含正/負對照;修掉 2 個評估器/分類 bug)。
- **階段**:第 2 階段 / S1。工具:`tools/analyzer/segment_flat.py`、`validate_flat_recall.py`、
  `genre_priors.py`、`validate_priors.py`。

## A. 平圖(未分層)流程

### 方法(純 CPU,無網路/GPU)
`segment_flat.py`:前景遮罩(alpha 或邊界主色 flood 去背)→ Lab k-means 顏色量化 → 每色連通元件
→ 小區丟棄 → 候選件 + `decomposability` 分數。環境無 rembg/onnxruntime/skimage,故走古典法。

### 真值召回閘(`validate_flat_recall.py`)
把分層 PSD **壓平**成單張平圖 → 自動拆件 → 拿**已知 PSD 圖層**當真值量 IoU 召回。

| 測試 | 真值件 | 候選 | recall@0.5 | 說明 |
|---|--:|--:|--:|---|
| robot_parts(同材質機器人,單一相連前景) | 5 | 10 | **0.0** | 顏色分不出重疊同色件 |
| Symbol_Ww(彩色角色,重疊) | 18 | 21 | **0.0** | 顏色區 ≠ 語意件 |
| 合成正對照(3 不相連色塊) | 3 | 3 | **1.0** | 不相連塊可靠召回 |

### ★ 核心發現(誠實)
1. **平圖語意拆件基本欠定**:單一相連前景(角色多屬此)的語意界線,靠顏色/幾何分不出來
   (robot 0/5、Symbol 0/18)。**唯一可靠自動拆件 = 前景的「不相連塊」**(正對照 3/3)。
2. **顏色分群候選 = 過度分割提案,非語意可動件** —— 只能當人工起手畫布,不能當交付件。
3. → **量化佐證「PSD-first 契約」**:拿到分層 PSD 幾乎白送拆件(S4 已驗無損);拿不到就得
   人工 / 未來 GPU 語意分層(SAM、See-Through)。這條路 CPU baseline 到頂了。
4. **修評估器 miscalibration(第 N 次教訓)**:初版 `decomposability` 給 robot 1.0(說「可試」)但
   實際 0 召回 → 分數不預測任何事,且連通度邏輯**反了**(單一 blob 是最難,不是最易)。
   重校準:分數主要由 `fg_components` 決定(單塊→0.2、多塊→0.5+),交叉檢查
   `decomposability_predicts_failure` 現為 True。**評估器要先對真值校準才可信。**

## B. 分鏡先驗庫(`genre_priors.py`)

### 內容
| 類型 | beats | 檔位 | 驗證真值 |
|---|---|---|---|
| `slot_bigwin` | In / Loop / Out | Super/Mega/Omg/Legend | **Award(coverage 1.0)** |
| `slot_reveal` | static/idle/comeout/open/hit/loop/close | — | **main_draw(coverage 1.0)** |
| `slot_symbol` | land/idle/win | — | ⚠️ UNVALIDATED(無真值 spine) |
| `character_idle` | idle/accent | — | ⚠️ UNVALIDATED |

每 beat 附關鍵字(供分類真實動畫名)+ 依結構角色(body/head/limb/effect)的動作模板(給 rigger 起手)。

### 真值覆蓋閘(`validate_priors.py`)
對 validated 類型,檢查其 beat 關鍵字能否覆蓋對應真實 spine 的動畫命名。
**slot_bigwin vs Award、slot_reveal vs main_draw 覆蓋率皆 1.0**,beat 分派正確、無 unmatched。

### ★ 修正:動畫名分類的子字串 bug
初版用**子字串**比對關鍵字 → `"end"∈"legend"`(In 誤判為 Out)、`"draw"∈"main_draw"`
(hit/loop 誤判為 open),覆蓋率雖 100% 但**分派全錯**。
改為**整個 token 比對**(camelCase + 底線 + 數字邊界切詞;`idle2→['idle','2']`)並**優先採最後一個 token
(節拍後綴)** → 分派正確。教訓:**高覆蓋率不代表分類正確,要看逐筆分派**。

## 可重現
```
python3 tools/analyzer/validate_priors.py            # 2 validated 類型 coverage 1.0 → PASS
python3 tools/analyzer/validate_flat_recall.py       # robot 平圖召回 0/5(誠實 baseline)
python3 tools/analyzer/segment_flat.py <flat.png> --out /tmp/cand   # 平圖拆件候選
python3 tools/analyzer/analyze_target.py <psd> --genre slot_reveal  # 用開獎先驗產分鏡
```

## 下一步候選
- 平圖流程升級路線(需資源):GPU 語意分層(SAM/See-Through)接同一 analyze_target 介面;或
  半自動(人在候選上歸併)。CPU 端可再加「不相連塊」直接當件的快路徑。
- 先驗庫:補更多**有真值**的類型(需對應 spine);或從一批真實 spine 自動歸納 beat 詞彙。
- 接 S3/S4:規格 → 實際素材(mesh 件串 generate_mesh_v2、region 件串 psd_slice)。
