# C2 — gen_lib.rig:weighted mesh 生成 + rig 自動推斷(結構軸的 rig 分支)

> spine-ai-editor 2.0 MERGE_PLAN Phase **C2**(2026-10-16 run 007)。承 C1(mesh 生成軸),
> C2 開 **rig 生成軸**:把 repo S5 的 rig 自動化 + weighted mesh 生成抽成 skill 入口。

## 這個 chunk 解什麼

v1.3.0 的 skill 能**修既有動畫手感**(curve_tools)、C1 讓 2.0 能**生成耐變形 mesh**(unweighted 形狀);
但「件只能整塊剛體位移、**沒有骨架階層**、**關節 pivot 放錯**(肢體繞錯點轉)」仍是 structural 限制。
當目標需要**多跳肢體鏈**(手→前臂→上臂→軀幹,轉肩整條手臂跟著動)時,需要:
①自動推出父子樹(誰掛誰);②關節 pivot 落在父子接觸縫(肩/肘/腕);③中段肢體用 weighted mesh
(既是某件的子、又是另一件的父)。C2 把這三件事搬進 2.0 並端到端自驗:

- **入口**:`skills/spine-ai-editor/assets/gen_lib/rig.py`
- **對外 API**:
  - `infer_rig_tree(parts)` → (root, tree, info):面積優先 root + 接觸距離 Dijkstra 父子樹(支援多跳鏈)。
  - `infer_joint_pivots(parts, tree)` → {child: (x,y)}:每子件關節 = 與**其父件**接觸縫質心。
  - `contact_seam_joint` / `centroid_pivot_baseline` / `diagnose_effect_contamination`(低階 + 負對照)。
  - `generate_weighted_part(skeleton, slot)` + `weighted_part_quality(gen)`:heat-diffusion / BBW 近似權重生成 + 品質量化。
  - `make_synthetic_limb_chain(psd)` + `build_rigged_skeleton(psd, out)`:合成鏈 fixture + `build_spine --rig --weighted` 端到端。
  - `award_robot_truth()`:載入 Award 機器人藝術家真值(parts/pivots/tree/fidelity)供校準。

## 閘:`validate_c2_rig.py` 5 AC 全 PASS

| AC | 驗什麼 | 結果 |
|---|---|---|
| C2-1 infer-truth | `infer_rig_tree`(Award 結構件)→ root==身體 且 tree==ROBOT_TREE;`infer_joint_pivots` 中位誤差 < 子件質心 baseline 且 max err/rig < 0.10 | PASS(pivot 21.6px < baseline 43.0px,max err/rig<0.10) |
| C2-2 weighted-gen-truth | `generate_weighted_part`(Award 身體+左手)→ partition of unity、≤4 骨/頂點、setup 乾淨、真實動畫骨骼變形 si=0/flip=0(checker_validated)、nv ≤1.4× 藝術家 | PASS(身體 98==98、左手 104≤112) |
| C2-3 chain-structure | `build_rigged_skeleton`(合成鏈 body→arm→forearm→hand,rig×weighted)→ 骨鏈非星形、深 4≥3、每 weighted mesh 件控制骨 parent==關節骨 b_{nm}、index 合法 | PASS |
| C2-4 **recursive-drive** | setup 不位移(rig==weighted-only 0.0px)+ 轉每關節 → 後代動/祖先旁支≈0 + **多跳**(轉 body 帶動隔一跳 forearm 80px)+ 關節旋轉逐幀結構件 si=0/flip=0 | PASS |
| C2-5 gate-non-vacuous | (a) weighted-only 版轉關節**全脫鉤**(位移≈0) (b) effect 件當結構 → 樹被汙染 (c) pivot 隨機 0.476 / 互換 0.276 med err/rig >> 0.10 | PASS |

跑:`python3 tools/analyzer/validate_c2_rig.py [--json]`。

## 關鍵發現

1. **rig 推斷對真值拓樸精確、pivot 勝 baseline 2×,且泛化到多跳鏈**。root = 面積最大件(軀幹穩健幾何
   簽名,非 degree-hub:純肢體鏈的中段 degree 最高卻非 root);父邊 = 接觸距離為權重的 Dijkstra 最短
   路徑樹(星形直達 body、鏈形經中段轉 → recover 鏈而非強制星形);關節 pivot = 子件最靠近其父件的
   接觸縫質心。對 Award 機器人真值 root/tree 完全吻合、pivot 中位誤差 21.6px(子件質心 baseline 43.0px)。

2. **weighted mesh 當鏈中段(既子又父)靠「控制骨掛該件關節骨 + 座標轉局部」**。weighted mesh 的控制骨
   不掛 root 而掛**該件的關節骨 b_{nm}**,bind 座標轉為相對關節骨的局部座標。setup 下父鏈皆純平移 →
   控制骨世界位置不變 → **bind 偏移完全不變、setup pose 精確保留**(C2-4 rig==weighted-only 0.0px);
   但關節骨(及其祖先)旋轉時,控制骨連同 weighted mesh 沿關節鏈**剛性遞迴帶動**(轉 body → arm →
   forearm 隔一跳也隨動)。

3. **weighted-only 版 = 天生脫鉤負對照**。同一 PSD 以 `rig=False, weighted=True` 建:weighted mesh 控制骨
   掛 root(b_{nm} 只是 slot 骨、不驅動 weighted mesh)→ 轉任何關節件皆不動(位移≈0)。這證「接進關節
   鏈」才是 rig×weighted 的收益,而非 build_spine 本就會動 → C2-4 的帶動 AC 非恆真。

## 護欄 / 誠實邊界

- **真值來源**:rig 推斷校準 = **Award 機器人藝術家真值**(骨世界位置=真值 pivot;ROBOT_TREE=真值樹);
  weighted 變形品質 = `weighted_deform_eval.eval_pv`(已對 Award 真值重現,checker_validated);
  合成鏈帶動/變形 = Spine 3.8 bone world transform(確定性、純 CPU、無瀏覽器)。
- **「weighted mesh 當鏈中段肢體」在 Award 無真實樣本**(其可拆肢體皆 region、星形單跳;weighted mesh
  只有 body(rig 根)+ 光暈(effect))→ 用**合成多跳鏈 fixture**(`make_limb_chain_psd`)補此缺口。
- ⚠️ **真實多 rig 真值**(多角色、非人形運動分群)仍屬**使用者資源**(S5→L3 硬缺口);此入口只搬**可自主**
  的合成端到端 + 單一真值(Award)校準。**pivot 沿肢體軸的精修 / 動起來的手感 = 美術微調(RULES A 類)**。
- **effect/structural 角色分類須作為輸入**(honest boundary):C2-5(b) 證天真把光暈(大面積背光、與多件
  重疊)當結構推會汙染樹 → 角色分類(由 note 語意)是 `infer_tree` 的前置輸入,非幾何可自決。
- **過渡期相依**:`rig.py` import repo `tools/{mesh_gen,rig,analyzer}`(透過 `_wire_repo_tools()` shim),
  與 B2/B3/B4/C1 一致;**E1** self-contained bundle 後移除。依賴 numpy/cv2/scipy/triangle/psd_tools(hook 已裝)。
- **排程 scope 邊界**:Cocos/viewer 實機載入 = 使用者端;排程用 bone world transform 幾何量化等價。

## 回歸

`check_readiness.py` 新增 cap `c2_rig` L2(併入 `spine-anim-forge`,仍 HOLD——生成庫整體尚未跨 skill 化
門檻)。既有 B1..C1 + S1/S3/S5 閘逐一 PASS(rig.py / validator 皆純新增,無改任何既有生成/產線值)。

## 下一步

Phase **D1**:把 repo 的閘紀律 + v1.3.0 `validator_v1` 合成單一 `assets/validator_v2.py`——一條指令同時驗
「runtime 可載入 / editor 可匯入 / loop 閉合 / stiffness / deform si / C1」,對一支 2.0 生成的大獎動畫
一鍵輸出全維度 pass/fail + 量化指標。
