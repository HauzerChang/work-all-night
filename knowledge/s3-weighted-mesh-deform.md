# S3 — weighted-mesh 變形評估器(LBS)+ Award 藝術家基準

- **結論**:補上 `compare_robot_mesh.py` 唯一未驗維度(weighted mesh 骨骼變形平滑度)。新工具
  `tools/mesh_gen/weighted_deform.py` 用 **linear-blend skinning** 把 weighted mesh 綁到 Award
  真實骨骼 pose 序列(從 12 支動畫的 bone timeline 取樣)上量拓樸品質。評估器核心數學經
  **per-bone bind 一致性 < 0.02px** 獨立驗證;**負對照(平滑 vs 硬綁)證明有鑑別權重品質的能力**。
- **信心**:高(核心 world-transform 數學對 3 件真實 weighted mesh 全部多骨頂點自洽 < 0.02px;
  結構件基準與負對照結果一致且方向明確)。
- **階段**:第 2 階段 / S3(補齊 `s3-robot-mesh-vs-award.md` 標註的「變形平滑度未驗」限制)。
- **工具**:`tools/mesh_gen/weighted_deform.py`(`--negctrl` 跑負對照)。

## 標準指令

```
python3 tools/mesh_gen/weighted_deform.py            # 藝術家基準;overall_pass → exit 0
python3 tools/mesh_gen/weighted_deform.py --negctrl  # 負對照;discriminates → exit 0
```

## 方法(對照 CLAUDE.md 雷點 #4/#6)

1. **骨架世界變換(Spine 3.8 normal mode)**:每骨 local matrix
   `la=cos(rot+shearX)·sx, lb=cos(rot+90+shearY)·sy, lc=sin(rot+shearX)·sx, ld=sin(rot+90+shearY)·sy`,
   與 parent 世界矩陣複合。Award 全 77 骨皆 normal mode(已確認);非 normal 會 raise。
2. **weighted mesh skinning**:每頂點 `[骨數,(boneIdx,bindX,bindY,weight)×N]` →
   `worldPos = Σ_b weight_b · M_b(bindX_b, bindY_b)`。
3. **真實動畫套用**:讀 bone timeline(rotate/translate/scale),線性取樣 keyframe 時間聯集 + 中點
   (curve 以線性近似;keyframe 時間點為**精確值**,拓樸極值都落在 keyframe 上 → 對驗證保守足夠),
   重算世界變換 → 變形後世界頂點 → 幾何閘(自交/翻面/退化,重用 `deform_eval`)。

## 評估器可信度(內建 gate)

- **per-bone bind 一致性**:多骨頂點的每根骨各自把自己的 bind 座標映到 setup 世界,應收斂到同一點。
  實測 3 件最大偏差 **光暈 0.019 / 左手 0.007 / 身體 0.008 px**(匯出 JSON 浮點捨入級)。
  這獨立於權重、獨立驗證了 world-transform 數學 + weighted 解析器正確。
- **setup 重建**:LBS 在 setup pose 的世界頂點拓樸 clean(3 件皆是)。

## Award 藝術家基準(真實生產 weighted mesh 在自家動畫下的拓樸)

| 件 | kind | nv | hull | bind一致性px | In | Loop | Out | 判定 |
|---|---|---|---|---|---|---|---|---|
| 光暈 | **effect**(hull==nv) | 78 | 78 | 0.019 | ⚠️ si≤71 flips≤7 | clean | clean | 記錄(非閘) |
| 左手 | structural | 80 | 42 | 0.007 | clean | clean | clean | **PASS** |
| 身體 | structural | 98 | 40 | 0.008 | clean | clean | clean | **PASS** |

## ⭐ 關鍵發現:`si=0` 不是 weighted mesh 的通用有效性判準

- **光暈(effect 件)在自家 `Award_Legend_In` 就自交**:t=0 已 si=71、area_ratio 1.16;
  一路到 t≈0.5 才 clean。**這是真實出貨美術的性質,不是評估器 bug**——鐵證:
  (a) 同骨系、同動畫下,身體/左手(structural)全程 0 自交;(b) bind 一致性 <0.02px 驗證數學;
  (c) 自交發生在**精確 keyframe 時間**(值無內插)。
- **成因**:光暈由 `4_LEG3/4/5/6` 驅動,`4_LEG6` 在 In 起手 **scale 1.667×**,而兄弟骨 `4_LEG5`
  同時 0.86× → 大幅非均勻縮放把軟邊 blob 折疊自重疊。光暈是**純邊界多邊形(hull==nv,0 內部點)**
  的軟邊羽化 blob(前一 session 的 `boundary-dense-v1` 正是為它加的),自重疊在視覺上遠不如
  不透明件敏感。
- **推論(評估器設計)**:weighted mesh 的變形品質閘應**分類**:
  - **structural 件(有內部頂點,hull < nv)**:`si=0` 是有效的硬閘(不透明結構的變形基準)。
  - **effect 件(hull == nv 純邊界 blob)**:自交是美術常態 → 只記錄為基準,不當 pass/fail;
    要比的是「不比藝術家基準更糟」(沿用 `compare_robot_mesh` 的 artist-baseline margin 哲學)。
  → `overall_pass = 評估器對每件都可信 AND structural 件在真實動畫下 clean`(目前 True)。

## 負對照:LBS 評估器能鑑別權重品質(下一步生成+BBW 的閘)

把身體的平滑藝術家權重換成 **naive 硬綁**(每頂點只綁最近骨、weight=1,差生成器的典型失敗),
施合成的極端相對骨旋轉(`4_LEG7` +deg):

| 相對旋轉 | 平滑(藝術家) si/flips | 硬綁 si/flips |
|---|---|---|
| 30° | **0 / 0** | 7 / 1 |
| 60° | **0 / 0** | 38 / 6 |
| 90° | 14 / 2 | 107 / 8 |

平滑權重耐到 ~60° 仍全 clean,硬綁 30° 就開裂;光暈真實 In 下平滑 si≤71、硬綁 si≤174(2.4×)。
→ **平滑(BBW 式)權重顯著較耐變形,評估器能量化這差距**。這就是下一步「我方生成 weighted mesh +
內部取樣密度 + BBW 權重」對照藝術家基準所需的閘。

## 誠實限制 / 下一步

- 本閘量的是**拓樸品質**(自交/翻面/退化/面積比),不是「與藝術家逐頂點位置相同」——weighted mesh
  無唯一解,對照哲學是「不比藝術家基準更糟」。
- curve 用線性近似(keyframe 精確);若日後要更嚴格的中間幀,可接緊湊 bezier 求值。
- **下一個 bounded chunk**:S3 生成 weighted mesh —— 內部取樣密度控制(補足 boundary-dense 幾乎無內部點)
  + BBW/heat-diffusion 權重,對身體/左手用本工具跑同一組真實/合成 pose,要求
  `structural clean 且 worst ≤ 藝術家基準 + margin`。真值(權重+骨架)已在 `Award.json`,純 CPU 可自驅。
