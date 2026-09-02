# S1 slot_bigwin 主秀重擊 beat 接進先驗庫(candidate 0g)

> 里程碑:2026-09-02。補 0f 的**端到端可達性缺口** —— 讓 big-win 資產經 `build_spine --animate`
> 直接輸出含主秀節拍的完整演出,而非只有 In/Loop/Out。

## 問題(0f 留下的缺口)

0f(`beat_templates.py`)提供了 `gen_hit`/`gen_reveal` 兩個主秀模板(anticipation+settle),
並註冊到 `gen_animations._DISPATCH`。但**要真的被端到端輸出**,storyboard 必須含一個被
`beat_category` 歸為 `hit`/`reveal` 的 beat。實查兩個 validated 先驗:

- **`slot_reveal`(真值 main_draw)**:beat `open→reveal`、`hit→hit` **已可達**(0f 起即成立)——
  main_draw 生產檔本身就有獨立的 `main_draw_open` / `main_draw_hit` 動畫。
- **`slot_bigwin`(真值 Award)**:beats 只有 `In/Loop/Out`。**Award 12 支動畫 = In/Loop/Out × 4 檔位,
  沒有任何獨立 hit/win 動畫** —— 生產檔把主秀節拍**折進 `In`(入場爆發)**。故
  `build_spine --animate --genre slot_bigwin` **從不輸出主秀 hit**,0f 模板對 big-win 端到端不可達。

## 做法(最小、誠實、不動已驗先驗)

在 `genre_priors.PRIORS["slot_bigwin"]` **新增一個 PROPOSAL beat `Hit`**(kw `hit/win/bigwin/impact/…`),
`beat_category("Hit")→hit` → 路由到 `gen_hit`。同時給 `_BIGWIN_ROLES["Hit"]` 補角色動作文字。
**已驗的 In/Loop/Out 一字未動**。端到端結果:`build_spine --animate` 輸出 `In, Hit, Loop, Out`。

**誠實界定**:`Hit` 對 Award 命名不命中(Award 無 hit 動畫)→ `validate_priors` 把它列為
`prior_beats_unused`,覆蓋率仍 **1.0**。即此 beat 是**先驗提案(PROPOSAL)非真值觀測**;Award 的主秀
折進 In 是該資產的美術選擇,本 chunk 提供的是「若要獨立主秀節拍」的可達路徑,不宣稱 Award 有它。

## 自我驗收 — `validate_bigwin_mainshow.py`(5 AC 全 PASS)

端到端跑 `build_spine --animate --genre slot_bigwin`(真實 `robot_parts.psd`),沿用 0f
`validate_beat_templates` 的結構簽章判定子(一致性):

| AC | 內容 | 實測 |
|---|---|---|
| **G1 reachability** | 端到端輸出含 `Hit`,結構件 bone ≥1 | `In,Hit,Loop,Out`;Hit 5 bones ✅ |
| **G2 hit signature** | body scale:真峰 ≥1.12 + 命中前下蹲 <0.99 + (scale−1) 變號 ≥3 | `b_身體` peak **1.279**、pre-min **0.931**、變號 **4** ✅ |
| **G3 chainable** | `Hit` 首尾幀皆 setup identity(scale≈1、alpha≈1)→ 可插 Loop 間 | start/end 全 identity ✅ |
| **G4 neg-control** | 同一 build 的 `In`(intro)、`Loop` **不**具 hit 簽章 | 兩者皆 False ✅ |
| **G5 regression** | validate_priors slot_bigwin 覆蓋率 1.0、Award In/Loop/Out 歸類不動、`Hit` 為 unused | cov 1.0、mapped=In/Loop/Out、unused=[Hit] ✅ |

**G4 是關鍵鑑別**:證明加的是**真·獨立主秀節拍**(有反向預備+阻尼回擺簽章),不是把入場改名。
用的是 0f 已驗可信的 `_hit_signature`(對稱脈衝 gen_pulse 判 False)。

## 回歸(全綠)

- `validate_anim.py --selftest`(0d):AC1–4 + 負對照全 PASS(Hit 為額外動畫,不干擾 intro/loop/outro 判定)。
- `validate_beat_templates.py`(0f):B1–B6 全 PASS(模板本身未動)。
- `validate_priors.py`:overall_pass、兩 validated 先驗覆蓋率 1.0。
- `validate_deform_gen.py`(0e):PASS。

## 邊界 / 下一步

- 這是**先驗庫接線**(把已驗模板接到 big-win 的預設演出),非新演算法/新美學。緩動幅度手感仍留使用者(A 類)。
- `spine-anim-forge` 區塊仍 **HOLD**(運動基元先驗、單一真值資產,防固化)。
- 後續可做:(F) 更多主秀節拍(anticipate-hold / multi-hit combo / cascade,各配結構簽章);
  或把 `Hit` 的觸發也接進 tiers(每檔位一支主秀)。
