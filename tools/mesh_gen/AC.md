# S3 mesh 生成器 — 驗收目標 (Acceptance Criteria)

> 依 RULES.md「先定可檢查的 AC」。PNG(alpha) → unweighted Spine mesh,純 CPU,可自評。
> **2026-06-24 校正**:加入真實 deform 閘、IoU 目標改對齊藝術家;合成 stress 降級為裕度探測。

## 靜態 AC(對來源 alpha)

| 編號 | 檢查項 | 量測 | 門檻 |
|---|---|---|---|
| AC1 | 輪廓吻合 | mesh 填滿 vs alpha 的 IoU | **≥ 藝術家同件 mesh 的 IoU**(此資產 curtain_left=0.918);無藝術家參照時用 0.90 |
| AC2a | 三角重心在內 | 重心在 mask 內比例 | ≥ 99% |
| AC2b | 無退化三角 | 面積≈0 三角數 | = 0 |
| AC2c | 無孤兒頂點 | 未被三角用到的頂點 | = 0 |
| AC3 | 頂點數預算 | 總頂點數 | **≤ 藝術家同件頂點數**(有真值時);無真值時 ≤ 64。64 是對 main_draw 小 mesh(窗簾 21v/陰影 12v)校準的,真實大件藝術家自身即 78~98v(見 `knowledge/s3-award-mesh-e2e.md`)|
| AC4 | Spine 格式 | unweighted、hull 排最前、索引在範圍 | 全過 |

## 變形 AC(正式閘 — 真實位移場轉移)

| 編號 | 檢查項 | 量測 | 門檻 |
|---|---|---|---|
| AC5 | 真實變形穩健 | `transfer_deform_check`:真實最大位移幀轉移後 | 0 自交 / 0 翻面 / 0 退化 |

> ⚠️ **不要**用 `stress_field`(合成場)當 pass/fail —— 它未校準(mag=315 面積比 2.0 >> 真實 1.13),
> 會造成假性失敗(見 `knowledge/s3-real-asset-finding.md`)。合成場僅供「無真實 deform 時的最壞裕度參考」。

## 驗證工具

- 靜態:`evaluate_mesh.py`
- 變形:`deform_eval.py`(`real_deform_field` + `transfer_deform_check`,經藝術家真值自一致性驗證)
- 整合(對真實資產):`validate_against_real.py`

## 真實結果(curtain_left)

v1 Delaunay:IoU 0.980、真實 deform 乾淨 → **整合 AC 通過**。
v2 strip:24v、IoU 0.911、deform 乾淨(經濟變體,IoU 略低於藝術家基準)。

> 主觀品質(變形手感)不在自評範圍,留待真實貼圖 + 使用者審查(SOP L2)。
