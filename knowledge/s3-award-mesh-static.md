# S3 端到端:生成 mesh vs Award 真實生產 mesh(靜態對照)

**結論**:把 S3 生成器對「真實生產標的」(Award 機器人 big-win 的 3 個 mesh 件)做靜態覆蓋率
對照,揪出並修掉 v1/Delaunay 回退的**軟邊輪廓取樣過疏**問題;修正後 3 件全過藝術家覆蓋率基準,
頂點預算貼近藝術家。同時確認一個重要 rig-requirement 事實:**這些 mesh 是 weighted、由骨頭
skinning 驅動、無 deform timeline**,與 main_draw 的機制不同。
**信心**:高(有藝術家真值 baseline + 前後對照 = 天然負對照)。**相關階段**:S3 / S4→S3 端到端。

## 標的與機制發現

`assets/robot_parts.psd`(713×693,5 圖層)⇄ Award spine slot `機器人拆件/<圖層名>`:

| 件 | Award attachment | 型別 | 藝術家頂點 / 三角 / hull |
|---|---|---|---|
| 光暈 | mesh | **weighted** | 78 / 76 / **78(全 hull,純輪廓多邊形)** |
| 左手 | mesh | **weighted** | 80 / 116 / 42 |
| 身體 | mesh | **weighted** | 98 / 154 / 40 |
| 右手 / 頭 | region | — | — |

- **3 個 mesh 全 weighted**(`len(vertices) != len(uvs)`),且 **9→12 支動畫中對這些 slot 完全沒有
  `deform` timeline** → 它們的變形 100% 來自**骨頭 skinning**(bind pose + 每頂點骨權重),
  不是 main_draw 那種「unweighted + deform timeline」。
- 這是「反推需求」的實例:同一個資產庫裡,大件柔性物(光暈/身體/手)用 **weighted skinning**;
  main_draw 窗簾/陰影用 **unweighted deform**。生成器要能兩者都產。

## 揪到的 bug / 校準(前後對照即負對照)

`generate_mesh.py`(v1)hull 密度由 Douglas-Peucker 的 `epsilon_frac` 決定(預設 0.008)。
對大型軟邊件(光暈 496×480 atlas region),0.008 只給 **14 個 hull 點** → 覆蓋率不足:

| eps | 光暈 hull | 光暈頂點 | 光暈 IoU | vs 藝術家基準 0.9795 |
|---|---|---|---|---|
| 0.008(舊預設) | 14 | 54 | 0.9292 | **FAIL** |
| 0.003 | 32 | 68 | 0.9779 | 邊緣 |
| **0.002** | 38 | 73 | **0.9832** | **PASS** |
| 0.001 | 58 | 92 | 0.9924 | pass(頂點超藝術家) |

- 再度印證舊發現(`s3-four-mesh-generalization.md`):**覆蓋率(IoU)由邊界取樣密度決定**。
- **負對照免費奉送**:修正前光暈是真 FAIL(0.929 < 0.980),證明這個 IoU 閘**有鑑別力**、
  不是無腦 pass;藝術家自身覆蓋率(`artist_iou`)當可信真值參照。

**修法**:v2 的 Delaunay 回退路徑改用 `eps_fallback=0.002`(`generate_mesh_v2.generate` 新增參數
並傳給 v1)。v1 standalone 預設仍 0.008(保住既有文件數字可重現);strip 路徑不受影響。

## 修正後結果(`tools/mesh_gen/validate_award_static.py`,exit 0)

| 件 | 模式 | 生成頂點 | 藝術家頂點 | 生成 IoU | 藝術家基準 | pass |
|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 73 | 78 | 0.9832 | 0.9795 | ✅ |
| 左手 | delaunay-v1 | 67 | 80 | 0.9913 | 0.9681 | ✅ |
| 身體 | delaunay-v1 | 77 | 98 | 0.9926 | 0.9760 | ✅ |

- 3 件皆低長寬比/塊狀 → 自動走 Delaunay(非 strip),頂點數皆 < 藝術家(精簡度更好或相當)。
- main_draw v2(strip)regression:curtain_left 仍 overall_pass(iou+deform 皆過)→ 無回歸。

## 尚缺(下一步,已列入 STATE)

- **weighted deform 閘**:要對這 3 件做「變形穩健度」對照,需先幫生成 mesh 算 **BBW 骨權重**
  並模擬 Award 的骨頭變換(S3 路線圖的 BBW + bone-sim 段,尚未實作)。本次只驗靜態覆蓋率。
- 光暈的藝術家 mesh 是「全 hull 純輪廓多邊形」(hull=78=全部頂點,無內部點)——
  一種極簡的「只描邊」拓樸;生成器目前會加內部點,靜態覆蓋率已達標,但風格不同(未來可加
  `contour-only` 模式對齊此類件)。

## 指令

```
python3 tools/mesh_gen/validate_award_static.py   # 3 件靜態對照,exit 0 = 全過
```
