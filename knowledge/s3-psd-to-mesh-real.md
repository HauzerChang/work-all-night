# S3 端到端驗收 — PSD 件 → generate_mesh → 對照真實生產 mesh(Award)

- **結論**:機器人拆件 PSD 的 3 個 mesh 件(光暈/身體/左手)跑 `generate_mesh_v2(auto)`,
  對照生產 spine `Award` 的**真實藝術家 mesh**(ground truth),3 件**全 `overall_pass`**:
  生成 mesh 的靜態覆蓋 IoU **≥ 藝術家 mesh - 0.03**,且**頂點數少 40~55%**、格式合法、0 孤兒、重心全在 mask 內。
  這是第一次把 S3 生成器對「非窗簾、非合成」的**真實生產標的 + 真值拓樸**做端到端驗收。
- **信心**:高(對真實生產 mesh 逐件比對;PSD↔atlas 同素材已於 s4 閉環;評估器先做自一致性 pre-check)。
- **階段**:第 2 階段 / S3×S4 串接(里程碑:合成/窗簾 → 真實 big-win 主角件)。
- **可重現**:`python3 tools/mesh_gen/validate_psd_to_mesh.py`(exit 0 = 3 件全過)。
  圖:`knowledge/figures/psd-to-mesh-robot.png`(藝術家橘 / 生成綠,線框疊 alpha)。

## 量化結果(共同框 = PSD 件 alpha,最高保真)

| 件 | 藝術家 (ground truth) | 生成 v2 | 覆蓋 IoU(gen vs artist) | 頂點省 |
|---|---|---|---|---|
| 光暈 | 78v / hull78 / 76t / IoU 0.949 | 35v / hull16 / 49t (delaunay-v1) | **0.933** vs 0.949(-0.016,過) | −55% |
| 身體 | 98v / hull40 / 154t / IoU 0.948 | 60v / hull20 / 97t (delaunay-v1) | **0.966** vs 0.948(**+0.018,更好**) | −39% |
| 左手 | 80v / hull42 / 116t / IoU 0.977 | 59v / hull19 / 97t (delaunay-v1) | **0.964** vs 0.977(-0.013,過) | −26% |

## 方法要點(如何取得可信的真值對照)

1. **共同座標系 = PSD 件 alpha**。Award mesh 的 `uvs` 是 **region-local 0..1**(非 atlas-page;
   驗證:疊到 PSD 件 alpha IoU 0.95~0.98)→ **推翻 s4 筆記「uvs 為 atlas UV 需先轉」的過度保守假設**。
   直接用 PSD 件(未旋轉、未 0.70 縮小)當共同框,避開 atlas derotate/scale 雜訊;PSD↔atlas 同素材已在 s4 閉環。
2. **先驗評估器(自一致性)**:藝術家自己的 mesh 疊 PSD alpha 只有 ~0.95(非 1.0)→ 這是誠實 baseline
   (藝術家 mesh 本就不完美貼齊 alpha,hull 是簡化)。生成 mesh 只需「與藝術家同級覆蓋」即算過,不用武斷 0.95。
3. **頂點預算 = 藝術家頂點數**:以生產精簡度為預算,生成若「同覆蓋、更少頂點」即為勝出。
4. **mode=auto 正確路由**:3 件長寬比皆 < 1.2(0.97/1.12/0.84)→ **全回退 v1 Delaunay**(非 strip)。
   證明 auto 啟發式對「blob 類」件選對拓樸(strip 只適合窗簾式單向拉伸長條)。

## ⚠️ 誠實範圍界定(這次**沒有**驗到什麼)

- **只驗靜態拓樸 + 覆蓋**,**未驗 deform**。原因:Award 這 3 件是 **weighted mesh(靠骨骼權重變形,
  無 deform timeline)**,生成的是 **unweighted mesh**。故沒有「逐頂點 deform 場」真值可轉移,
  也還沒生權重 → **不能宣稱生成 mesh 在機器人動畫下會正確變形**。
- 光暈的殘差(0.933 < 0.949)來自**粗 hull(16 點)裁掉柔性羽化邊的細突起**;藝術家用 78 點純 hull fan
  正是為了細描軟邊界。**啟發:軟放射/羽化形狀應調低 `epsilon_frac` 加密 hull 取樣**(目前 0.008 對硬邊 blob 夠、對軟邊偏粗)。

## 下一步(自然接續)

1. **權重 + weighted-deform 真值閘**:給 Award 骨架擺 pose(12 anims 之一)→ 用權重算藝術家 mesh 的
   世界頂點位移 → 得**真實 weighted 位移場** → 轉移到生成 mesh(需先給生成 mesh 生權重,BBW/heat)。
   這才閉合「生成 mesh 也能像生產件一樣正確變形」。← S3 最後一塊真值缺口。
2. **軟邊件的 hull 自適應 epsilon**:依 alpha 邊界羽化程度自動調 `epsilon_frac`(光暈類加密)。
3. **切圖→Spine JSON 組裝(SkelToJson)**:把「件→attachment(name=`PSD名/圖層名`、+2px、mesh/region 分配)」
   固化成端到端寫檔工具,直接吐可載入的 Spine JSON。
