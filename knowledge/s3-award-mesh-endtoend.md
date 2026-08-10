# S3 端到端驗收 — PSD件 → S3 mesh 對照真實生產 mesh(Award)

- **結論**:對機器人拆件的 3 個真實生產 mesh(`光暈`/`左手`/`身體`),用 Award atlas 切出的真實 alpha
  跑 S3 生成器,在**對齊藝術家頂點成本**(以其頂點數當預算、自適應 epsilon)下,生成 mesh 的輪廓覆蓋率
  (IoU vs 真實 alpha)**全部 ≥ 藝術家自身 mesh**,拓樸乾淨(0 退化/0 孤兒/重心全在內)。
  → 端到端「PSD→件→mesh」對真實生產標的驗收 **PASS**(里程碑:從 main_draw 合成/窗簾 → 真實 big win 主角件)。
- **信心**:高(真實生產貼圖 + 藝術家 mesh 為 ground truth + 正對照全過)。
- **階段**:第 2 階段 / S3 端到端(串接 S4 切件 → S3 mesh)。

## 驗收結果(`validate_award_mesh.py`,對齊藝術家頂點成本)

| 件 | 藝術家 IoU (v) | 生成 IoU (v, hull) | IoU≥藝術家 | 頂點≤藝術家 | 拓樸 |
|---|---|---|---|---|---|
| 光暈 | 0.9795 (78) | **0.9856** (78, h43) | ✓ | ✓ 78≤78 | ✓ |
| 左手 | 0.9681 (80) | **0.9940** (80, h56) | ✓ | ✓ 80≤80 | ✓ |
| 身體 | 0.9760 (98) | **0.9946** (97, h57) | ✓ | ✓ 97≤98 | ✓ |

指令:`python3 tools/mesh_gen/validate_award_mesh.py`(exit 0 = all_pass)。

## 三個關鍵發現

### 1. 輪廓解析度(epsilon)是 blob mesh 的 IoU 主槓桿;interior 密度近乎無關
掃描(eps 0.008→0.001 × max_interior 40/64):IoU 幾乎只隨 hull 輪廓密度上升,`max_interior`
加內部點對 IoU 無感(甚至微降)。**這是 strip 路徑「IoU 由 rows(邊界)決定、cols(內部)不影響」
在 Delaunay 路徑的對應版**——兩條生成路徑統一於同一原則:**覆蓋率由邊界取樣密度決定**。
→ 新增 `generate(target_verts=N)`:二分搜 epsilon 使頂點數 ≤ N 且盡量貼近,直接用頂點預算反推輪廓解析度。

### 2. 固定 64 頂點預算對「大而高保真」的生產件過緊
main_draw 窗簾藝術家僅 21v,故 AC3=64 夠用;但這 3 件藝術家用 78–98v。要對齊其覆蓋率就需相稱的
頂點數。**公平的 AC 是「相對藝術家頂點數」而非絕對常數**:本驗收改判「IoU≥藝術家 且 頂點≤藝術家」
(等成本或更省下達到等或更好覆蓋)。

### 3. Award 機器人 mesh 是 **weighted 且無 deform timeline**
(修正先前假設)`光暈/左手/身體` 的 `vertices` 長度 ≈ uvs 的 7×(多骨綁定攤平格式),且 9 支動畫**皆無**
這些 slot 的 deform timeline → 它們靠**骨骼權重**變形,非逐頂點 deform。
**推論**:對這類件**無真實逐頂點位移場可轉移**,`transfer_deform_check` 不適用(那是 unweighted+deform
資產如窗簾才有的真值);此處正確的閘是**靜態幾何**(輪廓覆蓋 + 拓樸)。deform 穩健性對 weighted 件
需另走「骨綁定 + pose」路線(未來 S5 骨架/權重能力再驗)。

## 修掉的 bug(有真值才抓得到)

`generate_mesh.filter_triangles` 依「重心在 mask 內」剔除凹形外三角後,可能留下**不被任何三角引用的
孤兒頂點**(AC2c 破)。原 4 mesh(窗簾走 strip、無此路徑)從未觸發;**光暈(凹形 glow,走 Delaunay)
才暴露**。修法:新增 `prune_orphans()` 在 filter 後移除孤兒並重編索引,保「hull 排最前」(n_hull 重算為
存活 hull 頂點數)。回歸:main_draw 4 mesh(strip)+ v1 delaunay 路徑全維持 PASS。
**教訓**:合成/單一資產測不到的路徑,換真實多樣件就會踩到 → 端到端對真實標的驗收有獨立價值。

## 可重現

```
python3 tools/mesh_gen/validate_award_mesh.py         # 3 件 all_pass, exit 0
python3 tools/mesh_gen/generate_mesh.py <png> --out m.json   # 預設 epsilon
# 程式內:generate(path, target_verts=80) → 自適應 epsilon 對齊頂點預算
```

## 下一步

- 把「PSD 切件 → S3 mesh(target_verts 對齊)→ Spine attachment(命名 `PSD名/圖層名` + 2px padding)」
  固化成 SkelToJson 組裝工具(候選 #2),端到端產出可載入的 Spine JSON。
- weighted 件的變形驗證需 S5(骨架/權重);目前對這類件只保證靜態幾何。
