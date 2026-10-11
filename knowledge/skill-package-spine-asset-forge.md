# 固化成果 — `spine-asset-forge` 備成 skill 套件(2026-10-11 run 001)

- **結論**:已達 **L3 READY** 的 `spine-asset-forge` 區塊(分層 PSD → 可載入 Spine 靜態素材)依 `skills/README.md` §6
  的人機邊界**備好為自包含 skill 套件** `skills/spine-asset-forge/`。repo 只負責「備好套件」;**sync 到使用者帳號屬 C 類里程碑、需使用者拍板**。
- **信心**:高 —— 套件**實跑驗證**(非只複製檔):兩個真實標的 round-trip 皆 `overall_pass: true`、`--weighted` 產完整 skeleton。
- **階段**:第 2 階段成果固化(skill 化);接在 `spine-mesh-doctor`(2026-08-27 v0.1.0)之後的**第二個**打包區塊。

## 為什麼這個 run 做這個(排程決策)

前一 run 004 已把 S1 cascade 線標記為**邊際價值遞減**(J-8..J-15c 連續 8 個 cascade 微變體),並列為 RULES **C 類**待使用者判斷;
高槓桿線(S5 多 rig 真值 / S4 分層 PSD / S1 影片輸入 / spine_inspector 實機)全阻塞在使用者資源。

面對「續產 J-15d cascade 變體(邊際、且在 HOLD 的 anim-forge 區塊)vs 做別的高價值自主事」,本 run 選後者:
**`skills/README.md` §6 明定「達門檻的區塊由自驅 session 產出/更新 `skills/<id>/` 套件」**——而 READINESS 矩陣早已顯示
`spine-asset-forge` 跨過門檻(2026-10-01 analyzer `gen` 閘 RED→GREEN 後),卻一直只有 `spine-mesh-doctor` 被打包。
這是一條**非 cascade、非資源阻塞、policy 明定該做**的高價值缺口 → 消化它,而非在 HOLD 區塊再疊第 9 個微變體。

## 套件內容(`skills/spine-asset-forge/`)

```
SKILL.md                    v0.1.0(觸發詞 / 能力邊界誠實表 / 用法 / 產出結構 / round-trip 判讀 / 地雷 / 回歸)
references/pipeline.md      座標契約 / atlas 打包 / mesh uv / weighted / round-trip 數學
assets/                     9 支自包含管線工具:
  build_spine.py            主線 SkelToJson(PSD → json+atlas+png)
  validate_build.py         round-trip 閘(重建 setup pose == 原圖)
  analyze_target.py         反推五段規格       genre_priors.py  分鏡先驗
  psd_slice.py              PSD 無損切件        generate_mesh_v2.py  strip mesh 拓樸
  generate_weighted_mesh.py 骨綁 weighted mesh  weighted_deform_eval.py  weighted 自驗
  atlas_crop.py             atlas 解析/取件(validate_build 用)
```

## 自包含關鍵(踩雷點)

- repo 內各工具用 `sys.path.insert(0, os.path.dirname(__file__))` + `os.path.join(..., "..", "mesh_gen")` 跨 `tools/analyzer`↔`tools/mesh_gen` 互 import。
- **扁平化到單一 `assets/` 目錄後**:`dirname(__file__)` insert 讓同目錄 bare import(`from psd_slice import ...`)自解析;`../mesh_gen` insert 指向不存在路徑但**無害 no-op**。
- 依賴閉包經實查為 9 檔(上列),無其他本地 import;外部 pip 依賴 = numpy/opencv-headless/psd-tools/Pillow/triangle/scipy(皆在 `requirements.txt`)。

## 驗收證據

| 檢查 | 結果 |
|---|---|
| 自包含 `build_spine`+`validate_build` robot_parts | `overall_pass: true`、premult MAE 0.031、0 孤兒 |
| 第二標的 Symbol_Ww(18 件) | `overall_pass: true`、MAE 0.236、0 孤兒 → 多標的 L3 |
| `--weighted` 路徑(robot) | 產 json+atlas+png+build_meta 完整 skeleton |
| cwd=skill 根、SKILL.md 文件用法實跑 | PASS(`python3 assets/build_spine.py <psd> --out <dir>`) |
| `analyze_target` 直出五段規格 | PASS |
| check_readiness(打包後) | **0 RED**;`spine-asset-forge` L3 → READY(本 run 不動 `tools/`,零回歸) |

## 待使用者拍板(RULES C 類)

- **是否 sync** `spine-asset-forge` + `spine-mesh-doctor` 到使用者的 skill 系統/帳號(帳號層級動作)。
- 高槓桿方向決策(前一 run 的 ①②③)仍未解、仍需使用者資源或方向指示。
- 已透過 PushNotification 送達使用者。
