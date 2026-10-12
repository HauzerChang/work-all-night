# S2/2.0 (B1) — 橋接閘:repo 生成器輸出 → v1.3.0 `validator_v1`(G1+G2 機械化)

> 排程主線 = **產出 spine-ai-editor 2.0**(2026-10-12 使用者拍板)。路線圖 `skills/spine-ai-editor/MERGE_PLAN_2.0.md`。
> 本篇 = **Phase B1**(B 階段的前提 chunk)。工具:`tools/analyzer/validate_v2_bridge.py`。

## 這個 chunk 在解什麼問題

2.0 要把 repo 半年累積的**確定性生成引擎 + 評估器紀律**併進使用者既有 skill `spine-ai-editor v1.3.0`。
但兩套品質閘驗的東西**不一樣**:

| 閘 | 驗什麼 | 漏什麼 |
|---|---|---|
| repo 69 閘 | runtime(spine-webgl)可載入、結構簽章、變形自交 | **不驗 Spine editor 可匯入** |
| v1.3.0 `validator_v1` | editor 可匯入(末鍵 curve=地雷 #12 AIOOBE crash)+ loop 閉合 + stiffness | 不生成、不驗結構簽章 |

MERGE_PLAN 的 **G2(雙真值驗收)** 要求 2.0 的輸出「**遊戲能播 且 編輯器能匯入**」。
B1 在搬任何生成器進 skill **之前**,先機械化證明這條接縫可自動化 —— 否則後面每個 chunk 都在未驗的地基上疊。

## 做了什麼(純新增,無改任何既有生成/產線值)

新檔 `tools/analyzer/validate_v2_bridge.py`:把 repo **最單純的 cascade big-win beat** 跑過真正的 `validator_v1`:

1. **生成**:`build_cascade_skeleton()` 用真實拆件(`robot_parts.psd`)件序,
   `G.build_animations` 產一支 `cascade` beat,組成 schema 合法的完整 Spine 3.8 JSON
   (bones + slots + default skin region 占位 + animations)。
2. **G1(機械化護欄)**:`curve_tools.strip_last_frame_curves()` 拔末鍵 curve,回報拔幾條。
3. **G2(編輯器真值閘)**:subprocess 呼叫**真正的** `skills/spine-ai-editor/assets/validator_v1.py --metric --loop-anims cascade`,
   解析其 error / loop 問題 / stiffness。
4. **負對照**(證閘非恆真):(a)注入末鍵 curve → 確認 validator_v1 抓到 editor-crash error,再 strip → 修好;
   (b)破壞某 bone scale 末鍵值(開環)→ 確認 loop 閉合抓到 `open loop`。

## 5 AC(全 PASS,真實 robot 骨架)

- **B1-1 generate+schema**:生成器產 cascade beat(5 bone / 1 effect slot 光暈),組成 schema 合法完整 Spine JSON(v0 底層 0 schema error)。
- **B1-2 editor-import 0 error**:過 G1 後 `validator_v1` **valid、0 error**(含末鍵 curve 檢查)→ 遊戲能播 **且** 編輯器能匯入。
- **B1-3 loop 閉合**:cascade(pop 波)首尾 identity → loop 閉合 **0 問題**。
- **B1-4 stiffness**:`validator_v1 --metric` 回報 cascade stiffness = **50.49**(有限可量),併入輸出。
- **B1-5 gate-non-vacuous**:負對照 (a) 末鍵 curve 被抓(error 明確指向 AIOOBE / `strip_last_frame_curves()`)+ strip 後回 valid;(b) 開環被 loop 閉合抓(`b_光暈.scale.x: open loop 1.0 != 1.5`)。

## 關鍵發現

1. **repo 生成器在單 beat 層級本就 editor 乾淨**:`gen_animations._bez` 只對 `frames[:-1]` 寫 curve
   (末鍵永不帶 curve)→ 單 beat 生成 **G1 拔 0 條**。所以「遊戲能播但編輯器炸」這個地雷 #12 風險,
   **不在 repo 的單 beat 生成**,而在**序列 compose/crossfade/loop**(把多段接起來時,前段尾幀的 outgoing curve
   可能變成某 timeline 的末鍵)。→ **G1 的真正戰場是 B4(序列)與 D1(統一閘),不是單 beat**。這把後面 chunk 的驗收重點釘住了。
2. **兩套閘的接縫可機械化**:生成 →(G1)strip →(G2)validator_v1 是一條可重跑、可機讀 pass/fail 的閘。
   G2 不必人工開 Spine editor:validator_v1 的末鍵 curve 檢查 = 地雷 #12 的程式化代理。
3. **負對照證明閘有牙**:不是「reveal 之類首幀非 identity 會誤報」——cascade pop 波首尾 identity,loop 閉合本該過;
   注入破壞後兩條負對照都確實 FAIL,證閘會因為 repo 輸出不乾淨而擋下(非恆真)。

## honest boundary

- 本閘只驗**最單純單 beat**(cascade pop)。多 beat 序列的末鍵 curve 風險、以及 reveal(首幀 collapsed,
  loop 閉合本就不該過,需 `--loop-anims` 排除)的介面差異,留 **B4 / D1**。
- 「哪個 beat 該用 cascade/pop」仍屬美術手感(A 類);本閘只驗客觀的 schema / editor 相容 / loop / stiffness。
- Cocos 實機 round-trip、spine_inspector 視覺確認 = 使用者端(排程 scope 邊界,見 MERGE_PLAN)。本閘用 spine-webgl 無頭等價(validator_v1)替代。

## 回歸

`check_readiness` 新增 cap `v2_bridge`(L2,role=pipeline,併入 `spine-anim-forge` 仍 HOLD);既有閘不受影響(純新增檔)。
