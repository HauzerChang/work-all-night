# C2 — gen_lib.rig:weighted mesh 生成 + rig 自動推斷(結構軸的 rig 分支)

> spine-ai-editor 2.0 MERGE_PLAN Phase **C2**(2026-10-16 run 007)。承 B1..B4(動畫生成軸)+ C1
> (mesh 生成軸),C2 開 **rig 軸**:把 repo 的 S3 weighted mesh 生成器 + S5 rig 自動化抽成 skill 入口。

## 這個 chunk 解什麼

C1 讓 2.0 能生成**耐變形 unweighted mesh**(形狀),但 mesh 要「跟骨骼平滑變形」還缺兩塊:
**骨綁權重**(weighted),與**骨架 rig 本身**(誰是誰的子件、關節 pivot 在哪)。v1.3.0 的 skill
**只能檢查**既有 rig/weighted mesh,且 `build_spine --rig` **假設星形**(每結構件直掛 body)。
C2 把這兩塊搬進 2.0:

- **入口**:`skills/spine-ai-editor/assets/gen_lib/rig.py`
- **對外 API**:
  - `infer_limb_tree(parts)` → (root, tree{child:parent}, info)。接觸距離 Dijkstra 樹,**不強制星形**
    (多跳肢體鏈 recover 成鏈)。
  - `infer_joint_pivots(parts, tree=None)` → {child: pivot_xy}。接觸縫質心(肩/頸/肘);tree=None 自動先推。
  - `generate_weighted_part_mesh(skeleton, slot, ...)` → 骨綁 weighted mesh(pv + Spine 攤平 vertices +
    真實動畫變形自評)。heat-diffusion/BBW 近似權重,partition of unity、至多 topk 骨。
  - `gate_limb_chain()` → 端到端自驗(合成多跳肢體鏈 → `build_spine --rig --weighted` → 遞迴帶動 + si=0)。
  - 輔助:`weighted_mesh_is_schema_valid` / `pv_to_spine_vertices` / `centroid_pivot_baseline` / `load_robot_rig_truth`。

## 閘:`validate_c2_rig.py` 5 AC 全 PASS

| AC | 驗什麼 | 結果 |
|---|---|---|
| C2-1 entrypoint+weighted-schema | 公開 API 對 Award 身體產 weighted mesh(schema 合法、partition of unity、至多 4 骨、nv≥藝術家、setup clean)+ `pv_to_spine_vertices` 攤平自洽 | PASS(nv 190≥98,worst\|Σw-1\|≈2e-16,最多 3 骨/頂點) |
| C2-2 **rig-inference-truth** | (a) 合成多跳鏈 `infer_limb_tree` root=body + recover **鏈**(非星形);(b) Award robot 星形真值 ROBOT_TREE + 接觸縫 pivot max err/rig<0.1 且中位贏質心 baseline | PASS(鏈 body→arm→forearm→hand;pivot 中位 0.028<baseline 0.056) |
| C2-3 **end-to-end-chain**(headline) | `gate_limb_chain()` overall:ac1 鏈結構(非星形、控制骨掛關節骨、鏈深≥3)+ ac2 setup 不位移 + ac3 遞迴帶動(多跳、weighted-only 脫鉤)+ ac3r region 葉件隨鏈 | PASS(鏈深 4,multi_hop=True) |
| C2-4 weighted-deform-clean+calib | (a) 生成身體 weighted mesh 真實動畫 worst si/flip/degen=0 validated;(b) **真值校準**:藝術家 weighted mesh(身體+左手)於真實動畫亦乾淨(閘不誤報);(c) 鏈 weighted 件變形乾淨 | PASS |
| C2-5 gate-non-vacuous | (a) 隨機 pivot(全 rig bbox)+ 關節互換中位 err/rig>>0.1(接觸縫<0.1);(b) 身體放大 4× 藝術家 si=0 vs 打亂權重 si=54、左手打亂直接被抓;(c) weighted-only 脫鉤 | PASS |

跑:`python3 tools/analyzer/validate_c2_rig.py [--json]`。

## 關鍵發現

1. **heat-diffusion 權重天然 partition of unity**。`(L+H)W=HP`(L=cotangent Laplacian、H=到最近骨
   熱貢獻、P=最近骨 one-hot)的解每頂點權重和=1(本資產實測 worst|Σw-1|≈**2.2e-16**,= 浮點機器精度);
   剪成每頂點至多 4 骨(Spine 上限)重正規化後仍守恆。→ **BBW 近似可純 CPU 稀疏解自動產骨綁網格**,
   不需 GPU、不需手工刷權重。生成 nv=190(> 藝術家 98)、真實動畫變形 si=0(與藝術家真值一致)。

2. **rig 推斷只客觀到「拓樸 + 接觸縫關節」,但這兩塊足以自動化整個 rig 結構**。
   - **拓樸**:接觸距離(加密邊界最近距離、重疊=0)完全圖自 root 跑 Dijkstra 最短路徑樹——
     星形各件經 body 直達全掛 body;**鏈形**遠端件經中間件轉 → **recover 鏈,不強制星形**
     (合成肢體鏈 body→arm→forearm→hand 完整還原)。root=面積最大件(軀幹穩健幾何簽名;
     degree-hub 於純鏈退化)。
   - **關節 pivot**:子件最靠近父件的接觸縫(距離最小 q 分位點)質心 → 對藝術家 rig 真值 err/rig
     **中位 0.028**(< 0.1)、顯著贏過質心 baseline(0.056),隨機/互換負對照 >> 0.1。
   - 沿肢體軸精確落點、該偏離接觸縫幾像素取手感 = 美術(A 類),本器輸出**草案**。

3. **「weighted mesh 當鏈中段肢體 → 遞迴帶動」需合成 fixture 補真值缺口**。真實資產 robot_parts
   的可拆肢體(頭/手)都是 **region 件、且都直掛 body**(星形/單跳);weighted mesh 只有 body(rig 根)
   + 光暈(effect)。故「weighted mesh 既是某件的子、又是另一件的父」在真實資產**無樣本**。
   `make_limb_chain_psd` 合成多跳鏈(arm/forearm 皆 weighted mesh、各在鏈中段)補上:演算法早已
   支援(接觸縫遞迴 + 控制骨掛該件關節骨),C2-3 證端到端確實成立(轉 rig 根 b_body → forearm
   經 arm 隔一跳仍隨動,weighted-only 版脫鉤=負對照)。

## 護欄 / 誠實邊界

- **真實多 rig 真值 = 使用者資源(S5→L3 硬缺口)**:Award 僅 1 個可拆肢體 rig,無法對「多個真實
  rig」驗泛化。本 chunk **只搬可自主的合成肢體鏈驗收** + 單一真實 rig(Award robot)的樹/pivot 真值。
- **結構 vs 特效角色分類為輸入**:把 effect 件(光暈:大面積、與多件重疊的背光)當結構件推會汙染
  樹(`infer_tree.diagnose_include_effect` 證:納光暈後 root 變光暈)→ 角色分類是另一子問題,為輸入。
- **軟性加成件(光暈)容許重疊**:additive 混合下自我重疊可見無害,不列硬性 si=0(見
  `s3-weighted-deform-evaluator.md`)。負對照用**不透明結構件**(左手直接打亂、身體放大 4× 分離)。
- **排程 scope 邊界**:Cocos/viewer 實機載入與 PMA 視覺 = 使用者端;排程用 Spine 3.8 bone world
  transform 幾何量化等價(`weighted_deform_eval` 已對 Award 真值重現)。
- **過渡期相依**:`rig.py` 目前 import repo `tools/{mesh_gen,rig,analyzer}`(透過 `_wire_repo_tools()`
  shim),與 B2/B3/B4/C1 一致;**E1** self-contained bundle 後移除。依賴 numpy/scipy(spsolve/cKDTree)/
  triangle(hook 已裝)。

## 與 C1 的互補

C1 生成器產 **unweighted** 形狀(可直接 reshape 驗拓樸);C2 補 **weight**(heat/BBW)與 **rig**
(樹 + pivot)。兩者合起來:件影像 → 耐變形拓樸(C1)→ 骨綁權重 + 自動 rig(C2)→ 會隨骨鏈遞迴
帶動的 weighted mesh。D1 再把 C1/C2 的變形 si 閘 + v1.3.0 validator_v1 合成單一 `validator_v2`。

## 回歸

`check_readiness.py` 新增 cap `c2_rig` L2(併入 `spine-anim-forge`,仍 HOLD——生成庫整體尚未跨
skill 化門檻:多 rig 真值缺口 + 運動基元手感先驗)。既有 B1..B4/C1 + S1/S3/S5 閘逐一 PASS
(rig.py / validator 皆純新增,無改任何既有生成/產線值)。
