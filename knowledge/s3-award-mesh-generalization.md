# S3 端到端驗證：真實生產件 → mesh → 對照 Award 藝術家 mesh

> 結論：**S3 `generate_mesh_v2` 泛化到真實生產機器人身體零件成功**（光暈/身體/左手 3 個 mesh，
> IoU ≥ 藝術家、頂點數 ≤ 藝術家、setup 拓樸乾淨）。過程校準出 v1 Delaunay 預設 epsilon 對曲折
> 有機輪廓太粗 → 改 epsilon=0.002 為 v2 fallback 預設。
> 信心：**高**（有真值對照 + 負向前後比較）。相關階段：S3 / S2 評估器。日期：2026-07-11。

## 標的與差異

`robot_parts.psd` 5 件 ⇄ Award spine slot `機器人拆件/{光暈,右手,頭,身體,左手}`。其中 **3 個是 mesh**：

| slot | 藝術家頂點 | 三角 | hull | 型態 | atlas 頁 / rotate |
|---|---|---|---|---|---|
| 光暈 | 78 | 76 | 78（全 hull，環狀） | weighted | Award2.png / rotate |
| 左手 | 80 | 116 | 42 | weighted | Award.png / 正 |
| 身體 | 98 | 154 | 40 | weighted | Award2.png / rotate |

**與 main_draw 窗簾/陰影的關鍵差異**：這 3 件是 **weighted（骨骼權重驅動）、無 deform timeline**；
main_draw 4 mesh 是 **unweighted + deform timeline**。→ 是不同拓樸類別，適合驗 S3 泛化。

## 驗證流程（純 CPU、有真值、可自驅）

`tools/mesh_gen/validate_award_mesh.py`：
atlas 切件（含 rotate 還原）→ `generate_mesh_v2`（auto）→
① 覆蓋率 IoU 對照藝術家 mesh 自身覆蓋率 ② setup pose 拓樸乾淨。

- **auto 模式對這 3 件全走 Delaunay-v1**（aspect 0.84~1.12 < 1.2，非 strip）——
  正確：這是緊湊有機件，不是窗簾直條。strip 只適用高瘦 row-convex 件。
- **deform 閘不適用**：無 deform timeline，不能用真實位移場轉移（會是零場、trivially pass）。
  骨骼驅動變形驗證需重建骨層級 + 動畫 transform → 後續獨立工作塊。本閘只驗靜態覆蓋率 + setup 拓樸。

## 發現與校準：v1 epsilon 對有機輪廓太粗

epsilon 掃描（覆蓋率 IoU vs 藝術家 baseline，PASS = gen ≥ artist）：

| slot | artist IoU | eps=0.008(舊預設) | 0.004 | **0.002** | 0.001 |
|---|---|---|---|---|---|
| 光暈 | 0.979 | 0.929 ✗ | 0.966 ✗ | **0.983 ✓ (73v)** | 0.992 (92v) |
| 左手 | 0.968 | 0.960 ✗ | 0.982 ✓ | **0.991 ✓ (67v)** | 0.996 (107v) |
| 身體 | 0.976 | 0.968 ✗ | 0.986 ✓ | **0.993 ✓ (77v)** | 0.995 (100v) |

- 舊預設 0.008（為近乎直邊的窗簾調的）Douglas-Peucker 簡化太粗，曲折有機輪廓覆蓋率掉 0.05（光暈最嚴重）。
- **eps=0.002 對 3 件全達/超藝術家覆蓋率，且頂點數 ≤ 藝術家**（73/67/77 vs 78/80/98）。
- 0.001 過細（頂點爆到 92~107，超過藝術家）→ 不採。
- 覆蓋率主要由**邊界簡化容差**決定（hull 點數），內部點影響小 —— 與 S3 strip「IoU 由 rows 決定」同源道理。

**改動**：`generate_mesh_v2.generate(..., epsilon=0.002)`，只作用於 Delaunay fallback 路徑
（strip 路徑不受影響，已回歸驗證：curtain_left/right/shadow 仍 mode=strip、overall_pass）。

## 副產：atlas_crop CW 還原在 Award 上獲外部確認

光暈/身體是 **rotate 件**（存在 Award2.png）。切件後藝術家 UV 疊回去 artist_iou 得 0.98
→ 若 derotate 方向錯，藝術家 mesh 對不上 alpha、IoU 會塌。這是對 2026-06-26「CCW→CW 方向修正」
的**獨立第三方確認**（先前靠 PSD 切件 alpha-IoU，這次靠藝術家 UV 幾何）。

## 最終結果（`validate_award_mesh.py`，全 overall_pass）

| slot | mode | gen v/tri/hull | IoU vs artist | setup si/flip/degen |
|---|---|---|---|---|
| 光暈 | delaunay-v1 | 73/106/38 | 0.983 ≥ 0.979 ✓ | 0/0/0 ✓ |
| 左手 | delaunay-v1 | 67/89/43 | 0.991 ≥ 0.968 ✓ | 0/0/0 ✓ |
| 身體 | delaunay-v1 | 77/115/37 | 0.993 ≥ 0.976 ✓ | 0/0/0 ✓ |

## 待續

- **骨骼驅動變形閘**（weighted mesh 在動畫下的拓樸穩健）：需重建 Award 骨層級 + 動畫 transform，
  對 weighted mesh 逐幀 computeWorldVertices，再跑自交/翻面檢查。這是 S3 對「無 deform、靠骨」件的
  真正變形驗證缺口。
- **生成 weighted mesh**：目前 S3 產 unweighted;真實生產件多為 weighted。BBW 權重(PLAN S3)未實作。
