# S3+S4 端到端:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把「PSD 切件 → `generate_mesh_v2` 自動生成 mesh」對真實生產 spine `Award` 的
  三個藝術家 weighted mesh(光暈/左手/身體)做量化對照,**三件全 PASS**。生成 mesh 覆蓋件本體
  ≥0.93、與藝術家覆蓋率 parity 0.98–1.02、輪廓 footprint IoU 0.92–0.96,且**頂點數只有藝術家的
  ~45–75%**(35/59/60 vs 78/80/98)。⇒ S3(mesh 生成)+ S4(PSD 切圖)串成端到端、對**真實藝術家
  真值**驗收通過(里程碑)。
- **信心**:高。純 CPU 可重跑;附雙向負對照(見下)確認比對器有鑑別力。
- **相關階段**:第 2 階段(鍛鍊四能力)— S3×S4 交會點。工具 `tools/mesh_gen/compare_against_award.py`。

## 為何比得動(關鍵幾何洞察,免 atlas 對位)

Spine mesh 的 `uvs` 是 [0,1] 正規化紋理座標;`width/height` 是**原始藝術尺寸**(非 atlas 縮小後)。
實測 Award mesh 的 W,H(708×685 / 259×217 / 381×427)≈ PSD 件 bbox(706×683 / 257×215 /
379×425,±2px padding)⇒ 藝術家 mesh 的 uvs 與生成 mesh 的 uvs 落在**同一件原生藝術的正規化空間**。
故可直接在正規化 UV 網格(512²)疊合比對,**不需 atlas 反旋轉/縮放對位**(該路已在
`s4-psd-to-spine-real` 用 alpha-IoU 0.92–0.99 確認同素材)。

## 量化結果(標準指令,exit 0)

`python3 tools/mesh_gen/compare_against_award.py <parts_dir> assets/Award.json`
(parts_dir = `psd_slice.py assets/robot_parts.psd -o <dir>` 的輸出)

| slot | mode | cover_gen | cover_real(藝術家) | parity | footprint_iou | verts gen/real |
|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | delaunay-v1 | 0.927 | 0.945 | 0.981 | 0.918 | **35 / 78** |
| 機器人拆件/左手 | delaunay-v1 | 0.955 | 0.981 | 0.973 | 0.957 | **59 / 80** |
| 機器人拆件/身體 | delaunay-v1 | 0.962 | 0.948 | 1.015 | 0.929 | **60 / 98** |

- 三件都走 **v1(Delaunay 散點)**:長寬比 <1.2 且非「直條」形(v2 auto 正確地不套 strip;strip 是
  為窗簾那種高瘦、單軸大拉伸件保留的)。robot 件為 blob 狀 → Delaunay 內部佈點覆蓋佳。
- 身體 parity **1.015**:生成 mesh 覆蓋率**略高於**藝術家(藝術家 mesh 邊界略內縮)。

## 評估器校準發現(重要,延續本專案「評估器需校準」主題)

**絕對覆蓋 IoU 門檻對羽化件不適用 → 必須用「對藝術家 parity」當閘。**
- 光暈是**羽化光暈**:內容像素中 **24.6% 為半透明**(alpha 8–250),平均 alpha 223.9;
  左手/身體僅 2.0–2.7% 半透明、平均 alpha ~252。
- 羽化邊界無法被三角形填到 >0.95:**連藝術家 78 頂點手做 mesh 對光暈也只有 0.945**。
- 故 `evaluate_mesh` 的絕對 `AC1_iou≥0.95` 對光暈**必然假性失敗**。本比對器的 **E1 只驗格式/拓樸**
  (孤兒/退化/索引/預算/重心),覆蓋率交給 **E2(≥0.90 覆蓋件本體)** 與 **E3(parity ≥0.95×藝術家
  且 footprint≥0.80)**。這是「職責分離 + parity-aware」,不是移動門柱 —— 有客觀羽化證據支持。

## 雙向負對照(確認比對器鑑別力)

以身體件為例(正對照 cover 0.962 / footprint 0.929):
- NC1 拿**左手真值 mesh** 當身體真值 → footprint **0.512**(<0.80 → E3 fail)。✓
- NC2 生成 uvs **上下翻轉** → cover 0.597、footprint 0.607(崩)。✓
- NC3 生成 uvs **平移 0.25** → cover 0.340(<0.90 → E2 fail)。✓

## AC(逐件,全過)

- E1 格式/拓樸合法(不含覆蓋率)· E2 cover_gen≥0.90 · E3 parity≥0.95×藝術家 且 footprint≥0.80 · E4 verts_gen≤verts_real。

## 產出 / 可重現

- 工具:`tools/mesh_gen/compare_against_award.py`(復用 `generate_mesh_v2` + `evaluate_mesh`)。
- 結果:`results/robot_award_compare/`(3 件生成 mesh JSON + `report.json`)。
- 來源件:`psd_slice.py assets/robot_parts.psd`(光暈/左手/身體;右手/頭在 Award 是 region 非 mesh,不列入)。

## 開放 / 下一步

- Award mesh 是 **weighted**、且有 deform 動畫;本次比對在 **setup/UV 靜態**層。**deform 對照**(把
  Award 真實位移場轉到生成 mesh 驗自交)為自然下一塊 —— 但需先把 weighted 世界座標 + 骨階層變換
  在 Python 重現(deform_eval 目前針對 unweighted;需擴充)。
- weighted 權重生成(BBW)尚未做:生成 mesh 目前 unweighted。要真正替換藝術家 mesh 還需綁權重(S3 後段)。
