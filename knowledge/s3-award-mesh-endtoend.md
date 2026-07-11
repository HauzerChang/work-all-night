# S3+S4 端到端:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:對真實生產標的完成「PSD 件 → `generate_mesh_v2` → 對照 Award 藝術家 mesh」端到端驗收。
  Award 中 3 個機器人 mesh 件(光暈/身體/左手)的 alpha 由 `psd_slice` 切出(已驗 = spine 生產素材),
  丟進 S3 生成器,**3 件全 overall_pass**:生成 mesh 有效(0 退化/0 孤兒/hull 閉合/頂點在預算內)
  且輪廓覆蓋率 IoU **達或勝過藝術家自身覆蓋率**(margin 0.02)。
- **信心**:高(對真實生產 mesh 交叉比對 + 覆蓋率負對照矩陣確認鑑別力)。
- **階段**:第 2 階段 / S3×S4 端到端(里程碑:S3 首次對「真實生產 mesh」而非 main_draw 窗簾驗收)。

## 量化結果(`tools/mesh_gen/compare_award_mesh.py`)

| 件 | 件px | 生成 mode | 生成 v/t/hull | 生成 IoU | 藝術家 v/t/hull | 藝術家覆蓋 IoU | overall |
|---|---|---|---|---|---|---|---|
| 光暈 | 706×683 | delaunay-v1 | 35 / 49 / 16 | 0.933 | 78 / 76 / 78 | 0.949 | ✅ |
| 身體 | 379×425 | delaunay-v1 | 60 / 97 / 20 | **0.966** | 98 / 154 / 40 | 0.948 | ✅ |
| 左手 | 257×215 | delaunay-v1 | 59 / 97 / 19 | 0.964 | 80 / 116 / 42 | 0.977 | ✅ |

## 三個真實發現

1. **`mode=auto` 對真實 blob 件正確路由到 Delaunay-v1**(非 strip)。3 件 aspect 皆 < 1.2
   (光暈近方、身體 1.12、左手 0.84),都不是「高瘦 row-convex」窗簾型 → auto 正確退回 v1。
   先前(`s3-four-mesh-generalization`)strip 是為窗簾長條設計;此處驗證 mode-selector 在
   **另一類形狀(blob)上也選對**。→ v2 的 auto 路由對兩類形狀都成立。

2. **生成 mesh 明顯更精簡卻覆蓋率相當或更好**:生成 35/60/59 v vs 藝術家 78/98/80 v。
   身體件生成 IoU(0.966)**勝過**藝術家覆蓋率(0.948),頂點還少四成。
   → 純輪廓覆蓋不需要藝術家那麼多頂點。

3. **藝術家頂點多 ≠ 覆蓋率高,而是為了 weighted deform 的控制密度**:這 3 件在 Award
   **weighted 且無 deform timeline**(靠骨骼權重 warp,非逐頂點 deform)。藝術家的
   78/98/80 頂點是給骨骼權重平滑變形用的控制點,不是為了填滿輪廓(輪廓 35~60 v 就夠)。
   → **S3 目前只生成「輪廓覆蓋足夠」的拓樸;要生成「適合骨骼權重 warp」的均勻控制網格是另一課題**
   (與 curtain 的逐頂點 deform 也不同)。這是誠實的能力邊界。

## 為何本比對不做 deform 轉移閘

`validate_against_real.py` 的變形閘依賴 `real_deform_field()`(從 deform timeline 取真實位移場)。
這 3 件在 Award **無 deform timeline** → 無位移場可轉移,deform 閘不適用。故本比對只做
**拓樸有效性 + 輪廓覆蓋率**;骨骼權重驅動的變形穩健性尚未涵蓋(見發現 3,屬 S3 未來課題)。

## 評估器可信度(負對照矩陣)

「藝術家 mesh(列)對件 mask(欄)」覆蓋 IoU:對角(相符)0.949~0.977,非對角(錯配)0.48~0.58。
→ 覆蓋率指標鑑別力清楚,不是恆高的假指標。

## uv 座標空間備註

Award 這 3 mesh 的 `uvs` 範圍約 0..1(量測:光暈 x[.012,.990]/y[.001,.952] 等),為 **region-local**,
故直接 `uv*(W,H)` 落回件像素空間即可比對(與 `generate_mesh_v2.to_spine` 輸出的 uv 同空間)。
(注意:若件在 atlas 為 rotate=true,atlas UV 需另處理;但 attachment JSON 的 uvs 已是 region-local,不受影響。)

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd --out /tmp/robot_pieces
python3 tools/mesh_gen/compare_award_mesh.py           # 3 件全 overall_pass,exit 0
```

## 下一步候選

- **「件 → Spine JSON」組裝工具(SkelToJson)**:固化 `PSD名/圖層名` slot 命名 + size+2px padding +
  生成 mesh,端到端產出可載入的 Spine JSON(把 S3+S4 真正串成產物)。
- S3 生成「均勻控制網格」變體(給 weighted deform 用,發現 3),需 BBW 權重才完整。
- S2 補圖閘 / 骨架閘(補齊 S2 樞紐)。
