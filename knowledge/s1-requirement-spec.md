# S1 塊3 — Asset & Rig Requirement Spec(運動型態量化)

- **結論**:S1 分析半段收官 —— 由每候選件的 per-frame affine 運動模型抽出**運動型態**(旋轉/平移、
  **pivot**、**振幅**、平移量)組成 Requirement Spec。合成 GT **注入已知運動**(手臂±16°/頭±9°+已知 pivot),
  反推後**振幅誤差 <1°、pivot 誤差 0~1px** → 精確真值閘 PASS。真實影片 `robot_dance` 產出需求規格
  (`assets/robot_dance_spec.json`):兩臂運動最大(右 11°/9px、左 6°/8px)、頭小、軀幹最穩。
- **信心**:高(合成注入真值反推誤差 <1°/<2px);真實影片規格為候選(誠實)。
- **階段**:S1(塊3,分析半段完成)。

## 運動參數抽取(每件)

per-frame affine `flow=[a·x+b·y+c, d·x+e·y+f]`:
- **旋轉率** dθ_t=(d−b)/2(反對稱部分)→ 積分 θ_t → **振幅=(θmax−θmin)/2 度**。
- **pivot** = affine 不動點 `M·p=−[c,f]`,以 |dθ| 加權平均(旋轉大幀較可信)。
- **平移振幅** = 件質心位移的峰峰/2;**motion_type**:旋轉邊緣位移(dθ·半徑) vs 平移量誰大。

## 評估器(比塊2更嚴:驗「參數量化正確」)

塊2 只驗「分對區塊(IoU)」;本塊驗「**反推的運動參數 vs 注入真值**」。合成注入 → 反推:

| 件 | 振幅 注入→反推(誤差) | pivot 誤差 |
|---|---|---|
| 右手 | 16° → 15.79°(0.21) | 0.0px |
| 頭 | 9° → 8.96°(0.04) | 0.0px |
| 左手 | 16° → …(<3.5) | <12px |

閘門檻:分對(IoU≥0.4)且有明顯運動(注入≥8°)的件,振幅誤差<3.5°、pivot 誤差<12px → **PASS**。

## 真實影片 Requirement Spec(robot_dance)

5 候選件(見 `assets/robot_dance_spec.json` + 圖 `knowledge/figures/`):右臂 rot~11°/trans~9px、
左臂 ~6°/8px(動作最大)、頭頂 ~3°/2px、軀幹底 ~1°/2px(最穩)。與塊1 熱圖(手臂主動、軀幹穩)一致。
誠實限制:真實舞動非純剛體,motion_type 多判為 translation(含整體 sway);k 需人給。

## 北極星 pipeline 現況

- **合成半段(資產/rig)**:PSD → mesh(S3)→ skeleton(S4)→ rig 階層+pivot(S5)→ weighted(S5)。
- **分析半段(影片)**:影片 → 運動場(塊1)→ 分群成件(塊2)→ **Requirement Spec(塊3)**。✅
- **待整合(第3階段)**:用 spec 的每件運動(pivot+振幅+相位)**驅動 rig 骨骼旋轉** → 生成動畫 timeline
  → 疊影片比對相似度 → 逼近目標。這是把兩半段接起來的最後一哩。

## 可重現
```
python3 tools/s1/requirement_spec.py    # 合成參數反推 PASS + 產 assets/robot_dance_spec.json
```
