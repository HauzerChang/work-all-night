# S3 — weighted mesh 骨骼驅動變形品質閘(補上唯一未驗維度)

- **結論**:新增 `tools/mesh_gen/weighted_deform.py`,對 Award 機器人 3 個 **weighted mesh 件**
  (光暈/左手/身體)在**真實骨骼動畫 pose**(`Award_Legend_In` + `Award_Legend_Loop`)下量化變形品質,
  三項自我驗證 AC 全 PASS,補上 `s3-robot-mesh-vs-award.md` 標記的**唯一未驗維度**:
  「靜態 IoU PASS ≠ bone-driven 變形平滑/乾淨」。這支閘從此可當「生成 weighted mesh」的通過門檻。
- **信心**:高。對真實生產 spine 的美術 weighted mesh + 真實動畫逐幀量化;skinning 數學經 setup 自一致錨定,
  且有嚴格負對照鑑別力。
- **階段**:第 2 階段 / S3。**里程碑:S3 首次驗 weighted mesh 骨骼變形**(先前只驗 unweighted deform 與靜態 IoU)。
- **工具**:`tools/mesh_gen/weighted_deform.py`(引擎 + 閘,可重現)。圖:`knowledge/figures/weighted_deform_artist.png`。

## 標準指令

```
python3 tools/mesh_gen/weighted_deform.py     # 3 件 3 AC 全 PASS → exit 0
```

## 引擎(可重用 API)

Spine 3.8 weighted skinning 的 Python 重現(對照 CLAUDE.md 雷點 #4/#6):

```
worldVertex = Σ_bone  weight_b · ( boneWorldMat_b · bind_b )
boneWorldMat = parentWorldMat · localMat(x, y, rotation, scaleX, scaleY)
```

- `world_transforms(sk, name2idx, anim, t)` → {boneIdx: 3×3 world mat},遞迴 parent·local;
  動畫 pose 由 bone 的 `rotate`/`translate`/`scale` timeline **相對 setup 的 offset** 疊加(線性內插取樣)。
- `compute_world_vertices(parsed, Wmap)` → weighted skinning 後的世界頂點。
- `parse_weighted(vertices)` → 每頂點 `[(boneIdx,bindX,bindY,weight), …]`(bind 為相對該骨 setup 座標)。
- `slot_visible_at(sk, anim, slot, t)` → 可見性 gating(見下)。

## 三項驗收(全 PASS)

| 件 | AC1 setup 自一致(norm_err<0.10) | AC2 硬不變量(可見幀 0 翻面/0 退化) | AC2 si_baseline | AC3 負對照缺陷 |
|---|---|---|---|---|
| 光暈 | 0.0156 ✓ | flips 0 / degen 0 ✓ | **4**(軟邊容忍) | si 61, flip 2 ✓ |
| 左手 | 0.0025 ✓ | flips 0 / degen 0 ✓ | 0 | si 1281, flip 1 ✓ |
| 身體 | 0.0703 ✓ | flips 0 / degen 0 ✓ | 0 | si 3072 ✓ |

- **AC1(reader 正確性錨)**:setup pose 下 weighted skinning 重建的頂點布局 ≈ `uvs`(region-local,
  world y-up → image y-down)。三件 norm_err 0.003~0.070 → **證明 bone 世界變換 + 骨綁權重數學正確**。
- **AC2(藝術家真值可被認證乾淨)**:可見幀 **0 翻面 + 0 退化**(見「硬 vs 軟不變量」)。
- **AC3(鑑別力/負對照)**:確定性打亂每頂點骨綁(骨綁循環位移 n/2,權重不變)→ 同 pose 下
  自交/翻面**遠超基準**(61~3072)→ 閘能區分好壞。

## 三個關鍵發現(本 session)

### 1. ⭐ 可見性 gating 是 weighted 變形閘的必要條件(CLAUDE.md 雷點 #2/#3 的量化證據)
未做 gating 時,光暈在 `Legend_In` 出現 **71 自交 / 7 翻面**、area_ratio 衝到 **1.98**。追查發現:
光暈 slot 有 **color timeline**:`ffffff00`(alpha=0,全透明)**stepped 持到 t=0.5**,到 t=0.6333 才
線性淡入到 `ffffffff`(全不透明)。而 LEG5/LEG6 的劇烈位移(LEG6 translate 到 x=-190, y=+378)
**全發生在 t≤0.5,即光暈完全不可見時**;等它可見(t≥0.63)骨骼已回穩。
→ **不可見幀的頂點怎麼亂都無視覺後果**。閘加 `slot_visible_at`(讀 color alpha + attachment timeline,
alpha 門檻 4/255,stepped/linear 內插):光暈 71→4 自交、7→0 翻面。這是「靜態≠變形」以外,
weighted mesh 特有、且**沒它會誤殺真實資產**的閘設計要點。

### 2. ⭐ 軟邊羽化件的自交要用「藝術家基準」,不是硬 0(校準教訓再現)
gating 後光暈**剩 4 自交,且只在 t=0.633 這一個 exact keyframe**(area 壓到 0.877;非線性內插假影
—— 已用 keyframe-only 對照確認,其餘幀 si=0)。這是**真實出貨資產在單一幀的微小自交**:
78 頂點密邊界的柔性加色發光,4 條邊界邊交叉肉眼無感,藝術家容忍之。
→ 若硬性要求「永遠 0 自交」會**否決藝術家自己的 mesh**(如同 deform_eval 早期合成壓力 miscalibration
的教訓)。故閘拆成:
  - **硬不變量(所有件、恆 0)**:`triangle_flips`(貼圖鏡射撕裂)、`degenerate`(三角塌陷)。
  - **軟基準(逐件記錄)**:`self_intersections` = 該件藝術家 worst(光暈 4、左右手/身體 0),
    作為未來「生成 weighted mesh」的通過門檻(gen_worst ≤ artist_baseline,沿用 compare_robot_mesh
    的 IoU 基準哲學)。

### 3. 這 3 件靠**純骨骼變換 + 權重**變形(無 deform timeline)
確認 `s3-robot-mesh-vs-award.md` 的假設:光暈綁 LEG3-6(≤3 骨/頂點)、左手綁 LEG5/9、
身體綁 LEG3/7/8;由 `Legend_In`/`Loop` 的 bone rotate/translate/scale 驅動。故用 `deform_eval`
(逐頂點 offset)驗它們不適用,必須用本檔的 skinning 引擎。

## 誠實界定 / 限制

- **內插為線性**:bone timeline 的 bezier 曲線以線性內插近似。已驗證問題幀(4 自交)出現在
  **exact keyframe**(bezier 必經點,線性=bezier),故結論不受內插精度影響;但若未來要量測
  「內插途中的最壞瞬時幾何」需補 Spine 緊湊 bezier 求值。
- **仍未做**:本閘驗的是「**藝術家 weighted mesh** 在真實 pose 下乾淨」+ 建立通過門檻。
  **下一步**:S3 生成器產出 weighted mesh(內部取樣密度控制 + **BBW 骨綁權重**),用本閘對照
  「gen worst ≤ artist baseline」,才真正閉合「生成 weighted mesh 變形品質」這條線。真值(權重/骨架)
  已在 `Award.json`。
- 未驗**主觀手感**(緩動/重量感)—— 依 RULES 留給使用者。
