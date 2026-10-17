# D1 — validator_v2:統一品質閘(一鍵五維度)

> spine-ai-editor 2.0 MERGE_PLAN Phase **D1**(2026-10-17 run 008)。承 Phase B(動畫生成)、
> Phase C(mesh/rig 生成)。D1 把前面各 chunk 累積的**閘紀律**合成單一一條指令。

## 這個 chunk 解什麼

2.0 的輸出合約是三件事同時成立:**遊戲能播**(runtime 可載入)、**編輯器能匯入**
(Spine editor 不炸,地雷 #12)、**mesh 在極端變形下不撕裂**(deform si=0)。此前要驗這三件,
得分別跑兩套閘、各自解讀:

- `validator_v1`(v1.3.0):runtime schema + editor 匯入末鍵 curve + loop 閉合 + stiffness。
- C1 `deform_si_gate`:mesh 真實位移場轉移的自交/翻面檢查。

**D1 = 把這兩套合成單一 `validator_v2`**:對一支 2.0 生成的大獎動畫,**一條指令**輸出
**全五維度** pass/fail + 量化,不必跑兩套、也不必人工開 Spine editor。

- **入口**:`skills/spine-ai-editor/assets/validator_v2.py`(`validate_v2()` + CLI + `--json`)。
- **五維度**:
  1. `runtime_loadable` — validator_v0 schema / 引用完整性(= spine-webgl 可載入的 CPU 代理)。
  2. `editor_importable` — v1 末鍵 curve(地雷 #12 AIOOBE)+ cx 超界升級(= editor 可匯入)。
  3. `loop_closure` — v1 loop 閉合(首尾值一致、首鍵在 0、末鍵在時長處)。
  4. `stiffness` — v1 `--metric`(key 處速度不連續量);**手感 A 類 → 預設只量化報告、不參與 overall 硬閘**。
  5. `deform_si` (C1) — 對 skin 內每個 **mesh** attachment 跑 `gen_lib.mesh.deform_si_gate`
     (有真實 deform → 真實位移場轉移 si/flips/degen;無 → 退回靜態拓樸)。

## 架構關鍵:單一真相來源,無漂移

「合成單一閘」最大的風險是**退化**——合出來的新閘比原來寬鬆/判準漂移。D1 用兩招擋住:

1. **維度 1–4 直接 in-process 呼叫 `validator_v1.run_checks()`**(與 CLI `validator_v1.py`
   **同一個函式**)。本 run 把 validator_v1 重構出 `run_checks()`,`main()` 只做參數解析 + 印出,
   **stdout 逐字不變** → B1 bridge(解析 v1 stdout)零回歸。validator_v2 不重寫任一判準,只把
   v1 的 `report.errors` 依「末鍵 curve/cx」vs「其餘」分流成 editor/runtime 兩維度、warnings 取 loop。
2. **維度 5 直接呼叫 `gen_lib.mesh.deform_si_gate`**(C1 的同一引擎)。

D1-2 再用**真正的 validator_v1 subprocess**(使用者端實際用的 CLI)對同一 skeleton 比對:
validate_v2 的 errors 集合 / loop problems / stiffness 數值**逐項一致** → 證「合成單一 ≠ 退化」。

## 閘:`validate_d1_validator.py` 5 AC 全 PASS

| AC | 驗什麼 | 結果 |
|---|---|---|
| D1-1 一鍵全維度 | 對「2.0 生成大獎 + 嵌入 C1 生成 mesh」→ 五維度全 present、runtime/editor/loop/deform_si 皆 PASS + stiffness 有限 + overall_pass + deform_si gated≥1 | PASS(stiffness 50.49、gated 1 件靜態乾淨) |
| D1-2 與 v1 一致(無漂移) | validate_v2 的 errors/loop/stiffness 與**真正 validator_v1 subprocess** 逐項一致 | PASS(errors 集合相同、stiffness 50.49==50.49) |
| D1-3 真實 deform 真值 | 真實 main_draw → deform_si 對 4 美術 mesh has_real_deform=True 且 clean(si=0) | PASS(4/4 mesh,curtain/shadow 皆 si=0) |
| D1-4 生成 mesh 在閘內 | C1 生成 strip mesh 經 validator_v2 **實際接線的** deform 引擎套真實場(源自原 artist uvs 轉移)→ si=0 clean;附帶:把生成幾何塞回 artist mesh-specific deform timeline(頂點佈局不一致)被抓 si>0 | PASS(正確轉移 si=0;inconsistent 構法 si=44 被抓) |
| D1-5 每維度各有牙 | 同一條 validate_v2 指令分別抓到:末鍵 curve→editor FAIL、破壞 loop→loop FAIL、hull tangle→deform_si FAIL、破壞 bone 引用→runtime FAIL | PASS(4/4 維度) |

跑:`python3 tools/analyzer/validate_d1_validator.py [--json]`。
單跑統一閘:`python3 skills/spine-ai-editor/assets/validator_v2.py <skel.json> [atlas] [--loop-anims A,B] [--json]`。

## 關鍵發現

1. **「合成單一閘」的正確性 = in-process 複用單一真相來源 + 與 CLI 逐項對齊**。validator_v2 不
   重寫判準,只合流 `validator_v1.run_checks()`(維度 1–4)+ `deform_si_gate`(維度 5);D1-2
   用 subprocess CLI 逐項對齊證無漂移。重構 v1 時**守住 stdout 逐字不變**是硬約束(B1 bridge 解析它)。
2. **deform timeline 綁定特定 mesh 的頂點佈局**。把一個件的幾何換掉、卻保留為「原 artist mesh」
   authored 的 deform timeline = **inconsistent skeleton**(頂點數/序不符),統一閘如實抓到 si>0
   (**不放水**)。正確驗「生成 mesh 耐真實變形」的方式是把 artist uvs 的真實位移場**轉移**到生成
   mesh(C1-2 / D1-4 的構法:場源自原 skeleton、mesh 為生成件),而非就地換幾何再讀。
3. **stiffness 是美術手感(A 類)→ 預設只量化、不硬閘**。只有客觀維度(runtime/editor/loop/deform_si)
   參與 overall_pass;`--stiffness-gate` 可選擇把「有限性」納入(非數值門檻)。
4. **weighted mesh 的逐骨 skinning 變形屬 C2 `weighted_deform_eval` 範疇**,統一閘對 weighted
   mesh(len(vertices)!=len(uvs))只驗 schema、不列 si 硬閘(honest boundary;未來可加一條
   weighted-deform 維度把 C2 閘也併進來)。

## 誠實邊界 / honest boundary

- **runtime「可載入」= validator_v0 schema/引用完整性**,作 spine-webgl 無頭載入的 CPU 代理;
  Cocos/viewer 實機載入 = 使用者端(排程 scope 邊界)。
- **main_draw 本身整體非 overall_pass 屬資產性質**:它是一次性開獎動畫(非 loop)、且含 clipping
  attachment(root)不在 atlas → runtime/loop 維度如實報 FAIL。D1-3 因此只斷言 **deform_si 維度**
  (真實 mesh 變形紀律),不斷言 main_draw overall。
- **linkedmesh / region / clipping** 不進 deform_si(linkedmesh 共用母 mesh 幾何、其餘非 mesh)。
- **過渡期相依**:validator_v2 `import gen_lib.mesh` → repo `tools/mesh_gen`,與 B/C 各 chunk 一致;
  **E1** bundle 後移除。
- **單一真值資產**:main_draw(4 美術 mesh)+ Award(生成件來源)+ B1 cascade 生成大獎 fixture。

回歸 **0 RED**(新增 cap `d1_validator` L2 pipeline,併入 `spine-anim-forge` 仍 HOLD)。
