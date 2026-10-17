# 2.0 (D1) 統一品質閘 validator_v2 — 全維度合成單一報告

> MERGE_PLAN_2.0 **Phase D1**(承 B/C 全部)。排程主線 = 產出 **spine-ai-editor 2.0**。
> 2026-10-17 run 008。cap `d1_validator_v2` L2 eval,回歸 **0 RED**。

## 問題 / 為何這個 chunk 有價值

Phase B/C 把 repo 半年累積的生成器逐一搬進 skill,**每個都配一支自己的閘**:
- 動畫生成:`gen_lib.make_beat`(B2)/ `pivot_axis`(B3)/ `sequence`(B4)。
- mesh/rig 生成:`gen_lib.mesh`(C1)/ `gen_lib.rig`(C2)。
- 品質真值:`validator_v0`(schema)、`validator_v1`(editor 匯入 + loop 閉合 + stiffness)、
  `gen_lib.mesh.deform_si_gate`(mesh 變形自交)、`gen_animations.is_c1_loopable`(C1 連續)。

驗收一支 2.0 生成動畫,要記住**上面四套閘各自怎麼跑、怎麼解讀、哪個維度看哪支**。
D1 把這些分散的驗收面**收斂成單一 `validator_v2`**——**一條指令輸出全維度 pass/fail + 量化指標**。

## 做了什麼(純新增 + 一次無損重構)

### 1. 新 `skills/spine-ai-editor/assets/validator_v2.py :: validate_v2()`
六維度統一品質閘,回傳結構化報告 `{overall_pass, source, hard_fail, dimensions:{...}}`。
每維度 `status ∈ {pass, fail, na, info, unavailable}`:

| 維度 | 來源 | 類型 | 判準 |
|---|---|---|---|
| `runtime_loadable` | `validator_v1` 的 v0 schema/ref error + cx 超界 | 硬閘 | runtime(spine-webgl)能不能載入 |
| `editor_importable` | `validator_v1` 的末鍵 curve error(地雷 #12) | 硬閘 | Spine editor 能不能匯入(runtime 會忽略,editor AIOOBE crash) |
| `loop_closure` | `curve_tools.loop_closure_report`(經 v1) | 硬閘 | 首尾值閉合 + key 單調 + 首鍵 0/末鍵 dur |
| `stiffness` | `curve_tools.stiffness_metric`(經 v1) | 量化指標 | key 處速度不連續量(越低越順);非有限才 fail |
| `deform_si` | `gen_lib.mesh.deform_si_gate`(C1) | 硬閘(有 mesh 時) | 每個 mesh 套真實 deform 位移場 si/flips/degen=0;無 mesh→na |
| `c1_continuity` | `gen_animations.is_c1_loopable`(B4) | 量化指標 | 自接點 C1-loopable + seam velocity gap;`--require-c1` 可升硬閘 |

`overall_pass` = 所有**硬閘**維度 PASS。`stiffness` 與未要求的 `c1` 只回報量化值不計入 overall(除非非有限)。

### 2. `validator_v1.py` 抽出程式化入口 `validate_v1()`(無損重構)
把 `main` 的檢查主體抽成 `validate_v1(json_path, atlas_path, loop_anims, want_metric) → (report, demoted, metrics)`,
`main` 只負責把結果格式化列印。**`main` 的 stdout 逐字不變**(B1-B4 四支閘都靠 subprocess 解析 v1 stdout,
重構後逐一重跑確認零回歸)。validator_v2 **import** `validate_v1` → 不產生第二套 editor/loop/stiffness 真值。

### 3. 新閘 `tools/analyzer/validate_d1_validator_v2.py`(5 AC)

## AC(全部客觀、可機讀)—— 5 AC 全 PASS

- **D1-1 unified-report**:對 **gen_lib 公開 API 生成**的大獎 beat(`generate_bigwin(DEMO_PARTS, "cascade")`),
  一次 `validate_v2()` 回傳含 6 維度的**單一報告**;硬閘(runtime/editor/loop)PASS、stiffness 有限(cascade 16.46)、
  `deform_si=na`(region 占位 beat 無 mesh)、`c1=info`(一次性 beat 預期非 C1)、overall PASS。
- **D1-2 runtime|editor 語意切分非恆真**:(a)注入末鍵 curve → `editor_importable` **FAIL** 但
  `runtime_loadable` **仍 PASS**(乾淨切分);(b)G1 `strip_last_frame_curves` 後 editor 回 PASS;
  (c)注入 cx>1(非末鍵)→ `runtime_loadable` **FAIL**(bezier runtime 解錯)。
- **D1-3 loop-closure**:生成 beat `loop_closure` PASS;破壞某 scale 末鍵值(首尾不一致)→ `loop_closure` **FAIL**
  (`open loop ...` 被抓)。
- **D1-4 deform-si(真值校準 + 負對照 + na)**:對 **main_draw(4 真實美術 mesh + 真實 deform)**
  `deform_si` **PASS**(藝術家 mesh 套真實位移場 si=0,4 mesh 全 clean = 真值校準);**負對照**把某 unweighted mesh
  hull 兩非相鄰頂點座標對調造 tangle → `deform_si` **FAIL**(worst si=39);生成 region beat → `deform_si` **na**。
- **D1-5 c1 + overall 組合非恆真**:idle Loop(`compose_idle_loop`)`is_c1_loopable`=True(seam vel gap 0.19)→
  `--require-c1 Idle_Loop` c1 升硬閘 **PASS** + overall PASS;一次性大獎 beat 預設 `c1=info`(不害 overall)、
  但 `--require-c1` 指到它 → c1 **FAIL** + overall FAIL;**overall 非恆真**:缺頂層 key 的壞 skeleton →
  `runtime_loadable` FAIL → overall FAIL。

## 關鍵發現

1. **「統一閘」的價值是語意切分而非檢查疊加**。validator_v1 把「runtime 載不進來(schema/cx)」與
   「editor 匯入 crash(末鍵 curve)」**混在同一份 error list**。validator_v2 依 error 字串前綴把它們拆成
   **兩個獨立維度**,才讓 G2「遊戲能播 **且** 編輯器能匯入」的雙真值**可逐維機讀判定**——這是 D1 的真正增量
   (不是「把 N 支閘串起來跑」,是「把混在一起的真值切開」)。
2. **編排層不產生第二套真值**。validator_v2 全靠 import 既有(各自已有負對照的)閘:抽 v1 程式化入口 +
   直呼 `gen_lib.mesh` / `gen_animations`。故各維度的**負對照紀律自動繼承**,D1 的閘只需證「編排正確」
   (6 維度都接對、overall 組合邏輯對),不必重證每個檢查本身非恆真。
3. **過渡期相依要優雅降級**。deform_si(需 repo `tools/mesh_gen`)、c1(需 `tools/analyzer`)取不到時標
   `unavailable`(不讓整支 crash),standalone 的維度 1-4(只需 assets/ 的 v0/v1/curve_tools)仍可跑。
   這對應 G5:E1 bundle 後補齊,過渡期先可用。
4. **硬閘 / 量化指標分層**。runtime/editor/loop(+ 有 mesh 時 deform_si)是硬閘;stiffness 與未要求的 C1
   是量化刻畫(一次性大獎 beat **本就** C0 可接但非 C1,是刻畫非失敗)。要求某動畫 C1 平滑(idle Loop 類)
   用 `--require-c1` 升硬閘 —— 讓同一支閘同時服務「大獎一次性」與「idle 可循環」兩種驗收語意。

## honest boundary

- Cocos/viewer 實機載入與 PMA 視覺 = **使用者端**(排程 scope 邊界);排程用 spine-webgl 無頭等價仍留 E 階段。
- stiffness 與未要求的 C1 為**量化指標非硬閘**(多低才算順屬手感 A 類)。
- 過渡期 import repo `tools/`(E1 self-contained bundle 後移除)。
- 真值資產 = gen_lib 生成 beat + main_draw 4 mesh(單一真值,防固化)。

## 用法

```
# 全維度精簡報告
python3 skills/spine-ai-editor/assets/validator_v2.py Main.json [Main.atlas]
python3 skills/spine-ai-editor/assets/validator_v2.py Main.json --loop-anims Loop
python3 skills/spine-ai-editor/assets/validator_v2.py Main.json --require-c1 Idle_Loop
python3 skills/spine-ai-editor/assets/validator_v2.py Main.json --json      # 機讀

# 程式化
from validator_v2 import validate_v2
rep = validate_v2("Main.json"); rep["overall_pass"]; rep["dimensions"]["deform_si"]["status"]

# D1 回歸閘
python3 tools/analyzer/validate_d1_validator_v2.py [--json]
```

## 下一步

Phase D 完成 → **Phase E(打包升版 & 交付)**。E1:把生成碼 bundle 進 `assets/`(self-contained,滿足 G5),
移除對 repo `tools/` 的硬相依(含 validator_v2 的 `_wire_repo_tools` shim)。E2 改 SKILL.md→2.0.0、
E3 跑 readiness + 重 zip、E4 依 RULES C 類回報使用者拍板是否 sync。
