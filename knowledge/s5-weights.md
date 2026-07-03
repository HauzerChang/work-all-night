# 權重(weighted mesh)— envelope 綁定 + LBS 變形閘,資產「動起來」

- **結論**:S3 最後一塊完成。`weights.py`(envelope 綁定:own+parent 關節 smoothstep 混合)
  + `skel_to_json --weights` + `validate_weights.py`(格式/變形掃描/**錨定** AC + pose 渲染)。
  左手 weighted mesh:±40° 旋轉掃描 **0 自交/0 翻面**、錨定位移比 **0.395**(剛性負對照=1.0)。
  pose 渲染證實**整隻機器人可動**(雙臂+頭,肩部不脫離)→ 「靜態資產→可動資產」閉環。
  證據:`knowledge/figures/robot_pose_strip.png`。
- **信心**:中高(幾何閘+錨定閘+視覺驗證;但僅一個 weighted 件、僅 2 骨混合,未及藝術家的
  子件級變形骨)。
- **階段**:第 2 階段 / S3 權重 + S5 綁定(兩者在此交會)。

## Award 藝術家權重真值(設計依據)

| mesh | 影響骨 | 每頂點骨數 | 混合頂點 | 權重和 |
|---|---|---|---|---|
| 光暈 78v | 4 根**部位骨**(3/4/5/6)— 跟著全身動 | ≤3, mean 1.58 | 38/78 (49%) | =1 |
| 身體 98v | 自身 + **4_LEG7/8(肩部輔助,子件級)** | ≤3, mean 1.63 | 60/98 (61%) | =1 |
| 左手 80v | 自身 + **4_LEG9(前臂,子件級鏈)** | ≤2, mean 1.49 | 39/80 (49%) | =1 |

**pattern**:和恰 1、稀疏(≤3)、混合只在局部;剛性為主。接縫頂點次要骨最高 0.84 → 我們 wmax=0.85。

## v1 設計(own + parent envelope)

- 有 parent 的 mesh 件:關節(draft pivot)半徑 R 內 smoothstep 混向 parent(最高 0.85),
  核心區剛性。R = 2.5 × sqrt(關節重疊面積/π)。次要權重 <0.01 捨去(保稀疏)。
- bind 座標 = 頂點世界 − 骨世界(本骨架 rotation 全 0)。
- 本資產只有左手符合(光暈=effect、身體=trunk 無 parent;頭/右手=region 剛體,與藝術家一致)。

## 驗證(全 PASS)

| AC | 結果 |
|---|---|
| 格式 | 和 ∈[1,1]、≤2 影響、索引合法 |
| 變形掃描(±15/25/40°)| 全部 0 自交/0 翻面/0 退化 |
| **錨定**(混合的存在意義)| 高 parent 權重頂點位移 = 剛性綁定的 **0.395**(tol 0.6;剛性=1.0 天然負對照) |
| 組裝(weighted)| 位置 0.001px、光柵 0.031(LBS 反推影像框)、骨架閘過 |
| pose 渲染 | 雙臂 ±22°+頭 ±8°:肩部連接、無破圖(視覺) |

## pose 渲染器(副產品,`validate_weights.render_pose`)

給 `{件名: 角度}` → 全件重繪(weighted=LBS、unweighted mesh=剛性、region=剛性;
旋轉沿骨階層傳遞)→ 逐三角 affine warp 貼圖。**這是後續「對目標影片逼近」迴圈的
渲染引擎雛形**(S1 之後:影片幀 ↔ pose 渲染幀比對)。

## 範疇外(誠實邊界,依證據標記)
1. **子件級變形骨**(藝術家的肩部輔助 4_LEG7/8、前臂 4_LEG9):「件內要再分幾節」需運動
   資訊(S1 反推)或人指定 — 單張平面圖推不出。
2. **效果件跨件綁定**(光暈綁 4 根部位骨、隨全身變形):特效歸屬的全域決策(A 類)。
   v1 光暈剛性 → 大擺動時光暈不跟手,視覺可接受度留人審。
3. LBS 直接了當;未做 BBW(需要件內多骨才有意義 — 等 1. 解鎖後升級)。
4. 渲染器是近似(逐三角 affine、最近鄰 z 合成),非 Spine runtime;實載驗仍待離線 runtime。

## 可重現
```
python3 tools/mesh_gen/skeleton_draft.py -o /tmp/robot_draft.json
python3 tools/mesh_gen/skel_to_json.py --draft /tmp/robot_draft.json --weights \
        --out /tmp/robot_asset/robot_weighted.json --eval          # 組裝 4AC
python3 tools/mesh_gen/validate_weights.py                          # 權重 4AC,exit 0
python3 tools/mesh_gen/validate_weights.py --render-pose '{"左手":-22,"右手":14,"頭":-8}' --pose-out /tmp/p.png
```
