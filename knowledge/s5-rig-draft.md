# S5 骨架階層草案(可自動部分)— rig_draft.py

- **結論**:S5 骨架能力的**可確定性自動化部分**落地 —— 由件 alpha 重疊自動推出合法骨架階層
  + 每關節 pivot 草案,世界版面保真;把 PLAN 明示的「唯一卡死處(pivot)」及 root 選擇、
  權重綁定明確標記為**待人**。純 CPU,過 `evaluate_skeleton` 驗證為合法骨架樹。
- **信心**:中高(自動部分確定性且經骨架閘 + 版面保真驗證;主觀部分誠實外包給人)。
- **階段**:第 2 階段 / S5(自動部分)。

## 自動 vs 待人(誠實界定)

**自動(確定性)**:
1. 件畫布 alpha 重疊圖(重疊像素數)。
2. 從 root BFS 生成樹:parent = 通往 root 路徑上與它重疊的件(重疊大者優先)。
3. 關節 pivot 草案 = 件與其 parent 的**重疊區質心**(肢體接到軀幹的接點)。
4. 重寫 bones 成父子鏈:bone local x/y 由 parent 世界位置反推 → **世界位置不變、版面保真(±0.5px)**。

**待人(A 類岔路,已 flag)**:
- **root 件選擇**:預設取重疊度最高;**背景件(如光暈,重疊度=4 與身體並列、面積最大)會誤選**
  → 需 `--root` 覆寫(robot 用 `--root 身體` 得合理階層:身體=root,頭/雙手/光暈為子)。
- **每關節 pivot 精確微調**(草案給重疊質心,`_needs_human_pivot=true`)。
- **mesh 權重綁定(BBW)**:目前 attachment 仍 unweighted;綁定為後續步驟。

## 為何這樣切分

PLAN 結論:**骨架 pivot 是唯一真正卡死、需人集中處理處**;別用 ML 學沒有唯一解的美術決定。
故 rig_draft 只自動化「可被幾何確定性算出」的連接與接點候選,主觀 pivot/root/權重交回人,
符合 L2 自主(客觀全自動、主觀留人)。

## 驗證

- robot_parts:`skeleton_valid=True`(過 evaluate_skeleton:單一 root/無環)。
- 自動 root=光暈(背景件,示範 root 需人確認);`--root 身體` → 合理階層 + 世界位置保真 ±0.5px。

## 可重現

```
python3 tools/mesh_gen/rig_draft.py assets/robot_parts.psd --prefix 機器人拆件 --root 身體 -o /tmp/rig.json
```

## 使用者決策(2026-07-01)+ pivot 可人為調整(已實作)

- **決策 1 root=身體(B 方案)** — 使用者確認(圖示 `knowledge/figures/s5_rig_decision.png`);已固化成
  `assets/robot_parts.rig.json`。**決策 2**:pivot 先用草案當起點,並要求工具提供人為調整功能。
- **pivot 升級為「功能性旋轉中心」**(非僅註記):`build_rig` 現把**非 root 件的 bone 原點設在 pivot**,
  並將 attachment 幾何平移 `(件中心 − bone原點)` → **bone 繞 pivot 旋轉,且 θ=0 版面完全保真**
  (rig 前後每頂點世界位置差 **0.006px**;pivot == bone 世界原點,經驗證)。
- **人為調整介面**:
  - `--emit-config <path>`:輸出可編輯 rig-config 範本(預填 root + 草案 pivot 的**圖素座標**,人依圖改數值即可)。
  - `--rig-config <path>`:載入 `{"root":件名,"pivots":{件名:[px,py]}}`,覆寫 root 與逐關節 pivot(缺者用草案)。
  - 產出仍過 `evaluate_skeleton`(合法骨架樹)。
- 這實現 L2 自主的「客觀自動 + 主觀留人可調」:連接/生成樹/草案 pivot 自動;精確 pivot/root 由人透過 config 定。

## 下一步

- **weighted mesh 綁定(BBW)** 把 unweighted mesh + rig 骨架接起來(S5 剩餘可自動部分);用 `evaluate_skeleton`
  AC3 驗權重合法。
- 人微調 pivot(改 `robot_parts.rig.json`)後,配動畫 timeline → 逼近目標運動(S1 影片反推的下游)。
