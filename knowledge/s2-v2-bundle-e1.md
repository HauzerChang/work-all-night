# 2.0 (E1) self-contained bundle — gen_lib 生成碼 bundle 進 `_bundled/`，移除對 repo `tools/` 的硬相依

> MERGE_PLAN_2.0 **Phase E1**(承 B/C/D 全部;Phase E 第一步、護欄 **G5**)。排程主線 = 產出 **spine-ai-editor 2.0**。
> 2026-10-18 run 009。cap `e1_bundle` L2 pipeline,回歸 **0 RED**。

## 問題 / 為何這個 chunk 有價值

Phase B/C/D 把 repo 半年累積的生成器 + 評估器紀律逐一搬進 `skills/spine-ai-editor/assets/gen_lib`，
但每個入口的 `_wire_repo_tools()` 在**過渡期**都靠 `sys.path` 掛 research repo 的
`tools/analyzer`、`tools/mesh_gen`、`tools/rig`：

- `make_beat` / `sequence` / `pivot_axis` → `tools/analyzer`(gen_animations / pivot_rotation / spine_anim)
- `mesh` → `tools/mesh_gen`(generate_mesh_v2 / deform_eval / atlas_crop)
- `rig` → `tools/mesh_gen` + `tools/rig`(generate_weighted_mesh / weighted_deform_eval / infer_pivots / infer_tree)
- `validator_v2`(維度 5/6) → `tools/mesh_gen` + `tools/analyzer`

部署到使用者端時，skill 只帶 `skills/spine-ai-editor/`，**沒有** repo 的 `tools/` →
那些 import 會炸(護欄 **G5｜self-contained** 要求的正是「不可讓 skill 在使用者端 import 不存在的 `tools/`」)。
E1 把需要的模組 **bundle 進 skill 自身**，收斂成**碼層 self-contained**。

## 做了什麼(純搬運 + rewire,不改任何生成/檢查邏輯)

### 1. `skills/spine-ai-editor/assets/gen_lib/_bundled/` — 13 個 repo 模組的 verbatim copy

| bundled | repo 來源 | 為何需要 |
|---|---|---|
| gen_animations / beat_templates / tier_variants / spine_anim / pivot_rotation | `tools/analyzer/` | 動畫生成庫 + 繞 pivot 變換 + 取樣器 |
| generate_mesh_v2 / generate_mesh / deform_eval / atlas_crop | `tools/mesh_gen/` | mesh 生成 + 真實 deform 自交閘 |
| generate_weighted_mesh / weighted_deform_eval / infer_pivots / infer_tree | `tools/mesh_gen/`+`tools/rig/` | weighted mesh + rig 自動推斷 |

- **扁平目錄 + bare import**：bundled 模組彼此以 `import spine_anim` / `from beat_templates import …` 互引。
  各 `_wire_repo_tools()` 把 `_bundled/` 插在 `sys.path[0]` → 這些 bare import 必命中自帶副本，
  **無需改任何原檔**（連 `gen_animations ⇄ beat_templates` 的 circular import 也靠扁平目錄自然解）。
- **不納入 `analyze_target`**（+ `psd_slice`/`genre_priors`/PIL 鏈）：它只在 `gen_animations.main()` CLI 內
  **lazy import**、**不在 gen_lib 公開 API 路徑**上，bundle 它只會把 PIL/psd 相依拖進來。使用者端若要
  PSD→storyboard CLI 另屬 S4/analyzer 範疇，非本生成庫對外契約。

### 2. rewire 4 個 `_wire_repo_tools()`(make_beat / mesh / rig / validator_v2)

路徑從 repo `tools/*` 改為 `_bundled/`(+ `assets/` 取 curve_tools/validator_v1)。
**函式名沿用 `_wire_repo_tools`** → `pivot_axis`/`sequence` 等既有呼叫處簽章零改動、零回歸。
語意已從「掛 repo tools」變「掛 bundled + assets」,docstring 同步更新。

### 3. `_bundled/README.md` — provenance 表 + re-sync 指令

明列每個 bundled 檔的 repo 真值來源、為何扁平目錄可行、以及 repo 原檔更新時的 `cp` + 重驗 SOP。

## 閘 `tools/analyzer/validate_e1_bundle.py` — 5 AC 全 PASS

隔離測試的精髓:**把 `assets/` 整份複製到 `/tmp`(repo 樹外)**,subprocess `python3 -I`、cwd 在外、
`sys.path` 剝除所有含 `work-all-night` 的路徑 → 若 `_bundled/` 不自足就一定炸。

- **E1-1 bundle-complete**：`_bundled/` 含全 13 模組；4 個 `_wire_repo_tools()` 原始碼**不再出現**
  repo tools 路徑 tuple(`("tools","analyzer")` 等)且引用 `_bundled`。
- **E1-2 isolated-pipeline(headline)**：隔離環境 `write_bigwin` 產大獎 beat → `validator_v1` **0 error**
  → `validator_v2` **overall PASS**;`stiffness cascade=16.46` 與 repo D1 值**逐位一致** = 行為等價(非只是「能跑」)。
- **E1-3 isolated-mesh-rig**：隔離環境下 make_beat/mesh/rig 的 wire 回傳模組 `__file__` **落在 `_bundled/`**
  (非 repo tools/);rig `infer_limb_tree` 對合成鏈 recover 成鏈(torso→upper→lower)、對合成星形 recover 星形。
- **E1-4 byte-identical**：`_bundled/` 每檔與其 repo 原檔**逐 byte 相同**(13/13) → 不產生第二份真值。
- **E1-5 teeth**：(a)把隔離副本的 `gen_animations.py` 移走 → 一呼叫生成即丟「需要 self-contained bundle」
  **ImportError**、pipeline 無法 overall(證隔離確實隔離 + bundle 集**最小完整**,非被環境同名模組偷渡);
  (b)wired `gen_animations.__file__` 落在 `_bundled/`(證 rewire 生效、非仍偷用 repo)。

**回歸**:B1-D1 共 7 支既有閘(`validate_v2_bridge`/`b2`/`b3`/`b4`/`c1`/`c2`/`d1`)**全經 rewired 的 bundled 路徑
PASS** → `check_readiness` **0 RED**(新增 cap `e1_bundle` L2 pipeline,併入 `spine-anim-forge` 仍 HOLD)。

## 關鍵發現

1. **self-contained 的最強證明是「在 repo 樹外跑」**，而非 repo 內「恰好 import 到」——
   後者會被 repo 的 `tools/` 殘留在 sys.path 偷渡成功而假性過關。subprocess + 剝 `sys.path` + cwd 在外
   是唯一能真正模擬「使用者只拿到 skill 資料夾」的方式。
2. **byte-identical 守則**把「bundle 是副本」這件事變成可機讀不變量:避免副本日後悄悄漂移成**第二份真值**
   (gate E1-4 一不一致就 FAIL),re-sync SOP 寫在 `_bundled/README.md`。
3. **circular import 靠扁平目錄 + bare import 自然解**:`gen_animations ⇄ beat_templates`(repo 原本用「把
   beat_templates import 放檔尾 + try/except」化解)在 bundle 後完全沿用,**不需也不應改原檔**。
4. **函式名穩定 = 零回歸的槓桿**:只改 `_wire_repo_tools()` 內部路徑、不改其名與回傳簽章 → 所有呼叫處
   (含 D1 validator_v2 的維度 5/6)不動即遷移成功。

## honest boundary

- 本 chunk 只做**碼層 self-contained**。使用者端**真正打包/安裝**(`.skill` zip、sync 到帳號)屬 **E3/E4**
  ——其中 E4「是否 sync」是帳號層級 **C 類里程碑**,需使用者拍板(見 RULES 升級政策)。
- Cocos/viewer 實機載入、PMA 視覺確認仍 = 使用者端(排程 scope 邊界);本閘用 repo 樹外 subprocess 的
  spine-webgl 無頭等價(validator_v1/v2)。
- `analyze_target`/PIL/psd 鏈刻意不 bundle(非公開 API 路徑);若未來把 PSD→storyboard CLI 列入 skill 對外
  契約,再評估是否連 S4 analyzer 一起 bundle。

## 下一步

Phase **E2**:改寫 `skills/spine-ai-editor/SKILL.md` → **2.0.0**(把 B/C/D/E1 的新軸寫進核心能力表 +
觸發詞 + Changelog),更新 `INSTALL.md`。隨後 **E3**(跑 `check_readiness` 更新 `READINESS.md` + 重 zip 成
`.skill`)、**E4**(C 類回報使用者拍板是否 sync)。
