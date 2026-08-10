# 資產前處理 pipeline SOP(S2 / S3 / S4)—— 純 CPU

> 這是 spine-ai-editor 的「上游」能力:在**組進 spine JSON 之前**,先把圖層/貼圖自動變成
> 乾淨、耐變形、可**量化驗收**的 mesh 與切件。所有工具在 `assets/mesh_gen/`,純 CPU、可自動跑、
> 附機讀 pass/fail 閘(exit code + JSON),不靠肉眼。與編輯/Cocos(references 其餘 SOP)前後接。

## 前置

```bash
pip install -r assets/mesh_gen/requirements.txt   # numpy opencv-python-headless scipy triangle psd-tools
```
`assets/mesh_gen/` 內腳本互相 import(`sys.path.insert(0, dirname)`),整個資料夾一起用。

## 何時走這條 SOP

| 使用者徵兆 | 能力 | 工具 |
|---|---|---|
| 「這張 PNG 幫我做成 mesh」「自動生成骨骼網格」 | S3 mesh 生成 | `generate_mesh.py` / `generate_mesh_v2.py` |
| 「這 mesh 動起來會不會破/撕裂」 | 變形閘 | `deform_eval.py` |
| 「生成的 mesh 夠好嗎」「跟藝術家比」 | 靜態 + 對照閘 | `evaluate_mesh.py` / `validate_against_real.py` / `validate_award_mesh.py` |
| 「這份 PSD 幫我切件」 | S4 PSD 切圖 | `psd_slice.py` |
| 「atlas 切一件」「切圖對不對」 | atlas 重組 / S2 閘 | `atlas_crop.py` / `evaluate_slicing.py` |

## S3 — PNG(alpha) → Spine mesh

兩條拓樸,`generate_mesh_v2(mode="auto")` 自動選:
- **strip(掃描線直條)**:高瘦、每列單一 alpha 區段(窗簾)。變形時各條平滑滑動 → 大單向拉伸最耐。
- **delaunay(v1)**:blob/凹形件(光暈、身體)。約束 Delaunay + 重心過濾 + 孤兒頂點修剪。

```bash
python3 assets/mesh_gen/generate_mesh_v2.py part.png -o part_mesh.json        # 預設 rows=10,cols=3
# blob 件對齊「藝術家頂點成本」→ target_verts 自適應 epsilon(輪廓解析度是 IoU 主槓桿)
python3 -c "import sys;sys.path.insert(0,'assets/mesh_gen');from generate_mesh import generate;import json;\
m,_=generate('part.png', target_verts=80); json.dump(m, open('part_mesh.json','w'))"
```

## S3 驗收閘(產出的 mesh 一定要過閘再交下游)

```bash
python3 assets/mesh_gen/evaluate_mesh.py part_mesh.json part.png                 # 靜態:IoU/重心/退化/孤兒/預算/格式
python3 assets/mesh_gen/validate_against_real.py --slot image/curtain_left --name image/curtain_left --gen v2
python3 assets/mesh_gen/validate_award_mesh.py                                    # 端到端對藝術家真實 mesh
```
⚠️ 變形閘**只用真實位移場轉移(`transfer_deform_check`),不要用未校準的 `stress_field`**。
weighted + 無 deform timeline 的件(靠骨骼權重變形)沒有逐頂點位移場 → 只驗**靜態幾何**。

## S4 — 分層 PSD → 各部位切件

```bash
python3 assets/mesh_gen/psd_slice.py character.psd --eval     # 切件 + manifest + 重組無損自驗(exit 0=PASS)
python3 assets/mesh_gen/make_test_psd.py                       # 沒真實 PSD 時造合成 fixture
```
契約見 `psd_contract.md`。真實慣例:**slot 命名 = `<PSD檔名>/<圖層名>`**;一圖層=一 slot;size 對應 spine +2px。

## S2 / atlas — 切圖與重組保真

```bash
python3 assets/mesh_gen/atlas_crop.py character.atlas sheet.png 'image/curtain_left' out.png   # 多頁 + CW derotate
python3 assets/mesh_gen/evaluate_slicing.py --atlas main_draw.atlas --png main_draw.png          # 重組保真閘
```

## 與 spine-ai-editor 其餘能力的合流

```
psd_slice(切件) → generate_mesh_v2 / generate(target_verts=)(產 mesh)
   → evaluate_mesh / deform_eval(驗收乾淨)
   → 【交給本 skill 的 patch_templates / SkelToJson 組進 spine JSON】
   → validator_v0 → minify → Cocos MCP 9 步推送 → preview
```

## 血淚教訓(評估器校準)+ 完整發現

見 `mesh_findings.md`。核心:**每個閘先跑正/負對照驗可信度再下判定**(本專案踩過四次 miscalibration);
**round-trip 自洽 ≠ 絕對正確**(靠外部真值才揪出 derotate 方向);**AC 相對真值、別用武斷常數**。
