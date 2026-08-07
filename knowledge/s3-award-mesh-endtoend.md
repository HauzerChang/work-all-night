# S3 端到端驗收 — PSD 切件 → generate_mesh_v2 → 對照 Award 真實 mesh

- **結論**:把「PSD→件→S3 mesh」整條接到**真實生產 mesh 真值**(Award 機器人 3 件光暈/身體/左手)對照,
  4 條靜態幾何 AC **3 件全 overall_pass**。生成 mesh 用**更少頂點**(35/60/59 vs 藝術家 78/98/80)
  達到與藝術家**同等覆蓋**(IoU 0.93~0.97),兩者覆蓋一致性 IoU 0.92~0.96。
- **信心**:高。有真實生產 mesh 當外部真值(非自洽 round-trip);uvs 方向由資料自證;含視覺疊圖佐證。
- **階段**:第 2 階段 / S3(里程碑:合成/自產 → **對真實生產 mesh 真值**端到端驗收)。

## 做了什麼

`tools/mesh_gen/compare_award_mesh.py`:對 Award 中為 mesh 的 3 件,各跑
1. **AC-A 藝術家基準 + uvs 解讀驗證**:把 Award mesh 的 `uvs`([0,1] region-local)映回件像素、
   填三角、對 psd_slice 切出的件 alpha 求 IoU。v 方向以「取較高 IoU 的 v / 1-v」自動判定。
2. **AC-B 生成覆蓋**:`generate_mesh_v2(auto)` 對同一件 alpha 的覆蓋 IoU ≥ 藝術家基準 − 0.03。
3. **AC-C 一致性**:生成 vs 藝術家 兩覆蓋遮罩的 IoU ≥ 0.80。
4. **AC-D 頂點預算**:生成頂點數 ≤ budget 且與藝術家同數量級。

## 結果(3 件全過)

| 件 | size | gen_mode | 藝術家 IoU(AC-A) | 生成 IoU(AC-B) | 一致性(AC-C) | 生成v / 藝術家v |
|---|---|---|---|---|---|---|
| 光暈 | 706×683 | delaunay-v1 | 0.9486 | 0.9331 | 0.9179 | 35 / 78 |
| 身體 | 379×425 | delaunay-v1 | 0.9477 | 0.9660 | 0.9284 | 60 / 98 |
| 左手 | 257×215 | delaunay-v1 | 0.9768 | 0.9642 | 0.9572 | 59 / 80 |

視覺疊圖:`knowledge/figures/s3-award-mesh-overlay.png`(左=藝術家 amber、右=生成 green,3 件)。

## 關鍵發現

1. **uvs 解讀被真值證實**:「Spine mesh `uvs` = region-local `[0,1]`、v 由上而下」正確 —— 3 件 flip_v 皆
   False 且藝術家 mesh 覆蓋自身輪廓 IoU 0.95~0.98(若解讀錯,IoU 會崩)。這是**用外部真值校準評估器**
   (前有 stress_field / composite 白底 / derotate 方向三次 miscalibration 教訓)。
2. **v1(散點 Delaunay)對「團塊狀」真實件通用**:3 件長寬比皆 < 1.2 → auto 正確回退 v1(非 strip)。
   v1 對團塊件覆蓋達藝術家水準,與 v2-strip 對「高瘦條狀」件(窗簾)專精**互補**;auto 選對了模式。
3. **生成 mesh 更精簡**:少 ~25–55% 頂點即達同等覆蓋(邊界取樣夠即可;藝術家頂點含手感冗餘)。
   殘差主要來自凹口(如光暈突出的手臂)被直弦切過 → 生成 IoU 略低於藝術家但在 margin 內。

## ⚠️ 本閘的限制(誠實記錄)

- **只驗靜態幾何,未驗 deform 穩健度**:這 3 件在 Award **無 deform timeline**(靠骨骼/權重變形,
  非逐頂點 deform)→ **沒有真實位移場可轉移**。故 S3 的「耐變形」結論仍只來自 main_draw 4 mesh
  (curtain/shadow,有 deform),本次未加成。要對機器人件驗變形,需在 inspector 裡由骨骼權重驅動
  (需 Award 綁定 + 權重),超出本 bounded chunk。
- 件 alpha 來源為 PSD 切件(原始解析度);Award atlas 為 0.70 縮小版,幾何比對用 PSD 件更精確。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot     # 切件
python3 tools/mesh_gen/compare_award_mesh.py /tmp/robot                       # 3 件全 overall_pass
```

## 下一步候選

- 把「件→Spine attachment」組裝固化(SkelToJson):用本次確認的 uvs=region-local 慣例 + `PSD名/圖層名`
  slot 命名 + size+2px padding,端到端產 Spine JSON(候選 2)。
- 若要補機器人件的 deform 驗:需骨骼/權重路徑(S5 相關),非純幾何。
