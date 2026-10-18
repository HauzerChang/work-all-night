# 2.0 (E1) self-contained bundle — 生成/驗收碼打包進 skill,移除 repo `tools/` 硬相依

> MERGE_PLAN_2.0 **Phase E / E1**(承 B/C/D 全部,收斂護欄 **G5「self-contained」**)。
> 排程主線 = 產出 **spine-ai-editor 2.0**。2026-10-18 run 009。cap `e1_bundle` L2 eval,回歸 **0 RED**。

## 問題 / 為何這個 chunk 有價值

B/C/D 把 repo 半年累積的生成器 + 統一閘搬進 `skills/spine-ai-editor/`,但**每個入口的
`_wire_repo_tools()` 過渡期仍 import repo 的 `tools/analyzer` / `tools/mesh_gen` / `tools/rig`**:

- `gen_lib.make_beat` / `pivot_axis` / `sequence` → `gen_animations` / `pivot_rotation` / `spine_anim`(analyzer)
- `gen_lib.mesh` → `generate_mesh_v2` / `deform_eval` / `atlas_crop`(mesh_gen)
- `gen_lib.rig` → `generate_weighted_mesh` / `weighted_deform_eval` / `infer_pivots` / `infer_tree`(mesh_gen+rig)
- `validator_v2` 維度 5/6 → `gen_lib.mesh` + `gen_animations`

**純使用者端(只拿到 skill 資料夾、沒有本 research repo)會 import 不到而爆。**
G5 要求「最終打包時生成碼要 bundle 進 `assets/`,不可讓 skill 在使用者端 import 不存在的 `tools/`」。
E1 把這條過渡期相依收掉:skill 自帶所需生成碼,repo 外也能跑。

## 做了什麼(純新增 bundle + 無損 rewire)

### 1. `assets/gen_lib/_bundled/` — 18 模組的 import 閉包(trimmed copy)

從 B/C/D 入口實際會 wire 的 10 個進入點出發,對 `tools/{analyzer,mesh_gen,rig}` 做**靜態 import 閉包**,
得 **18 個模組**(repo 三個 tool 目錄共 93 個 `.py` → 只搬 18,真正 trimmed):

```
analyze_target  atlas_crop  beat_templates  deform_eval  evaluate_mesh  gen_animations
generate_mesh  generate_mesh_v2  generate_weighted_mesh  genre_priors  infer_pivots
infer_tree  pivot_rotation  psd_slice  spine_anim  tier_variants
validate_against_real  weighted_deform_eval
```

- **逐 byte 複製**(非改寫),附 `BUNDLE_MANIFEST.json`(每模組 `{from, sha256}`)→ 可機讀驗漂移、可重建。
- 放成**一個扁平目錄**:這些 repo 模組本就用「同目錄平面 import」(各自 `sys.path.insert` 自己的 dir),
  全放進同一個 `_bundled/` 後彼此的 `import X` 自然在 bundle 內解析(**不是** package,**無** `__init__.py`,
  否則平面 `import gen_animations` 會壞)。外部相依(numpy/cv2/scipy/triangle/psd_tools/PIL)是 pip 套件,
  不屬 G5 的 repo-tools 相依,留給 `requirements.txt`。

### 2. 各 `_wire_repo_tools()` 改為「bundle 優先、repo tools fallback」

`make_beat` / `mesh` / `rig` / `validator_v2` 四處 shim(`sequence` / `pivot_axis` 共用 `make_beat` 的 shim):
把 `_bundled/` **插到 `sys.path` 最前**(優先來源),repo `tools/` 僅在 `_bundled/` 不存在時當 repo 環境 fallback
(`os.path.isdir` 守衛 → repo 外那些路徑不存在也不插)。

- **為什麼零回歸**:repo 內既有閘(validate_b2/c1/d1…)自己會先 `import` repo 版(`sys.modules` 快取),
  gen_lib 之後再 wire 拿到的是**同名快取**;且 bundle 與 repo **逐 byte 相同** → 行為完全一致。
- **為什麼 self-contained**:repo 外只有 `_bundled/` 提供這些模組 → 預設真值來源即 bundle。

## 閘:`tools/analyzer/validate_e1_bundle.py` — 5 AC 全 PASS

最可信的 self-containment 證法**不是靜態掃 import**(蓋不到 `sys.path.insert` 的動態 wiring),
而是**把 `assets/` 複製到 repo 外、subprocess 清掉 env/sys.path 的 repo 路徑後實跑**:

- **E1-1 faithful_trimmed_copy**:manifest 列的 18 模組 sha256 == repo 原檔 == manifest 值(逐 byte);
  對 `_bundled/` **重算** import 閉包 → 所有「本地(repo-tool)import」都落在 bundle 內(**閉包完整、無漏相依**);
  18 << 93(trimmed)。
- **E1-2 generation_self_contained(headline)**:複製 `assets/` → repo 外 TEMP,subprocess `PYTHONPATH` 清空、
  只掛 `TEMP/assets` → `generate_bigwin` / `generate_idle` / `compose` / `crossfade` / `bone_origins_from_skel`
  全跑成(schema 合法);且 `gen_animations` / `generate_mesh_v2` / `generate_weighted_mesh` 的 `__file__`
  **皆在 `_bundled/`**(provenance 驗證),`sys.path` **不含** repo `tools/`。
- **E1-3 validator_self_contained**:同隔離環境 → `validate_v2` 對生成 beat 回
  **deform_si=na / c1=info / overall PASS**(維度 5/6 **wired**,非 `unavailable`);對 **main_draw 4 真實 mesh**
  `deform_si=pass`;`mesh.deform_si_gate`(curtain_left,clean/has_real_deform)與 `rig.infer_limb_tree`(root=torso)
  直呼亦成 → mesh_gen + rig 確實來自 bundle 且能算。
- **E1-4 negative_control**:同隔離環境**但刪掉 `_bundled/`** → `generate_bigwin` / mesh / rig 皆 **ImportError**
  (錯誤指名缺的模組);`validate_v2` 維度 5/6 退 **`unavailable`** 但維度 1-4 仍 **PASS**、overall 仍 True
  (graceful,不整支 crash)→ 證 **bundle 承重**(拿掉就壞)+ validator **降級正確**(閘非恆真)。
- **E1-5 zero_regression**:repo 環境既有閘 `validate_b2_genlib.py` 仍 `exit 0`(rewire 未破壞 repo 側)。

> 同場加映:rewire 後手動複跑 `validate_b2_genlib` / `validate_c1_mesh` / `validate_d1_validator_v2` 皆 exit 0。

## 關鍵發現

1. **self-containment 的可信證法 = 把資產搬出 repo 實跑**。靜態 grep import 看不到各入口用
   `sys.path.insert` + 平面 `import` 做的**動態 wiring**;唯有「複製 assets/ 到 repo 外、清 sys.path 的 repo 路徑、
   subprocess 跑生成 + 驗收」才真的證明「使用者端拿到的東西能動」,且用 `__file__` 做 **provenance 驗證**(解析自
   `_bundled/` 而非 repo)把「碰巧 repo 還在 path 上」的假性通過擋掉。
2. **逐 byte 複製 + sha256 manifest = 漂移防護**。bundle 不改寫內容(只搬位置),未來若有人改了 repo 的
   `tools/` 卻忘了 re-bundle,**E1-1 立刻 FAIL**(sha256 不符)提示重建 → bundle 不會悄悄過時。
3. **bundle 優先但零回歸**靠兩件事並存:repo 既有閘先 import repo 版(`sys.modules` 快取先到先贏)+
   bundle 與 repo **逐 byte 相同**。所以「predir = bundle」不改變任何 repo 內行為,只是讓**使用者端有東西可 import**。
4. **扁平 bundle 比重寫 import 省事且更安全**:這些 repo 模組本就假設「同目錄平面 import」,全丟進一個非 package
   的 `_bundled/` 即天然自洽;加 `__init__.py` 變 package 反而會破壞平面 `import gen_animations`。

## honest boundary

- 外部 pip 套件(numpy / opencv / scipy / triangle / psd_tools / Pillow)**仍需安裝**;G5 只管「不依賴 repo
  `tools/`」,不管 pip 相依(清單在 `requirements.txt`)。使用者端安裝 skill 時需一併備妥。
- Cocos / viewer 實機載入與 PMA 視覺確認 = 使用者端(排程 scope 邊界,本閘用 repo 外 subprocess + validator_v2
  無頭等價)。
- 本 chunk **只收過渡期相依**,未動任何生成/產線數值(bundle 逐 byte 同 repo;rewire 後 repo 側逐位元不變)。
- **E2**(改 `SKILL.md` → 2.0.0:核心能力表 + 觸發詞 + Changelog;更新 `INSTALL.md`)、**E3**(重跑
  `check_readiness` + 重 zip 成 `.skill` 交付檔)、**E4**(依 RULES **C 類**回報使用者拍板是否 sync,屬帳號層級)
  為後續 run。

回歸 **0 RED**(新增 cap `e1_bundle` L2 eval,併入 `spine-anim-forge` 仍 HOLD——生成能力的運動基元仍是手感先驗,
打包 self-contained 不改變 anim-forge 的 HOLD 理由)。
