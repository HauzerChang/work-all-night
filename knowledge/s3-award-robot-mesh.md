# S3 對真實生產 mesh 驗收:Award 機器人 3 件(光暈/身體/左手)

> 結論:generate_mesh_v2 對 3 個真實 **weighted、骨骼驅動** 生產 mesh 的靜態覆蓋率
> **全部達到/超過藝術家基準,且頂點數 ≤ 藝術家**。同時揭露評估器對「weighted / 無 deform」
> mesh 的兩個盲點並修正。
> 依據:`assets/Award.{json,atlas,png}` 真實 spine ground truth。信心:高(有真值對照)。相關階段:S3 + S4 端到端。

## 標的(Award spine 的機器人拆件 mesh)

| slot | 藝術家 nv / hull / tris | weighted | deform timeline |
|---|---|---|---|
| `機器人拆件/光暈` | 78 / 78(全 hull)/ 76 | ✅ | ❌ 無 |
| `機器人拆件/身體` | 98 / 40 / 154 | ✅ | ❌ 無 |
| `機器人拆件/左手` | 80 / 42 / 116 | ✅ | ❌ 無 |

(`右手`、`頭` 為 region 非 mesh;5 件均由 PSD `robot_parts.psd` 對應圖層而來,見 `s4-psd-to-spine-real.md`。)

## 驗收結果(`validate_against_real.py --gen v2`,region 直接取自 Award atlas)

| slot | 生成 nv | 生成 IoU | 藝術家基準 IoU | deform 閘 | overall |
|---|---|---|---|---|---|
| 光暈 | 73 | 0.9832 | 0.9795 | N/A | **PASS** |
| 身體 | 77 | 0.9926 | 0.9760 | N/A | **PASS** |
| 左手 | 67 | 0.9913 | 0.9681 | N/A | **PASS** |

→ 生成 mesh 覆蓋率**全部 ≥ 藝術家**,且頂點數更精簡(73/77/67 vs 78/98/80)。

## 關鍵發現

1. **這 3 件都是 weighted + 無 deform timeline**(靠骨骼變形,session-005 已推測,本次逐 anim 掃描 12 支動畫證實)。
   → **deform-transfer 閘不適用**(位移場轉移是為 unweighted+deform 的窗簾設計的)。老實標 N/A,
   不要讓它 trivially pass 造成假訊號。

2. **預設 `epsilon=0.008`(窗簾/main_draw 調出來的)對生產 blobby 件太粗** — 只給 14~21 hull 點,
   IoU 落在藝術家基準下方(光暈 0.929 < 0.980)。掃描 epsilon:
   - `0.004`:身體/左手過、光暈仍 fail(0.966)。
   - **`0.002`:3 件全過且 hull 密度(38/37/43)、nv(73/77/67)接近藝術家精簡度 → 設為 v2 delaunay 回退預設。**
   - `0.0005`:IoU→1.0 但 hull 爆到 115~251,過度取樣。
   - **IoU 由 hull 密度(epsilon)單調決定**,與 S3 早期「IoU 由 rows 決定」同源:覆蓋率=邊界取樣密度。

3. **hull 密度需隨輪廓複雜度調**:窗簾(平滑長條,strip 模式不吃 epsilon)vs 機器人(複雜 blobby,
   走 delaunay 回退)最佳 epsilon 不同。0.002 對兩類都安全(main_draw 4 mesh 全走 strip,不受影響 → 無回歸)。

## 修的東西(`validate_against_real.py`)

- 原本無條件呼叫 `real_deform_field`,對 weighted mesh 會把 `vertices`(格式
  `[骨數,骨idx,bindX,bindY,權重,...]`)誤 reshape 成 Nx2,與 uvs 數不符 → scipy griddata crash。
- 改:先判 `weighted = len(vertices)!=len(uvs)` 與 `has_deform`(掃 deform_frames)。
  - 無 deform → `AC_real_deform.applicable=false`(靠骨骼),overall 只看 IoU。
  - weighted+有 deform → 標 `applicable=false`(位移場轉移尚未支援 weighted),不假 pass。
  - unweighted+有 deform → 原本的真實位移場轉移閘(窗簾)。
- 報告新增 `slot`、`artist_mesh`(nv/hull/tris/weighted)欄位,方便對照。

## 未解 / 下一步(重要 gap)

- ⚠️ **weighted-bone mesh 的變形穩健性目前無閘**。窗簾靠 deform timeline,有位移場可轉移;
  機器人靠骨骼權重變形,要驗需:讀 setup bind-pose(逐頂點 `[骨,bindXY,權重]` 展開)、
  在動畫某幀套 bone world transform 算變形後世界座標,再跑自交/翻面。這是 S3 對「骨骼驅動 mesh」
  的下一個評估器(deform_eval 目前只做 unweighted deform)。
- 端到端「件→Spine JSON 組裝」(SkelToJson):命名慣例 `<PSD檔名>/<圖層名>`、size+2px、
  mesh vs region 分配(會 warp→mesh、剛體→region)已知,可固化成工具。
