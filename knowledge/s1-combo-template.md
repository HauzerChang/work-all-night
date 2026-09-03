# S1 candidate 0g — big-win「連擊 / rollup」主秀 beat 模板(multi-hit combo)

> 里程碑 2026-09-03。續 0f(hit/reveal,anticipation+settle):補上「同一拍內**多次遞減重音**」
> 這個 In/Loop/Out 與單一 hit 都表達不了的 big-win 節拍(連環中獎 / 金幣 rollup / 連莊)。
> 檔:`tools/analyzer/beat_templates.py::gen_combo`、`tools/analyzer/validate_combo_template.py`、
> 圖 `knowledge/figures/s1_combo_template.png`。

## 為什麼需要它(缺口)

- 0d 的 `gen_pulse` 只是**單一對稱三角脈衝**;0f 的 `gen_hit` 是**單次**蓄力→命中→阻尼回擺。
- 但 big-win 有一類節拍是**一拍內連續多次、強度遞減的重音**(rollup 數字滾動、連環爆分)。
  單擊/脈衝的結構(1 個正峰)無法表達;硬串 3 個 hit 又會各自 0.5s 太散、且首尾多次歸零不像「連貫一擊組」。
- 缺口確認:實查 `slot_bigwin` 真值 `Award` 只有 `<Tier>_In/Loop/Out`(climax = 進場本身,無獨立 hit),
  而**沒有任何模板可產「遞減連擊」**。故本 chunk 補模板(不動已驗 `slot_bigwin`/`slot_reveal` 先驗)。

## 模板設計(`gen_combo`,純 CPU 確定性)

- N=`_COMBO_N`(預設 3)次擊;每擊 `(peak-1)` 乘 `_COMBO_DECAY^k`(預設 0.62)→ **峰值遞減**
  (follow-through / 能量耗散)。`peak` 沿用 0f 的 `_PEAK`(role-aware:特效 1.35 > 身體 1.28 > 末梢/頭 1.18)。
- 每擊 scale 包絡:`1.0 →(蓄力 dip <1,anticipation)→ peak_k →(回落)~1.0`;擊間回到 identity 附近 → **獨立可分辨的擊**。
- role-aware:`limb` 每擊甩鞭(rotate,遞減幅度,首尾 0);`特效` 每擊亮度閃(alpha 先暗蓄→亮,遞減);body/head 只 scale。
- **首尾皆 setup identity**(scale=1/rotate=0/alpha=1)→ 可插在 Loop 循環間、或與 In/Loop/Out 無縫串接。
- 時長 `DUR["combo"]`=1.2s(容納 3 擊)。

## 結構簽章 = 客觀真值(非美感)

主秀節拍無唯一正確運動(先驗手感),故閘驗**定義「連擊」的客觀結構簽章**,並用負對照證明鑑別力:

1. **≥2 個獨立正峰**(擊間 scale 回落 identity 附近而分段)—— 單擊/脈衝僅 1 峰。
2. **峰值嚴格遞減**(peak_k 遞減)—— **關鍵鑑別子**:天真「等幅重複脈衝」有多峰但不遞減 → 被判非 combo。

峰偵測 `peak_segments`:`(scale-1)` 連續 > `PROM`(0.03)的每一區段取最大值為一峰;區段間須回落 ≤ PROM
→ 保證峰**獨立**(長平台只算 1 峰)。這使「等幅重複」也能被抓到多峰,再由「遞減」條件過濾。

## 自我驗收(`validate_combo_template.py`,C1–C6 全 PASS)

端到端經 `gen_animations.build_animations`(beat_category('combo')→_DISPATCH['combo']),對**真實 robot 5 拆件+role**:

| AC | 內容 | 結果 |
|---|---|---|
| C1 well-formed | finite / 時間嚴格遞增 / JSON round-trip | PASS |
| C2 chainable IF | combo 首尾皆 setup identity(可插 Loop 間/串接) | PASS |
| C3 multi-peak | 每 bone scale ≥2 獨立正峰(5 件皆 **3 峰**) | PASS |
| C4 decaying peaks | 峰值嚴格遞減(如身體 [1.28,1.174,1.108]) | PASS |
| C5 separated+antic | 擊間 troughs 回落 identity 附近(≤+0.05)+ 每擊前 anticipation 蓄力(<1) | PASS |
| **C6 negative control** | 單擊 hit / 對稱脈衝 → FAIL C3(1 峰);**等幅重複** / **遞增** → FAIL C4;真 combo 具簽章 | **PASS(5/5)** |

**C6 是評估器可信度核心**:證明閘能分辨連擊 vs 單擊 vs 等幅重複 vs 遞增。
「等幅重複脈衝」通過 C3(多峰)卻被 C4(遞減)攔下 —— 正是「遞減」這一簽章的鑑別價值所在。

## 端到端接線(不動已驗先驗)

- `beat_templates.py`:新增 `gen_combo` + `COMBO_KEYWORDS`(combo/rollup/cascade/chain/streak/連擊/連環/…)+ `DUR["combo"]`。
- `gen_animations.py`:註冊 `_DISPATCH["combo"]` + `_CAT_KEYWORDS`(主秀類別置前,exact/substring 命中優先於泛用 pulse)。
- `genre_priors.py`:只在 **UNVALIDATED 的 `slot_symbol`** 加一個 `combo` beat(連環中獎 rollup)
  → `build_spine --animate --genre slot_symbol` 端到端輸出 `land/idle/win/**combo**`。
  **未動 `slot_bigwin`/`slot_reveal`**(validated_against=Award/main_draw);`validate_priors` 仍 overall PASS
  (unvalidated genre 略過;且 `prior_beats_unused` 本就非 fail 條件)。

## 回歸(全 PASS)

0f `validate_beat_templates`(B1–B6)、0d `validate_anim --selftest`(AC1–4+負對照)、
0e `validate_deform_gen`(OVERALL_PASS)、`validate_priors`(overall_pass)。

## 誠實界定 / 邊界

- 連擊次數 N、衰減率、峰值、緩動**幅度**屬手感(A 類,留使用者微調);閘只驗**結構簽章**(多峰+遞減+分離+首尾介面)。
- 這是 `spine-anim-forge` 區塊的第 4 個運動基元(0d keyframe / 0e deform / 0f hit·reveal / **0g combo**);
  區塊**仍 HOLD**(運動基元皆先驗、單一真值資產 robot,防固化)。cap:`storyboard_combo_beat` L2。
- 未做(候選續):cascade(**跨件錯開起始相位**的波浪擴散,屬 build_animations 層的 per-part 相位偏移,非單模板);
  anticipate-hold(長蓄力單放)。
