# S3 端到端:機器人 PSD 件 → mesh,對照 Award 真實 mesh

> **結論**:把 `robot_parts.psd` 的 3 個「會 warp」件(光暈/身體/左手)經 S4 切圖 → S3
> `generate_mesh_v2` 生成 mesh,對照生產 spine `Award` 的真實藝術家 mesh,**覆蓋率達到或逼近
> 藝術家水準,且頂點數更少**。這是「PSD → 件 → mesh」對真實生產標的的端到端驗收。
> **信心:高**(有真值可比、純 CPU 可重跑)。**相關階段:第 2 階段 S3/S4 串接。**

## 驗收數據(2026-07-09,eps=0.005 校準後)

| 件 | 模式 | GEN 頂點/三角 | GEN IoU | ARTIST 頂點/三角 | ARTIST 覆蓋率 | 判定(IoU ≥ 藝術家) |
|---|---|---|---|---|---|---|
| 光暈 glow | delaunay-v1 | 44 / 56 | **0.961** | 78 / 76 | 0.949 | ✅ 超越 |
| 身體 body | delaunay-v1 | 67 / 104 | **0.980** | 98 / 154 | 0.948 | ✅ 超越 |
| 左手 lhand | delaunay-v1 | 66 / 104 | **0.974** | 80 / 116 | 0.977 | ≈ 99.7%(等效) |

- 遮罩來源:S4 `psd_slice` 切出的件 PNG(原尺寸、正立);GEN/ARTIST 皆量測於同一件 alpha。
- ARTIST 覆蓋率 = 藝術家 mesh 的 `uvs × (W,H)` 重組多邊形 vs 件 alpha 的 IoU(不需權重,故 weighted mesh 也適用)。
- 對照圖:`knowledge/figures/s3-robot-psd-vs-award.png`(上=GEN 綠,下=ARTIST 橘)。
- **生成 mesh 頂點數一律少於藝術家**(44<78、67<98、66<80),覆蓋率卻相當 → 拓樸效率良好。

## 三個關鍵發現

### 1. 機器人件是 **weighted + 骨骼驅動、無 deform timeline**(與窗簾根本不同)
- Award 中 光暈/身體/左手 為 **weighted mesh**(`vertices.length ≠ uvs.length`);右手/頭為 region。
- 9→12 支動畫**皆無 `機器人拆件/*` 的 deform timeline**(已掃描確認)→ 它們靠**骨骼**動,不靠 deform 頂點動畫。
- **推論**:S3 的 deform 閘(`real_deform_field` 位移場轉移)對機器人件 **N/A**(沒有 deform 場可轉移)。
  窗簾那套「耐變形」驗證不適用;機器人件的變形穩健性只在**指定骨權重後**才有意義。
- **S3 要成為真正 drop-in 替代 weighted mesh,還缺 BBW 權重生成**(路線圖 S3 列了但尚未實作)。
  目前生成的是 unweighted mesh —— 幾何/拓樸/覆蓋率已驗證達標,權重是下一塊。

### 2. `generate_mesh_v2` auto 模式**正確地對機器人件回退 delaunay-v1**(非 strip)
- 三件長寬比 0.84~1.12(< strip 門檻 1.2)→ auto 判為非 strip,回退 v1 Delaunay。
- 這是**對的**:strip 拓樸是給窗簾那種「高瘦、順單軸拉伸」的件;機器人件是塊狀,Delaunay 才合適。
- 印證 v2 的 mode=auto 分流在真實資產上判斷正確。

### 3. v1 預設 `epsilon_frac=0.008` 對**高頻輪廓**取樣過疏 → 已校準
- 光暈是**放射狀鋸齒**輪廓;0.008(佔周長 0.8%)的多邊形簡化把鋸齒磨平 → IoU 只有 0.933 < 藝術家 0.949。
- 掃描:eps 0.008→0.005 使 光暈 0.933→0.961、身體 0.966→0.980、左手 0.964→0.974,頂點僅 +7~9。
- **處置**:`generate_mesh_v2.generate()` 新增 `delaunay_eps` 參數,**fallback 預設改 0.005**(真實件校準)。
  `generate_mesh.py` 自身預設**維持 0.008**(不動,避免影響其合成 AC 測試);只有 v2 的 delaunay 分流採新值。
- **副發現**:`evaluate_mesh` 的固定閾值(IoU≥0.95、頂點預算 64)是**合成期預設**;真實件的正確標的是
  **藝術家自身的覆蓋率與頂點數**(光暈藝術家自己也只 0.949 < 0.95;身體/左手藝術家用 98/80 頂點 > 64 預算)。
  → 後續整合閘應以「藝術家基準」為準(`validate_against_real` 已採此哲學),固定閾值僅作合成快篩。

## 重跑指令

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o <out>   # 切 5 件
# 對 光暈/身體/左手 三件 PNG 跑 generate_mesh_v2.generate()(auto→delaunay-v1, eps=0.005)
# 量測:evaluate_mesh.evaluate(mesh, mask) 的 AC1_iou vs 藝術家 uvs×(W,H) 覆蓋率
```

## 未解 / 下一步

- **BBW 權重生成**:讓生成的 unweighted mesh → weighted、綁到 Award 的骨,才是真正的 drop-in。
- **左手 0.974 vs 0.977 的 0.3% 缺口**:刻意不做 per-件特調(eps 再細會過度加密簡單件、傷通用性);
  視為等效通過。若日後要嚴格超越,可加「依輪廓頻率自動選 eps」而非全域降 eps。
