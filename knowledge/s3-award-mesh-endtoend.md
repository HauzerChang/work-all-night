# S3 端到端驗收 — PSD 件 → generate_mesh_v2 → 對照 Award 真實生產 mesh

- **結論(里程碑)**:把「PSD 切件 → S3 mesh 生成」對**真實生產 mesh**(Award big win 機器人)
  端到端驗收。3 個 mesh 件(光暈/身體/左手)生成 mesh **覆蓋率全數達到或超過藝術家真值**,
  且用 **31~48 頂點(藝術家用 78~98)** —— 覆蓋率相當、頂點省 ~40~60%,靜態 AC 全過。
- **信心**:高(對真實生產 mesh 有 ground truth uv 可逐件比對;正/負向都測過)。
- **階段**:第 2 階段 / S3 端到端(接續 S4 真實 PSD 驗收)。

## 方法

1. `psd_slice.py` 切 `robot_parts.psd` → 各件原解析度 alpha PNG(光暈 706×683 / 身體 379×425 / 左手 257×215)。
2. `generate_mesh_v2.generate(mode="auto")` 生成 mesh(3 件 aspect < 1.2 或非 row-convex → 走 v1 Delaunay 分支)。
3. 對照 `Award.json` 同名 slot 的真實 mesh:
   - **Award mesh 的 `uvs` 為 region-local 0..1**(Spine runtime 再用 atlas region u,v 映射到貼圖頁),
     故可直接 `uv*(W,H)` 疊回 PSD 切件 alpha 重建藝術家覆蓋 → `artist_iou`(真值 baseline)。
   - 生成 mesh 用 `evaluate_mesh` 量 IoU + 拓樸。
4. 工具:`tools/mesh_gen/compare_award_mesh.py`(可重現)。

## 量化結果

| 件 | 生成 IoU | 生成頂點 | 藝術家 IoU | 藝術家頂點 | 達標 | 靜態AC |
|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | 0.9641 | 31 | 0.9486 | 78 | ✅ | 全過 |
| 機器人拆件/身體 | 0.9828 | 47 | 0.9477 | 98 | ✅ | 全過 |
| 機器人拆件/左手 | 0.9796 | 48 | 0.9768 | 80 | ✅ | 全過 |

`compare_award_mesh.py` summary:`all_static_ac_pass=True, all_iou_meets_artist=True`。

## 關鍵發現 / 教訓

1. **IoU 純由 hull(邊界)密度決定,內部點數不影響覆蓋率** —— 對 v1 Delaunay 分支再次驗證,
   與 v2 strip 的「rows 決定 IoU、cols 不影響」是**同一原理**(跨兩種生成器家族一致)。
   → 調 `epsilon_frac`(Douglas-Peucker 容差)即可移動覆蓋率;內部點只助變形平滑。
2. **v1 預設 epsilon=0.008 是為窗簾(strip)調的,對 compact blob 太粗**(光暈/左手覆蓋率差藝術家 ~1.5%)。
   `generate_mesh_v2` 的 blob-fallback 改用 `blob_epsilon=0.004` + `blob_interior=18`
   → 3 件在 **≤64 頂點預算內**達藝術家覆蓋率。v1 自身 default 未動(保住 legacy 窗簾路徑)。
3. **加 orphan 清理(`drop_orphans`)**:filter_triangles 後可能留下「未被任何三角用到的內部點」
   (光暈環狀凹處),違反 AC2c。清理只丟內部孤兒(hull 點在約束三角化恆被 segment 使用),
   不破壞「hull 排最前」不變式 → 光暈由 nv33→31、AC2c 過。
4. **Award mesh uvs 是 region-local**(非 atlas-page):range≈0..1,`uv_flip_v_used=false`
   → PSD 切件與 spine mesh **幾何級對齊**(v 不需翻),再次獨立確認 PSD↔spine 同素材(前為 texture alpha-IoU)。
5. 這 3 件在 Award **無 deform timeline**(靠骨骼權重變形),故真實 deform 閘 N/A;本輪聚焦靜態覆蓋率對照。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd --eval   # 先確認切件無損
python3 tools/mesh_gen/compare_award_mesh.py                        # 端到端對照(需先切件到 scratchpad/robot_parts)
```

## 副記:shadow2 region 共用

`main_draw` 的 `image/shadow2` attachment 其 `path=image/shadow`(與 shadow 共用同一 atlas region)。
故 `validate_against_real --name image/shadow2` 會在 atlas 找不到 region;需以 region **path** 取貼圖。
curtain_left/right + shadow(獨立 region)v2 驗證全過,S3 結論不受影響。

## 下一步

- 把慣例固化成「件 → Spine JSON」組裝工具(SkelToJson):`<PSD名>/<圖層名>` slot 命名、
  size+2px padding、mesh/region 依需求分配、blob 用 v1(epsilon 0.004)/ strip 用 v2。
- 之後補 S2 補圖閘 / 骨架閘。
