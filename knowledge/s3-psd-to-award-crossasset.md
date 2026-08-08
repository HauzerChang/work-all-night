# S3 跨資產推廣:PSD 件 → 生成 mesh → 對照 Award 真實藝術家 mesh

- **結論**:S3 mesh 生成器**跨資產成立** —— 從第二份生產資產(Award 機器人 big win)的
  分層 PSD(`robot_parts.psd`)切出 3 個「在真實 spine 裡是 mesh」的件(光暈/左手/身體),
  自動生成的 mesh **靜態輪廓覆蓋率達到或逼近藝術家自己的 mesh,且頂點數更精簡**。
  端到端 **overall_pass=True**(`validate_psd_to_mesh.py`,exit 0)。
- **依據/信心**:對真實生產資產、以藝術家 mesh 自身覆蓋率為基準、含負對照 → **高信心**(靜態範圍內)。
- **相關階段**:第 2 階段 S3(mesh)× S4(PSD 切圖)串接;S3 首次離開 main_draw。

## 驗收結果(`python3 tools/mesh_gen/validate_psd_to_mesh.py`,margin=0.015)

| 件 | 模式 | 生成 IoU | 藝術家基準 IoU | gap | 生成頂點 | 藝術家頂點 | refine 輪 | pass |
|---|---|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1-refined(eps=0.002) | 0.9796 | 0.9795 | +0.0001 | **65** | 78 | 3 | ✅ |
| 左手 | delaunay-v1 | 0.9642 | 0.9681 | −0.0039 | **59** | 80 | 1 | ✅ |
| 身體 | delaunay-v1 | 0.9660 | 0.9760 | −0.0100 | **60** | 98 | 1 | ✅ |

三件皆:AC1 覆蓋率 ≥ 藝術家基準−margin、AC2 mesh 合法性閘全過、AC3 頂點數 < 藝術家(更精簡)。

## 關鍵發現

1. **機器人件不是 strip 拓樸**:三件長寬比 < 1.2 且非 row-convex(blob 狀)→ v2 auto **回退 v1 Delaunay**。
   印證 strip 模式是「窗簾/陰影」這類高瘦、單向拉伸件的專用解,不是萬用。
2. **軟邊/圓形件需更細的輪廓取樣**:光暈是羽化的放射漸層,預設 `epsilon_frac=0.008` 把圓弧
   邊界切成多邊形而**undershoot**(IoU 只 0.933,落後基準 0.046)。把 epsilon 減半到 **0.002**
   → IoU 0.980,追平藝術家且僅 65 頂點(< 78)。→ **加了自我驗證 refine 迴圈**(見下)。
3. **硬邊件預設即達標**:左手/身體(邊界清晰)第一輪(eps=0.008)就落在基準 −0.004 / −0.010 內,
   且頂點數大幅精簡(59<80、60<98)。
4. **生成器比藝術家精簡**:三件生成頂點都少於藝術家(65/59/60 vs 78/80/98),覆蓋率相當
   → 確定性演算法在「靜態貼合」上不輸手做,還更省頂點預算。

## 自我驗證迴圈(RULES 5 輪預算的落地)

`validate_psd_to_mesh.gen_with_refine`:delaunay 路徑若 IoU 未達 `藝術家基準−margin`,
把 `epsilon_frac` 減半(下限 0.002)重試,最多 5 輪,取 IoU 最佳者。光暈用了 3 輪達標。
(strip 路徑不吃 epsilon,其覆蓋率由 rows 決定,另有 `validate_against_real` 驗收。)

## 評估器可信度(先驗再判定)

- **基準非平凡**:藝術家 mesh 對自身輪廓覆蓋率 0.968~0.980(不是 1.0 也不是 0),gap 有鑑別意義。
- **負對照**:把生成 mesh 整體平移 30px → IoU 0.966→**0.703**(遠低於基準)→ 閘能抓錯位。
- **失敗→通過可追溯**:光暈預設 eps 明確 fail(0.933<target),refine 後才 pass → AC1 非橡皮圖章。

## ⚠️ 範圍界定(誠實,勿過度宣稱)

- Award 機器人 mesh 全為 **weighted(骨骼驅動)**,變形靠 bone skinning,**無 deform timeline**。
  本閘**只驗靜態輪廓覆蓋 + mesh 合法性 + 精簡度**,**未**驗 deform 穩健性。
- weighted-mesh deform 重現(依 bone 綁定權重推世界座標)是**尚未具備的能力** → 列為 S3 下一步。
- PSD 件(全解析度)與 Award atlas region(打包 ~0.70 縮小)是同素材兩尺度(先前 alpha-IoU
  0.92~0.99 已證);兩邊各自「mesh 覆蓋自身輪廓」,IoU 尺度無關,故可比。

## 可重現指令

```
python3 tools/mesh_gen/validate_psd_to_mesh.py          # 3 件全 pass,exit 0
python3 tools/mesh_gen/validate_psd_to_mesh.py --margin 0   # 更嚴(光暈仍過,左手/身體看 refine)
```
