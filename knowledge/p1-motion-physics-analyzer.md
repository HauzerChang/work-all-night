# P / S6 — 動畫「物理可信度」分析器 + 評估器(v1)

- **來源**:使用者新增研究項目(2026-08-21)「spine 動畫中的物理世界」:①認知材質與其運動
  ②認知質量/面積/空氣阻力/慣性等物理屬性 ③讓產出動畫更具說服力、動態更自然。
- **結論**:把三個抽象目標落成**可量測的運動學簽名**,建 `tools/analyzer/motion_physics.py`
  從真實生產動畫抽取,並**雙控**驗證評估器可信:負對照(線性化去慣性)+ 正對照(已知相位延遲回收)。
  兩資產 `--selftest` 皆 `validated:True`。
- **信心**:中高(核心 ease/慣性指標經負對照鑑別、follow-through 相位法經正對照校正一個**符號 bug**;
  squash/soft-body 為描述量)。
- **階段**:第 2 階段延伸 / 新能力軌 **P(物理可信度)**。方法論依 RULES:確定性演算法 + 評估器,
  不用 ML 學「無唯一解的美術決定」。

## 標準指令

```
python3 tools/analyzer/motion_physics.py <asset.json>              # 完整物理簽名報告
python3 tools/analyzer/motion_physics.py <asset.json> --selftest   # 負+正對照 → validated 才 exit 0
python3 tools/analyzer/motion_physics.py <asset.json> --negctrl    # 只跑 ease 鑑別力
```

## 三目標 → 可量測簽名的對映

| 使用者目標 | 物理量 | 可量測簽名(本工具) |
|---|---|---|
| ②質量 / 慣性 | 加速需時 | **ease_in**(慢起步,bezier 起點速度 <1) |
| ②重量 / 阻尼 | 減速需時 | **ease_out**(慢收尾,bezier 終點速度 <1) |
| ③自然 / 說服力 | 非等速 | **inertia_index**=(ease_in+ease_out)/2;線性=機械感=0 |
| ①末梢跟隨(overlapping) | 慣性傳遞 | **follow_through**:父→子活動訊號互相關相位延遲(child 落後為正) |
| ②慣性 / 果凍(材質) | 阻尼彈簧 | **overshoot**:末梢越過終點再回彈的比例 |
| ①有質量的軟體 | 體積守恆 | **squash_stretch**:scale 的 sx·sy 偏離 1 的程度 |
| ①布料 / 窗簾(材質) | 行進波 | **soft_body**:deform 位移峰值隨時間移動量 |

## 對真實資產的量化發現(誠實)

| 簽名 | main_draw(reveal) | Award(bigwin) | 解讀 |
|---|---|---|---|
| inertia_index | **0.556** | **0.221** | 皆遠 > 線性 0 → 動作有明確加減速(慣性/重量) |
| ease 分布 | open 0.72 / comeout 0.05 | — | 慢件(窗簾拉開)重 ease、快件(彈出)近線性 |
| follow_through(child 落後比例) | 0.32 | **0.58** | Award 多關節腿鏈有明顯末梢跟隨;窗簾同步剛體較少 |
| overshoot 比例 | **0.75** | **0.82** | ⭐ **過衝/回穩是此風格最主力的物理裝置**(彈跳感 juice) |
| squash 體積守恆比例 | 0.03 | 0.03 | ⭐ **幾乎不用體積守恆 S&S**;scale timeline 是大幅「彈入」縮放,非擠壓保體積 |
| soft_body 行進波 | 窗簾 travel 11~12(idle2) | 無 deform | 窗簾=布料材質(deform 波);Award 靠骨+權重不靠 deform |

**風格結論(可追溯自資料)**:slot game 動畫的物理詞彙 = **ease(慣性)+ overshoot(回穩彈跳)為主**,
**體積守恆 squash&stretch 幾乎不用**,follow-through 視 rig 關節度而定(articulated 才明顯)。

## 評估器可信度(雙控,RULES:每能力必配評估器且需驗證)

- **負對照(ease)**:`linearize()` 去除所有 bone 曲線 → inertia_index 掉到 **0.0**;real(0.22~0.56)>> 0
  → `discriminative:True`。證明 ease 指標抓的是真實慣性而非恆定偏移。
- **正對照(lag)**:合成 child = parent 延遲 d 樣本(d∈{0,3,6,-4,9})→ 互相關**全數精確回收**。
  ⚠️ **本控抓到一個真 bug**:初版 `_xcorr_lag` **符號相反**(child 落後回報成領先),
  正對照 MISMATCH → 修正對齊式(b[i]≈a[i-d])→ 全 OK。**教訓:相位/方向類指標必配正對照**(同專案累犯的「評估器 miscalibration」家族)。

## 誠實界定 / 下一步(候選)

- 本 v1 是**分析/評估器**(讀真實動畫的物理簽名 + 自證可信),**尚未**做「注入物理」的生成端。
- ease/overshoot 指標穩健且可負對照;follow-through/squash/soft-body 為描述量(follow-through 已正對照,
  squash/soft-body 尚缺獨立正對照 → 標為描述性,勿當硬閘)。
- **下一 bounded chunk 候選**:
  1. **材質分類器**:用上述簽名把一段動畫/一個件判為 rigid / cloth / jelly(+信心),對 main_draw 窗簾(cloth)
     vs 剛體件做真值對照。
  2. **物理注入 v1(生成端)**:給一條「機械」關鍵影格,自動加 ease(依指定質量)+ overshoot(依阻尼)
     + 末梢 lag,用本評估器量「注入後 inertia_index/overshoot 上升且拓樸不壞」。可串 S1 分鏡→keyframe。
  3. **squash&stretch 體積守恆正對照** + 「有質量落地」樣板(擠壓保體積)。
