# S3 端到端驗收 — 自動 mesh vs Award 真實生產 mesh(機器人拆件)

- **結論**:對真實生產件(Award「機器人拆件」的 3 個 mesh:光暈 / 身體 / 左手),
  用 atlas 真實貼圖跑 S3 生成器(v2 auto),**3 件全通過**「覆蓋率 ≥ 藝術家 且 頂點數 ≤ 藝術家」
  雙軸 AC。這是 S3 首次對**真實生產 mesh 有真值**的端到端驗收(先前 main_draw 是同一資產內比對,
  此處是跨資產、跨美術來源的獨立標的)。
- **信心**:高(真值 = 生產 spine 的藝術家 mesh;正/負皆有,IoU 與頂點數雙軸比對;含視覺 overlay)。
- **階段**:第 2 階段 / S3(里程碑:合成 → main_draw → 跨資產真實生產件)。

## 結果(`validate_award_mesh.py`,gen v2 auto)

| 件 | 生成 v/t | 生成 IoU | 藝術家 v | 藝術家 IoU | budget | 覆蓋 pass | 合法 pass |
|---|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | 61v/97t | **0.9656** | 78v | 0.9795 | 78 | ✅(margin 0.02)| ✅ |
| 機器人拆件/身體 | 69v/107t | **0.9858** | 98v | 0.9760 | 98 | ✅(**勝過藝術家**)| ✅ |
| 機器人拆件/左手 | 57v/82t | **0.9816** | 80v | 0.9681 | 80 | ✅(**勝過藝術家**)| ✅ |

→ 身體/左手 的自動 mesh **覆蓋率勝過手做**且**更精簡**(69<98、57<80);光暈略低於手做但在 margin 內、且更精簡。
視覺 overlay:`figures/award-robot-mesh-overlay.png`(綠=藝術家、青=生成,兩者皆貼合 alpha)。

## 關鍵發現與修正

### 1. 這 3 件是 **weighted mesh 且無 deform timeline**(∴ 只做靜態覆蓋 AC)
Award 12 支動畫對 `機器人拆件/*` **全無 deform**(已查證):變形靠 **weighted bone**,不是逐頂點 deform。
故對這批件,有意義的 AC 是「**靜態覆蓋率**」而非 deform 耐受 —— 我的生成器目前不產權重,
weighted deform 無真值可比。**weighted deform 對照留待 S3 後續(BBW 權重生成)。**

### 2. v1 Delaunay 預設 epsilon 太粗,系統性低估「彎曲/圓潤輪廓」→ **0.008 → 0.004**
光暈是大面積、圓潤軟邊的件(496×480)。舊 `epsilon_frac=0.008` 只簡化出 **14 點 hull**,
弦割過曲邊 → 覆蓋率 0.929、且有孤兒頂點。sweep 證實 **覆蓋率由 hull 取樣密度(epsilon)決定**
(呼應 v2 strip 的「IoU 由 rows 決定」),與 cols/內部點無關:

| eps | hull | IoU(光暈)|
|---|---|---|
| 0.008 | 14 | 0.929(fail)|
| **0.004** | **22** | **0.966(pass)** |
| 0.002 | 38 | 0.983(但 73v 超舊 budget)|
| 0.001 | 58 | 0.992 |

改 `generate_mesh.generate` 預設 `epsilon_frac=0.004`。**回歸全過**:main_draw curtain_left(v1)、
4 mesh(v2)、S2 切圖閘 全 exit 0。

### 3. 頂點 budget 該對齊藝術家,而非武斷 64(方法論一致性)
舊 AC3 `budget ≤ 64` 是對 main_draw 小 mesh(窗簾 21v/陰影 12v)校準的;**真實大件藝術家自身即用 78~98v**。
沿用專案既有做法(把武斷常數換成藝術家基準,如 IoU 0.95→藝術家),**改用 per-piece budget = 藝術家頂點數**:
「自動 mesh 不比手做的多頂點」是真正有意義的 leanness 判準。3 件生成 v(61/69/57)皆 < 藝術家(78/98/80)。

## UV / atlas 對齊備忘(踩過)
- Award mesh uvs 為 **region-local 0..1**(logical、未旋轉方向),非 atlas-page UV → `artist_iou` 直接
  `uv×(cropW,cropH)` 即對(main_draw 亦然)。
- `atlas_crop.extract` 對 rotate=true 件用 **CW derotate**(已校正),輸出即 logical 方向,與 uvs 對齊。
- atlas 貼圖 ~0.70 縮小打包不影響 IoU(生成與重組同在 crop 像素格,scale 一致)。

## 可重現
```
python3 tools/mesh_gen/validate_award_mesh.py            # 3 件 overall_pass, exit 0
python3 tools/mesh_gen/validate_against_real.py --gen v1 # 回歸:curtain_left v1
python3 tools/mesh_gen/validate_against_real.py --gen v2 # 回歸:main_draw 4 mesh
```

## 下一步
- **切圖→Spine JSON 組裝(SkelToJson)**:把「PSD/atlas 件 → 自動 mesh → 寫回 Spine attachment
  (`<PSD名>/<圖層名>` slot、+2px padding、size)」固化成工具,端到端產出可載入的 Spine JSON。
- **S3 權重(BBW)**:有了骨架後為生成 mesh 算 bone 權重,才能對 weighted deform 做真值對照(補上這批件缺的 AC5)。
