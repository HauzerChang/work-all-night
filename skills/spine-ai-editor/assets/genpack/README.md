# genpack — self-contained generation/eval bundle (E1)

這是 **spine-ai-editor 2.0** 的「自帶生成引擎」套件（MERGE_PLAN_2.0 的 **G5｜self-contained**）。
把本 research repo `tools/` 裡、`gen_lib` 與 `validator_v2` 公開 API 會用到的確定性純 CPU
模組，**byte-identical trimmed copy** 進來，讓這個 skill 在**使用者端沒有 repo `tools/`** 時也能跑。

## 內容（13 模組，來源見 `MANIFEST.json`）

- 動畫生成：`gen_animations.py`（cascade/pop/reveal/wobble/twist/squash/combo/charge + 序列 compose/crossfade/loop + C1 判準）、
  `beat_templates.py`、`tier_variants.py`、`spine_anim.py`（取樣/重取樣）、`pivot_rotation.py`（繞關節 `Δ=(M−I)(O−P)`）。
- mesh 生成/變形閘：`generate_mesh_v2.py`（strip，預設）、`generate_mesh.py`（v1 fallback）、
  `deform_eval.py`（真實位移場轉移自交閘）、`generate_weighted_mesh.py`（heat-diffusion/BBW 近似）、
  `weighted_deform_eval.py`、`atlas_crop.py`。
- rig 自動推斷：`infer_pivots.py`（父子接觸縫 pivot）、`infer_tree.py`（肢體父子樹）。

## 怎麼被載入

`gen_lib/*.py` 與 `validator_v2.py` 的 `_wire_repo_tools()` 會**優先**把本 `genpack/` 掛上
`sys.path`（repo `tools/` 僅作開發環境 fallback）。使用者端的 `.skill` 只帶 `assets/`，所以
載到的就是本 bundle。第三方套件（numpy / opencv / triangle / scipy）屬 pip 相依（見 `requirements`），
不在 bundle 範圍。

## 不在 bundle 內的相依（honest boundary）

- `analyze_target`（分層 PSD → 五段規格，S1 前端）**僅** `make_beat.parts_from_psd()` 的 PSD 輸入路徑用到；
  這是可選的輸入前端（需 psd-tools / PIL），核心「parts/影像 → 生成 → 驗收」API 不需要它。
  該路徑在 bundle 不含時會退回 repo `tools/analyzer`，取不到時給清楚錯誤。

## 同步紀律（防漂移）

`MANIFEST.json` 記錄每個 bundled 檔對應的 repo 來源與 sha256。閘
`tools/analyzer/validate_e1_bundle.py` 會驗證 bundle 與 repo 來源**仍逐位元一致**——
若未來某 run 改了 repo `tools/` 卻忘了重 bundle，閘會 RED 擋下。重 bundle = 重跑 E1 的 cp + manifest 步驟。
