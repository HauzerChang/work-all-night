# S3 端到端 — 生成 mesh 對照 Award 真實生產 mesh(光暈/身體/左手)

- **結論**:把 S3 生成器對 `Award`(機器人拆件)真實生產 spine 的 3 個 mesh 件做端到端對照,
  以**藝術家自己的 mesh** 為 IoU 真值基準。修正一個真實泛化缺口後 **3 件全 PASS**:
  生成 mesh 覆蓋率 ≥ 藝術家、頂點數 ≤ 藝術家、setup pose 0 自交/0 退化。
- **信心**:高(對真實生產標的、以藝術家 mesh 為真值、正/負向皆量化)。
- **階段**:第 2 階段 / S3(里程碑:S3 從 main_draw 4 mesh → 跨資產、跨 mesh 類型泛化)。

## 標的與性質(與 main_draw 窗簾/陰影不同類)

`robot_parts.psd` 的 3 件在 Award 中皆為 **weighted mesh**(靠骨骼權重變形,**無 deform timeline**):

| 件 | Award 真值 | 生成(v2 auto) |
|---|---|---|
| 光暈 | 78v / hull78(全邊界)/ 76t / weighted | 73v / hull38 / delaunay-v1-adaptive |
| 身體 | 98v / hull40 / 154t / weighted | 69v / hull29 / delaunay-v1-adaptive |
| 左手 | 80v / hull42 / 116t / weighted | 57v / hull30 / delaunay-v1-adaptive |

→ 這 3 件**非** strip(近方/寬、非 row-convex),v2 auto 一律回退 Delaunay(v1)。
故本輪實測的是 **v1 對真實剛體/骨綁件的泛化**,補上 main_draw(全 strip)未覆蓋的一類。

## 適用的閘(為何不套 deform 閘)

- deform 閘(`transfer_deform_check` / `real_deform_field`)需 **unweighted vertices**(Nx2)
  且需 deform timeline。這 3 件 weighted + 無 deform → **不適用**。
- 有真值可比的是:**AC1 靜態覆蓋率 IoU**、**AC3 頂點預算(vs 藝術家)**、
  **AC2 setup pose 靜態拓樸有效性**(0 自交/0 退化)。
- weighted mesh 的「變形穩健度」需 BBW 權重生成(S3 未來步驟)才可自評,本輪明確排除。

## ★ 真實泛化缺口與修正:覆蓋率由**邊界取樣密度**決定

第一輪(v1 固定 `epsilon_frac=0.008`):身體/左手 PASS,但**光暈 FAIL**
(gen IoU 0.929 < 藝術家 0.979)。查因:光暈是**柔邊圓形光暈**,Douglas-Peucker 用固定
epsilon 把圓弧簡化成 14-gon(hull=14),內縮切掉圓角 → 少 ~5% 覆蓋。藝術家反而用 hull=78
(全邊界點)密貼柔邊。

epsilon 掃描(光暈,region 496×480)證實**單調**關係,與 strip 的「IoU 由 rows 決定」同理:

| epsilon_frac | 0.008 | 0.004 | 0.002 | 0.001 | 0.0005 |
|---|---|---|---|---|---|
| hull | 14 | 22 | 38 | 58 | 115 |
| IoU | 0.929 | 0.966 | 0.983 | 0.992 | 0.996 |

**修正 = 閉環自適應邊界細分**(`generate_mesh.generate(target_iou=, vertex_cap=)`):
epsilon 由粗到細,取「達 target_iou 且頂點 ≤ vertex_cap」的最粗值;無一達標則取 cap 內最佳。
`target_iou=None`(預設)沿用固定 epsilon → **向後相容**(main_draw 4 strip 不受影響,重驗全過)。
v2 auto 的 Delaunay 回退開啟 `target_iou=0.98, vertex_cap=96`。

修正後(mode=delaunay-v1-adaptive):

| 件 | gen IoU | 藝術家 IoU | gen nv | 藝術家 nv | overall |
|---|---|---|---|---|---|
| 光暈 | 0.983 | 0.980 | 73 | 78 | ✅ |
| 身體 | 0.986 | 0.976 | 69 | 98 | ✅ |
| 左手 | 0.982 | 0.968 | 57 | 80 | ✅ |

## 教訓 / 可重用

- **覆蓋率的通用槓桿 = 邊界取樣密度**:strip 用 `rows`、Delaunay 用 `epsilon`。二者皆宜「閉環對
  覆蓋率目標自適應」,而非固定魔數 —— 固定 epsilon 對圓/柔邊件會系統性欠覆蓋。
- **生成器可比藝術家更精簡**:3 件生成頂點數 57–73 vs 藝術家 78–98,同時覆蓋率更高。
- **閘的適用性要先判**:weighted+無 deform 的件不能硬套 deform 閘(否則 crash 或假結果);
  先讀 mesh 性質(weighted?有 deform timeline?)再選閘。

## 可重現

```
python3 tools/mesh_gen/compare_award_mesh.py     # 3 件 all_pass=True, exit 0
# 回歸:main_draw 4 strip mesh 仍全 overall_pass(見 s3-four-mesh-generalization.md 指令)
```
