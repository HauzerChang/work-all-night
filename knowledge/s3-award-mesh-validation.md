# S3 端到端驗收 — PSD→件→mesh 對真實生產標的(Award 機器人 3 mesh)

- **結論**:把 S3 mesh 生成器對**真實生產 spine 的 mesh 件**(Award「機器人拆件」的
  光暈 / 身體 / 左手,皆為 weighted mesh)做端到端靜態覆蓋 IoU 驗收。**預設 epsilon 下失敗**
  (光暈 −0.050、身體/左手 −0.008);查明主因是**固定 `epsilon_frac=0.008` 對有機輪廓在生產解析度下
  hull 過稀**。新增**自適應 epsilon**(`generate_adaptive`,逐步加細至覆蓋 IoU≥target)後,
  **3 件全部達/超藝術家 baseline**(gap +0.004 ~ +0.014),且 main_draw 4 mesh 無回歸。
- **信心**:高(對真實生產 mesh 的 ground-truth baseline 比對 + 單調掃描曲線 + 回歸測試)。
- **階段**:第 2 階段 / S3(里程碑:S3 從自家 main_draw → 真實生產標的 Award)。

## 對象與 ground truth

Award 機器人 3 個 mesh 件(對應 `robot_parts.psd` 圖層,見 `s4-psd-to-spine-real.md`):

| 件 | 藝術家 mesh | atlas mask(切出) | 藝術家 mesh IoU vs alpha(baseline) |
|---|---|---|---|
| 光暈 | 78v / hull 78(純輪廓多邊形)/ 76t | 496×480 | 0.9795 |
| 身體 | 98v / hull 40 / 154t | 267×299 | 0.9760 |
| 左手 | 80v / hull 42 / 116t | 181×152 | 0.9681 |

**3 件皆 weighted 且無 deform timeline** → 靠骨骼/權重變形,非逐頂點 deform。

## 關鍵發現

1. **frame 對齊**:Award mesh `uvs` 是 **region-local 正規化**(每件 uvs 幾乎撐滿 [0,1]),
   **不是 atlas-page UV**(先前 `s4` 筆記的假設過度保守)。故 `atlas_crop.extract`(多頁 + CW derotate)
   切出的 upright region mask 與 attachment uvs 同框 → 藝術家 mesh 對自身 alpha IoU 0.97~0.98(驗證對齊)。
   實作直接沿用 `validate_against_real.artist_iou`。
2. **deform 閘不適用(誠實標記)**:weighted mesh 的 `vertices` 是變長 compact 格式,無法 reshape;
   且無 deform timeline。`deform_eval.real_deform_field` 對這類件會崩。→ `validate_against_award.py`
   明確標 `AC_real_deform.applicable=false` 並附原因,**不用未校準的 stress 場冒充**(遵守 RULES)。
3. **v2 auto 對 blob 自動退回 v1**:v2 strip 只在「條狀」形狀啟用;3 個機器人件被判為非條狀 → 走 `delaunay-v1`。
   故 v1/v2 結果完全相同。合理:strip 的優勢是 deform 耐受,這些件無逐頂點 deform,strip 無用武之地。
4. **主因:固定 epsilon 不通用**。`epsilon_frac` 雖相對周長,但**輪廓複雜度**不同:
   main_draw 窗簾近矩形(0.008 夠);Award 機器人件有機輪廓,0.008 的弦跨過凹處 → hull 過稀、覆蓋不足。
   單調掃描(光暈):

   | eps | nv | hull | IoU | gap vs artist |
   |---|---|---|---|---|
   | 0.008 | 54 | 14 | 0.9292 | −0.0503 |
   | 0.004 | 61 | 22 | 0.9656 | −0.0139 |
   | **0.002** | 73 | 38 | 0.9832 | **+0.0037** |
   | 0.001 | 92 | 58 | 0.9924 | +0.0129 |

   eps≈0.002 時 hull 數收斂到與藝術家同量級(光暈 38、身體 37、左手 43 vs 藝術家 78/40/42),
   且覆蓋達/超 baseline。**藝術家把光暈 over-tessellate 到 78 hull 多為了平滑 weighted deform,非覆蓋**。

## 修正:`generate_adaptive`(generate_mesh.py)

自 eps=0.008 起,若覆蓋 IoU(vs 自身 alpha)< target(預設 0.98)就 eps 減半再試,
直到達標或頂點數觸頂(預設 200)。回傳 `(mesh, mask, meta)`,meta 記實際 eps 與掃描軌跡(可稽核)。
**自適應解決「不同解析度 / 不同輪廓複雜度」的通用性**,取代 magic constant。

驗收(`validate_against_award.py --gen adaptive`,exit 0):

| 件 | eps_used | gen nv/hull | IoU | artist baseline | gap |
|---|---|---|---|---|---|
| 光暈 | 0.002 | 73 / 38 | 0.9832 | 0.9795 | +0.0037 |
| 身體 | 0.004 | 69 / 29 | 0.9858 | 0.9760 | +0.0098 |
| 左手 | 0.004 | 57 / 30 | 0.9816 | 0.9681 | +0.0135 |

**無回歸**:main_draw curtain_left v2 仍 overall_pass(0 自交);adaptive 對 curtain_left 選 eps=0.004、
IoU 0.99、44v,達標。

## 可重現

```
python3 tools/mesh_gen/validate_against_award.py --gen both       # 預設 eps:body/hand 近 baseline、glow 差 0.05
python3 tools/mesh_gen/validate_against_award.py --gen adaptive   # 3 件全 pass(exit 0)
```

## 下一步 / 開放項

- **deform 級驗收仍缺**:這 3 件是 weighted/骨驅動,靜態 IoU 過但「權重變形品質」未驗。
  要真正對照需 **S3 權重步驟(BBW)**——把生成 mesh 綁到 Award 對應骨、跑動畫、比世界頂點。屬 S3 下一子題。
- 把 `generate_adaptive` 設為端到端 PSD→Spine JSON 組裝(SkelToJson,STATE 候選 2)的預設拓樸生成器。
- 光暈這類**軟邊/羽化**件:alpha 閾值(目前 >8)會影響「形狀」定義,未來補圖/貼圖級驗要留意。
