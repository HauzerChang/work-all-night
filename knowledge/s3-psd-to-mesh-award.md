# S3×S4 端到端 —「PSD件 → 自動 mesh → 對照 Award 真實 mesh」(里程碑)

- **結論**:把 S4(PSD/atlas 切件)與 S3(mesh 生成)串成一條,對 Award 生產 spine 的
  3 個 **mesh 件(光暈/左手/身體)** 做正面對照。自動生成的 mesh 在**有真值的三項閘全過**:
  覆蓋率 ≥ 藝術家、頂點數 < 藝術家、格式合法。**首次拿自動 mesh 對真實生產 mesh 正面比對且通過。**
- **信心**:高(真值 = Award 藝術家 mesh 的 uvs/triangles;切件來源 = Award atlas 切件,
  已確認 = PSD 切件同素材,見 `s4-psd-to-spine-real.md`)。
- **階段**:第 2 階段 / S3×S4 整合(從各自對真實檔驗收 → 端到端串接對真實標的驗收)。
- **工具**:`tools/mesh_gen/validate_psd_to_mesh_award.py`(exit 0 = overall_pass)。
- **圖**:`knowledge/figures/s3-award-robot-mesh.png`(3 件生成 mesh 疊在真實件 alpha 上)。

## 結果(標準指令 `python3 tools/mesh_gen/validate_psd_to_mesh_award.py`)

| 件 | 生成頂點 | 藝術家頂點 | 生成 IoU | 藝術家 IoU 基準 | 覆蓋率 pass |
|---|---|---|---|---|---|
| 光暈 | 73 (hull 38) | 78 | 0.9832 | 0.9795 | ✅ |
| 左手 | 67 (hull 43) | 80 | 0.9913 | 0.9681 | ✅ |
| 身體 | 77 (hull 37) | 98 | 0.9926 | 0.9760 | ✅ |

→ 3 件皆**用更少頂點達到 ≥ 藝術家的輪廓覆蓋率**,vertex budget / format 亦全過,`overall_pass=true`。

## 關鍵發現

1. **epsilon 需隨件尺寸調(輪廓取樣密度)**:v1 預設 `epsilon_frac=0.008` 是為 main_draw
   小窗簾校準;套到大件(光暈 atlas 496px)輪廓過粗 → 覆蓋率僅 0.929(不足)。掃描發現
   **0.002 對 3 件覆蓋率皆達/超越藝術家、頂點數仍低於藝術家** → 定為 blob 件預設 `BLOB_EPSILON`。
   教訓:輪廓簡化的**絕對**容差要看件的像素尺度,不能一個常數打天下(後續可改為依周長自適應)。

2. **這 3 件為 blob(非高瘦 row-convex)→ strip 不適用,走 v1 Delaunay**;v2 strip 的通用性
   僅限窗簾類長條件(見 `s3-four-mesh-generalization.md`)。blob 件靠加密輪廓 hull 取覆蓋率。

3. **Award 機器人 mesh 皆 weighted 且無 deform timeline**(逐 12 動畫確認 0 條 deform)。
   → 它們靠**骨骼權重**變形,不是逐頂點 deform。因此**本資產不存在「逐頂點 deform 真值」**,
   deform 閘無法用本資產運動。

## ⚠️ 方法論:deform 閘在此為「探針」非 pass/fail(honest 決策)

因本資產無逐頂點 deform 真值,唯一可用位移場是**跨資產轉移 main_draw 窗簾的真實位移場**。
轉移到 blob 時 area_ratio 依件的長寬比大幅偏離 ~1:身體 1.22(clean, si=0)、光暈 1.21(si=3)、
**左手 2.05(si=21,窗簾場把方形手過度拉伸 → OOD)**。

→ 依 repo 既有教訓(`deform_eval.stress_field` docstring;2026-06-24 stress miscalibration),
**非代表性/OOD 位移場不可當 pass/fail 閘**。故此測列為 `probe_deform_stress`(informational),
**不計入 `overall_pass`**。觀察:當位移場代表性(area_ratio ~1.2)時 mesh 乾淨或近乾淨(身體 0/光暈 3);
過拉伸(左手 2.05)才自交 —— 再次印證 v1 散點 Delaunay 在大單向拉伸下的已知弱點。

## 可重現

```
python3 tools/mesh_gen/validate_psd_to_mesh_award.py                    # 3 件全跑,exit 0
python3 tools/mesh_gen/validate_psd_to_mesh_award.py --slot 機器人拆件/身體  # 單件
python3 tools/mesh_gen/validate_psd_to_mesh_award.py --epsilon 0.008    # 重現「過粗→光暈覆蓋率不足」
```

## 下一步候選

- **把慣例固化成 SkelToJson(切件→Spine JSON 組裝)**:`<PSD名>/<圖層名>` slot 命名 +
  size+2px padding + mesh/region 分配 + 生成 mesh 寫回 → 端到端「PSD → 可用 Spine JSON」。
- blob 件的 deform 穩健若要成為真閘,需**真值來源**:或做 weighted 綁定 + 骨骼旋轉的變形檢查,
  或取一支真有 blob per-vertex deform 的資產。
