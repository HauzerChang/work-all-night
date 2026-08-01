# S3 端到端驗收 — 生成 mesh 對照 Award 真實生產 mesh(機器人 3 件)

- **結論**:把 S3 `generate_mesh_v2(auto)` 跑在 **Award atlas 抽出的真實件貼圖**(光暈/左手/身體),
  與 Award **真實生產 mesh** 對照。生成 mesh 對真實件 alpha 的**覆蓋 IoU 0.93 / 0.96 / 0.97 全達標、
  格式合法、頂點 48–61 ≤ 64 預算**,且**比藝術家精簡**(藝術家 78/80/98 頂點)。這是「PSD/atlas 件 →
  S3 mesh」對真實標的的端到端驗收。
- **信心**:生成側 = 高(對真實生產貼圖直接量測);藝術家對照側 = 中(需解 weighted 幾何 + 近似對正)。
- **階段**:第 2 階段 / S3(里程碑:合成/main_draw 之外,對「另一套真實生產資產」再驗)。
- **工具**:`tools/mesh_gen/compare_award_mesh.py`(可重現)。

## 主要發現

### 1. 三件真實 mesh 全走 v1 Delaunay(strip 是窗簾專用)
`generate_mesh_v2` auto 判準:aspect≥1.2 且 row-convex → strip,否則回退 v1 Delaunay。
三件的 crop 長寬比(光暈 496/480、身體 267/299、左手 181/152)都不夠瘦長 → **全部回退 v1**。
→ **strip 拓樸是窗簾類長條專用;blob/光暈/身體這種團塊件用 Delaunay**。S3 的兩條路徑在真實資產上都被實測到。

### 2. 生成 mesh 對真實件 alpha 的覆蓋(可靠指標,不依賴對正)

| 件 | crop(atlas 縮小版) | 生成模式 | 頂點/hull/三角 | 覆蓋 IoU | 藝術家頂點 |
|---|---|---|---|---|---|
| 光暈 | 496×480 (rot) | delaunay-v1 | 54 / 14 / 86 | **0.929** | 78(hull 78,純邊界扇形) |
| 左手 | 181×152 | delaunay-v1 | 48 / 18 / 76 | **0.960** | 80(hull 42) |
| 身體 | 267×299 (rot) | delaunay-v1 | 61 / 21 / 98 | **0.968** | 98(hull 40) |

→ 生成 mesh **覆蓋真實件都 ≥0.93、頂點數比藝術家少 20–40%**(48–61 vs 78–98),格式全合法。
光暈藝術家用「78 頂點全 hull 的放射扇形」(適合發光漸層);S3 用 Delaunay 內部佈點也能覆蓋。

### 3. ⚠️ Award.json 的 uvs 與已重打包的 Award.atlas 不一致
Award.json mesh `uvs` **跨滿整頁**(光暈 u 0.012–0.990、v 0.001–0.952),但 Award.atlas 該 region 只占
Award2.png 一小塊(xy 562,879 / size 496×480,~0.70 縮小重打包)。→ **json uvs 來自原始(未縮小)打包,
與出貨 atlas 不同座標系**。
**教訓**:比對真實 mesh 形狀**不能用 json uvs → atlas 對照**(會全 0);要改用 **mesh 自身幾何**
(weighted → 解設定姿勢世界座標,與 atlas 打包無關)。這也提醒:出貨 atlas 縮放重打包後,
attachment 的 width/height 記**原始邏輯尺寸**、uvs 卻可能仍是**原始打包 uv**,兩者與縮小 atlas 都要小心對齊。

### 4. 藝術家 mesh 形狀對照(近似,交叉驗證用)
解 weighted 頂點(`[n,(bone,bx,by,w)*n]` → Σ w·boneSetupWorld·bind)得設定姿勢輪廓,以 dihedral(8 種)
+ 等向縮放對正到件 alpha,取最佳覆蓋:

| 件 | 藝術家覆蓋 | 生成 vs 藝術家 mesh IoU | 對正 |
|---|---|---|---|
| 光暈 | 0.877 | 0.846 | tf2(y 翻) |
| 左手 | **0.970** | **0.947** | tf2 |
| 身體 | 0.611 | 0.613 | tf2 |

- **左手/光暈:生成 mesh 與藝術家 mesh 覆蓋高度一致(0.85–0.95)** → S3 產物 ≈ 藝術家輪廓。
- **decoder 自我驗證**:左手解出的世界 bbox 257×216 ≈ attachment wh 259×217(近乎完全吻合)→ 解碼正確。
- **身體覆蓋僅 0.61(self_check flag=fail)**:身體 weighted 跨 3 骨,主骨 `4_LEG3` 設定 rot **87.81°**
  → 設定姿勢輪廓被旋轉近 90°、bbox aspect 0.72 vs crop 0.89。**90° dihedral + 等向縮放對正無法吻合任意
  角度旋轉 + 多骨混成的斜輪廓** → 這是**量測對正的局限,不是已證實的生成缺陷**(身體對自身件 alpha 的
  覆蓋 0.968 才是可靠品質值)。要嚴謹對照身體需 Procrustes/主軸對正(留待後續)。

## 可重現
```
python3 tools/mesh_gen/compare_award_mesh.py     # 預設 3 件,輸出 JSON
```
`self_check_artist_mapping_ok` = 藝術家覆蓋≥0.80(對正可信與否的旗標)。

## 下一步建議
- 生成側結論可信;若要把「生成 vs 藝術家」對照做到嚴謹(尤其身體),補**主軸/Procrustes 對正**再量 mesh IoU。
- 或轉向 candidate #2(切件 → Spine JSON 組裝 SkelToJson,端到端產檔),把本次確認的 v1/strip 分流固化進 pipeline。
