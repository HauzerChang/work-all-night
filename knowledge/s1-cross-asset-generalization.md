# S1 主秀 beat 生成器跨資產泛化(candidate XA)

> 2026-10-03 run 003。cap `cross_asset_generalization`(L2,併入 `spine-anim-forge`,仍 HOLD)。
> 閘:`tools/analyzer/validate_cross_asset_generalization.py`(5 AC 全 PASS)。

## 動機:攻擊重複 ~24 次、卻從未實測的 honest boundary

`spine-anim-forge` 的**每一條** cap(tier 幅度 J、combo/wobble/squash/twist/charge/cascade 的
count-aware、cascade 方向 J-5~J-7、pivot 主秀整合 G-2、…)結語都寫同一句:
**「單一真值資產(robot),與 anim-forge 同 HOLD」**。也就是:整個主秀 beat 生成能力,**一直只在
一個資產**(`assets/robot_parts.psd`)上被驗過。這是它遲遲離不開 HOLD 的**主因之一**(另一是運動手感
屬 A 類、出貨屬 C 類)。

但看生成器實作(`gen_animations.py`):所有主秀/待機基元都是 **role-based** ——
`gen_loop(role, …)` / `gen_in` / `gen_pulse` / `gen_combo` / `gen_wobble` / … 依
`role ∈ {body, head, limb, 特效}` 路由到固定運動基元,**完全不綁特定件名**。因此生成器**理應與資產無關**,
「單一真值資產」對**結構簽章層**其實是**過度保守**的 boundary —— 但從未被實測推翻。本次補上實測。

## 做了什麼

新增**第二個獨立真實資產**的泛化閘,把「只在 robot 驗過」的結構簽章,實測到
`assets/Symbol_Ww.psd`(repo 內既有):一個 DJ 風格角色符號,**18 件**(頭/身體/左手1-3/右手1-2/
耳機/墨鏡/鬢角/音符/框/底/wild…)、**180×180 畫布**,與 robot(5 件 + root、713×693 畫布)**件集/件數/
尺度全然不同**。閘**不重寫**簽章數學,而是**復用既有 per-cap 閘的 `run()`**(monkeypatch 其 `PSD`),
確保度量與 robot 上**逐條一致** → 可信度最高、零判準漂移。

### 5 AC(全 PASS)

- **XA1 pipeline on 2nd asset**:Symbol_Ww 端到端 build(slice→analyze→build→animate→tier-variants)
  成功產 43 animations;8 個主秀 beat 家族(burst/hit/combo/charge/cascade/wobble/squash/twist)× 4 檔位
  變體皆 present/finite/有 bone;且**結構確不同於 robot**(18≠5 件、180²≠713×693)→ 證真·不同資產。
- **XA2 signatures(復用 `validate_tier_variants.run()`)**:在第二資產上 J2 介面 identity、J3 crux 幅度
  單調(Super<Mega<Omg<Legend)、J4 結構簽章、J5 負對照(含平增益守衛)**全 PASS**。
- **XA3 count-aware(復用 6 條 count 閘)**:tier_combo / wobble / squash / twist / charge / cascade_count
  的 `run()` 在第二資產上皆 `OVERALL_PASS` → 段數軸家族整體泛化。
- **XA4 crux — asset-dependent threading 隨幾何改變**:cascade 跨件相位 threading 是唯一**與資產相關**的
  簽章(讀件幾何/件序)。第二資產穿 **18 件**(robot 穿 5 件),皆依件序嚴格遞增、散佈 ≥0.30(仍一道
  有序跨件波);**threading 件數 == 資產件數**(每件入波);兩資產波序**成員/長度皆不同** → 證波真讀資產
  幾何,**非寫死 robot 樣式**(寫死樣式在 18 件資產上會失敗或只穿 5 件)。
- **XA5 anchor + neg-control**:(a) **ANCHOR**:同一 `validate_tier_variants.run()` 在 robot 上亦 PASS →
  證本閘度量**重現既有 per-cap 結果**,故第二資產 PASS 是**真泛化非放寬判準**;(b) **NEG**:第二資產上把
  增益階梯全設 1.0 → 幅度單調性 FALSE → 本閘在**新資產**上仍保有鑑別力(非恆真)。

## 量化對照(robot vs Symbol_Ww)

| 指標 | robot | Symbol_Ww |
|---|---|---|
| 件數(含 root) | 5(+root) | 18(+root) |
| 畫布 | 713×693 | 180×180 |
| 主秀 beat 家族 | 8 全present | 8 全present |
| tier 幅度單調(hit/combo/…) | PASS | PASS(**幅度值與 robot 逐檔相同**,因幅度是生成器常數) |
| 6 count 閘 | PASS | PASS |
| cascade threading 件數 | 5(0.158→0.70) | **18**(0.158→0.70) |

**重點**:幅度/段數簽章是生成器**常數**(與資產無關 → 兩資產數值相同);唯一**讀資產**的 cascade threading
**正確隨件數/幾何自適應**(5→18)。兩者合起來才是完整的泛化證據:
不讀資產的簽章「換資產不變」、讀資產的簽章「換資產正確跟著變」。

## 關鍵發現

1. **「單一真值資產」對結構簽章層是過度保守的 honest boundary**:生成器既 role-based,其結構不變量
   (介面 identity / tier 單調 / count 遞增 / cross-channel 守恆)本就**與資產無關**,實測第二真實資產即證之。
   ~24 條 cap 重複此 boundary 卻從未實測 —— 這正是「宣告/機制就緒 ≠ 有 AC 驗」通則的又一實例
   (同 E 模板就緒≠產線會用、0i 幾何就緒≠生成器接上、G-2 apply_pivots 掃過≠主秀 beat 有 AC)。
2. **泛化要同時驗「不變的」與「該變的」**:只驗「換資產簽章不變」會漏掉「生成器是否真讀資產」;
   cascade threading 是唯一讀資產的通道,必須驗它**隨幾何正確改變**(件數 5→18、波序成員不同),
   否則一個「永遠輸出固定 robot 波」的壞生成器也能騙過前者。
3. **復用既有閘的 `run()` 當度量 = 最可信的泛化閘**:不重寫簽章數學(零判準漂移),monkeypatch `PSD`
   即把 per-cap 閘「搬到」新資產;anchor(同閘在 robot 仍 PASS)保證度量未被悄悄放寬。

## honest boundary(仍在)

- **本閘 PASS ≠ anim-forge 可出貨**:出貨是 **C 類**(使用者拍板);運動**手感/美感**是 **A 類**(主觀,
  本閘只驗客觀結構簽章)。本閘只把「單一真值資產」boundary 升級為「2 個獨立真實資產」—— 離開 HOLD 的
  **必要非充分**條件。
- **仍只 2 個資產**:Symbol_Ww 與 robot。更多真實資產(不同骨架拓樸/件數)仍可再加;本閘已把加法做成
  **參數化**(`SECOND`/`ANCHOR` + 復用既有 `run()`),新增資產成本低。
- **cascade 的件序相位來源**本身(用 geo / 手感常數)仍 PROPOSAL(A 類,見 J-5~J-7);本閘只驗其
  **threading 隨資產改變**,不評方向選擇的美感。

## 後續候選(皆自主)

- 把泛化閘擴成 **N 資產參數化矩陣**(再加 `main_draw` 的可拆件或合成資產),把「2 資產」推到「≥3 資產」。
- 若使用者提供**第二個含藝術家 rig/pivot 真值**的資產(D,資源類),則 S5 rig/pivot 的「單一真值資產」
  boundary 也能同法升級(但 rig 需**藝術家真值**,非純結構簽章 → 不可純自主,屬 C/資源類)。
