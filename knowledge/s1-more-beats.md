# S1 candidate 0g — 擴充 big-win 主秀 beat 庫:combo(多峰遞增)+ anticipate_hold(長蓄力)

> 續 candidate 0f(`s1-beat-templates.md`)。0f 交付 `hit`(反向預備→命中→阻尼回擺)與
> `reveal`(藏→蓄勢→炸開→回穩)。0g 補 STATE「下一個 bounded chunk」建議 (F)**更多主秀節拍**,
> 再加兩個 big-win 節拍,**各有互不相同、可量化的客觀結構簽章**,並用負對照證明鑑別力。

## 交付

- `tools/analyzer/beat_templates.py`(擴充):
  - **`gen_combo(role, side_sign, radial)`** — multi-hit combo(連擊)。三段 **遞增** impact,
    各含蓄力 dip + 部分回擺,尾段阻尼回穩。scale 峰嚴格遞增 `p1<p2<p3`(=role peak),峰間回落 <1
    (下一擊的蓄力)。role 加成:limb 三連甩(幅度遞增)、head 三連點、特效 每擊亮度閃 + 旋轉。時長 0.9s。
  - **`gen_anticipate_hold(role, side_sign, radial)`** — 蓄力充能。長時間 squash(0.85)並 **hold**
    (τ0.15–0.45)→ 單發大釋放 overshoot(peak)→ 阻尼回擺。role 加成:limb 反向拉滿 hold 後爆甩、
    特效 壓暗 hold 後瞬亮。時長 0.8s。
  - 常數 `IMPACT_PROM=1.10`(impact 峰門檻;loop 微呼吸 ≤1.03、hit settle 回彈 ~1.015,皆在門檻下)。
  - keyword 清單 `COMBO_KEYWORDS` / `CHARGE_KEYWORDS`。
- `tools/analyzer/gen_animations.py`(wire):`_DISPATCH["combo"|"charge"]` + `_CAT_KEYWORDS` 置前
  (exact/substring 命中優先於泛用 pulse)+ `DUR.update`(combo/charge 時長對 `spine_anim.duration` 一致)。
- `tools/analyzer/validate_more_beats.py`(新閘,6 AC)+ `knowledge/figures/s1_more_beats.png`。

## 兩個**互不相同**的結構簽章(本 chunk 的核心)

主秀 beat **無唯一正確運動**(先驗手感),故閘驗的是**定義該節拍的客觀簽章**,而非美感:

| 節拍 | 簽章(可量化) | 與單發 hit 的分離 |
|---|---|---|
| **combo** | **遞增 impact 峰數 ≥3**(≥1.10 的局部極大且嚴格遞增) | 單發 hit 只有 **1** 個 impact 峰 |
| **anticipate_hold** | **峰前長蓄力**:峰前持續 <0.97 的樣本佔全長 **≥0.35** | hit 蓄力僅短暫 dip(佔比 <0.35) |

兩者仍共用 0f 的通用簽章:**anticipation**(峰前 scale <1)+ **settle**(`(scale-1)` 變號 ≥3,阻尼回擺)。
且兩簽章**互斥**:combo 非長蓄力(`charge_sig(combo)=False`)、charge 非多峰(`combo_sig(charge)=False`)。

## 驗收結果(`validate_more_beats.py` 6 AC 全 PASS,exit 0)

| AC | 判準 | 結果 |
|---|---|---|
| M1 well-formed | finite / 時間嚴格遞增 / JSON round-trip | ✅ |
| M2 可串接介面 | combo/charge 首尾皆 setup identity(可插 Loop 間) | ✅ |
| M3 真峰 | scale overshoot ≥1.12(兩者實測峰 1.347) | ✅ |
| M4 各自簽章 | combo 每 bone **3** 遞增 impact 峰;charge 蓄力佔比 **0.456–0.473** ≥0.35 | ✅ |
| M5 共用節拍品質 | 兩者皆有 anticipation + settle | ✅ |
| M6 負對照(**9 條**) | 見下 | ✅ |

**M6 負對照(9 條全過)**:①真 combo 具 combo 簽章、②真 charge 具 charge 簽章(正對照);
③單發 hit **非** combo(僅 1 峰)、④單發 hit **非** charge(蓄力佔比小);⑤對稱脈衝 gen_pulse **非** combo、
⑥對稱脈衝 **非** charge;⑦**等峰 combo**(把三峰壓成同值)**非遞增** → FAIL combo 簽章(證「遞增」是必要條件,
非只看峰數);⑧combo 簽章 ≠ charge 簽章、⑨charge 簽章 ≠ combo 簽章(互斥)。

## 關鍵發現

- **impact 峰門檻 1.10 是乾淨切點**:loop 微呼吸最大 1.03、hit 的 settle 回彈 overshoot 僅 ~1.015 —— 都在門檻下,
  故「≥1.10 的局部極大」只數到真 impact,單發 hit 穩定得 1、combo 穩定得 3,不受取樣密度/回彈抖動干擾。
- **combo 的鑑別子是「遞增」不只是「多峰」**:等峰 combo(3 個相同峰)被負對照 ⑦ 判 FAIL —— 遞增(escalation)
  才是「連段升溫」的本質,單看峰數會把「三個一樣大的敲擊」誤判為 combo。
- **anticipate_hold 的簽章用「時間佔比」而非「深度」**:蓄力**深度**(0.85)hit 也有;差別在**持續時間**——
  charge 把低檔 hold 一段(佔比 ~0.47),hit 只是快速掠過(佔比 <0.2)。時間佔比對峰值大小/取樣解耦,最穩。
- 兩節拍沿用 0f 的 identity 介面契約(首尾 identity)→ 可與 In/Loop/Out 及彼此無縫串接。

## 誠實界定 / 邊界

- 主秀 beat 的**緩動幅度/手感**(峰值、蓄力深淺、幾段連擊)屬美術主觀(A 類),留使用者;閘只保證**結構簽章**成立。
- combo/charge 目前由 fixture storyboard(真實 robot 5 拆件 role 端到端)驅動;若要 `build_spine --animate` 直出,
  需把 combo/charge 併入 `genre_priors`(如 (E) 對 hit/reveal 所做),並同步 `validate_priors` 真值覆蓋(勿動已驗先驗)。
- `spine-anim-forge` 區塊**仍 HOLD**(運動基元為手感先驗、單一真值資產,防固化;達 L3 前不打包)。新增 cap
  `beat_library_expansion` L2。

## 回歸(未破壞既有)

- 0f `validate_beat_templates.py` 6AC ✅;0d/0e `validate_anim.py`(robot slot_bigwin,含 `--selftest` 負對照)✅;
- (E) `validate_priors.py` overall_pass ✅(combo/charge keyword 置前不影響 In/Loop/Out 分類);
- keyword dispatch 實測:`BigWin_Combo`→combo、`Charge_Up`→charge,端到端 build_animations 產出正確時長(0.9 / 0.8s)。
