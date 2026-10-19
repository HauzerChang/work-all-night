# 2.0 (E1) self-contained bundle:生成碼 verbatim 進 `_vendor/`,移除對 repo `tools/` 的硬相依(G5)

- **結論**:spine-ai-editor 2.0 的 `gen_lib`(B2..C2 搬進來的生成庫)與 `validator_v2`(D1 統一閘)在 B/C/D
  階段都是**過渡期 import repo `tools/`**(analyzer/mesh_gen/rig)才跑得動——在使用者端(只有 skill、沒有
  research repo)會 `ImportError`。**E1 把這 13 個 repo 生成模組 verbatim 複製進
  `skills/spine-ai-editor/assets/gen_lib/_vendor/`**,並把每個 `_wire_repo_tools()` 改成**優先掛 `_vendor/`**
  → skill 單獨搬走、清掉 PYTHONPATH 仍能生成 + 六維度驗收。**MERGE_PLAN 的 G5(self-contained)達成**。
- **信心**:高。`tools/analyzer/validate_e1_bundle.py` **5 AC 全 PASS**(隔離環境實測:把 skill 複製到無
  repo `tools/` 的 tmp 根 + 清 PYTHONPATH,生成與驗收全綠);check_readiness **0 RED**(verbatim 複製 → 零回歸)。
- **相關階段**:專案第 3 階段(整合成可交付 pipeline/skill);MERGE_PLAN_2.0 **Phase E1**(承 B/C/D 全部)。

## 問題:X 搬進來 ≠ 使用者端跑得動

B2..C2 把生成器抽成 `gen_lib/*.py`、D1 合成 `validator_v2.py`,但每支都靠 `_wire_repo_tools()` 把 repo 的
`tools/analyzer`、`tools/mesh_gen`、`tools/rig` 掛上 `sys.path` 再 `import gen_animations` 等。排程環境下
SessionStart hook 把這些路徑塞進 PYTHONPATH,所以 gate 一直綠;**但 skill 一旦交付到使用者帳號(沒有 research
repo),這些 bare import 會全部失敗**。G5 就是為了堵這個洞:「生成碼要 bundle 進 `assets/`,不可讓 skill 在
使用者端 import 不存在的 `tools/`」。

## 做了什麼(全 additive,repo 產線值零改動)

1. **13 個 repo 模組 verbatim 複製進 `assets/gen_lib/_vendor/`**(逐一 byte-identical):
   - `tools/analyzer`:`gen_animations` / `spine_anim` / `beat_templates` / `tier_variants` / `pivot_rotation`
   - `tools/mesh_gen`:`generate_mesh_v2` / `generate_mesh` / `deform_eval` / `atlas_crop` /
     `generate_weighted_mesh` / `weighted_deform_eval`
   - `tools/rig`:`infer_pivots` / `infer_tree`
2. **4 處 `_wire_repo_tools()` 改成優先掛 `_vendor/`**(`make_beat.py` / `mesh.py` / `rig.py` /
   `validator_v2.py`;`sequence.py`+`pivot_axis.py` 經 `make_beat._wire_repo_tools` 代理,免改)。
   手法:`for p in reversed((vendor, ...repo tools...)): sys.path.insert(0, p)` → `_vendor` 最終排最前。
   repo `tools/` 保留為**次要 fallback**。
3. 更新 `gen_lib/__init__.py` 與各模組 docstring(E1 已完成的說明)。
4. 新閘 `tools/analyzer/validate_e1_bundle.py`(5 AC)。

## 關鍵發現

1. **隔離手法是整個驗收的樞紐**:把 `skills/spine-ai-editor/` 整包複製到 `tmp_root/spine-ai-editor/`,child
   以 `cwd=tmp_root`、env 去掉 `PYTHONPATH` 跑。`_wire` 算的 `repo = 四層上 = tmp_root`,其下**沒有 `tools/`**,
   PYTHONPATH 也空 → **唯一能 import 到生成碼的來源就是 `_vendor/`**。這才是真正證明 self-contained 的方法
   (在 repo 環境裡跑永遠分不清是靠 _vendor 還是靠 PYTHONPATH)。
2. **verbatim(非 trim)是零回歸的保證**:repo 環境下 `import gen_animations` 會**先命中 PYTHONPATH 上的 repo
   複本**(或先前 gate 已載入的 `sys.modules` 快取),行為與 E1 前**逐位元一致** → 既有 70 閘零回歸;使用者端
   無 repo 時命中 `_vendor`,**同一份碼**。兩邊行為必然一致,因為是 verbatim。(trim 要逐函式證等價才能保零
   回歸,成本高;E1 先求 self-contained,縮肥列為後續 nice-to-have。)
3. **負對照證隔離真的靠 `_vendor`**:在隔離 skill 複本**刪掉 `_vendor/gen_animations.py`**(`_wire` 直接
   import 的核心模組,必在 cascade 生成路徑上)→ `generate_bigwin` 如預期 `ImportError`。這排除「其實偷偷走了
   別處的複本、_vendor 是死碼」的假性過關。(第一版誤選 `spine_anim.py` 當犧牲品 → 刪了仍過:因 `spine_anim`
   只被 gen_animations 的**特定 lazy 路徑**用,cascade 生成不觸發 → 教訓:負對照的犧牲品要選**在被測路徑上**的
   模組。)
4. **honest trimming 的一個真實案例**:`gen_animations.main()` 裡 `from analyze_target import analyze` 會牽出
   `PIL` / `psd_slice` / `genre_priors` 一大串子樹,但那是 **CLI-only 的 lazy import**,`gen_lib` 從不呼叫
   `main()` → **不需要 bundle**。靠「實際被 import 的才搬」把 bundle 收斂在 13 個,而非無腦全搬 `tools/`。

## 5 AC(`validate_e1_bundle.py`,全自動量化)

- **E1-1 bundle-complete**:`_vendor/` 含 13 模組、逐一與 repo 原檔 **byte-identical**、在**隔離 sys.path
  (只有 _vendor)**下全部 import OK。
- **E1-2 anim-headline(headline)**:隔離環境下 `generate_bigwin(DEMO_PARTS, 'cascade')` →
  `validator_v2.validate_v2` **六維度單一報告**,硬閘 runtime/editor/loop PASS + `overall_pass=True`(純碼、
  無外部資產)。
- **E1-3 mesh-headline**:同隔離下 `generate_and_gate_part`(main_draw `curtain_left`,絕對路徑傳入=使用者
  data)→ strip mesh 30 頂點、真實 deform `clean=True`、`overall_pass=True`(證 numpy/cv2/scipy 走 `_vendor`
  的生成/評估碼可 standalone)。
- **E1-4 v2-six-dim**:同隔離下 validator_v2 維度 5(`deform_si=na`)/ 維度 6(`c1_continuity=info`)皆成功
  **wire**(非 `unavailable`)→ 六維度全可跑,不再因缺 repo tools 而退化。
- **E1-5 neg-control**:隔離 skill 複本刪掉 vendored `gen_animations.py` → `generate_bigwin` 如預期
  `ImportError`(證 `_vendor` 確為隔離下真正被用的相依,非死碼/非偷偷走他處)。

## honest boundary / 未解

- `_vendor` 是 **verbatim 複本非 trimmed**——G5 self-contained 已達成,縮肥(砍掉各模組未用函式)列為後續
  nice-to-have,且需逐函式等價證明才能保零回歸。
- E1-3 需 `main_draw` 使用者資產(**data 非 code**);self-contained 要求的是**碼**自帶,使用者 spine 資產本
  就是使用者輸入。
- **E2**(改寫 `SKILL.md` → 2.0.0:新軸寫進核心能力表 + 觸發詞 + Changelog;更新 `INSTALL.md`)、
  **E3**(跑 check_readiness 更 `READINESS.md` + 重 zip 成 `.skill`)、**E4**(依 RULES **C 類**回報使用者拍板
  是否 sync,打包/安裝屬帳號層級)為後續 chunk。
- cap `e1_bundle` L2 pipeline 併入 `spine-anim-forge`,該區塊**仍 HOLD**(運動基元為手感先驗、真實多 rig 真值
  屬使用者資源,見 PLAN/READINESS)。
