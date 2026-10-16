# C2 — gen_lib.rig:weighted mesh 生成 + rig 自動推斷(結構軸的 rig 分支)

> spine-ai-editor 2.0 MERGE_PLAN Phase **C2**(2026-10-16 run 007)。承 C1(mesh 生成軸),
> C2 補上結構軸的 **rig 軸**:把 repo 的 weighted mesh 生成 + rig 自動推斷(tree + pivot)抽成 skill 入口。

## 這個 chunk 解什麼

C1 讓 2.0 能**生成**耐變形 mesh,但那是 **unweighted**(靠逐頂點 deform 動);且 C1 不處理
「件要綁到哪根骨、骨架父子怎麼接、關節 pivot 擺哪」。當「結構性無法做到」是因為**件沒綁骨 /
綁錯父子 / pivot 擺錯關節 / 只能整塊剛體位移(無 weighted mesh 平滑彎折)**時,需要把這條
rig 上游補起來。C2 把兩塊能力搬進 2.0:

- **入口**:`skills/spine-ai-editor/assets/gen_lib/rig.py`
- **對外 API**:
  - rig 自動推斷:
    - `infer_limb_tree(parts)` → `(root, tree{child:parent}, info)`;接觸距離 Dijkstra 樹,recover 鏈(非強制星形)。
    - `infer_joint_pivots(parts, tree)` → `{child: joint_xy}`;關節 = 子件最靠父件的 q 分位點質心(接觸縫)。
    - `infer_rig(parts)` → `{root, tree, pivots, info}`;一條龍。`rig_is_schema_valid` 可機讀自檢。
  - weighted mesh 生成:
    - `generate_weighted_part_mesh(skeleton, slot, max_area, topk)` → heat-diffusion weighted mesh(gen bundle)。
    - `eval_generated_weighted(gen)` → setup 自一致 + 真實動畫 deform(worst si/flip/degen + 平滑度)。
    - `weighted_deform_gate(skeleton, slot, mutate, amplify)` → 既有藝術家 weighted mesh 過同一道閘(真值校準/負對照)。
  - 真值/合成 fixture:`synthetic_limb_chain` / `synthetic_star` / `award_robot_struct_parts` / `load_award_robot_parts`。

## 閘:`validate_c2_rig.py` 5 AC 全 PASS

| AC | 驗什麼 | 結果 |
|---|---|---|
| C2-1 entrypoint+schema | 公開 API 皆 callable;`infer_rig` 對合成鏈產 **schema 合法** rig(root∈parts、無環、每非 root 件有 parent+pivot) | PASS |
| C2-2 **tree-topology** | 合成肢體鏈 fixture → 端到端 recover 成**鏈**(upper→torso、lower→upper,非星形,鏈深 2 跳);合成星形 → 全掛 torso;Award 機器人 → 推斷樹 == 真值 ROBOT_TREE;τ_frac band[0.008..0.20] root+tree 穩定 | PASS |
| C2-3 pivot-accuracy | Award 機器人每關節 pivot max err/rig=**0.051**<0.10(draft 級);中位 21.6px < 質心 baseline | PASS |
| C2-4 weighted-gen | 身體/左手生成 heat-diffusion weighted mesh → setup 自一致 + 真實動畫 si=0/flip=0/degen=0 + nv 98/104 ≤ 1.4× 藝術家(98/80);真值校準:藝術家既有 weighted mesh 真實動畫全幀乾淨 | PASS |
| C2-5 gate-non-vacuous | 隨機父指派命中率 0.014<0.05 + 左手平移 1500px → 父邊改掛右手(幾何驅動);隨機 pivot 0.169/互換 0.276 皆>0.10;打亂權重放大動作 si=54>0(藝術家 si=0) | PASS |

跑:`python3 tools/analyzer/validate_c2_rig.py [--json]`(~50s)。

## 關鍵發現

1. **rig 拓樸是接觸幾何問題,不是先驗假設問題**。`infer_tree` 用件間接觸距離(加密邊界最近距;
   重疊=0)構成完全圖,root=**面積最大件**(軀幹的穩健幾何簽名),父邊=自 root 的接觸距離
   Dijkstra 最短路徑樹。星形(各件經 body 直達)與多跳鏈(遠端件經中間件轉)**都 recover**,
   不硬編星形 → `--rig` 完全自決。踩雷:root 須 **area-primary 非 degree-hub**——純肢體鏈的
   中間件 degree 最高卻非 root(root 在鏈端);重疊 composite 下 degree 飽和(見
   `s5-limb-tree-inference.md`)。

2. **pivot 的可客觀化子問題 = 「關節落在父子接觸縫」**。肩/頸/hip 都在子件與父件的接觸縫上;
   `infer_pivots` 取 child 點集中最靠 parent 的 q 分位點質心當關節,對 Award 真值 max err/rig=0.051
   (draft 級,顯著勝「用子件質心」天真 baseline)。**沿肢體軸的精修、動起來的手感屬美術微調**
   (RULES A 類),不在此客觀閘內——本器輸出草案,使用者再微調。pivot 準度取決於件輪廓保真
   (rect 代理會爆閘,alpha 輪廓才準 → PSD-first 論點在 rig 階段再現,見 `s5-rig-pivot-inference.md`)。

3. **weighted 權重 = cotangent Laplacian + heat H 稀疏解**(Baran & Popović bone-heat;BBW 實用近似,
   純 CPU)。`(L+H)W=HP` 天然滿足 partition-of-unity(每頂點權重和=1)且在網格上平滑擴散,
   剪成每頂點 ≤4 骨(Spine 上限)後重正規化。與 C1 互補:**C1 的 unweighted strip 靠逐頂點 deform
   動(窗簾/旗幟類),C2 的 weighted mesh 靠骨骼 skinning 動(肢體類)**——形狀生成(C1)vs
   骨綁權重(C2)兩面齊備。

4. **合成鏈 fixture 補「weighted mesh 當鏈中段肢體」的真值缺口**。真實 Award 機器人可拆肢體都是
   region 件、都直掛 body(星形單跳),無「weighted mesh 既是子又是父」樣本;合成鏈
   (body→arm→forearm→hand,只相鄰件接觸)用確定性矩形幾何補上多跳驗收,**純幾何無需真值**。
   `build_spine --rig --weighted` 的端到端整合(控制骨掛關節骨、沿鏈遞迴帶動後代)另見
   `validate_rig_weighted_chain.py`(本 chunk 的 skill 入口聚焦 **推斷 + 生成** 三函式)。

## honest boundary(誠實界定)

- **真實多樣 rig 真值仍屬使用者資源(S5→L3 硬缺口)**。本 chunk 只搬「單一 Award 真值 + 合成鏈」
  可自主的部分。要讓 rig 推斷泛化到各種人形/非人形骨架(L3),須使用者提供更多真實 rig 真值——
  這道硬缺口不變(見 `s5-limb-tree-inference.md` / `s5-rig-weighted-combo.md`)。
- **effect/structural 角色分類是輸入**。NC3(repo validate_tree)證天真把光暈(大面積背光 effect)當
  結構件會奪走 root → 推斷前須先分類 effect vs structural(另一子問題)。
- **軟性加成件(光暈)不列 si=0 硬性 AC**。藝術家自身即 si>0(additive 混合下重疊視覺無害);本閘
  weighted mesh 生成只對不透明結構件(身體/左手)驗硬性 si=0。
- Cocos/viewer 實機載入與 PMA 視覺 = 使用者端(排程 scope 邊界,用真實 deform 幾何量化等價)。
- 過渡期 import repo `tools/mesh_gen` + `tools/rig`(E1 self-contained bundle 後移除)。

## 回歸

`check_readiness` **0 RED**(新增 cap `c2_rig` L2 pipeline,併入 `spine-anim-forge` 仍 HOLD)。
既有 repo 閘(`validate_tree`/`validate_pivots`/`validate_weighted_gen`/`validate_weighted_deform`)
逐一 PASS,證抽成 skill 入口後行為一致。
