# S3 端到端:PSD 機器人件 → generate_mesh_v2 → 對照 Award 真實 mesh

- **結論**:S3 mesh 生成器對**真實生產標的**(Award spine 的機器人 3 件 mesh)端到端驗收
  **通過** —— 生成 mesh 的靜態覆蓋率(IoU)在 3 件上**全部 ≥ 藝術家自身 mesh**,且頂點數
  **≤ 藝術家**。修正了「delaunay 回退對真實羽化軟邊 under-cover」的缺陷。
- **依據**:`tools/mesh_gen/validate_robot_parts.py`(可重現);用 `assets/Award.{json,atlas,png}`
  真實貼圖切件為 alpha 來源。
- **信心**:高(對真實生產真值 mesh 逐件量化,非合成)。
- **階段**:第 2 階段 S3 / 與 S4(PSD→件)串接。

## 對照結果(2026-08-17)

| 件 | region | mode | IoU_gen | IoU_artist | 頂點_gen | 頂點_artist | 判定 |
|---|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | 496×480 | delaunay | 0.9856 | 0.9795 | 78 | 78 | ✅ |
| 機器人拆件/左手 | 181×152 | delaunay | 0.9852 | 0.9681 | 61 | 80 | ✅ |
| 機器人拆件/身體 | 267×299 | delaunay | 0.9876 | 0.9760 | 71 | 98 | ✅ |

拓樸全乾淨:0 退化三角 / 0 孤兒三角 / centroid_in_mask=1.0 / 格式合法。

## 關鍵發現

1. **這 3 件走 delaunay 回退,不是 strip**:v2 `auto` 依 `aspect≥1.2 且 row-convex` 判 strip;
   機器人件圓潤/寬扁 → 落到 delaunay-v1。**strip 只適合窗簾類直條件**,通用生成仍需 delaunay 分支穩健。

2. **缺陷:固定 `epsilon_frac=0.008` 對真實羽化軟邊 under-cover**。Douglas-Peucker 用固定容差把
   軟邊(如光暈)的外周切進 silhouette 內,IoU 低於藝術家(光暈 0.929 < 0.980,左手/身體亦皆低)。
   合成 fixture 是硬邊,掩蓋了這個問題 → 又一次「合成通過、真實才現形」(呼應 S3 real-asset finding)。

3. **修法:自適應 hull 覆蓋目標(asset-independent)**。`boundary_points(cover_target=)`:從
   `epsilon_frac` 起每次 ×0.8 縮小容差,直到 hull 多邊形填滿 ≥ `cover_target`×mask 面積。
   v2 delaunay 回退設 `cover_target=0.99`。**覆蓋率變成可控旋鈕**,軟邊自動取更細 hull、硬邊維持精簡:
   - 光暈 eps 自動收到 ~0.0017(hull 78),身體只需 ~0.0033(hull 35)。
   - `0.99` 是穩健甜蜜點:3 件 IoU 全過藝術家、頂點數全 ≤ 藝術家;拉到 0.995 會讓光暈灌到 104 頂點(過頭)。

4. **deform 閘對這 3 件 N/A(誠實標註)**。Award 這 3 件**沒有 deform timeline**(靠加權骨骼驅動,
   見 `log/2026-06-26-005.md`:會 warp 的件做 mesh,但 warp 由骨骼加權而非 deform)。
   `real_deform_field` 無真實位移場 → 硬跑會拿到**零位移的假性乾淨**。故 `validate_robot_parts.py`
   明確標 N/A,不讓它 vacuous pass。**加權骨骼驅動的耐變形驗收需 bone transform**,列為後續課題。

5. **靜態評估器 `vertex_budget=64` 是合成期預設,對真實件不適用**。藝術家真實 mesh 本身就 78/80/98,
   均 >64。真實對照應以**藝術家頂點數**為預算基準(本驅動即如此),而非 64。

## 無回歸

改動只碰 delaunay 回退路徑;`generate_mesh.generate(cover_target=None)` 維持舊行為(相容既有呼叫)。
4 個 main_draw mesh 全走 **strip** 模式,不受影響 —— `validate_against_real.py --gen v2` 對
curtain_left/right + shadow/shadow2 重驗 **overall_pass 全 True**。

## 標準指令

```
python3 tools/mesh_gen/validate_robot_parts.py          # 3 件端到端(IoU vs 藝術家 + 頂點預算;deform N/A)
python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot image/curtain_left --name image/curtain_left  # 回歸
```
