# S1 big-win 主秀 beat 模板(candidate 0f)—— anticipation + settle

- **結論**:candidate 0d(`gen_animations.py`)的主秀節拍只有 `gen_pulse` 的**對稱三角脈衝**
  (identity→peak→identity),缺兩個經典動畫原理。本次補上 **hit / reveal 兩個 role-aware 主秀模板**
  (`beat_templates.py`),把 **anticipation(反向預備)+ settle/follow-through(阻尼回擺)** 做成
  確定性 keyframe;配自我驗收閘 `validate_beat_templates.py`(6 AC 全 PASS,含負對照)。
- **信心**:高(純 CPU 確定性 + 結構簽章可量化 + 負對照鑑別力)。真值界定見下。
- **相關階段**:第 2 階段 S1(分鏡→動畫)。續 0d(bone/slot keyframe)、0e(mesh deform)。**cap `storyboard_beat_templates` L2;`spine-anim-forge` 區塊仍 HOLD。**

## 為什麼要做(0d 的缺口)

0d 的 `gen_pulse`:`(scale-1)` 只有單一正峰(0→+→0),沒有:
1. **Anticipation**:出手前先反向蓄力(squash 下蹲 / 反向甩)——讓命中更有力。
2. **Settle / follow-through**:命中後**越過 identity 再阻尼回擺**,而非直線回到 1。
這兩者是 big-win「主秀」節拍與泛用「輕重音」的分野。主秀 beat(hit/reveal)是 slot 大獎演出的核心。

## 模板(`tools/analyzer/beat_templates.py`)

- **`gen_hit`** — Anticipation → Impact → Settle。**首尾皆 setup identity**(可插在 Loop 循環間當重音)。
  scale 包絡(τ):`1.0 →(蓄)0.93 →(命中)peak →(下衝)0.965 →(上衝)1.015 → 0.995 → 1.0`;
  `(scale-1)` 依序 `0,−,+,−,+,−,0` → 反向預備 + 阻尼回擺。role 加成:limb whip(反向蓄力→甩出→回擺)、
  head 點頭衝擊、特效 亮度閃(先暗後亮阻尼)+ 旋轉甩。peak 依 role:body 1.28 / 特效 1.35 / head·limb 1.18。
- **`gen_reveal`** — Collapsed → 蓄勢 hold → Burst overshoot → Settle。**首 collapsed(scale~0.02 / alpha 0)、
  尾 identity**(大獎現身,之後可接 Loop)。scale:`0.02→0.02(hold)→peak→0.95→1.02→1.0`;
  alpha:`0→0(hold)→1(burst)→1`。

wire 進 `gen_animations`:新增類別 `hit` / `reveal`(關鍵字含中英,見 `HIT_KEYWORDS`/`REVEAL_KEYWORDS`),
`hit`/`burst` 移出泛用 `pulse`。註冊放 `gen_animations` 檔尾避免 import 迴圈(beat_templates 只需上方已定義的
`DUR`/`_rot`/`_xy`/`_color`)。單位/內插同 0d(linear;關鍵幀值本身編碼阻尼回擺,取樣穩健)。

## 自我驗收閘(`validate_beat_templates.py`,6 AC 全 PASS)

用 `spine_anim.py` 取樣 240 點,對 fixture(**真實 robot 拆件 5 件+role** 端到端經 `build_animations`):

| AC | 判準 | 結果 |
|---|---|---|
| **B1 well-formed** | finite / 時間嚴格遞增 / JSON round-trip | PASS |
| **B2 chainable IF** | hit 首尾 identity;reveal 首 collapsed、尾 identity | PASS |
| **B3 impact peak** | 真峰值 scale overshoot ≥1.12(hit 1.348 / reveal 1.35) | PASS |
| **B4 anticipation** | hit 命中前 scale 下蹲 <0.99(實測 0.931);reveal burst 前蓄勢 hold | PASS |
| **B5 settle** | hit `(scale-1)` 變號 ≥3(阻尼回擺);reveal 峰後穿越 ≥2 | PASS |
| **B6 負對照** | 對稱脈衝(gen_pulse)判為**非主秀**、不歸位 FAIL B2、無峰 FAIL B3、真 hit 具簽章 | PASS |

**真值界定(honest)**:主秀 beat **沒有唯一正確運動**(屬先驗手感),故閘驗的是**定義主秀節拍的客觀
結構簽章**(anticipation 反向預備 + settle 阻尼回擺 + 真峰 + 可串接介面),**不驗美感**;緩動曲線/幅度手感留使用者(A 類)。
幅度/相位為可調參數。圖:`knowledge/figures/s1_beat_templates.png`。

## 關鍵發現

- **結構簽章足以分辨「主秀 hit」與「天真脈衝」**:`(scale-1)` 的**符號變化數**是強鑑別子——真 hit(反向蓄力+阻尼
  回擺)≥3 次變號,對稱三角脈衝只有單正峰(0 次負向偏移)→ 負對照 `symmetric_pulse_not_main_show` 乾淨分離。
- **anticipation 用「峰前是否下蹲 <1」判定**最穩:與峰值大小解耦,對取樣密度不敏感。
- **可串接性沿用 0d 的 identity 介面契約**:hit 首尾 identity → 可任意插在 In/Loop/Out 之間;reveal 首 collapsed
  尾 identity → 專用於「現身」後接 Loop。與 0d/0e 的無縫串接論點一致。

## 回歸(未破壞既有)

- 0d `validate_anim`(robot/Symbol_Ww)+ `--selftest` 負對照:仍全 PASS(pulse 關鍵字調整不影響 In/Loop/Out 類別)。
- 0e `validate_anim(--animate --deform)`:仍 PASS。

## 待續

- **接進 genre 先驗庫**:目前 hit/reveal 由 fixture storyboard 驅動(真實拆件 role 端到端);把主秀 beat 併入
  `genre_priors` 的 `slot_bigwin`/`slot_reveal`(需同步 `validate_priors` 真值覆蓋,避免動到已驗先驗)為後續小步。
- 更多主秀節拍(anticipate-hold / multi-hit combo / cascade),各配結構簽章 AC。
- 幅度/緩動的美感微調 = 使用者 A 類。
