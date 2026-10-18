# `_bundled/` — spine-ai-editor 2.0 self-contained 生成碼（E1，2026-10-18）

MERGE_PLAN_2.0 **Phase E1** 的落點：把 `gen_lib`(make_beat / pivot_axis / sequence / mesh / rig)
與 `validator_v2` 原本**過渡期 import 的 repo `tools/` 模組**，以 **verbatim copy** bundle 進此目錄，
使本 skill **不再相依 research repo 的 `tools/`**（滿足護欄 **G5｜self-contained**）。

部署到使用者端時，skill 只帶 `skills/spine-ai-editor/`，沒有 repo 的 `tools/`；E1 之前各
`_wire_repo_tools()` 會 `import 不存在的 tools/` 而炸。E1 後它們一律指向本 `_bundled/`。

## 真值來源（provenance）— 本目錄每檔皆為下列 repo 檔的逐 byte 副本

| bundled 檔 | repo 來源 | 用途 |
|---|---|---|
| `gen_animations.py` | `tools/analyzer/gen_animations.py` | 確定性大獎生成庫（cascade/pop/wobble/twist…、序列 compose/crossfade、C1 判準 `is_c1_loopable`） |
| `beat_templates.py` | `tools/analyzer/beat_templates.py` | beat 模板（與 gen_animations 互為 circular import，兩者必須同在 bundle） |
| `tier_variants.py` | `tools/analyzer/tier_variants.py` | 檔位幅度差異化（gen_animations 模組級 import） |
| `spine_anim.py` | `tools/analyzer/spine_anim.py` | Spine 3.8 取樣器（pivot_rotation / gen_animations 相依；自身無 repo 相依） |
| `pivot_rotation.py` | `tools/analyzer/pivot_rotation.py` | 繞任意點變換 `Δ=(M−I)(O−P)`（B3 pivot_axis 相依） |
| `generate_mesh_v2.py` | `tools/mesh_gen/generate_mesh_v2.py` | mesh 生成引擎（strip/delaunay/boundary-dense；C1） |
| `generate_mesh.py` | `tools/mesh_gen/generate_mesh.py` | v1 mesh 生成（generate_mesh_v2 lazy fallback） |
| `deform_eval.py` | `tools/mesh_gen/deform_eval.py` | 真實 deform 位移場自交閘（C1；weighted_deform_eval 相依） |
| `atlas_crop.py` | `tools/mesh_gen/atlas_crop.py` | atlas 裁切 / alpha 輪廓（infer_pivots lazy 相依） |
| `generate_weighted_mesh.py` | `tools/mesh_gen/generate_weighted_mesh.py` | weighted mesh 生成（heat-diffusion/BBW 近似；C2） |
| `weighted_deform_eval.py` | `tools/mesh_gen/weighted_deform_eval.py` | weighted 真實 skinning 自交閘（C2；infer_pivots 相依） |
| `infer_pivots.py` | `tools/rig/infer_pivots.py` | 關節 pivot 推斷（父子接觸縫；C2） |
| `infer_tree.py` | `tools/rig/infer_tree.py` | 肢體父子樹推斷（接觸距離；C2） |

> **未納入**：`analyze_target.py`（+ 其 `psd_slice`/`genre_priors`/PIL 鏈）只在 `gen_animations.main()`
> CLI 內 lazy import，**不在 gen_lib 公開 API 路徑上**，故不 bundle（避免拖進 PIL/psd 相依）。
> 使用者端若要 PSD→storyboard 的 CLI，另屬 S4/analyzer 範疇，非本 skill 生成庫對外契約。

## 相依規則（為何「扁平目錄」可行）

bundled 模組彼此以 **bare import** 互引（`import spine_anim`、`from beat_templates import …`）。
各 `_wire_repo_tools()` 把本目錄 **插在 `sys.path[0]`**，故這些 bare import 必命中自帶副本，
不會誤抓使用者環境的同名模組。13 個模組名彼此不衝突，也不與 skill 自有的
`validator_v0/v1/v2`、`curve_tools` 衝突。

## re-sync（repo 原檔更新時）

本目錄是副本，**不是**第二份真值。repo 的 `tools/` 原檔若變更，須重跑同步並重驗：

```bash
# 從 repo 根執行
cp tools/analyzer/{gen_animations,beat_templates,tier_variants,spine_anim,pivot_rotation}.py \
   tools/mesh_gen/{generate_mesh_v2,generate_mesh,deform_eval,atlas_crop,generate_weighted_mesh,weighted_deform_eval}.py \
   tools/rig/{infer_pivots,infer_tree}.py \
   skills/spine-ai-editor/assets/gen_lib/_bundled/
python3 tools/analyzer/validate_e1_bundle.py   # E1-4 會驗 byte-identical；不一致即 FAIL
```

`validate_e1_bundle.py` 的 **E1-4** 以 byte-compare 守住「bundle==repo 原檔」，避免副本悄悄漂移。
