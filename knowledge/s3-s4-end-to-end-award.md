# S3+S4 端到端:真實 PSD 件 → 生成 mesh → 對照 Award 生產 mesh

- **結論**:把 S4(PSD 切圖)與 S3(mesh 生成)串成端到端,並用**第二組獨立真實真值**
  (機器人拆件 `robot_parts.psd` ⇄ 生產 spine `Award.json` 的 mesh)驗證 S3。
  `generate_mesh_v2`(auto)對三件 mesh(光暈/身體/左手)生成的 mesh,覆蓋率全數
  **達到或優於藝術家生產 mesh 的相對基準**(margin 0.03),且頂點數更省。端到端 `overall_pass=True`。
- **信心**:高(對真實生產 PSD + 真實 spine mesh 雙向真值;評估器自洽、免旋轉猜測)。
- **階段**:第 2 階段 / S3×S4 整合(里程碑:端到端 PSD→件→mesh 對真實標的驗收)。
- **工具**:`tools/mesh_gen/validate_psd_to_mesh.py`(可重現:`python3 tools/mesh_gen/validate_psd_to_mesh.py`)。

## 量化結果(2026-07-06)

| 件 | 生成 mode | 生成 v/hull/tris | 生成 IoU(對切件) | 藝術家 v/hull/tris | 藝術家 IoU(對自身輪廓) | AC |
|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 42 / 25 / — | **0.961** | 78 / 78 / 76 | 0.983 | ✅ |
| 身體 | delaunay-v1 | 60 / 20 / 97 | **0.966** | 98 / 40 / 154 | 0.983 | ✅ |
| 左手 | delaunay-v1 | 59 / 19 / 97 | **0.964** | 80 / 42 / 116 | 0.981 | ✅ |

- 三件長寬比 <1.2 / 非窄長條 → v2 auto 回退 v1 Delaunay(strip 只對窗簾類高瘦件)。
- 生成 mesh 頂點數皆少於藝術家(42/60/59 vs 78/98/80)仍達覆蓋率 → 精簡度不輸生產件。
- **deform 閘 N/A**:這 5 件在 Award **無 deform timeline**(靠骨骼權重變形),無逐頂點位移場可轉移。
  本 AC 只做靜態幾何(覆蓋/拓樸/預算)。與 main_draw 4 mesh(有 deform)互補。

## ★ 方法論關鍵:藝術家 mesh 覆蓋率如何「自洽、免旋轉猜測」地量

踩過的坑 → 校正(第四次評估器校準教訓,延續 stress_field / composite 白底 / derotate 方向):

1. **Award mesh uvs 是 region-local `[0,1]`(不是 atlas 頁 uv)**。實測 uv 幾乎鋪滿 [0,1](81 verts
   有 12 個 u>0.9、12 個 v>0.9)。若誤當頁 uv 乘 pageWH,會把件放大到整頁 → IoU 假性崩到 0.23。
2. **uvs 對應「直立(de-rotated)」方向**,rotate:true 件的 uvs 不是 stored(旋轉存放)方向。
   - 對 **stored** crop 光柵化:光暈/身體僅 0.45~0.70(錯)。
   - 對 **de-rotated** crop(`atlas_crop.crop_region`,已 CW 校正)光柵化,uv 直接 ×(cropW,cropH)、
     **無需翻轉**:三件全 IoU 0.98。 → 這才是正確、自洽的藝術家基準。
3. 因此「藝術家 mesh 覆蓋率」定義 = mesh 三角填充區 IoU **它自己的 de-rotated region alpha**。
   與「生成 mesh 覆蓋率」= mesh 填充 IoU 它依據的 PSD 切件 alpha,兩者都是「mesh 蓋住自己真實輪廓
   的緊密度」→ 可公平對比。**先驗證此基準本身可信(三件 0.98)再下判定**(守則:評估器先校準)。

## 由此觸發的兩個生成器改進(generate_mesh.py,向後相容)

發現「光暈」(大、軟邊發光,706×706、無孔洞、5.7% 像素落在 alpha 8–128 羽化帶)在固定
`epsilon_frac=0.008` 下 hull 只 16 點 → 輪廓欠取樣、IoU 0.933(<0.95)。修正:

1. **自 tune 輪廓密度**(`generate(target_iou=..., vertex_budget=...)`):epsilon 由粗到細掃描,
   取「預算內達 target_iou 的最細一組」。用生成器自身覆蓋率評估器決定 hull 取樣密度
   (呼應守則「每能力必配評估器」)。`generate_mesh_v2` 的 Delaunay 回退預設帶 `target_iou=0.96`。
   `target_iou=None` 維持原行為(不影響既有呼叫)。
2. **孤兒頂點修剪**(`prune_orphans`):`filter_triangles` 砍凹形外三角後,邊界頂點可能變孤兒
   (Spine 格式禁孤兒 / 破壞 hull-first)。修剪並保住 hull-first 順序重編索引。光暈由此去掉 2 孤兒。

**回歸驗證**:main_draw 4 mesh(curtain_left/right + shadow/shadow2,皆走 strip 模式,不受 v1 改動影響)
`validate_against_real --gen v2` 全 `overall_pass=True`、deform si=0、IoU 對齊原基準(0.93/0.93/0.95/0.95)。
shadow2 slot 的 attachment 名是共用的 `image/shadow`(--name image/shadow)。

## 下一步

- 把「件→Spine attachment 組裝(SkelToJson)」補上:用已固化的 `PSD名/圖層名` slot 命名 + size+2px padding
  + mesh/region 分配,把生成 mesh 寫回 Spine JSON,端到端產出可載入的 skeleton。
- 或推進 S2 補圖閘 / 骨架閘(純 CPU 樞紐)。
