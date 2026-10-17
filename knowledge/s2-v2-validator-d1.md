# 2.0 (D1) 統一品質閘 validator_v2:六維度一鍵雙真值

> **結論**:把 research repo 的「閘紀律」＋ v1.3.0 `validator_v1` 合成**單一指令**
> `skills/spine-ai-editor/assets/validator_v2.py`,對一支 2.0 生成的(大獎)動畫**一鍵輸出
> 全維度 pass/fail ＋ 量化指標**。這是 2.0 的 **G2(雙真值驗收)** 在**一條可重跑機讀閘**裡的落點。
> **依據**:`tools/analyzer/validate_d1_validator_v2.py` 5 AC 全 PASS(exit 0);`check_readiness` 0 RED。
> **信心**:高(核心四維 self-contained,延伸兩維對真實資產/合成負對照皆有牙)。
> **相關階段**:MERGE_PLAN_2.0 **Phase D1**(承 B1..B4 + C1/C2,Phase C 完成後進入 D 統一閘)。

## 為什麼要這個 chunk

B1..C2 把 repo 的生成/推斷器逐一抽成 skill 入口,每個 chunk **各自**配一個閘(`validate_bN/cN_*.py`)。
但 2.0 的對外承諾是 **G2 雙真值**:生成的動畫要「**遊戲能播(runtime 可載入)** 且 **編輯器能匯入**」,
再加上 loop 閉合 / stiffness / mesh 不撕裂 / 自接點平滑。這些維度此前**散在各閘**,沒有一條指令能對
「一支 2.0 產物」一次跑完所有維度。D1 把它們合成**單一 `validate_v2()` 函式 + CLI**,成為交付時的統一驗收點。

## validator_v2 六維度(每項獨立 PASS / FAIL / NA / UNAVAILABLE)

| # | 維度 | 來源 | 判準 |
|---|---|---|---|
| 1 | `runtime_loadable` | `validator_v0`(schema + 引用完整性) | 0 error = spine-webgl 載入的純 CPU 代理 |
| 2 | `editor_importable` | 地雷 #12 末鍵 curve + cx(curve/c3)超 [0,1] | = v1.3.0 validator_v1 編輯器真值,0 問題 |
| 3 | `loop_closure` | `curve_tools.loop_closure_report` | 首尾閉合 + 首鍵 0 / 末鍵 dur + key 單調 |
| 4 | `stiffness` | `curve_tools.stiffness_metric` | 永遠回報;`--stiffness-max` 才當硬閘 |
| 5 | `deform_si` | `gen_lib.mesh.deform_si_gate` | mesh 在真實 deform 下 si/flip/degen=0;無 mesh+deform → NA |
| 6 | `c1_continuity` | `gen_animations.is_c1_loopable` | loop 動畫自接點值+速度皆連續;不傳 `--loop-anims` → NA |

- **核心 1–4 self-contained**(只依賴同資料夾 `validator_v0` / `curve_tools`)。
- **延伸 5–6** 過渡期 lazy import repo tools;import 不到 → **UNAVAILABLE**(不拖垮核心,使用者端無 repo tools 仍能跑核心四維)。

## 驗收結果(validate_d1_validator_v2.py 5 AC 全 PASS)

- **D1-1 unified-report**:對一支 **2.0 生成**(gen_lib `generate_bigwin` 公開 API)cascade 大獎動畫,一鍵輸出
  六維度結構完整報告(每維 status/metrics/problems;核心四維有值;stiffness=16.46)。
- **D1-2 headline-G2**:該 2.0 大獎動畫**所有可檢維度 PASS** —— runtime(0 error)+ editor(0 地雷#12)+
  loop(首尾 identity)+ stiffness(16.46 有限)→ `overall_pass=True`;deform_si / c1 為 NA(大獎 beat 無 mesh、
  一次性 beat 不傳 --loop-anims)。**一條指令證「遊戲能播 且 編輯器能匯入 且 可循環」**。
- **D1-3 deform-truth**:對**真實資產 main_draw**(4 mesh×deform)→ deform_si 維度**逐 mesh clean(si=0)**
  (curtain_left/right 在 main_draw_close 幀、shadow/shadow2 在 main_draw_open 幀皆 si=0)。藝術家真值本身過閘
  (= checker_validated,承 C1/C2 的真值校準)→ 證**維度非假性過**。
- **D1-4 c1-discriminate**:idle Loop(`generate_idle`)→ c1_continuity **PASS**(C1-loopable);一次性大獎 beat 當
  loop_anims → **FAIL**(非 C1-loopable)→ 維度能把**真 Loop** 與**一次性 beat** 乾淨分開。
- **D1-5 gate-non-vacuous(四維各一負對照)**:(a)注入末鍵 curve → editor_importable **FAIL** + overall FAIL;
  (b)破壞 scale 末鍵值 → loop_closure **FAIL**;(c)移除 root bone → runtime_loadable **FAIL**;
  (d)main_draw 某 mesh 對調兩非相鄰 hull 頂點造 tangle → deform_si **FAIL**(si=34)。四維皆抓到。

## 關鍵發現

1. **兩套品質閘 + 結構軸變形閘 + 序列平滑閘可合成單一可重跑機讀閘**:runtime(spine-webgl 可載入)、
   editor(Spine editor 可匯入,地雷 #12 程式化代理)、deform_si(C1 的真實位移場轉移)、c1(B4 的自接點 C1)
   原本散在 B1/C1/B4 各閘,D1 證它們可用同一 `validate_v2()` 一次跑完 → **G2 不必人工開 Spine editor**。
2. **NA vs FAIL 的語意分離是誠實關鍵**:一次性大獎 beat 首尾 identity 但自接點速度突變(B4/L-4 已證非 C1-loopable)
   → **不傳 `--loop-anims` 時 c1 標 NA 而非 FAIL**,傳才當硬閘。否則會把「本就不該循環的 beat」誤判成品質問題。
   deform_si 同理:無 mesh+deform 的件 → NA,不是過。`overall_pass` 只看**非 NA / 非 UNAVAILABLE** 的維度。
3. **核心四維 self-contained、延伸兩維 graceful degrade**:validator_v0 + curve_tools 已在 `assets/`,核心四維
   在使用者端(無 repo `tools/`)也能跑;deform_si / c1 import 不到時標 UNAVAILABLE(不讓延伸維度拖垮核心),
   E1 bundle 後兩維亦 self-contained。這是 G5(self-contained)在過渡期的務實形態。

## 護欄 / 誠實邊界

- **真相來源**:runtime 維度為 spine-webgl 載入的**純 CPU schema 代理**(排程 scope 邊界,Cocos/viewer 實機載入
  與 PMA 視覺 = 使用者端);deform_si 一律用 `deform_eval` 真實位移場轉移(承 C1,不用未校準 stress_field)。
- **stiffness 絕對門檻屬美術手感**(A 類):預設只回報數值不當硬閘,`--stiffness-max` 才啟用。
- **過渡期相依**:`validator_v2` 延伸兩維 lazy import repo `tools/analyzer` + `tools/mesh_gen`,與 B2..C2 一致;
  **E1** bundle 後移除(核心四維已無此相依)。
- **單一真值資產**:deform 真值校準用 main_draw 4 mesh;2.0 產物用 gen_lib `DEMO_PARTS` 生成的 robot 替身。

## 回歸

`check_readiness.py` 全綠(新增 cap `d1_validator_v2` L2 pipeline,併入 `spine-anim-forge` 仍 HOLD,0 RED、無 GREEN→RED);
B1 bridge 閘 + gen_lib `__init__` 匯入逐一 PASS,證無回歸。`validator_v2.py` / 閘皆純新增,無改任何既有生成/產線值。

## 下一步

Phase **E**(打包升版 & 交付,里程碑 / C 類拍板):E1 生成碼 bundle 進 `assets/`(self-contained,滿足 G5)、
E2 改寫 `SKILL.md` → 2.0.0、E3 跑 readiness + 重 zip、E4 依 RULES C 類回報使用者拍板是否 sync。
(Phase B/C/D 核心升級全完成;E 為交付層,其中打包/安裝屬帳號層級需使用者決定。)
