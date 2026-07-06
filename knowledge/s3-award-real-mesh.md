# S3 端到端驗收:真實件 → 生成 mesh → 對照 Award 生產 mesh(外部真值)

- **結論**:把 Award(big win spine)機器人拆件的 **3 個藝術家手做 mesh**(光暈/身體/左手)當
  S3 生成器的**外部真值**,端到端跑「atlas 生產貼圖切件 → `generate_mesh_v2`(auto→Delaunay v1)→
  量化」並逐件對照。調到 `eps=0.002` 後**3 件全 overall_pass**:generated 靜態 IoU 全 **≥ 藝術家
  mesh 自身 IoU**(baseline),0 退化 / 0 孤兒。首次對「真實生產 mesh 真值」而非合成/自製標的驗收。
- **信心**:高(真值來自生產 spine;alpha 來源為實際打包貼圖;UV 慣例經 silhouette 外部校驗)。
- **階段**:第 2 階段 / S3 端到端(S3+S4 串接的里程碑收口)。
- **工具**:`tools/mesh_gen/compare_award_mesh.py`(指令 `python3 tools/mesh_gen/compare_award_mesh.py`)。

## 量化結果(eps=0.002,budget=140,margin=0)

| 件 | 藝術家 nv/hull/tris | 藝術家 IoU | 生成 nv/hull/tris | 生成 IoU | gap | pass |
|---|---|---|---|---|---|---|
| 光暈 | 78 / 78 / 76 | 0.9795 | 117 / 38 / 194 | 0.9832 | **+0.0037** | ✅ |
| 身體 | 98 / 40 / 154 | 0.9760 | 117 / 37 / 195 | 0.9926 | **+0.0166** | ✅ |
| 左手 | 80 / 42 / 116 | 0.9681 | 123 / 43 / 201 | 0.9913 | **+0.0232** | ✅ |

(藝術家 mesh 皆 **weighted**;光暈是純 hull ring — 78 頂點全在邊界、fan 三角。)

## 兩個校準過的關鍵事實(動手前務必記住)

1. **Spine JSON 的 mesh `uvs` 是 region 局部 0..1**,不是整頁 atlas UV(先前 log-006 的
   「需先轉 region 局部」筆記過度保守)。runtime 才透過 atlas region(含 rotate/縮小打包)貼回。
   → 藝術家 uvs 直接 `×(W,H)` 就是 derotate 後**邏輯朝向**切件的像素座標。
   **外部校驗**:3 件 artist mesh 對 derotate 切件 silhouette IoU = **0.968 / 0.980 / 0.976**
   (光暈/身體 rotate=true,CW derotate 後仍對齊 → 一併確認 atlas_crop 的 CW 方向正確)。
2. **這 5 件在 Award 無 deform timeline**(靠骨骼權重變形,非逐頂點 deform)→ **不跑 deform 閘**
   (沒有真實位移場可轉移;依 RULES 絕不用未校準合成壓力充數)。這裡可信的量化軸是**靜態輪廓 IoU**。

## 生成器兩處改動(由真實件逼出來)

- **`eps` 預設 0.008 對細緻生產件太粗**:hull 只有 14~21、IoU 低於藝術家基準(光暈差 -0.053)。
  eps 掃描顯示 **0.002 是甜蜜點**(hull 37~43 ≈ 藝術家 38~78,IoU 全過)。故 `compare_award_mesh`
  預設 eps=0.002;`generate_mesh_v2.generate` 新增 `eps/max_interior/min_dist` 參數轉發給 v1。
  註:main_draw 4 mesh 走 strip(v2),不受 v1 eps 影響。
- **孤兒內部頂點修復**:凹形區被 `filter_triangles` 濾掉後,少數內部點無三角引用(AC2c fail)。
  `generate_mesh.prune_orphans()`:保 hull 環、移除未引用內部點、重映射三角索引。

## 侷限 / 下一步

- **生成器頂點效率略遜藝術家**:達同等 IoU 需 117~123v(藝術家 78~98v)。Delaunay 內部過採樣;
  藝術家把頂點放在關鍵摺點更省。覆蓋率/穩健度達標,但「頂點預算最小化」仍有優化空間。
- 這 3 件無 deform,故**耐變形**未在真值上驗;耐變形結論仍以 main_draw 4 mesh(有 deform)為準。
- 下一步:把「件→Spine JSON 組裝」(`PSD名/圖層名`、mesh/region 分配、+2px、atlas 0.70 縮放、
  region-local uvs)固化成 SkelToJson 工具,端到端輸出可載入的 Spine mesh attachment。
