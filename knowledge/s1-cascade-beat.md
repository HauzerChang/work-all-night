# S1 candidate 0h — cascade(跨件錯開波):第一個「跨件時序」主秀節拍

> 里程碑 2026-09-04(session 002)。續 0f(hit/reveal)、0g(combo/anticipate_hold)的主秀 beat 庫,
> 補上一個**維度不同**的節拍:前面全是**單件內**的時間簽章,cascade 是**跨件**的時間簽章。

## 為什麼 cascade 是新維度(不是「再多一個脈衝」)

0f/0g 的四個節拍(hit/reveal/combo/anticipate_hold)都是**單件內**的時序簽章:同一個 beat 套到每一件,
每件的時間曲線都一樣(peak 都落在同一時刻)。它們的鑑別子(反向預備、阻尼回擺、遞增多峰、長蓄力佔比)
全都能在**單一件的 scale 曲線**裡量到。

cascade 不同:它是「一件接一件依序亮起」的**波**。每件依其**件序相位** phase∈[0,1] 錯開觸發,
所以簽章**不在單件曲線裡**,而在「**各件峰值時刻的排序與散佈**」——這是件與件**之間**的關係。

| 維度 | 節拍 | 簽章所在 | 鑑別子 |
|---|---|---|---|
| 單件內時序(0f/0g) | hit / reveal / combo / anticipate_hold | 單一件的 scale 曲線 | 反向預備、阻尼回擺、遞增多峰、蓄力時間佔比 |
| **跨件時序(0h)** | **cascade** | **各件峰時刻的序列** | **峰時刻依件序嚴格遞增 + 散佈 ≥0.30** |

## 交付物

- **`tools/analyzer/beat_templates.py`** `gen_cascade(role, side_sign, radial, phase=0.0)`:
  單件 pop 波,峰中心 `c = LEAD(0.16) + phase*SPAN(0.54)`(τ∈[0.16, 0.70])。scale 包絡:
  `1.0 → hold 1.0(輪到前)→ 0.94(蓄力)→ peak(pop,全域峰=c)→ 0.97→1.005(阻尼回擺)→ 1.0`。
  首尾皆 identity(pop 波可插 Loop 間);特效件加亮度閃、末梢件加甩,皆對齊 c。
  常數 `CASCADE_LEAD/SPAN`、`CASCADE_KEYWORDS`、`DUR["cascade"]=1.2`。
- **`tools/analyzer/gen_animations.py`**:註冊 `_DISPATCH["cascade"]` + `_CAT_KEYWORDS` 置前;
  新增 `_PHASE_AWARE={"cascade"}`;`build_animations` 先過濾**有效件**(有 bone 的)算總數,
  再對 phase-aware 類別帶入 `phase = pi/(nvalid-1)`(第一件 0、末件 1)。**這是本次唯一的架構變更**:
  讓生成器把「件序」餵進單件產生器。其餘類別簽章與呼叫方式**完全不變**(非 phase-aware 不吃 phase)。
- **`tools/analyzer/validate_cascade.py`**(新,6 AC + 7 條負對照):端到端經 `build_animations`
  (才會帶入 phase)量測。
- `check_readiness.py`:`spine-anim-forge` 新增 cap `cross_part_cascade`(L2)。

## 驗收結果(6 AC + 7 條負對照全 PASS,exit 0)

對真實 robot 5 拆件(件序:光暈/右手/頭/身體/左手)端到端:

| AC | 判準 | 結果 |
|---|---|---|
| C1 well-formed | finite / 時間嚴格遞增 / JSON round-trip | ✅ |
| C2 chainable IF | 每件 bone 首尾 identity、特效 slot alpha 首尾=1 | ✅ |
| C3 impact peak | 每件 scale overshoot ≥1.12(實測 1.176–1.336) | ✅ |
| **C4 跨件簽章** | 峰時刻 **[0.158, 0.296, 0.429, 0.567, 0.700]** 依件序嚴格遞增、散佈 **0.542** ≥0.30 | ✅ |
| C5 shared beat | 每件仍具 anticipation(峰前 <1)+ settle((scale-1) 變號 ≥3) | ✅ |
| C6 負對照(7) | 見下 | ✅ |

**C6 負對照(證跨件維度的鑑別力)**:
- `combo`(同 beat 套每件、**時序相同**)各件峰時刻 spread≈0 → FAIL cascade(跨件維度的直接負對照);
- **打亂件序** → 峰時刻非遞增 → FAIL;**反序** → 遞減 → FAIL;
- **跨維度正交**:cascade 單件是**單峰**,`has_combo_signature`(≥3 遞增峰)判為 False → 證 cascade 與 0g **不同維度**;
- **單件 cascade** 無 spread → 非波(cascade 需 ≥2 件);
- 正對照:真 cascade 簽章成立。

## 關鍵發現

- **「模板就緒 ≠ 生成器接上」在此又一次體現,但形式不同**:0f/0g 的模板只要 `_DISPATCH` 註冊就會被套;
  cascade 卻**需要生成器把件序(phase)餵進來**才有意義。跨件簽章逼出了 `build_animations` 的第一個
  per-part 參數 threading —— 前四個節拍都不需要(它們對件無差別)。
- **cascade 簽章要端到端量,不能只測 `gen_cascade`**:phase 是 build_animations 配的,直接呼叫
  `gen_cascade` 只能驗單件形狀,驗不到「波」。故 validator 一律經 `build_animations`(順帶證 threading 有接上)。
- **pop 波 vs reveal 波**:選 pop 波(首尾 identity)當預設 —— 保留可串接介面(能插 Loop 間),
  且每件恰一個全域峰 → argmax 峰時刻乾淨、跨件排序穩健。reveal 波(每件 start collapsed 依序現身)是
  自然變體,但首非 identity 且多件 collapse 疊加會擾動 argmax,列為未來擴充。
- **散佈門檻 0.30 是乾淨切點**:5 件真波 spread 0.54;combo/hit(同時序)spread≈0。門檻取兩者中間,
  對件數/取樣密度不敏感。

## 誠實限制 / 下一步

- 主秀 beat **無唯一正解**(先驗手感),閘驗**客觀結構簽章非美感**;波的緩急、件序美感留使用者(A 類)。
- cascade 目前由 fixture storyboard 驅動;若要 `build_spine --animate` 直出,需併入 `genre_priors`
  (如 (E) 對 hit/reveal 所做),同步 `validate_priors` 真值覆蓋 —— 是「(H) combo/charge 接先驗庫」的同類後續。
- 件序目前=storyboard 件序;可再進一步用**空間位置**(如由左到右、由中心外擴)決定波的方向,屬美術方向(A 類)。
- `spine-anim-forge` 仍 **HOLD**(運動基元先驗、單一真值資產,防固化;達 L3 前不打包)。

## 產出檔案

- 新增:`tools/analyzer/validate_cascade.py`、`knowledge/s1-cascade-beat.md`、`knowledge/figures/s1_cascade.png`。
- 更新:`tools/analyzer/beat_templates.py`(gen_cascade + CASCADE_KEYWORDS + DUR)、
  `tools/analyzer/gen_animations.py`(cascade 註冊 + `_PHASE_AWARE` + build_animations phase threading)、
  `tools/check_readiness.py`(cap `cross_part_cascade`)、`STATE.md`、`knowledge/README.md`。
