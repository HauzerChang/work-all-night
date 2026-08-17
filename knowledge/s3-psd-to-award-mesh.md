# S3 端到端驗收 — 真實 PSD 件 → 生成 mesh → 對照 Award 生產 mesh

- **結論**:把「PSD → 件 → S3 mesh」整條接到**真實生產標的**上驗收。用 `robot_parts.psd`
  的 3 個 mesh 件(光暈 / 身體 / 左手,在生產 spine `Award` 中皆為 mesh)跑 `generate_mesh_v2`,
  與 Award 藝術家 mesh 對**同一件 alpha** 做覆蓋 IoU 對照 → **3 件全數 pass**
  (生成 IoU 在藝術家 baseline ±0.02 內,身體甚至反超)。
- **信心**:高。用同一套光柵化方法分別重建生成/藝術家 mesh 貼回同一 mask(apples-to-apples 相對比較);
  另渲染三張疊圖(`knowledge/figures/psd2award_*.png`)**視覺確認兩者對齊無座標錯位**,排除「baseline 被錯位壓低」的假性通過。
- **階段**:第 2 階段 / S3 + S4 串接(端到端里程碑:切圖 pipeline 已對真實檔驗收 → 現在 mesh 生成也對真實 mesh 驗收)。

## 資料與工具

- 工具:`tools/mesh_gen/validate_psd_to_award.py`(切件由 `psd_slice.py` 產,mesh 由 `generate_mesh_v2.py` 產)。
- 重現:
  ```
  python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
  python3 tools/mesh_gen/validate_psd_to_award.py        # overall_pass=True
  ```

## 量化結果(覆蓋 IoU vs Award 藝術家 mesh)

| 件 | 生成 mode | 生成 頂點/hull/IoU | 藝術家 頂點/hull/IoU(weighted) | AC(±0.02) |
|---|---|---|---|---|
| 光暈 | delaunay-v1 | 35 / 16 / **0.933** | 78 / 78 / 0.949 | ✅ pass |
| 身體 | delaunay-v1 | 60 / 20 / **0.966** | 98 / 40 / 0.948 | ✅ pass(反超) |
| 左手 | delaunay-v1 | 59 / 19 / **0.964** | 80 / 42 / 0.977 | ✅ pass |

## 關鍵發現 / 解讀(honest)

1. **這 3 件自動選到 `delaunay-v1`,不是 strip**:長寬比 <1.2 且非 row-convex(團塊狀,非高瘦窗簾)。
   `generate_mesh_v2` 的 auto 分流正確——這幾件在 Award **無 deform timeline**(bone-weighted,靠骨骼權重變形),
   故 v1 散點拓樸的「大單向拉伸自交」弱點在此**不適用**;此標的**相關的品質閘是靜態覆蓋率**,不是 deform 閘。
   → 印證「先判斷 mesh 的變形機制(deform timeline vs bone-weight),再選拓樸與對應的閘」。

2. **生成頂點數遠少於藝術家(35/60/59 vs 78/98/80),覆蓋率卻相當**:藝術家的多餘頂點不是為覆蓋,
   是為 **weighted 骨骼變形的控制密度**(在骨影響邊界插點)。純覆蓋任務用更少頂點即可打平
   → **權重/綁定密度屬 S5(骨架)範疇,不是 S3 覆蓋任務的責任**。這條界線要記住:S3 交「覆蓋足夠的拓樸」,
   權重繪製/rig 密度留給 S5。

3. **光暈略低於藝術家(0.933 vs 0.949)源於細長突起取樣不足**:光暈有細天線/尖刺,藝術家用
   **hull=78=全頂點的純邊界 mesh**貼合;生成 v1 hull 僅 16 → 邊界取樣稀,尖刺覆蓋略遜。
   → **改進槓桿:v1 的輪廓取樣點數**(對應 v2「IoU 由 rows(邊界密度)決定」的同一原理)。仍在 ±0.02 內過關。

4. **身體反超(0.966 > 0.948)合理**:藝術家 mesh 對身體某些末梢略內縮(hull 40 未鋪滿全 alpha),
   生成 mesh 的外接輪廓覆蓋更滿。疊圖確認兩者對齊,非錯位假象。

## 座標/格式注意(可重用)

- Award mesh `uvs` 為 **region-local 0..1**(Spine runtime 再乘 atlas region uv-rect),可直接 `uvs*W_piece` 貼回件 mask。
- Award 這 3 件是 **weighted mesh**(`len(vertices) != len(uvs)`),但 `uvs`/`triangles`/`hull` 欄位照常,
  覆蓋率重建只需 uvs+triangles,不受 weighted 影響。
- y 取向:件 alpha 為影像座標(y-down),Award uvs 亦 y-down → 本工具兩種取向都算取較高者,實測 3 件全 `as-is`(同慣例)。

## 對 pipeline 的意義

- **S4(PSD 切圖)→ S3(mesh 生成)端到端對真實生產標的閉環驗收通過**:切件無損(前里程碑)+ mesh 覆蓋達標(本次)。
- 下一步自然是把「件 → Spine attachment(含 mesh)」寫成組裝工具(SkelToJson),用 `機器人拆件/<圖層名>` 命名慣例
  + size+2px padding + mesh/region 分配,端到端吐出可載入的 Spine JSON。權重與 pivot 留給 S5。
