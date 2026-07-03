# S3×S4 端到端:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把 S4(PSD 切圖)接到 S3(mesh 生成),對**真實生產標的**(Award「機器人拆件」3 個
  mesh 件:光暈/身體/左手)端到端驗收 **全 PASS**。自動生成 mesh 的**靜態覆蓋率 IoU ≥ 藝術家
  生產 mesh**(margin 0.01),頂點數相近或更省,格式/品質閘全過。
- **信心**:高(對真實生產 spine 的藝術家 mesh 做 ground-truth 對照 + 格式閘 + 自我修正收斂)。
- **階段**:第 2 階段 / S3×S4 串接(里程碑:PSD→件→mesh 對真實標的閉環)。
- **工具**:`tools/mesh_gen/validate_psd_to_mesh.py`(標準指令見末)。

## 結果(robot_parts.psd → generate_mesh_v2 → 對照 Award.json)

| 件 | gen 模式 | gen nv | gen IoU | 藝術家 nv/hull/tris | 藝術家 IoU | 覆蓋 | 格式 | overall |
|---|---|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1(eps=0.004) | 60 | 0.9643 | 78 / 78 / 76 | 0.9486 | ✅ | ✅ | ✅ |
| 身體 | delaunay-v1(預設) | 60 | 0.9660 | 98 / 40 / 154 | 0.9477 | ✅ | ✅ | ✅ |
| 左手 | delaunay-v1(eps=0.004) | 100 | 0.9796 | 80 / 42 / 116 | 0.9768 | ✅ | ✅ | ✅ |

→ 三件生成 mesh 覆蓋率皆**達到或超過**藝術家生產 mesh,頂點預算內。

## ★ 關鍵發現

### 1. 變形機制與 main_draw 不同 → 變形閘 N/A(但靜態真值可比)
- **main_draw 窗簾/陰影** = **unweighted + deform timeline**(逐頂點 deform)→ 可用真實位移場轉移閘
  (`deform_eval.transfer_deform_check`)驗變形穩健。
- **Award 機器人件** = **weighted(骨綁,`len(vertices)≠len(uvs)`)+ 全 12 anim 皆無 deform timeline**
  → 變形靠**骨骼/權重**,無位移場可轉移 ⇒ 本標的的變形閘 **N/A**。
- ⇒ 對 weighted 件,可對照的真值是**靜態覆蓋率 + 拓樸品質**;weighted 變形穩健度需 **BBW 權重**
  (S3 後續子能力,PLAN 已列「+ BBW 權重」),不在本閘。**這修正了「所有 mesh 都用 deform 場驗」的隱含假設。**

### 2. `epsilon_frac` 由外形複雜度決定 → 覆蓋率驅動的自我修正
- 生成器預設 `epsilon_frac=0.008` 是為 main_draw 簡單外形(矩形窗簾)調的;**器官狀/不規則邊界**
  (光暈是實心不規則光團,中心 alpha=255、bbox 覆蓋率僅 0.465,非空心環)在 0.008 下**邊界欠取樣**
  → 覆蓋率 0.90~0.93 落後藝術家。
- 收斂 epsilon 階梯(0.008→0.004→0.002→0.001)後,0.004 即讓光暈達 0.964(nv 60,vs 藝術家 78)。
- `validate_psd_to_mesh.py` 內建此**覆蓋率驅動的 epsilon 細化**(≤4 輪,符合 RULES 5 輪預算),
  自動收斂到藝術家基準,無需人工調參。

### 3. 生成器 bug:凹形件過濾三角後留內部孤兒頂點 → 已修
- v1 對凹形/不規則件三角化後,`filter_triangles`(重心在 mask 外的三角丟棄)會**孤兒化內部點**
  (光暈 eps=0.004 有 3 個內部孤兒,`evaluate_mesh` AC2c 抓到 → 格式 fail)。
- 修法:`generate_mesh.prune_orphans()` — 移除未被任何三角使用的頂點並重新索引。孤兒只發生在
  內部點(hull 被 `segments` 約束必連),故 **hull 順序與數量不變**(Spine hull-first 格式保住)。
- 修後三件孤兒=0、格式全過。**教訓:凹形是 mesh 生成的通用陷阱,覆蓋率高不代表拓樸乾淨。**

## 揭示的真實生產慣例(補充 s4-psd-to-spine-real.md)
- 藝術家 mesh 皆 **weighted**;不規則發光件(光暈)用**全 hull 環狀**拓樸(78v 全 hull、76 tris),
  身體/左手用 hull+內部點(hull 40/42、內部 58/38)。我們的 Delaunay 拓樸不同但覆蓋率相當。
- 頂點數量級一致(藝術家 78~98、我們 60~100),證明自動拓樸在**精簡度**上也對齊生產標準。

## 可重現
```
python3 tools/mesh_gen/validate_psd_to_mesh.py        # 3 件全 overall_pass,exit 0
# 自訂:--psd --skeleton --parts 光暈 身體 左手 --slot-prefix 機器人拆件/ --margin 0.01 --budget 128
```

## 下一步候選
- 把「件→Spine mesh attachment」寫出(SkelToJson):用本閘達標的 mesh + `PSD名/圖層名` slot 慣例
  + size+2px padding,端到端產出可載入 Spine JSON(接 S4 下游、PLAN option 2)。
- weighted 變形:實作 BBW 權重(需骨架)→ 才能對 Award 這類 weighted 件驗變形穩健(需 S5 骨架先行)。
