# S3+S4 端到端驗收 — PSD 切件 → 生成 mesh → 對照 Award 真實藝術家 mesh

- **結論**:把 S4(PSD 切件)與 S3(mesh 生成)**串成端到端 pipeline**,對「真實生產標的」
  (Award「機器人拆件」的 3 個 mesh 件:光暈 / 身體 / 左手)驗收,**3 件全 PASS**
  (生成 mesh 對 piece 輪廓的 IoU ≥ 藝術家手做基準 − 0.03,且生成 mesh 自身格式/幾何 AC 全過)。
- **信心**:高。有 (a) 真實藝術家 mesh 作 ground truth、(b) uv→像素映射的自驗閘、(c) 視覺線框疊圖三重佐證。
- **階段**:第 2 階段 / S3+S4 整合(里程碑:兩能力首次端到端對真實生產標的驗收)。
- **工具**:`tools/mesh_gen/psd_mesh_vs_award.py`;圖 `knowledge/figures/s3-psd-mesh-vs-award.png`。

## ★ 關鍵新發現:Spine JSON mesh `uvs` 是 **region-local [0,1]**,不是 atlas page 全域

驗證 Award 3 個 mesh 的 uv 範圍(左手 u∈[0.008,1.0]、v∈[0.004,1.0])→ 佔滿 [0,1],
而非該 region 在 page 的子矩形(左手 region 只佔 page 2040² 的 181×152)。
**故 JSON uvs 是相對 region 的區域座標,runtime(`AtlasAttachmentLoader`/`Mesh.updateUVs`)
才用 region 的 u,v,u2,v2 + rotate 映射到 atlas page。**

**實務含意(重要,先前雷點清單沒寫)**:要把藝術家 mesh 疊回「件的邏輯圖(= PSD 切件)」比對,
直接 `piece_pixel = (u*W, v*H)` 即可,**完全不需處理 atlas 的旋轉/0.70 縮放**(那些只是打包細節)。
本閘的「映射自驗」證實此點:藝術家 mesh 對自己件 alpha 的 IoU = **0.949 / 0.948 / 0.977**(全 ≥ 0.80 門檻,
v 軸不需翻)。若 uvs 是 page 全域,這個直接映射會得到極低 IoU —— 沒發生 → 確認 region-local。

## 驗收數據(`--psd robot_parts.psd --award Award.json`,exit 0)

| 件 | 藝術家 mesh | 藝術家 IoU | 生成 mode | 生成頂點 | 生成 IoU | gap vs 藝術家 | pass |
|---|---|---|---|---|---|---|---|
| 光暈 | 78v / hull 78(純周界扇形) | 0.9486 | delaunay-v1 | 35v(hull 16) | 0.9331 | **−0.0155** | ✅ |
| 身體 | 98v / hull 40 | 0.9477 | delaunay-v1 | 60v(hull 20) | 0.9660 | **+0.0183** | ✅ |
| 左手 | 80v / hull 42 | 0.9768 | delaunay-v1 | 59v(hull 19) | 0.9642 | −0.0126 | ✅ |

## 觀察與結論

1. **3 件全走 v1(Delaunay 散點)不是 v2 strip**:光暈/身體/左手長寬比 0.97/1.12/0.84 均 < 1.2
   且非高瘦 → v2 auto 正確回退 v1。**v2 strip 是給窗簾類「高瘦單向拉伸」件的;blobby/wide 件用 v1 才對。**
   → 印證 `generate_mesh_v2` 的 auto 分流邏輯對真實件也做出正確選擇。
2. **軟邊件的 IoU 天花板由羽化 alpha 決定,不是 0.95**:光暈是輻射狀光暈,**連藝術家都只有 0.9486**。
   `evaluate_mesh` 內建的絕對 `iou_thresh=0.95` 對這種件會假性失敗 → 本閘沿用
   `validate_against_real.py` 已定的校正:**IoU 門檻 = 藝術家基準 − margin**,不用武斷 0.95。
   (又一次印證「別用武斷絕對閾值,要對齊藝術家真值」。)
3. **拓樸策略差異(視覺可見)**:光暈藝術家用「純周界扇形」(hull=頂點=78,無內部點)緊貼羽化外緣;
   我們 v1 用 16 點 hull + 內部 Delaunay → 覆蓋主體佳但周界較粗,IoU 低 0.015(仍在 margin 內)。
   **改進槓桿(未做):對軟邊 blob 提高 contour hull 取樣密度可再貼近藝術家。** 身體/左手我們反而更省頂點且 IoU 相當。
4. **deform 閘不適用**:這 3 件在 Award **無 deform timeline**(靠骨骼/權重變形,見 s4-psd-to-spine-real)。
   故本閘只驗**靜態輪廓對藝術家真值**;逐頂點 deform 穩健性(v2 的強項)不在此閘範圍,也非這些件的需求。

## 閘自身可信度(evaluator-of-evaluator)

- **映射自驗**:藝術家 mesh 對自己件 IoU 必須 ≥ `MAP_SANITY=0.80`,否則標 `mapping_ok=False` 拒絕採信
  → 防「uv 映射錯(如 v 軸方向)卻假性通過」(專案已三度踩 evaluator miscalibration:stress_field、
  composite 白底、atlas derotate 方向 → 本閘一開始就內建自驗)。
- 三件 mapping_ok 全 True、v 不翻 → 映射正確。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts   # 切件(可選)
python3 tools/mesh_gen/psd_mesh_vs_award.py                                       # 端到端閘,exit 0 = PASS
```

## 下一步候選

- 把「件→Spine mesh attachment」**寫出組裝工具(SkelToJson 雛形)**:固化 region-local uvs + `PSD名/圖層名`
  slot 命名 + size+2px + mesh/region 依需求分配,端到端產出可載入 Spine JSON(接候選 2)。
- (改進)對軟邊 blob 件加「contour 密取樣 hull」模式,把光暈類的 IoU 再往藝術家推。
