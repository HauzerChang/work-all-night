# S5(b) — 推斷 pivot → Spine 骨骼父子鏈,寫入 build_spine

> 里程碑 2026-08-29(接續同日 s5-rig-pivot-inference.md 的接觸縫 pivot 推斷)。
> 把「關節 pivot」從一個座標,接成**可載入 Spine 的關節鏈**:子件骨座落關節、parent 到父件骨。
> 這是 S5 rig-pivot 區塊由「單點 pivot」邁向「素材會動且關節正確」的關鍵一步。

## 解決的問題

`build_spine.py` 原本把**每個件的骨各自綁 root、擺在件的影像中心**(flat rig)。
後果:轉某肢 = 繞該件自己的中心自轉 → 頭原地打轉、脫離身體;根本沒有「關節」概念。
真正的 rig 需要:**子件骨落在關節 pivot、且 parent 到父件骨**。如此:
- 轉子件骨 = 繞關節旋轉(頭繞脖子、手繞肩膀)—— 正確關節行為。
- 轉父件骨 = 整條子樹跟著剛體位移 —— 肢體正確掛在父件上。

## 產出

| 檔案 | 角色 |
|---|---|
| `tools/rig/build_rig.py` | 通用**骨鏈建構器 + 姿勢求值器**(確定性、純 CPU,無瀏覽器)。`build_bone_chain(parts_world, tree, pivots)` → Spine bones(x,y 為相對父骨局部座標)+ 件→骨名 + 件局部多邊形;`part_world(part,…,pose)` 用骨鏈合成算變形後世界點;`fixed_point_of_rotation` 由旋轉前後點雲解不動點(關節)。世界變換重用 `weighted_deform_eval`,與真實 Spine 3.8 對齊。|
| `tools/rig/validate_rig_tree.py` | **接合閘**(真值=Award 機器人 rig)。4 AC 全 PASS。|
| `tools/analyzer/build_spine.py --rig-tree` | 端到端:子件骨落推斷關節 pivot、parent 到父件(body)骨;region/unweighted-mesh 件皆補償 attachment 偏移使 setup 不變。|
| `tools/analyzer/validate_build.py`(升級) | round-trip 重建器改為**合成骨鏈世界變換 + 讀 region attachment x,y 偏移**;對 flat rig 退化為舊行為(向後相容,robot rgb_mae 0.031 不變)。|

## 接合閘 4 AC(`validate_rig_tree.py`,全 PASS)

- **AC1 setup round-trip**:jointed rig 在 setup(全骨 identity)重建的件世界點雲 == 原件世界點雲。
  max 位移 7.6e-4 px(骨座標 3 位小數捨入下限,< 0.01 px 閾)。**接骨鏈不移動任何件**。
- **AC2 關節行為正確**:逐子件「轉自己骨」θ=25°,解剛體旋轉不動點,落在藝術家真值關節上
  (max err/rig=0.051 < TAU=0.10);中位 jointed 21.6px **< flat rig 43.0px**(flat 骨在件中心 → 不動點=質心)。
  用**中位**而非逐件:緊湊肢體(右手)質心偶爾恰近其關節(17px),逐件宰制是灌水,中位才是誠實集體宣稱
  (與 `validate_pivots` AC2 同基準)。
- **AC3 父件繼承**:轉「身體(根件)」骨 → jointed rig 子件跟著動(位移 min 75.7px)且**全機維持剛體**
  (件間距最大變化 1.7e-13);flat rig 子件**完全不動**(各綁 root 不繼承)→ 脫節。證明骨鏈把肢體正確掛上父件。
- **AC4 泛化界定(誠實)**:實查 Award slots → **僅機器人被拆件**(`機器人拆件/*`),
  OMG/SUP/MEG 角色為**單一 slot 無拆件**。故接觸縫關節推斷**無多 rig 真值可驗** —— 這是**資產限制,非方法限制**,如實回報不灌水。

## build_spine --rig-tree 端到端(對 robot_parts.psd)

- 骨鏈:`b_身體`(parent=root,件中心)、`b_頭`/`b_左手`/`b_右手`(parent=`b_身體`,落在接觸縫關節)。
- region 子件 attachment 帶補償偏移(x,y = 件中心 − 骨原點),unweighted mesh 子件則平移頂點補償
  → **setup pose 渲染不變**。
- 驗證:`validate_build` round-trip **AC 全 PASS**(rgb_mae 0.031、0 孤兒,與 flat 完全相同);
  直接量測:轉 `b_頭` 30° 的旋轉不動點 == 脖子 pivot(**0.0 px**),flat rig 則會繞頭質心(偏 50px)。

## 座標關鍵(踩過/需記住)

1. **Spine bone x,y 是相對父骨的局部座標**;setup 全骨 rotation=0 scale=1 → 局部 = 世界差(單純平移合成)。
2. **attachment 補償**:骨從件中心移到關節後,region 用 `x,y` 偏移、mesh 平移頂點,才能讓 setup 位置不動。
   `validate_build` 原本假設「骨位==影像中心」且忽略 attachment 偏移 → 必須升級成合成骨鏈 + 讀偏移(已做,向後相容)。
3. **拓樸序**:Spine bones 陣列需 parent 在子之前 → 先出根件群、再出子件群(slots 仍照 z 序 = 繪製序,與骨序解耦)。
4. **肢體父子樹來源**:目前取自分析器 role note(`結構件/body|head|limb`、`特效件`);body=根,其餘結構肢體→body,
   特效件→root。屬**先驗**,非學自真值(見限制)。

## 誠實限制 / 未竟(通往 L3)

- **多 rig 真值受資產限**:Award 僅機器人被拆件,無第二個拆件角色可交叉驗證泛化(AC4 已如實標注)。
- **肢體父子樹取自 role 先驗**,非自動幾何推斷(STATE 項 (c),接觸/包圍關係推父子仍待做)。
- **weighted + jointed 未整合**:`--rig-tree` 目前把 mesh 件走 unweighted(控制骨 index 與關節鏈重排的整合待做);
  `--weighted` 與 `--rig-tree` 併用時本次以 unweighted 接鏈(已於輸出提示)。
- **pivot 沿肢體軸精修 / 動起來手感**:屬美術微調(RULES A 類),不在客觀閘內。
- 因此 `spine-rig-pivot` 區塊維持 **L2 → HOLD**(pipeline gate GREEN 但無 L3、且泛化受資產所限);
  達 L3(多 rig 真值 + 自動父子樹 + weighted 整合)前不打包成 skill。

## 一鍵驗證

```
python3 tools/rig/validate_rig_tree.py                       # 接合閘 4 AC
python3 tools/analyzer/build_spine.py assets/robot_parts.psd --rig-tree --out /tmp/robot_rig
python3 tools/analyzer/validate_build.py assets/robot_parts.psd /tmp/robot_rig   # round-trip 不變
```
