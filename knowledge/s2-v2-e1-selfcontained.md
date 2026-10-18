# 2.0 (E1) self-contained bundle:gen_lib / validator_v2 → bundled 生成引擎,repo tools/ 零相依

> MERGE_PLAN_2.0 **Phase E1**(承 B/C/D 全部,2026-10-18 run 009)。硬性正確性護欄 **G5**
> (「最終打包時生成碼要 bundle 進 `assets/`,不可讓 skill 在使用者端 import 不存在的 `tools/`」)。

## 背景:B2→D1 留下的過渡期相依

B/C/D 把 repo 半年累積的生成/評估引擎逐一抽成 skill 入口(`gen_lib.make_beat` / `pivot_axis` /
`sequence` / `mesh` / `rig` + `validator_v2`),但每個入口的 `_wire_repo_tools()` 都是**過渡期路徑
shim**:把本 research repo 的 `tools/analyzer`、`tools/mesh_gen`、`tools/rig` 掛上 `sys.path` 再
`import gen_animations` 等。這在排程(repo 環境)能跑,但**使用者端只裝 skill、沒有 `tools/`** →
`import gen_animations` 會 `ModuleNotFoundError`。E1 的 chunk 目標就是收斂掉這條硬相依。

## 做了什麼

### 1. bundle 13 個執行期模組(逐位元複本)進 `assets/gen_lib/_bundled/`

掃出 gen_lib 五模組 + validator_v2 執行期**實際**需要的 repo 模組(含傳遞相依),共 13 個:

| 來源 | 模組 |
|---|---|
| `tools/analyzer` | gen_animations · beat_templates · tier_variants · spine_anim · pivot_rotation |
| `tools/mesh_gen` | generate_mesh_v2 · generate_mesh · deform_eval · atlas_crop · generate_weighted_mesh · weighted_deform_eval |
| `tools/rig` | infer_pivots · infer_tree |

**相依封閉性**:這 13 個彼此以**裸名 import**(`import spine_anim`、`from deform_eval import ...`、
`from infer_pivots import ...`),全落在同一扁平資料夾 → 只要 `_bundled/` 在 `sys.path`,相依全數解析;
且多個模組 import 期自帶 `sys.path.insert(0, os.path.dirname(__file__))` → 進一步自我 bootstrap 同目錄
siblings。**刻意不 bundle** `analyze_target`(S1 PSD 反推分析器,連 `psd_slice`/`genre_priors`/PIL)——
只有 PSD 驅動路徑用得到,屬使用者端/過渡期;自主 CPU 生成路徑(DEMO_PARTS / 合成 mask / 合成 parts)完全不需要。

### 2. 五個 `_wire_repo_tools()` + 一個 `_wire()` 改指向 `_bundled/`

`gen_lib/{make_beat, mesh, rig}.py` 的 `_wire_repo_tools()`、`pivot_axis.py` 的 `_wire()`(透過
make_beat)、`validator_v2.py` 的 `_wire_repo_tools()` 全部改成把 `_bundled/`(+ `assets/` 供
curve_tools/validator_v1)掛上 `sys.path`,**不再 reference repo `tools/`**。錯誤訊息改為「bundle 應隨 skill 安裝」。

## 為何「逐位元複本」而非 trim

- **零回歸 by construction**:bundle 與 repo 來源 byte-identical → in-repo 既有 B/C/D 閘行為不變
  (in-repo 時 gate 多半已直接 import repo 模組,module cache 命中 repo 複本;external 時只有 bundle;
  兩邊同一份碼)。E1-5 實測六閘全 PASS。
- **完整性以 external 隔離測試證明**(見下),而非靠「看起來 import 得到」。

## 閘 `tools/analyzer/validate_e1_selfcontained.py` —— 5 AC 全 PASS

- **E1-1 bundle 完整 + 逐位元**:13 模組齊備、與 repo 來源 SHA-256 **byte-identical**、`_bundled/` 無未登錄的額外 `.py`。
  → bundle 是忠實複本,是零回歸與可稽核的根據。
- **E1-2(headline)external self-contained**:把整個 `assets/` **複製到 repo 外**(`tempfile`)、子程序
  `PYTHONPATH` 只給複製出的 assets、cwd 設中性空目錄(無 repo 在 import path)→ 跑 gen_lib 五模組公開 API:
  beat×4(cascade/pop/wobble/twist)過 validator_v2 硬閘、idle + 繞關節 pivot(轉 `b_arm_L/R`)、
  mesh 生成(合成橢圓 mask → nv=30/hull=22 schema 合法)、rig 推斷(合成 chain → root=torso、tree={upper,lower})、
  sequence compose+crossfade+write。**全成功,再掃 `sys.modules`:任何 `__file__` 落在 repo 內 = 洩漏 → 實測 0 洩漏**。
- **E1-3 negative control**:external 複本**移掉 `_bundled/`** → 生成 `ImportError`(rc=7,「No module named 'gen_animations'」)。
  證明生成確實靠 bundle 撐,不是某個環境 fallback。
- **E1-4 validator_v2 external 六維度**:四 beat 在 external 複本跑 `validate_v2` → 硬閘 runtime/editor/loop
  **PASS**、`deform_si`/`c1_continuity` **可用(na/info,非 unavailable)** → 統一閘的維度 5/6 bundle wire 也成功、overall PASS。
- **E1-5 in-repo 零回歸**:既有 B2/B3/B4/C1/C2/D1 **六閘** in-repo 仍全 exit 0。

## 關鍵發現

1. **「self-contained」的真正證明是 external 隔離 + `sys.modules` 洩漏掃描,不是「能 import」**——
   在 repo 內跑永遠 import 得到(repo 在 path),只有把 assets 搬出 repo、path 只留複本、再驗「沒有任何
   載入模組來自 repo」才算數。E1-2 的洩漏掃描是這個 chunk 的機讀落點。
2. **逐位元複本 = 零回歸 by construction**——不手動 trim 就不會引入 behavior drift;維護約定是「repo 來源
   改了就重新逐位元複製 + 重跑 E1-1」,兩邊永遠一致(E1-1 不一致即 FAIL,逼使同步)。
3. **G5 的邊界是「不 import 不存在的 tools/」,不是「不需要任何使用者資料」**——生成路徑 self-contained;
   但**真值校準資料**(`Award.json` 的藝術家 hull → weighted mesh 生成;`main_draw.json` → deform 真值)
   與 **PSD 反推**(analyze_target 鏈)本就該由使用者提供,刻意留在使用者端。external 測試因此只驗
   **合成 fixture 的 rig 推斷路徑**,weighted-mesh-from-Award 的生成留在 in-repo/C2 閘覆蓋。這是 honest boundary 非缺口。

## honest boundary

- weighted mesh **生成**需 Award hull 真值(使用者資料),external 測試只驗合成 rig 推斷;C2 閘仍在 in-repo 覆蓋該路徑。
- `parts_from_psd`(PSD 驅動取件)仍需 repo S1 分析器(analyze_target 鏈),刻意不 bundle → 使用者端/過渡期路徑。
- Cocos MCP / viewer 實機載入 = 使用者端(排程 scope 邊界);本閘用 external spine-webgl 無頭 + validator_v2 等價驗收。

## 回歸 / 產出

- 新增 cap `e1_selfcontained` L2 pipeline(閘 `validate_e1_selfcontained.py`),併入 `spine-anim-forge`(仍 HOLD)。回歸預期 **0 RED**。
- 產出:`assets/gen_lib/_bundled/`(13 模組 + README)、五處 wire 改寫、閘、本篇。
- **Phase E 下一步**:E2(改寫 `SKILL.md`→2.0.0 + `INSTALL.md`)、E3(重跑 readiness + 重 zip `.skill`)、
  E4(依 RULES **C 類**回報使用者拍板是否 sync——打包/安裝屬帳號層級)。
