# S3 對真實生產 mesh 的端到端驗收(PSD 件 → v2 mesh → 對照 Award 藝術家 mesh)

- **結論**:S3 自動生成的 mesh 對 **Award 生產 spine 的 3 個機器人件(光暈/身體/左手)**,
  覆蓋輪廓的能力 **≥ 出貨的手做藝術家 weighted mesh**,且**頂點預算 ≤ 藝術家**;
  「PSD 件 → mesh」與「atlas 件 → mesh」幾何等價。此為 S3+S4 首次對**有真值的真實生產標的**閉環。
- **依據**:`tools/mesh_gen/compare_award_mesh.py`(純 CPU,可自驅);圖見
  `knowledge/figures/s3-award-mesh-compare.png`(橙=生成 / 綠=藝術家,疊同一 alpha)。
- **信心**:高(靜態覆蓋 + 內在拓樸);**deform 未涵蓋**(見下「限制」)。
- **相關階段**:第 2 階段(S3 mesh 生成器 + S4 PSD 切圖),端到端串接。

## 對照設計(為何公平)

Award 的 3 件在生產中是**手做 weighted mesh**(有骨綁定)。用同一素材跑 S3,問:
**自動 mesh 覆蓋輪廓 ≥ 藝術家 mesh?** 沿用 `validate_against_real` 的 artist-baseline
相對閘(不用武斷 0.95),因為藝術家 mesh 自身覆蓋率才是該素材的合理天花板。

三條腿:
- **A. atlas 件 → v2 mesh**:coverage IoU vs 真實 alpha,且 ≥ 藝術家 mesh 覆蓋率 + 頂點預算對照。
- **B. PSD 件 ↔ atlas 件**:各自裁到 alpha bbox 後 silhouette IoU(證同素材)。
- **C. PSD 件 → mesh vs atlas 件 → mesh**:正規化網格 hull 覆蓋 IoU(證 PSD→mesh ≡ atlas→mesh)。

## 量化結果(標準指令 `compare_award_mesh.py`,eps=0.002 → overall_pass)

| 件 | gen coverage IoU | 藝術家 baseline | pass | gen nv/hull | 藝術家 nv/hull | B 輪廓 IoU | C mesh IoU |
|---|---|---|---|---|---|---|---|
| 光暈 glow | 0.9832 | 0.9795 | ✅ | 73 / 38 | 78 / 78 | 0.912 | 0.926 |
| 身體 body | 0.9926 | 0.9760 | ✅ | 77 / 37 | 98 / 40 | 0.950 | 0.876 |
| 左手 lefthand | 0.9913 | 0.9681 | ✅ | 67 / 43 | 80 / 42 | 0.973 | 0.973 |

- 3 件生成 mesh **setup 內在拓樸全乾淨**(0 退化三角)。
- B 輪廓 IoU 0.91~0.97 與先前「PSD↔atlas alpha-IoU 0.92~0.99」一致 → 再證同素材、閉環成立。

## 關鍵發現:coverage IoU 由 **hull 邊界密度(epsilon_frac)** 決定

epsilon 掃描(atlas 件,v1 Delaunay 分支):

| eps | 光暈 hull/nv/IoU | 身體 hull/nv/IoU | 左手 hull/nv/IoU |
|---|---|---|---|
| 0.008(舊預設) | 14 / 54 / 0.929 ✗ | 21 / 61 / 0.968 ✗ | 18 / 48 / 0.960 ✗ |
| 0.004 | 22 / 61 / 0.966 | 29 / 69 / 0.986 ✅ | 30 / 57 / 0.982 ✅ |
| **0.002(建議)** | 38 / 73 / 0.983 ✅ | 37 / 77 / 0.993 ✅ | 43 / 67 / 0.991 ✅ |
| 0.001 | 58 / 92 / 0.992 | 60 / 100 / 0.995 | 84 / 107 / 0.996 |

- 舊預設 `epsilon_frac=0.008`(為 main_draw 窗簾/陰影等**簡單形**調校)對有機生產件**邊界取樣不足**
  → 覆蓋率低於藝術家 baseline。降到 **0.002** 三件全過,且 nv(73/77/67)**仍 ≤ 藝術家(78/98/80)**。
- 呼應先前 strip 的「IoU 由 rows 決定」:覆蓋率的樞紐永遠是**邊界密度**,內部點只補三角化。

## 工具改動

- `generate_mesh_v2.generate(..., eps=None)`:新增可選參數轉發到 v1 hull 容差。
  **預設 None = 沿用 v1 舊行為(0.008),故 main_draw 4 mesh 整合 AC 零回歸**(已驗:
  curtain_left/right、shadow overall_pass=True,deform 乾淨;shadow2 與 shadow 共用 region)。
  有機件請顯式傳 `eps=0.002`。
- `compare_award_mesh.py`:leg B/C 修正 — 兩來源件**各自裁到 alpha bbox 再配準**
  (先前未裁 atlas 的透明 padding,身體件假性掉到 0.62;修正後 0.95)。

## 限制 / 下一步(誠實界定)

- **未涵蓋 weighted-mesh 真實 deform 轉移**:Award 3 件是 **weighted mesh**,其 `vertices` 為
  變長綁定格式 `[骨數, boneIdx,bindX,bindY,weight, ...]`(非 2*nv),現有 `real_deform_field`
  只支援 unweighted(main_draw)。要對 Award 件做「真實 deform 下 0 自交/翻面」閘,需先寫
  **weighted-mesh setup/deform 世界座標重現器**(computeWorldVertices 的 CPU 版:setup 世界點 =
  Σ weight·bone·bindPos;deform timeline 疊加)。→ 列為下一個 bounded chunk。
- 目前結論僅限**靜態覆蓋 + 內在拓樸**;動態穩健性對 Award 件尚未量化(對 main_draw unweighted 已驗)。
