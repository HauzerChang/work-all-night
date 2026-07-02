# S3 端到端:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把 `robot_parts.psd` 的 3 個 mesh 件(光暈 / 身體 / 左手)經 `psd_slice` 切出、
  `generate_mesh_v2` 生成 mesh,再與 **Award 生產 spine 的藝術家真實 mesh** 做像素級比對,
  **端到端 3/3 件全 PASS**:生成 mesh 覆蓋率與藝術家近乎持平(gen 0.93~0.97 vs art 0.95~0.98,
  差距 ≤2%),且**頂點數只有藝術家的 4~7 成**(gen 35/60/59 vs art 78/98/80)仍達標。
- **信心**:高。對真實生產 mesh 有 ground truth;比對度量經負對照證明有鑑別力。
- **階段**:第 2 階段 / S3 × S4 串接(里程碑:S3 首次對「真實藝術家 mesh」而非合成/自資產驗收)。

## 量化結果(uv 光柵化到 PSD 件像素空間)

| 件 | gen 模式 | gen 頂點/三角 | art 頂點/三角 | gen IoU/alpha | art IoU/alpha | gen↔art IoU |
|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 35 / 49 | 78 / 76 | 0.933 | 0.949 | **0.918** |
| 身體 | delaunay-v1 | 60 / 97 | 98 / 154 | 0.966 | 0.948 | **0.928** |
| 左手 | delaunay-v1 | 59 / 97 | 80 / 116 | 0.964 | 0.977 | **0.957** |

- **AC-A 格式**:3 件皆合法 Spine mesh(unweighted / hull 最前 / 索引範圍 / 頂點 ≤64)✅
- **AC-B 覆蓋率不遜藝術家**:gen ≥ 0.90 且 ≥ art−0.03 → 3/3 ✅(身體甚至反超藝術家)
- **AC-C mesh↔mesh 相似**:gen↔art 填充 IoU ≥ 0.90 → 3/3 ✅

> 3 件長寬比皆 <1.2 或非 row-convex,`generate_mesh_v2 auto` 全數回退 **v1 Delaunay**
> (strip 模式是為窗簾那種高瘦件設計)。故本次實為 **v1 對真實 blob 型件的驗收**。

## ★ 關鍵發現 / 踩雷:Award mesh 的 vertices ≠ 件內形狀,要用 **uvs**

診斷過程(先假性失敗→揪錯,是這次最重要的產出):

1. 初版用藝術家 mesh 的 **vertices**(`px=x+W/2, py=H/2−y`)光柵化 → art IoU/alpha 僅 **0.47~0.62**。
   production mesh 不可能只覆蓋一半件 → 判定是**我的度量對齊錯了**,不是藝術家 mesh 爛。
2. 印出 bbox:光暈 vertices 跨度 **802×780**(遠大於 width×height=708×685)且**非置中**;
   左手 301×299 vs 259×217。→ 藝術家 mesh 的 **vertices 位於骨架 setup pose 的擺位框**
   (含 attachment 在骨架中的平移/縮放),**不是件影像的局部框**,不能拿來還原件內形狀。
3. 改用 **uvs**(region 正規化 0..1,`px=uv_x·W, py=uv_y·H`,**top-origin:v 隨影像列增加,不翻 y**)
   → art IoU/alpha 升到 **0.95~0.98**,符合 production mesh 緊貼件的預期。
4. y 方向由實測定案:flipy=False(0.95) vs flipy=True(0.43~0.60)→ **不翻 y**。

**慣例更新**:比對 Spine mesh「件內形狀」一律走 **uvs**(region 局部、top-origin),
**不要用 vertices**(那是 setup pose 世界擺位)。生成器的 uvs=(x/W, y/H) 恰為同一慣例,兩者天然對齊。
(先前 `s4-psd-to-spine-real.md` 猜「uvs 為 atlas UV 需轉 region 局部」;實測這 3 件 uvs **已是 region 正規化**、
跨度貼滿 [0,1],不需再轉——藝術家把 attachment uv 存成 region-local。)

## 度量可信度(負對照)

- 同件 gen↔art = 0.918;**跨件** gen(光暈)↔art(左手)=0.572、↔art(身體)=0.496 → 遠低於 0.90 門檻。
- → 度量能區分「對的件」與「錯的件」,gate 可信(再次落實 RULES「評估器先驗證再下判定」)。

## 產出 / 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
python3 tools/mesh_gen/compare_to_award.py /tmp/robot_parts   # overall_pass=true, exit 0
```
- 工具:`tools/mesh_gen/compare_to_award.py`(PSD件→gen→對照 Award,含負對照可複跑)。
- 圖:`knowledge/figures/s3-psd-to-award-mesh.png`(綠=生成 v1 / 紅=Award藝術家,線框疊件)。

## 意義與下一步

- **S3+S4 端到端首度對真實生產標的閉環**:PSD 件切圖 → 自動生成 mesh → 覆蓋率追平藝術家、頂點更省。
- 侷限:Award 這 5 件**無 deform timeline**(靠骨骼/權重變形),故本次只驗**靜態覆蓋**,
  未驗 per-vertex deform(無真實位移場可轉移;RULES 禁用未校準合成場)。
- 下一步候選:(a) 把「件→Spine mesh attachment」寫成 SkelToJson 組裝(固化 `PSD名/圖層名` 命名 + uv=region-local
  + +2px padding 慣例),端到端產出可載入的 Spine JSON;(b) S2 補圖閘 / 骨架閘。
