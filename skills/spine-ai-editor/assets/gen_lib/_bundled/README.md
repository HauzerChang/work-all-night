# gen_lib/_bundled — self-contained 生成引擎(Phase E1,2026-10-18)

> **G5 self-contained bundle**:這裡是 `gen_lib` 執行期需要的 repo 生成/評估模組的
> **逐位元複本**(verbatim copy)。目的是讓 `spine-ai-editor` skill 在使用者端**不需要**
> 本 research repo 的 `tools/` 目錄即可跑完整的確定性大獎生成 + 變形/rig 閘。

## 為什麼是「逐位元複本」而非 trim

- **零回歸保證**:bundle 與 repo `tools/` 來源逐位元相同 → in-repo 既有 B/C/D 閘行為不變
  (in-repo 時 gate 直接 import repo 模組,module cache 命中 repo 複本;external 時只有 bundle)。
- **完整性以 external 測試證明**:`tools/analyzer/validate_e1_selfcontained.py` 把整個 `assets/`
  複製到 repo 外、`PYTHONPATH` 只給複製出的 assets(無 repo `tools/`),跑 gen_lib 公開 API +
  validator_v2 → 全過才算 self-contained;移掉本資料夾 → import 失敗(負對照)。

## 模組來源對照(13 個,E1 gate AC E1-1 逐位元校驗)

| bundled | ← repo 來源 |
|---|---|
| `gen_animations.py`       | `tools/analyzer/gen_animations.py` |
| `beat_templates.py`       | `tools/analyzer/beat_templates.py` |
| `tier_variants.py`        | `tools/analyzer/tier_variants.py` |
| `spine_anim.py`           | `tools/analyzer/spine_anim.py` |
| `pivot_rotation.py`       | `tools/analyzer/pivot_rotation.py` |
| `generate_mesh_v2.py`     | `tools/mesh_gen/generate_mesh_v2.py` |
| `generate_mesh.py`        | `tools/mesh_gen/generate_mesh.py` |
| `deform_eval.py`          | `tools/mesh_gen/deform_eval.py` |
| `atlas_crop.py`           | `tools/mesh_gen/atlas_crop.py` |
| `generate_weighted_mesh.py` | `tools/mesh_gen/generate_weighted_mesh.py` |
| `weighted_deform_eval.py` | `tools/mesh_gen/weighted_deform_eval.py` |
| `infer_pivots.py`         | `tools/rig/infer_pivots.py` |
| `infer_tree.py`           | `tools/rig/infer_tree.py` |

## 相依封閉性(為何只要這 13 個)

模組彼此以**裸名 import**(`import spine_anim`、`from deform_eval import ...`、
`from infer_pivots import ...` 等),全在本扁平資料夾 → 只要本資料夾在 `sys.path`,
相依即全數解析。多個模組 import 期自帶 `sys.path.insert(0, os.path.dirname(__file__))`
→ 進一步自我 bootstrap 同目錄 siblings。

**刻意不 bundle**:`analyze_target`(S1 PSD 反推分析器,連 `psd_slice`/`genre_priors`/PIL)
——只有 PSD 驅動路徑(`make_beat.parts_from_psd`、`gen_animations` CLI)用得到,屬**使用者端/
過渡期**;自主 CPU 生成路徑(DEMO_PARTS / 合成 mask / 合成 parts)完全不需要。呼叫 PSD 路徑
且本 repo `tools/` 不在時會給清楚錯誤,不影響核心生成能力的 self-contained。

**資料檔**(`assets/main_draw.json`/`assets/Award.json` 等)屬**真值校準**(benchmark_real /
load_award_robot),只在 repo 內的閘用;不在生成路徑,故 bundle 不含資料檔亦 self-contained。

## 維護

本資料夾由 E1 產生。若 repo `tools/` 的對應來源更新,**重新逐位元複製**並重跑
`validate_e1_selfcontained.py`(AC E1-1 會因不一致而 FAIL,逼使同步)。切勿只改 bundle 不改來源
(或反之)——兩邊必須一致。
