# C2 — gen_lib.rig:weighted mesh 生成 + rig 自動推斷(結構軸的 rig 分支)

> spine-ai-editor 2.0 MERGE_PLAN Phase **C2**(2026-10-17 run 007)。承 C1(unweighted mesh 生成),
> C2 補完 **mesh 的另一半 + 綁骨/組骨架**:weighted mesh(靠 skinning 變形)+ 關節 pivot / 肢體父子樹推斷。

## 這個 chunk 解什麼

C1 的 `mesh.py` 生成**靠逐頂點 deform 變形**的網格(窗簾/旗幟/頭髮);但另一大類件(肢體)
**靠骨骼 skinning 變形**,需要 **weighted mesh**(藝術家手工綁權重)。而且一堆拆件要能動,
還得先知道**誰是根、誰掛誰、關節放哪**。v1.3.0 的 skill 能檢查/驅動既有骨架,但這兩件都做不到:

- C1 解「件沒有 mesh」;**C2 解「件有 mesh 但沒綁骨 / 一堆件沒組成骨架」**。
- **入口**:`skills/spine-ai-editor/assets/gen_lib/rig.py`(包 repo 三個確定性純 CPU 生成/推斷器)。
- **對外 API**:
  - weighted mesh:`generate_weighted_part_mesh` / `weighted_schema_valid` / `weighted_deform_gate` /
    `generate_and_gate_weighted`(件 → 生成 → schema + 真實 skinning 變形閘 + 平滑度 + 頂點預算,一條龍)。
  - rig 推斷:`infer_limb_tree`(件世界多邊形 → root + 父子樹)/ `infer_joint_pivots`(父子樹 → 關節 pivot)/
    `rig_from_parts`(件 → 樹 + pivots,一條龍,排除 effect 件)。
  - loaders / fixture:`load_award_robot_parts` / `award_robot_tree` / `make_chain_parts` / `make_star_parts`。

三個底層器(均 repo 既有、對 Award 真值驗過):`generate_weighted_mesh`(三角化內部密度 +
heat-diffusion/BBW 近似權重)、`infer_pivots`(父子接觸縫)、`infer_tree`(接觸距離 Dijkstra)。

## 閘:`validate_c2_rig.py` 5 AC 全 PASS(全經公開 API)

| AC | 驗什麼 | 結果 |
|---|---|---|
| C2-1 生成+schema+預算 | 公開 API 對 Award 不透明件產 Spine **weighted** mesh(weighted 格式、每頂點 partition of unity 權重和=1、≤4 骨、hull∈(0,nv])+ 頂點 ≤1.4× 藝術家;軟件 schema 亦合法 | PASS(身體 98/98、左手 104/80) |
| C2-2 **real-skinning si=0**+真值校準 | 生成 weighted mesh 放回**真實動畫** skinning → setup 乾淨 + 逐幀 si=0/flip=0 + 平滑度不劣於藝術家;藝術家同件經同 checker 亦 si=0(checker_validated)→ 過閘與真值一致 | PASS |
| C2-3 pivot 準度+勝 baseline+保真依賴 | infer_joint_pivots max err/rig<0.10;中位勝質心 baseline;rect 代理(--no-alpha)爆閘 | PASS(0.051 / 21.6<43.0px / rect 0.82) |
| C2-4 tree 真值+穩定+多跳通用 | Award root==身體 且 拓樸==真值 ROBOT_TREE;τ_frac band 穩定;合成鏈 recover 鏈、合成星形 recover 星形 | PASS |
| C2-5 閘非恆真 | (a) pivot 隨機/互換 med/rig 0.44/0.28>>TAU (b) tree 隨機命中 0.015 + 納 effect(光暈)汙染樹(root→光暈) (c) weighted hull-tangle → 真實 skinning 閘 setup si>0(身體 150、左手 65) | PASS |

跑:`python3 tools/analyzer/validate_c2_rig.py [-q]`。

## 關鍵發現

1. **weighted mesh「真實變形 si=0」靠 heat-diffusion partition-of-unity 平滑權重**。生成器以
   cotangent Laplacian + bone-heat(`(L+H)W=HP`)解出天然滿足「每頂點權重和=1」且在網格上
   平滑擴散的權重,剪成每頂點 ≤4 骨(Spine 上限)。藝術家同件 mesh 經同一 checker 亦 si=0
   → 生成**追平真值**(非閘太鬆、非假性過)。對照 C1 的 unweighted strip:C1 靠**拓樸選擇**
   耐單向拉伸,C2 靠**權重平滑**耐骨骼旋轉——兩條變形機制各有對應的生成策略。

2. **pivot/tree 準度取決於「件輪廓保真」**(rect 代理爆閘,再現 rig 階段的 PSD-first 論點)。
   contact-seam pivot 用件世界多邊形算父子最近點;用 atlas alpha 真實輪廓 max err/rig=0.05
   (draft 級),換成粗略 bounding-rect 代理立刻爆到 0.82。→「能要到分層 PSD / 準確輪廓就要」
   這個 repo 總策略,在 rig 階段同樣成立。

3. **effect vs structural 語意分類「須作為輸入」,是 honest boundary 非 bug**。infer_tree 用
   面積最大件當 root、接觸距離 Dijkstra 連邊;光暈(大面積背光、與多件重疊)若當結構件,
   會奪走 root 並汙染全樹(C2-5b 實測 root→光暈)。`rig_from_parts(effect_names=...)` 把這
   分類顯式當輸入排除。語意分類本身是另一子問題(S1 分析器 struct_role 關鍵字已可供,見 s1)。

4. **weight-scramble 不一定破,hull-tangle(動拓樸)才是可靠負對照**。試過 `mutate_scramble_weights`
   / `mutate_rebind_far`:對**根件**(身體)無效(根骨諸子骨 setup 近似剛性,打亂綁定幾乎不位移,
   si 仍 0)。改用 C1-5 式**對調兩非相鄰 hull 頂點的 bind**(動拓樸、令邊界交叉)→ setup si>0
   穩定被抓。教訓:負對照要破的是「幾何拓樸」,不是「參數值」,才對剛性退化魯棒。

## 護欄 / 誠實邊界

- **真相來源**:weighted 變形閘用 `weighted_deform_eval.eval_pv`(對 Award 真值重現的 Spine 3.8
  skinning),**不用**未校準合成場;對不透明結構件過「真實動畫 si=0」硬閘。
- **軟性加成件(光暈)**:additive 混合視覺無害、藝術家自身即 si>0 → **不列 si 硬閘**,只驗 schema。
  (= 誠實界定:生成器對軟件極端 reveal 尚未追平藝術家手工拓樸,屬已知限制。)
- **pivot 沿軸精修 / 手感、effect 語意分類** = 美術 / 輸入(RULES A 類);本器只做可客觀化的
  「關節落在父子接觸縫」+「拓樸推斷」。
- **真實多 rig 真值 = 使用者資源**(S5→L3 硬缺口):本 chunk 只搬可自主的合成 fixture(鏈/星形)+
  Award 單 rig 真值。weighted uvs 由 setup 世界 bbox 正規化(schema 級),**真 atlas UV = build_spine / 使用者端**。
- **過渡期相依**:`rig.py` import repo `tools/mesh_gen`(generate_weighted_mesh / weighted_deform_eval)
  + `tools/rig`(infer_pivots / infer_tree),與 B2/B3/B4/C1 一致;**E1** bundle 後移除。
  依賴 numpy / scipy / triangle(hook 已裝)。

## 回歸

`check_readiness.py` 全綠(新增 cap `c2_rig` L2 pipeline,併入 spine-anim-forge,0 RED,無 GREEN→RED);
`rig.py` / 閘皆純新增,無改任何既有生成/產線值(既有 weighted_gen / pivots / tree / chain 閘逐一 PASS)。

## 下一步

Phase **D1**:把 repo 的閘紀律 + v1.3.0 `validator_v1` 合成單一 `assets/validator_v2.py`——一條指令
同時驗「runtime 可載入 / editor 可匯入 / loop 閉合 / stiffness / deform si / C1」。AC=對一支 2.0 生成的
大獎動畫一鍵輸出全維度 pass/fail + 量化指標。(C 階段 mesh/rig 併接至此完成。)
