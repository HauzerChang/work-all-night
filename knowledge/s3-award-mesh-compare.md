# S3 端到端:PSD 件 → 生成 mesh → 對照 Award 真實藝術家 mesh

> 結論、依據、信心、階段。相關階段:第 2 階段(S3 mesh)/ 與 S4 串接。

## 結論(信心:高 — 有藝術家真值 + 視覺 + 量化三重驗)

**第一次把 S3 mesh 生成器拿去對「真實生產標的、有藝術家真值」比對,3 件全過靜態整合 AC。**
輸入是分層 PSD 的切件(`robot_parts.psd`),目標是機器人對應生產 spine(`Award.json`)裡
藝術家手做的 3 個 **weighted** mesh。走完整 `PSD → 件 → generate_mesh_v2 → 對照真值` 路徑。

| 件(Award slot) | 生成 IoU | 藝術家 IoU | 生成頂點 | 藝術家頂點 | 幀一致性 alpha-IoU | overall |
|---|---|---|---|---|---|---|
| `機器人拆件/光暈` | 0.933 | 0.949 | **35** | 78 | 0.936 | ✅ |
| `機器人拆件/身體` | 0.966 | 0.948 | **60** | 98 | 0.972 | ✅ |
| `機器人拆件/左手` | 0.964 | 0.977 | **59** | 80 | 0.987 | ✅ |

- **覆蓋率對齊**:生成 mesh 的填滿 IoU 與藝術家 mesh 在同幀重建的 IoU 差 ≤ ~1.5%
  (身體甚至略高於藝術家)。門檻 = 「≥ 藝術家基準 − margin(0.03)」,符合 AC.md AC1 的精神
  (對齊藝術家而非武斷 0.95)。
- **頂點更精簡**:生成 35/60/59 頂點 vs 藝術家 78/98/80,~40–55% 更省,靜態全乾淨
  (0 退化 / 0 孤兒 / 重心全在 mask / 格式合法 / 頂點預算內)。
- **幀一致性**:PSD 件 alpha ↔ atlas 件 alpha 的 alpha-IoU 0.94–0.99,再次確認 PSD 切件 = Award
  貼圖同素材(呼應 log 006 的 0.92–0.99),故「在 PSD 幀對照藝術家 uvs」是有效比較。
- 視覺圖:`knowledge/figures/s3-award-compare.png`(綠=生成、橘=藝術家、灰=alpha)。
  可見兩者輪廓一致;藝術家在細尖特徵(光暈尖刺、手指)貼合更緊 → 那 ~1.5% 差距的來源。

## 依據 / 如何重現

```
python3 tools/mesh_gen/compare_to_award.py       # exit 0 = all_pass
# 先決:psd_slice 已把 robot_parts.psd 切到 /tmp/robot_parts(harness 內不自動切,
#       需先跑 python3 -c "import sys;sys.path.insert(0,'tools/mesh_gen');\
#       from psd_slice import slice_psd; slice_psd('assets/robot_parts.psd','/tmp/robot_parts')")
```

## 重要邊界 / 尚未涵蓋(誠實記錄)

1. **僅靜態**。Award 的這 3 個 mesh 是 **weighted(骨骼 skinning 驅動)**,`animations` 裡
   **沒有 deform timeline**(已逐 anim 掃描確認)。因此既有的 deform 閘(讀 deform timeline 的
   `real_deform_field`)對這些件**無真實場可用** → 本次未做變形對照。
   生成的 mesh 是 unweighted。**加權 mesh 的變形閘(用骨骼位移場:setup vs 動畫幀的世界頂點差)
   是下一個 bounded chunk**,需實作 weighted `computeWorldVertices` + 從 bone 動畫(rotate/translate/
   scale + 階層)算 pose。
2. **對照在 PSD 幀**,藝術家 uvs(region-local 0..1)重建至 PSD 件尺寸;幀一致性 0.94–0.99 非
   像素完美,~1–6% 的 IoU 差可能含幀雜訊而非純 mesh 覆蓋差。
3. `generate_mesh_v2` auto 對這 3 件(長寬比 <1.2、非高瘦)**自動回退 v1 Delaunay** — 對圓胖 blob
   本就該用 v1;strip 是給窗簾類高瘦件。此結果驗證了 auto 選路的合理性。

## 校正過的雷點(本次踩到)

- Award mesh 的 **uvs 是 region-local 0..1**(非 atlas 全頁座標)。log 006 曾警告「atlas UV 需轉」,
  本次逐件實測 uvs 範圍皆 ≈ [0,1],與各 region 的 page uv-rect 不同 → 確認 region-local,
  `artist_iou`(uvs×[W,H])直接可用。**更正 log 006 那條警告**。
- atlas region 被 ~0.70 縮小打包、且部分 rotate;`atlas_crop.extract` 已自動選頁 + CW derotate,
  切出的件為 logical orientation,與 PSD 件同向(alpha-IoU 高即證)。
