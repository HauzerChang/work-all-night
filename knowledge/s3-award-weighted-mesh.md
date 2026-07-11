# S3 端到端對照 Award(第二個真實骨架)+ weighted mesh 發現

> 結論優先。信心:高(有真實生產真值 + 量化閘 + 回歸)。階段:第 2 步(S3 鍛鍊)。日期:2026-07-11。

## 一句話

把 S3 mesh 生成器**推廣到第二個真實生產骨架 Award 的 3 個機器人 mesh 件**做端到端
「atlas 切件 → `generate_mesh` → 對照藝術家 mesh」靜態驗收:修正 v1 兩個缺陷後
**3 件覆蓋率 IoU 全 >0.988、全數超過藝術家自身基準**。過程發現一個重要事實:
**Award 生產 mesh 全為 weighted**,現有 deform 閘只支援 unweighted。

## 關鍵發現

### 1. 生產 mesh 是 weighted(main_draw 是特例)
- Award 3 個 mesh 件(`機器人拆件/身體` 98v、`左手` 80v、`光暈` 78v)**全部 weighted**:
  `vertices` 為 `[boneCount, boneIdx,bindX,bindY,weight, ...]` 變長格式,`len(vertices) != len(uvs)`。
- 相對地,`main_draw` 的 4 個 mesh **全 unweighted**(此前所有 deform 工具的隱含假設)。
- 影響:`deform_eval.real_deform_field / transfer_deform_check` 直接把 `vertices` 當
  `nv×2` reshape,對 weighted 會 `ValueError: different number of values and points` → crash。
  `validate_against_real`(含 deform 閘)因此**不能直接用於 Award**。
- **靜態覆蓋率比對只用 `uvs`+`triangles`,與加權無關** → 仍可做,故本次走靜態路線
  (新工具 `compare_award_static.py`)。weighted deform 支援列為下一 chunk(需 setup-pose 骨架世界變換求解器)。

### 2. v1 邊界容差:相對周長 → 絕對像素(尺度不變)
- 舊 `boundary_points` 用 `epsilon_frac × perimeter`。大件(光暈 480px blob,周長大)→ 容差變大 →
  Douglas-Peucker 抄捷徑 → hull 只剩 14 點、IoU 0.929(掉到藝術家基準 0.9795 之下)、且產生孤兒頂點。
- 改成**固定像素容差** `epsilon_px`(預設 2.0)後,大小件邊界密度一致。掃描(Award 3 件):
  | eps_px | 光暈 IoU/nv | 身體 IoU/nv | 左手 IoU/nv |
  |---|---|---|---|
  | 1.5 | 0.9943 / 108 | 0.9930 / 81 | 0.9904 / 66 |
  | **2.0** | **0.9918 / 90** | **0.9925 / 77** | **0.9884 / 61** |
  | 3.0 | 0.9874 / 81 | 0.9876 / 71 | 0.9804 / 56 |
  - eps_px=2.0 為預設:IoU 全 >0.988、頂點數 ≈ 或少於藝術家(90/77/61 vs 78/98/80)。

### 3. v1 孤兒頂點缺陷 → 加 `drop_orphans`
- `filter_triangles` 丟掉重心落在 mask 外的三角時,可能孤立掉某頂點(光暈舊 eps 下出現 1 個)。
- 新增 `drop_orphans()`:移除未被引用頂點、重編索引、依保留數重算 `hull`。
  因 used 升序且 hull 索引在最前段,**「hull 排最前」不變式維持**。
- 驗證:強制 coarse eps=12(舊會留 1 孤兒)→ 現 orphans=0、格式合法、索引在範圍內。

### 4. strip 模式不適合 blobby 件(再確認 v2 分工)
- 對 Award 3 件(近方形、row-convex)強制 strip:即使 r18c7(126v)IoU 也只 0.92~0.95,劣於 v1。
- 印證:**strip 專為高長寬比、需耐單向拉伸的件(窗簾);blobby/圓形件用 v1 Delaunay**。auto gate 維持不變。

## 驗收數據(端到端,margin=0.02)

| 件 | weighted | 藝術家基準 IoU | 生成 IoU | 生成 nv(藝術家 nv) | 通過 |
|---|---|---|---|---|---|
| 機器人拆件/身體 | ✔ | 0.9760 | **0.9925** | 77 (98) | ✅ |
| 機器人拆件/左手 | ✔ | 0.9681 | **0.9884** | 61 (80) | ✅ |
| 機器人拆件/光暈 | ✔ | 0.9795 | **0.9918** | 90 (78) | ✅ |

**藝術家基準 IoU 全 0.96~0.98(非 1.0)**:證明用 `uvs×[W,H]` 光柵化藝術家 mesh 與 atlas 切件 alpha
對得上 → 也**再次確認 atlas_crop 的 CW derotate + 多頁選頁正確**(第二骨架、含 3 個 rotate 件)。

## 回歸(確認無破壞)

- main_draw 4 mesh `--gen v2`:curtain_left/right、shadow 全 `overall_pass`(deform 乾淨)。
  (`image/shadow2` 與 `image/shadow` 共用同一 attachment/region → 用 name=shadow2 取 region 不存在,
  為既有資產事實,非本次回歸。)
- main_draw `--gen v1` curtain_left:改用 eps_px=2.0 後 IoU 0.98→**0.9963**、deform 仍乾淨。

## 產出 / 指令

- 新增 `tools/mesh_gen/compare_award_static.py`
  (`python3 tools/mesh_gen/compare_award_static.py` → 3 件靜態端到端閘,退出碼 = all_pass)。
- 改 `tools/mesh_gen/generate_mesh.py`:`boundary_points` 絕對像素容差、新增 `drop_orphans`、
  `generate(epsilon_px=2.0)`、CLI `--epsilon` 語意改為像素。

## 下一步(見 STATE)

**weighted-mesh deform 支援**:需 setup-pose 骨架世界變換求解器(逐骨 local rotate/translate/scale/shear
沿父鏈組合 → 求 weighted 頂點世界座標 + 真實 deform)。有了它才能把 deform 閘(0 自交/翻面)
推廣到 Award,完成「PSD→件→mesh」對生產真值的**動態**端到端驗收。
