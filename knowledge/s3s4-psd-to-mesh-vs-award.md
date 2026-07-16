# S3+S4 端到端:PSD件 → 生成 mesh → 對照 Award 真實生產 mesh(有真值)

- **結論**:把 S4(PSD 切件)與 S3(mesh 生成)串成端到端,對 Award 生產 spine 的機器人 3 個
  **真實 mesh 件**(光暈 / 身體 / 左手)做覆蓋率對照。**生成 mesh(v1 Delaunay)的 alpha 覆蓋率
  與藝術家 mesh 打平(margin ≤0.02,身體還略勝),且用更少頂點**;3 件靜態幾何品質閘全過。
  → 端到端「PSD → 件 → mesh」對真實標的驗收通過(覆蓋 + 靜態拓樸軸)。
- **信心**:高(對真實生產 mesh 交叉比對 + 映射經自校驗)。
- **階段**:第 2 階段 / S3×S4 整合(里程碑)。工具:`tools/mesh_gen/compare_to_award_mesh.py`。

## 量化結果(`compare_to_award_mesh.py --gen v1`,overall_pass=true)

| 件 | 藝術家 mesh (v/t/hull) | 藝術家自覆蓋 IoU | 生成 v1 (v/t/hull) | 生成覆蓋 IoU | parity(±0.02) |
|---|---|---|---|---|---|
| 光暈 | 78 / 76 / **hull78**(純邊界) | 0.9486 | 35 / 49 / 16 | 0.9331 | ✅ |
| 身體 | 98 / 154 / 40 | 0.9477 | 60 / 97 / 20 | 0.9660 | ✅(勝) |
| 左手 | 80 / 116 / 42 | 0.9768 | 59 / 97 / 19 | 0.9642 | ✅ |

- 生成器用 **~40–60% 頂點**達到藝術家等級覆蓋(35 vs 78、60 vs 98、59 vs 80)。
- `--gen v2`(auto)對 3 件**全 fallback 到 delaunay-v1**(aspect<1.2 或非 row-convex)→
  驗證 auto 路由正確:有機非直條件走 v1,窗簾式直條件才走 strip。
- 圖:`knowledge/figures/s3s4-robot-mesh-vs-award.png`(每列 左=藝術家橙 / 右=生成綠)。

## ★ 評估器可信度校正(第四次 miscalibration,務必記取)

對照真值前,**藝術家 mesh 的 uv→件 alpha 映射錯了兩版才校對**:

1. **當 atlas-page 座標**(uv×pageWH,取 region rect):身體 IoU=**0**(mesh uvs 不落在 atlas
   region 位置)→ 這份 JSON 的 uvs **不是**此 atlas 打包座標(提供的 Award.png/Award2.png 是
   重打包/縮小版;uvs 與其像素位置不對應)。
2. **依 mesh bbox 正規化**到 [0,1]:對「uv 未填滿件」的身體施加各向異性拉伸 → 自覆蓋率
   假性掉到 **0.6388**(光暈/左手因 uv 近乎填滿件而僥倖 0.91/0.97,掩蓋了問題)。
3. **✅ 正解:uvs 是 piece-local 正規化**(0..1 直接對應 attachment width×height,含 alpha 透明留白)。
   證據:身體 uv-x span=0.759 ≈ alpha_bbox_w/piece_w=286/379=0.755;uv-y span=0.940 ≈
   403/425=0.948。直接 uv×(W,H) → 3 件自覆蓋率 **0.9486 / 0.9477 / 0.9768**(全 ≥0.85 可信)。

> 教訓延續(前有 stress_field、composite 白底、atlas derotate CCW/CW):**任何「對真值」的
> 映射都要先用自校驗(藝術家 mesh 覆蓋自己的 alpha 應 ≥~0.9)確認,再信其 pass 判定。**
> 本工具內建 `mapping_trustworthy`(自覆蓋 ≥0.85)閘,映射錯會直接判 overall_pass=false。

## 靜態閘的另一處校正

`evaluate_mesh.evaluate` 內建 `AC1_iou` 絕對門檻 **0.95**,對**軟邊件**(光暈,藝術家自身
僅 0.949)miscalibrated → 會假性失敗。`compare_to_award_mesh` 的靜態閘**只取幾何有效性
條目**(format / 重心在內 / 無退化 / 無孤兒 / 頂點預算),覆蓋率交由 `AC_coverage_parity`
對藝術家真值判定(比武斷 0.95 更對,呼應 AC.md「AC1 應 ≥ 藝術家基準」)。

## 邊界 / 未涵蓋(誠實記錄)

- **deform 軸 N/A**:這 3 件在 Award **無逐頂點 deform timeline**,靠**骨骼權重(weighted)**變形。
  本次只驗「覆蓋率 + 靜態拓樸」;**未**驗生成 mesh 在骨骼驅動下的變形保真度。
- 生成 mesh 為 **unweighted**;要真正取代生產件,還需綁骨 + 權重(屬 S5)。頂點更少在
  weighted 變形下是否夠柔,未測。
- 因此本里程碑證明的是:**S3 生成器對真實有機生產件,能以更精簡拓樸達到藝術家等級的靜態覆蓋**;
  不是「生成件可直接上線」。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
python3 tools/mesh_gen/compare_to_award_mesh.py --gen v1   # overall_pass=true, exit 0
python3 tools/mesh_gen/compare_to_award_mesh.py --gen v2   # 同結果(auto→v1 fallback)
```

## 下一步候選

- **weighted mesh 對照**:若要驗 deform 軸,需一個「有逐頂點 deform 的真實 mesh 件」;
  main_draw 的 4 unweighted mesh 已驗過。Award 的角色件(OMG/megawin/superwin)也是 weighted。
- **切件→Spine JSON 組裝(SkelToJson)**:把 `PSD名/圖層名` + size+2px padding + 生成 mesh
  固化成端到端「PSD → Spine attachment(region 或 mesh)」寫出工具。
- **S2 補圖閘 / 骨架閘**(補齊 S2 樞紐)。
