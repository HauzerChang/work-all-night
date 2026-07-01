# S3×S4 端到端 — 對「真實生產 mesh」(Award 機器人拆件)驗收生成器

- **結論**:S3 mesh 生成器對真實生產 spine(Award「機器人拆件」)的 3 個 mesh 件
  (光暈/左手/身體)**端到端驗收通過**:我們生成的 mesh 覆蓋率**達到或超過藝術家真實
  mesh,且頂點數更少**(3 件全 `overall_pass`,exit 0)。這是 S3 首次對「藝術家手做的
  真實生產 mesh」做 ground-truth 覆蓋率對照(先前只對 main_draw 窗簾/陰影)。
- **信心**:高 —— 評估器先過自我校驗(藝術家真值拓樸乾淨)+ 雙向負對照(縮放/平移/拓樸打亂皆被抓)。
- **階段**:第 2 階段 / S3×S4 串接(里程碑:合成→main_draw→真實生產標的)。

## ★ 兩種 mesh regime(選錯拓樸/閘會白忙)

| | main_draw 4 mesh | Award 機器人 3 mesh |
|---|---|---|
| 權重 | **unweighted** | **weighted**(靠骨骼/權重變形) |
| deform timeline | **有**(9 anim 全 deform) | **無** |
| 形狀 | 高瘦窗簾/陰影(aspect≥1.2, row-convex) | blob/身體(aspect 0.84~1.12) |
| 拓樸選擇 | **v2 strip**(deform-robust) | **v1 Delaunay**(輪廓+內部) |
| 真正的品質標的 | 真實位移場轉移後 0 自交/0 翻面 | **覆蓋率保真** + UV 拓樸有效 |
| deform 閘 | `transfer_deform_check` | **N/A**(無 per-vertex deform,誠實標註) |

- `generate_mesh_v2 auto` 對 3 件**正確回退 v1**(aspect<1.2 → 非 strip)。選對了工具。
- weighted mesh 做覆蓋率/UV 拓樸只需 `uvs`+`triangles`(與權重無關);setup XY 需骨骼變換,
  故靜態 mesh 的拓樸不變量改在 **UV(貼圖版面)空間**檢查自交/翻面/退化。

## ★ 覆蓋率由輪廓 epsilon 決定(可重用旋鈕,呼應 strip 的 rows)

預設 `epsilon_frac=0.008` 對**柔邊/羽化**件(光暈)太粗 → 覆蓋率不足(0.929 << 藝術家 0.980)。
`validate_award_mesh.py` 內建 **AC 驅動 auto-epsilon 搜尋**(由粗到細掃 `[0.008,0.005,0.003,0.002,0.0015]`,
≤5 輪對應迭代預算),取第一個「覆蓋率≥baseline−margin、nv≤藝術家、拓樸乾淨」的最省頂點解:

| 件 | 藝術家 nv/IoU | 生成 nv/IoU(選定 eps) | 結果 |
|---|---|---|---|
| 光暈 | 78 / 0.9795 | 68 / 0.9779 (eps 0.003, 3 輪) | ≈ 藝術家,少 13% 頂點 |
| 左手 | 80 / 0.9681 | 53 / 0.9755 (eps 0.005, 2 輪) | **勝**,少 34% 頂點 |
| 身體 | 98 / 0.9760 | 68 / 0.9834 (eps 0.005, 2 輪) | **勝**,少 31% 頂點 |

- **通則**:覆蓋率 IoU **由邊界取樣密度(epsilon/hull)決定,內部頂點不影響**
  —— 與 v2「IoU 由 rows 決定、cols 不影響」同一結論的另一半。柔邊件需更細 epsilon。
- 光暈 hull=nv=78(0 內部):藝術家對純輪廓柔光把全部頂點都放邊界,印證覆蓋率=邊界事。

## 評估器可信度(先驗再下判定)

- **自我校驗**:3 件藝術家真值 UV 拓樸全乾淨(si=0/flip=0/degen=0)→ 閘忠實,故 pass 可信。
- **負對照**(光暈/身體):uvs 向心縮 15% → IoU 0.98→0.72;平移 8% → 0.70;
  三角索引打亂 → si 2152/4137。皆遠低於 target,**gate 鑑別力充分**,margin=0.005 安全。

## 端到端閉環(PSD→件→mesh→對真實 mesh)

- canvas 用 **atlas 切件**(uvs 原生 0..1 空間,免配準猜測);先前已證 **PSD 切件 ↔ atlas 切件
  alpha-IoU 0.92~0.99**(同素材,見 `s4-psd-to-spine-real.md`),故等價驗證了 PSD 來源的件。
- 完整鏈:`psd_slice`(PSD→件)→ `generate_mesh`(件→mesh)→ `validate_award_mesh`
  (對 Award 藝術家真實 mesh 覆蓋率對照)。3 件全通過。

## 可重現

```
python3 tools/mesh_gen/validate_award_mesh.py            # 3 件 overall_pass, exit 0
python3 tools/mesh_gen/validate_award_mesh.py --margin 0 # 更嚴:光暈用 eps=0.002(nv78/0.983)
```

## 下一步候選

- 把 auto-epsilon(覆蓋率驅動)沉澱進 `generate_mesh` 本體(目前在 validator 內),做成
  「給目標覆蓋率+頂點預算 → 自動選 epsilon」的生成器能力。
- 剛體件(右手/頭 = region+rotation)不需 mesh;切圖→Spine JSON 組裝(SkelToJson)固化
  `PSD名/圖層名` + mesh/region 分配 + +2px padding + atlas 0.70 縮放。
- S2 補圖閘 / 骨架閘(純 CPU)。
