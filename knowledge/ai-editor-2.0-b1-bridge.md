# spine-ai-editor 2.0 — Phase B1 橋接閘(repo 生成 → v1.3.0 validator_v1)

- **結論**:本 repo 的確定性生成引擎(`gen_animations`)產出的動畫,**能無痛通過**使用者既有
  `spine-ai-editor v1.3.0` 的 `validator_v1`(= runtime 可載入 **且** editor 可匯入 **且** loop 閉合
  **且** stiffness 可量)。兩道硬性併接護欄 **G1(末鍵 curve 必拔)+ G2(雙真值驗收)已機械化、可回歸**。
- **依據**:`tools/analyzer/validate_v2_bridge.py` 5 AC 全 PASS(exit 0);新 cap `v2_bridge_validator_v1`
  併入新區塊 `spine-ai-editor-2.0`(check_readiness)。
- **信心**:高(真的把生成輸出跑過 v1.3.0 的 `validator_v1`,含負對照證閘有牙)。
- **相關階段**:專案第 3 階段(整合成可交付 pipeline/skill);MERGE_PLAN_2.0 Phase B 的第一個有界 chunk。

## 關鍵事實(本閘釘住)

**repo 生成天生 G1-safe**:`gen_animations._bez` 只對 `frames[:-1]` 下緊湊 bezier
(`curve=EASE, c2=0, c3=EASE, c4=1`),**末鍵永不帶 curve**;且 `EASE=0.25 ∈ [0,1]`
→ validator_v0 的 bezier 範圍檢查不報、validator_v1 的末鍵 curve editor 檢查不觸發。
換言之,repo 既有生成器輸出**本就符合**地雷 #12(末鍵 curve → Spine editor 匯入 AIOOBE crash)
的規避條件 —— 這是 2.0 併接「免費」拿到的相容性,本閘以正對照證實、以負對照證閘非恆真。

## 做了什麼

- 新閘 `tools/analyzer/validate_v2_bridge.py`:
  - **主體** = 最單純的 cascade big-win beat(pop 波)。fixture 用**合成 5 件骨架**
    (head/torso/arm_l/arm_r/glow,self-contained,**不依賴 PSD**);cascade 跨件簽章的**真實性**
    已由 `validate_cascade.py` 覆蓋,本閘只驗「生成 → v1.3.0 閘」的**橋接**。
  - `_build_doc`:把生成的 beat 包成**完整 Spine 3.8 skeleton JSON**。slots/skins 由骨架件
    **自動導出**(每個非 root 骨 `b_X` → slot `X` 綁 `b_X` + default skin 一張 region `X`)——
    fx 件(`特效` role)的 slot `color`/alpha timeline 才有合法 slot 可引用(踩過:忘了宣告 slot `glow`
    → validator_v0 報 `unknown slot 'glow'`)。
  - `wrap_skeleton_json`:`_build_doc` + **G1**(`strip_last_frame_curves`,模擬 2.0 產線契約;
    此 beat 本就無末鍵 curve → strip 回 0,正對照)。
  - `run_validator_v1`:把 doc 寫暫存 JSON,**真的跑一遍** `validator_v1.main(--metric)`,回 (rc, 錯誤行, stdout)。

## 5 AC(全 PASS)

- **V1 generate+wrap**:build_animations 產 cascade beat → 包成完整 Spine 3.8 JSON(含 slots/skins.default)
  + JSON round-trip + `SA.all_finite`。
- **V2 validator_v1 clean(G2)**:跑過 `validator_v1` → **rc==0、0 個 [ERR ]**
  (含 schema/引用完整性 + **末鍵 curve** editor 檢查)。
- **V3 loop closure(可接 Loop)**:`curve_tools.loop_closure_report == []`
  (pop 波每 bone scale timeline 首尾 identity、首鍵在 0、末鍵在 dur=1.2)。
- **V4 editor 閘有牙 + G1(負對照)**:
  (a) 原生 anim 末鍵 **0 curve**(`strip_last_frame_curves` 回 0);
  (b) 人工把 `curve` 注進某 bone scale timeline 的**末鍵** → `validator_v1` **rc==1 且 [ERR ] 點名末鍵 curve**
      (閘非恆真,有鑑別力);
  (c) `strip_last_frame_curves` 後再跑 → **rc==0**(G1 機械化修復,地雷 #12 可自動擋)。
- **V5 stiffness 可量(advisory)**:`curve_tools.stiffness_metric` 有限 ≥0(cascade pop = **49.84**),回報。
  honest:**不設 stiffness 閾值** —— 手感主觀屬使用者/A 類;本閘只證「量得出」。

## 關鍵發現

1. **repo 生成與 v1.3.0 editor 契約天生相容**:`_bez` 只碰 `frames[:-1]` → 末鍵永遠乾淨,
   2.0 併接不需改任何既有生成器就滿足地雷 #12。
2. **G1/G2 可機械化、可回歸**:產線契約 = 「`json.dump` 前過 `strip_last_frame_curves` + 跑 `validator_v1`」,
   本閘把它做成一鍵 pass/fail + 負對照,後續每搬一個生成器進 skill(B2+)都可複用此橋接閘守門。
3. **wrap 的 slots/skins 必須隨 fx 件自動導出**:凡 beat 含 slot timeline(color/alpha/attachment),
   wrap 時就要宣告對應 slot(綁 bone)+ default skin attachment,否則 validator_v0 擋。

## honest boundary

- cascade pop 波的運動基元/節拍/stiffness 高低仍屬**美術手感**(A 類);本閘只證 G1/G2 可機械化,不評美感。
- fixture 為**合成件**(跨件真實性另由 `validate_cascade` 覆蓋)。
- **尚未**把生成器搬進 skill 的 `assets/`(B2)、未 self-contained 打包(E);本 chunk 只建立橋接閘。
- cap `v2_bridge_validator_v1` L2 **eval**,新區塊 `spine-ai-editor-2.0` 仍 **HOLD**(達 E 前不升版)。

## 下一步

- MERGE_PLAN_2.0 **Phase B2**:把 cascade/pop/wobble/twist 生成函式整理進 skill 的 `assets/gen_lib/`
  (或過渡期 references 指向 repo tools),補一節 SOP 到 `references/animation_patch_patterns.md`,
  用本橋接閘(+ `spine-viewer.html` 可載入)驗收。
