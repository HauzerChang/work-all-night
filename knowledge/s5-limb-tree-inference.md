# S5 (c) — 肢體父子樹自動推斷(移除 rig 最後一個「取自先驗」環節)

> 里程碑 2026-08-31。S5 rig pipeline 此前有兩個確定性環節 + 一個先驗:
> pivot 落點(接觸縫,`infer_pivots` ✅)、pivot→bone 樹寫入(`--rig` ✅)、
> **但「誰是 root / 誰是誰的父件」一直取自分析器 note 先驗(假設星形)**。本次補上這環:
> 由**拆件相鄰幾何自動推斷父子樹**,使 `build_spine --rig` 完全自決,且支援多跳肢體鏈。
> 工具:`tools/rig/infer_tree.py`、閘 `tools/rig/validate_tree.py`(exit 0 = 全 PASS)。

## 結論

- **可自動推斷者 = 拓樸(root + parent 邊)**,純幾何、確定性、無 ML。對 Award 機器人 rig
  真值樹 **AC1–AC4 + 3 負對照全 PASS**;接進 `build_spine --rig` 後原 4 AC 端到端**回歸全 PASS**。
- **root = 面積最大件(trunk)**,degree 為 tiebreak/診斷(見下「為何 area-primary」)。
- **父邊 = 以接觸距離為權重的完全圖,自 root 跑 Dijkstra 最短路徑樹**;星形/多跳鏈皆正確 recover。
- **信心**:高(對唯一真實可拆肢體 rig 精確吻合 + 合成鏈驗多跳 + 負對照具鑑別力)。相關階段:S5。

## 演算法(`infer_tree`)

1. 各件世界多邊形**加密**(沿邊補點,step=2px)→ 準確件間最近距離。
2. 接觸距離 `d(a,b)`:加密邊界最近距離(scipy cKDTree);任一件點落入對方內(重疊)→ `d=0`。
3. **root** = 面積最大件(平手取接觸度最高)。
4. **父邊** = 完全圖(權重=接觸距離)自 root 跑 Dijkstra;`parent[x]` = x 到 root 最短接觸路徑前驅。

## 為何 root 用 area-primary,不用 degree-hub(踩過)

- 初版用 degree-hub(在 τ 內相鄰件數最多者當 root)。**對星形對**(軀幹掛多肢=hub),
  但**純肢體鏈爆掉**:鏈 `torso–upper–lower` 中「中間件 upper」degree=2 最高 → 被誤選為 root,
  但 root 應在鏈端(torso)。合成鏈 AC4 即抓到此 bug(root=upper)。
- 真實軀幹的穩健幾何簽名是**最大面積**(trunk 是最大質量件),不是最高 degree。改 area-primary 後
  robot(body 78393 最大)、合成鏈(torso 最大)、合成星形三者 root 全對。
- **degree 在重疊 composite 下常飽和**:機器人 4 結構件在合成座標互相重疊,τ=0.06·scale 時所有件 degree=3
  (見接觸矩陣:body 對三肢皆 0;連 head–右手=0、head–左手=9.6 也有 spurious 重疊)→ degree 無鑑別力,
  **area 才是真正決定 root 的訊號**。這也是為何 tree 幾乎不依賴 τ(Dijkstra 只吃距離權重)。

## 接觸矩陣(Award 機器人,px;honest 記錄)

|      | 身體 | 頭 | 左手 | 右手 |
|------|----|----|-----|-----|
| 身體 | 0  | 0  | 0   | 0   |
| 頭   | 0  | 0  | 9.6 | 0   |
| 左手 | 0  | 9.6| 0   | 43  |
| 右手 | 0  | 0  | 43  | 0   |

- body 對三肢皆重疊(0)→ 天然 hub;肢體間有 spurious 重疊(head–右手=0)→ degree 飽和。
- 星形仍正確 recover:root=body 時三肢的 body 直達邊皆 0 權重 → Dijkstra 直掛 body(2 跳同為 0 但不改進,`<` 嚴格)。

## 真值閘(`validate_tree.py`)

| 校驗 | 內容 | 結果 |
|---|---|---|
| **AC1** root 正確 | area-primary 推得 root == body(且 area_max==body) | **PASS** |
| **AC2** 拓樸精確 | 結構父子樹邊集合 == 真值 `ROBOT_TREE`(頭/左手/右手→身體) | **PASS** |
| **AC3** 門檻穩定 | root+tree 在 τ_frac∈[0.008,0.20](8 點)完全不變 | **PASS**(tree 本就 τ-無關) |
| **AC4** 多跳通用 | 合成鏈 torso→upper→lower recover 成**鏈**(非強制星形);合成星形亦正確 | **PASS** |
| **NC1** 隨機父指派 | 隨機父指派命中真值率 ≈1.4%(<5%)→ 閘非恆過 | **PASS** |
| **NC2** 斷開左手 | 左手平移 1500px → 其父邊由「身體」改變(幾何驅動,非硬編) | **PASS** |
| **NC3** 天真納 effect | 把光暈(大面積背光、與多件重疊)當結構 → root/樹全被光暈奪走 | **PASS**(證須角色輸入) |

- **真相來源**:parts 世界多邊形 = `infer_pivots.load_award_robot`(mesh hull / atlas alpha 輪廓);
  truth tree = `ROBOT_TREE`。純 CPU、無瀏覽器。

## 接進 build_spine(`rig_layout` 重寫)

- 結構件集合仍由 note 的 effect/structural 語意分類決定(**honest boundary**:role 分類是另一子問題,見 NC3);
  **root 與 parent 邊改由 `infer_tree` 幾何推斷**,不再假設星形。
- 結構子件 pivot 改對**其推得的父件**取接觸縫(`contact_seam_joint(parent_sil, child_sil)`)——
  多跳鏈中子件關節落在與**直接父件**的縫,而非一律對 body。
- bone 以**拓樸序**(root BFS,effect/孤兒殿後)輸出,確保父必先於子(支援 2+ 跳鏈)。
- `validate_rig_build.py` 端到端 4 AC **回歸全 PASS**(rig_root=b_身體 自動推得;結構子件掛 body)。

## 界定 / 下一步

- **honest boundary**:本器推**拓樸**,不做 effect vs structural 的**角色分類**(NC3 顯示天真納入
  光暈會被其大面積+多重疊奪走 root/邊)→ role 分類須作為輸入(目前來自分析器 note)。這是獨立子問題。
- **多跳鏈**演算法已支援(AC4 合成鏈驗),但 **Award 只有星形一件真實 rig**;真實多跳鏈真值仍屬使用者資源。
- `spine-rig-pivot` 區塊**維持 HOLD**:L3 仍需多個真實 rig,本次補齊「拓樸自動化」但未新增真值 rig。
  這遵守防固化(拓樸推斷已 L2 可信,但整體 rig pipeline 的 L3 缺口=多 rig 真值不變)。
- 純軸向精修 / 手感仍屬美術(RULES A 類)。
