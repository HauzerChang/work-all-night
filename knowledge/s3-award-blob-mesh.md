# S3 端到端「PSD 件 → 生成 mesh → 對照 Award 真實 blob mesh」(里程碑)

- **結論**:把 `robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手)經 `psd_slice` 切出 → 餵
  `generate_mesh_v2`(blob 件 aspect<1.2 → auto **回退 v1 Delaunay**) → 與 **Award 真實生產
  mesh** 做靜態輪廓覆蓋(IoU)+ 拓樸預算對照。**3 件全 `overall_pass`**:生成 mesh 用**更少
  頂點**達到與藝術家**相當(身體甚至更好)**的輪廓覆蓋。
- **意義**:S3 第一次對 **weighted/blob 型**真實生產 mesh 驗收(先前 main_draw 4 件是
  deform-timeline 窗簾/陰影 strip)。端到端「PSD→件→mesh」對真實標的成立。
- **信心**:高(對真實生產 spine ground truth 比對 + UV 空間先驗 + 三聯圖視覺確認)。
- **階段**:第 2 階段 / S3 ∩ S4(把 S4 切件接上 S3 生成)。

## 量化結果(`compare_to_award.py`,margin=0.03)

| 件 | 生成 mode | 生成 v / hull / tri | 生成 IoU | 藝術家 v / hull / tri (weighted) | 藝術家 IoU | 判定 |
|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 35 / 16 / 49 | 0.933 | 78 / 78 / 76 | 0.949 | ✅(headroom 0.014) |
| 身體 | delaunay-v1 | 60 / 20 / 97 | **0.966** | 98 / 40 / 154 | 0.948 | ✅(生成更佳) |
| 左手 | delaunay-v1 | 59 / 19 / 97 | 0.964 | 80 / 42 / 116 | 0.977 | ✅ |

- 生成頂點數全 < 藝術家(35<78、60<98、59<80)→ 更精簡且 IoU 相當。
- 三聯圖見 `figures/award_{光暈,身體,左手}.png`(左=來源 alpha,中=生成覆蓋,右=藝術家覆蓋;
  綠=命中、紅=溢出 mask 外、橘=漏覆蓋)。

## UV 空間先驗(關鍵前置,已驗證)

Award mesh JSON `uvs` 為 **region-local 0..1**(非 atlas-page 空間),與 atlas 的
rotate/scale(~0.70 縮小、光暈/身體在 Award2.png 旋轉打包)**無關** → `uvs×(W_psd,H_psd)`
直接落在 PSD 件(原始解析度、未旋轉)輪廓上。**證據:藝術家 IoU 0.948~0.977 很高**
(若 uvs 為 atlas-page 空間會極低)。沿用 main_draw `artist_iou` 同一假設,此處再次成立。

## 兩個真實發現(可重用)

1. **藝術家對「非變形末端」刻意不滿覆蓋**:身體 mesh `uvs` x 僅到 0.759、底部小腿/腳處留大片
   橘(未覆蓋)→ 藝術家**故意不把 mesh 鋪到不需變形的末端**(那些區域靠別的 slot 或不動)。
   這也是為何身體生成 IoU(0.966)**反而高於**藝術家(0.948)。
   → 教訓:對 blob mesh,「IoU 對齊藝術家」是合理門檻,生成略高於藝術家**不代表更好**,可能只是
   多覆蓋了藝術家刻意省略的不動區。**輪廓覆蓋是必要非充分**;真正品質還要看變形區是否被涵蓋。

2. **v1 Delaunay 在凹形件會「跨接凹缺」溢出**:光暈是凹形(伸出的手指 + 身體間深凹)。v1 的
   hull 經 Douglas-Peucker(epsilon=0.008)只簡化到 **16 點**,跨接深凹 → 三聯圖中段大片**紅**
   (溢出);藝術家用 **78 hull 點**緊貼凹邊故幾乎無溢出。雖仍過 margin(0.933≥0.919),但這是
   v1 對凹形 blob 的**結構性弱點**(strip 模式不適用 blob,救不了)。
   → 後續候選:凹形件改用 `epsilon` 自適應 / concave-hull(alpha shape)/ 加大 hull 取樣密度。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
python3 tools/mesh_gen/compare_to_award.py --parts /tmp/robot_parts --figs knowledge/figures
# overall_pass=true (exit 0)
```

## 下一步候選

- **凹形 blob 的 hull 保真**:對 IoU 溢出大(凹形)的件,降 `epsilon` 或上 concave-hull,
  再對光暈重測溢出是否收斂(有藝術家 78-hull 真值可比)。
- **變形級對照**:Award 這 3 件是 weighted(靠骨權變形),無 deform timeline → 需先把
  weighted mesh 的骨權重也納入比對(目前只比 setup-pose 輪廓拓樸),才算完整。
- 把「件→Spine attachment」命名/尺寸慣例(`PSD名/圖層名`、+2px、atlas 0.70)固化成 SkelToJson。
