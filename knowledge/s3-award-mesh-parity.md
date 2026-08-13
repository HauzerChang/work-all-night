# S3 端到端:件 → 生成 mesh 對照 Award 真實生產 mesh(靜態覆蓋率達標）

- **結論**：S3 `generate_mesh_v2`(auto→v1 精修)對 **Award 三個真實 weighted mesh 件**
  (`機器人拆件/{光暈,左手,身體}`)的靜態覆蓋率 **全部達到/超過藝術家基準,且頂點數 ≤ 藝術家**。
  這是 S3 第一次對「**別的資產(Award,非 main_draw)+ weighted mesh + 生產品質**」驗收通過。
- **信心**:高。評估器先過校準閘(藝術家自 IoU 0.968~0.980),再下判定。
- **相關階段**:專案第 2 階段 / S3 / S4(端到端 PSD→件→mesh 的下游收斂)。

## 驗收數據(target_iou=0.98,`tools/mesh_gen/award_mesh_compare.py`)

| 件 | atlas | 藝術家 v / IoU | 生成 v / hull / IoU | gap | pass |
|---|---|---|---|---|---|
| 光暈 | Award2, rotate | 78 / 0.9795 | 78 / 43 / **0.9856** | +0.0061 | ✅ |
| 左手 | Award, upright | 80 / 0.9681 | 61 / 36 / **0.9884** | +0.0203 | ✅ |
| 身體 | Award2, rotate | 98 / 0.9760 | 68 / 28 / **0.9834** | +0.0074 | ✅ |

- 生成頂點數 **≤ 藝術家**(78/61/68 vs 78/80/98)→ 不是靠灌頂點硬贏,是拓樸效率相當。

## 兩個關鍵校準發現(都推翻先前記載,務必記住)

1. **Award mesh 的 uvs 是 region-local 0..1、對應「去旋轉後的直立影像」**——
   **不是 atlas-UV**(session-006 log 記為 atlas-UV 有誤)。
   實測:對直立 crop 直接 `u*Wc, v*Hc`(無翻轉/無旋轉)填三角形,藝術家自 IoU = 0.97~0.98,
   是全 8 種翻轉/旋轉組合中**唯一的高分**(其餘 ≤0.70)。
   → **獨立佐證 session-006 的 CW 去旋轉修正**:生產 spine 的 uvs 恰好落在 CW 去旋轉的 crop 上。
   兩條互不相干的證據(PSD 外部真值 + 生產 mesh uvs)同指 CW,方向已雙重確認。
2. **覆蓋率由「邊界(hull)取樣密度」主導,內部點密度(max_interior)幾乎不影響**——
   再次印證 4-mesh 推廣時的「IoU 由 rows 決定、cols 不影響」。
   v1 預設 `epsilon_frac=0.008` 對**羽化/曲率大**的件(光暈)過粗(hull 只 14 點 → IoU 0.919,
   落後藝術家 0.06);`epsilon≈0.002`(hull 38)→ 0.983,達藝術家水準。實心件(左手/身體)
   在 0.008 就已接近藝術家(gap −0.008),但仍受益於加密。

## 生成器改動(自我精修,opt-in)

- `generate_mesh.generate(..., target_iou=None, vertex_budget=200)`:給 `target_iou` 時,
  用評估器量自身覆蓋率,未達標就 **逐步降 epsilon(×0.6)加密邊界**,直到達標 / 觸頂點預算。
  `target_iou=None` → 行為與舊版完全一致(不影響既有 v1 驗證,curtain_left v1 仍 0.9796)。
- `generate_mesh_v2.generate(..., target_iou=0.98)`:非 strip(blob 類)走 v1 fallback 時開精修。
  strip 路徑(main_draw 4 mesh)**完全不受影響** —— 已回歸驗證 4 mesh 全 overall_pass。
- 設計理念:生成器**不偷看藝術家基準**(生產時沒有真值),只用「自身覆蓋率達 0.98」這個
  通用品質閘自我收斂;benchmark 再證明「達 0.98 ⇒ 追平/超越藝術家」。

## deform 註記(未做,下一步候選)

- 這 3 件在 Award 是 **weighted、無 deform timeline**(靠骨骼 warp),故**不套用** main_draw 的
  「真實位移場轉移」自交閘。要驗 weighted 件的變形穩健,需重現 bone-skinning(讀 weighted
  `vertices` 的 `[骨數,骨idx,bindX,bindY,權重,...]` + 骨動畫),屬另一個 bounded chunk。
- 本次僅收斂**靜態覆蓋率**;這是端到端「PSD/atlas 件 → 生成 mesh → 對生產真值」的第一個達標里程碑。

## 復現

```
python3 tools/mesh_gen/award_mesh_compare.py         # 3 件,overall_pass=True
# 單件 + 換頁自動:--piece 機器人拆件/光暈
# 回歸:validate_against_real.py --gen v2 對 main_draw 4 mesh 全 overall_pass(strip 不受影響)
```
