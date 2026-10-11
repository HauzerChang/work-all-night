---
name: spine-asset-forge
description: |
  從**分層 PSD / 目標圖**鍛造出**可直接載入的 Spine 3.8 素材**(skeleton.json + atlas + png),
  純 CPU、不需 Spine editor。把「反推需求規格 → 切件 → 生 mesh 拓樸 → 組裝骨架 JSON」串成一條
  有 round-trip 保真閘把關的靜態素材產線。

  Use when the user wants to:
  (1) 把一張**分層 PSD**(或已拆好的件)自動變成一份**可載入 Spine 的 skeleton.json + atlas**;
  (2) 反推一張目標圖的**資產需求規格**(哪些件可動 / 哪些是特效 / 建議切法 / 哪些件該用 mesh);
  (3) 為每個軟邊/大面積件自動產**mesh 拓樸**(strip 式,耐變形,預設 rows=10 cols=3);
  (4) 驗證產出的素材是否**無損 round-trip**(重組回原圖的像素誤差 + 無孤兒 slot/attachment);
  (5) 用「切圖保真閘」確認 atlas 重組不失真。

  觸發詞:「PSD 轉 spine」「生成 spine 素材」「目標圖反推規格」「自動切件」「件轉 mesh」
  「SkelToJson」「組裝骨架 json」「素材鍛造」「這張圖能不能做成 spine」「spine 素材 round-trip」。

  Requires: Python 3 + numpy + opencv-python-headless + scipy + triangle(+ psd-tools 讀 PSD)。
  輸入契約:**分層 PSD**(平面未分層圖只有 baseline 召回,見「能力邊界」)。
  本 skill 為**本研究 repo 錨定式**(執行需 repo 的 `tools/` 產線),非獨立 vendored 套件 —— 原因見下。
---

# spine-asset-forge

把「一張圖 → 會被 Spine 載入的素材」從手工切圖＋手搭骨架,變成**一鍵、可量化驗收**的 CPU 產線。

> **version: 0.1.0**（2026-10-11,初版套件）
>
> Changelog：
> - **0.1.0** — 初版,固化本研究 repo 的**靜態素材鍛造**區塊(`spine-asset-forge`)。
>   達 skill 化門檻:四個核心能力全 ≥ L2 GREEN、端到端 round-trip 達 L3(見 repo `skills/READINESS.md`,
>   真相以 `python3 tools/check_readiness.py` 即時輸出為準)。此區塊自 2026-10-01(analyzer `gen`
>   閘 RED→GREEN)起即達門檻,本版正式備好套件。
>
> **與 `spine-ai-editor` 的關係**:那支 skill 明說「mesh 交給 Spine editor」、著重讓**既有**素材動起來並落地
> Cocos;本 skill 補它上游的空白——**從零生出靜態素材**。分工:**forge 從零生素材 → mesh-doctor 把關品質 →
> spine-ai-editor 讓素材動起來並落地**,三者串成一條線。

---

## 能力邊界(誠實界定)

| 能力 | 成熟度 | 說明 |
|---|---|---|
| 反推分析 `analyze_target` | L2 真值驗收 | 分層 PSD → 五段規格(件/特效/分鏡/拆圖/補圖);對 Award 真值以**召回**(award ⊆ proposed)過閘 + 負對照 |
| 切件 `psd_slice` | L2 真值驗收 | PSD → 各部位件 + manifest;切圖保真閘 `evaluate_slicing` 45/45 無損重組 |
| mesh 拓樸 `generate_mesh_v2` | L2 真值驗收 | 件 → strip mesh(rows=10,cols=3=30v,4 mesh 全 deform 乾淨,過藝術家基準) |
| **端到端** `build_spine` | **L3 端到端** | SkelToJson 組裝 → 可載入 Spine;**round-trip 重組像素 MAE<3**、無孤兒 slot/attachment(一鍵驗證) |
| **未涵蓋** | — | **animation / weighted / rig / pivot**(屬 HOLD 的 `spine-anim-forge`、`spine-rig-pivot`——生成端尚未達 L3,勿當本 skill 能力);**平面未分層圖自動拆件**(同材質語意召回 ≈0,CPU 到頂,需 GPU 或分層 PSD) |

> ⚠️ **防半成品鐵律**(見 repo `skills/README.md`):本 skill 只收**靜態幾何/貼圖**產線。
> 動畫、weighted mesh、rig/pivot 的**生成器**仍在研究中(評估器雖 L2,生成端未達 L3)→ **不列為本 skill 能力**,
> 僅於此標為「已知限制 / 未涵蓋」。要讓素材會動,走 `spine-ai-editor`。

## 產線(四段,一條線)

```
分層 PSD ──analyze_target──▶ 五段需求規格 ──psd_slice──▶ 各件 PNG + manifest
   │                                                          │
   │                               generate_mesh_v2 ◀─────────┘(軟邊/大面積件)
   │                                      │
   └──────────── build_spine ◀───────────┘
                     │
                     ▼
        skeleton.json + atlas + png（可直接載入 Spine 3.8）
                     │
                 validate_build  ← round-trip 保真閘(像素 MAE + 無孤兒)
```

**五段需求規格**(`analyze_target` 產出,範例見 `references/pipeline_and_spec.md`):
1. 運動構件(可動件:z/bbox/面積/質心)
2. 周邊特效分類(特效 vs 結構 + 子類 + 結構角色)
3. 動作腳本/分鏡(先驗提案,PROPOSAL——手感項留使用者)
4. 拆圖策略(slot 命名 / 切法 / region vs mesh / pivot 提示)
5. 補圖需求(遮擋區分級;無 GPU 下屬契約依據,不是自動能力)

## 用法(於本研究 repo)

```bash
# 端到端:分層 PSD → 可載入 Spine 素材(靜態幾何/貼圖)
python3 tools/analyzer/build_spine.py <in.psd> --out <out_dir>
#   產 <out_dir>/skeleton.json + atlas + png + build_meta.json

# 只要需求規格(五段):
python3 tools/analyzer/analyze_target.py <in.psd>

# round-trip 保真閘(素材是否無損、無孤兒):
python3 tools/analyzer/validate_build.py <in.psd> <out_dir>
```

> ℹ️ **動畫/weighted/rig 旗標**(`--animate` `--weighted` `--rig` `--pivot-rotate` …)屬**其他區塊**
> (`spine-anim-forge` / `spine-weighted-forge` / `spine-rig-pivot`)。它們在 `build_spine` 可跑,但其
> **生成器成熟度未達 skill 門檻**,不在本 skill 的驗收承諾內。

## 判讀(round-trip 閘)

- `AC3_roundtrip_recon.premult_rgb_mae` / `alpha_mae`:把切出的件依 atlas+json 重組回畫布,與原圖的像素誤差。**須 < thresh(3.0)**。
- `AC4_no_orphan.orphan_ratio`:有 slot 無 attachment(或反之)的比例。**須 ≈ 0**。
- `AC1/AC2`:slot/bone/skin 結構完整、setup pose 可重建。

## ⚠️ Spine 3.8 地雷(本產線已內建處理)

1. **PMA(Premultiplied Alpha)**:atlas 切圖/重組須與 Cocos 的 PMA 設定一致,否則發光/半透明區糊成死亮色。
2. **mesh unweighted 判定**:`vertices.length == uvs.length` 為 unweighted;hull 頂點必排 vertices 最前。
3. **atlas 多頁 + CW derotate**:`atlas_crop` 已修方向 bug;切件保真由 `evaluate_slicing` 間接覆蓋。
4. **緊湊 bezier / 命名空間**等 3.8 細節見 repo `CLAUDE.md`。

詳見 `references/pipeline_and_spec.md`。

## 為什麼是「repo 錨定式」而非 vendored 自含套件

本 skill **不把 `tools/` 的程式碼複製進 `assets/`**(有別於 `spine-mesh-doctor` 的 vendored 作法),原因是
誠實的工程取捨:`build_spine` 的端到端閉包達 **23 個本地模組**,且其中 `gen_animations` / `tier_variants` /
`beat_templates` 等是**本研究排程幾乎每次都在改**的活躍核心。把它們凍結複製一份會**數天內就與 repo 漂移**,
違反本 repo「單一真值來源」原則。故本版採 repo 錨定:SKILL.md + references 固化**能力契約與用法**,
**回歸以 `check_readiness.py` 對 repo 實跑**為準。

> **未來 vendoring 路徑(待 anim/weighted/rig 區塊也成熟、核心穩定後)**:把靜態產線閉包抽成穩定子集
> 複製進 `assets/`,使 skill 可脫離 repo 執行。現階段活躍核心尚不宜凍結。

## 回歸 / 維護

升版前跑(於本研究 repo):`python3 tools/check_readiness.py`。對應區塊 `spine-asset-forge` 須全 GREEN。
曾 GREEN 轉 RED = 迴歸,擋升版。新能力須 ≥ L2 GREEN 才可加入(MINOR bump);
動畫/weighted/rig 要進本 skill,須其**生成器**各自達 L3(目前 HOLD)。

> **同步(sync)屬使用者帳號層級動作**:repo 只負責備好此套件於 `skills/spine-asset-forge/`;
> 是否把它 sync 成帳號可觸發的 skill,由使用者拍板(RULES C 類)。
