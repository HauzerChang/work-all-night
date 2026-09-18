# S1 (G-4''''') squash 接檔位差異化 — 耦合 shear + 非均勻 scale 的**體積守恆放大**

> candidate **G-4'''''**（2026-09-18）。cap `squash_tier_coupled_amplitude` L2 → 併入 `spine-anim-forge`（仍 HOLD）。
> 閘：`tools/analyzer/validate_squash_tier.py`（5 AC 全 PASS）。圖：`figures/s1_squash_tier.png`。

## 補的 honest boundary

G-4''''（`squash_shear_scale_coupling`）讓 `gen_squash` **第一次**產出耦合的 shear + 非均勻 scale
（斜拉果凍擠壓，scaleX=1+q 拉長、scaleY=1/(1+q) 壓扁 ⇒ scaleX·scaleY≡1 面積守恆、scaleX≠scaleY 非均勻）。
但當時 squash **不在** `MAIN_SHOW_CATS` —— 因為 (J) 的預設 scale 增益 `_amp_scale` **只放大 identity 上方**
（`v'=1+g(v−1)` 僅當 v≥1；v<1 樓地板不動）。對 squash 這會 **只放大 scaleX>1 而 scaleY<1 不動 → 破壞
scaleX·scaleY≡1**（實測 Legend g=2.1 下積 →1.15）。於是「愈高檔位主秀愈爆」對其餘節拍都成立，唯獨斜拉擠壓
強度不隨檔位變 = 不一致。這是「檔位機制就緒 ≠ 每個新通道接上」的又一實例（同 E/H/I/J/G-4'/G-4''）。

## 解法：體積守恆放大 = 兩軸取同一指數 `v' = v^g`

要放大擠壓「強度」而仍面積守恆，對兩軸取**同一指數 g**：

```
scaleX' = scaleX^g ,  scaleY' = scaleY^g
⇒ scaleX'·scaleY' = (scaleX·scaleY)^g = 1^g = 1      （恆體積守恆，與 g 無關）
```

性質（皆可量測，構成檔位簽章 / 介面契約 / 阻尼保形）：
- **恆守恆**：scaleX·scaleY≡1 → 放大後仍 ≡1（4 位小數量化殘差 <1e-4 ≪ TOL_VOL=0.02）。
- **介面保持**：identity 幀 v=1 → 1^g=1（首尾 (1,1) 不動，可插 Loop）。
- **檔位簽章**：非均勻度 |scaleX−scaleY| 隨 g 單調變大（Super 0.30 → Legend 0.63）。
- **阻尼保形**：擠壓幅度 |scaleX_i−1| 仍隨極值嚴格遞減（scaleX_i 遞減 → scaleX_i^g 遞減）。

這是**相似變換（等比 scale）的自然對數延伸**：等比 pulse 對兩軸同乘 s（`v·s`）；體積守恆 squash 對兩軸同乘冪
（`v^g`）。檔位改的是**擠壓強度**（幅度），不改**守恆約束**（結構），與 wobble「同比放大保阻尼簽章」同精神。

shear 通道沿用 wobble：`v'=g·v`（對 0 對稱）→ shear 峰同時隨檔位遞增（16→33.6°）。
⇒ **耦合雙通道檔位差異化**：shear 與非均勻 scale **同時**放大，且守恆約束保持。

## 實作（純加性，向後相容）

- `tier_variants.py`：
  - `MAIN_SHOW_CATS` 加入 `squash`（原被排除，honest boundary 已補）。
  - 新增 `VOLUME_CONSERVING_CATS = {"squash"}`；`_amp_scale_vc(v, g) = v ** g`。
  - `amplify_bone_tl(b, g, volume_conserving=False)`：`volume_conserving=True` 時 scale 走 `_amp_scale_vc`，
    否則走原 `_amp_scale`（hit/combo/charge/reveal 的 overshoot+樓地板語意不變）。shear/rotate/translate
    兩模式相同（g·v）。`amplify_anim` 轉傳旗標。
- `gen_animations.build_animations`：`vc = cat in TV.VOLUME_CONSERVING_CATS`，依 cat 路由給 `_amplify_anim`。
- **向後相容**：Super g=1 → `v^1==v`、`1·v==v` → squash__Super **逐位元 == base squash**；其餘主秀不受影響
  （仍走 `_amp_scale`）；不帶 tier_gains → 逐位元同舊行為。

## 自我驗收（`validate_squash_tier.py`，先驗庫 → 真實 build_spine robot 骨架 → build_animations）

- **ST1** present + backward-compat：每檔位 `squash__{tier}` dual-channel（≥1 bone 同時帶 shear+非均勻 scale）、
  finite、路由回 squash；base（含 In/Loop/Out）帶/不帶 tier_gains 逐位元不變；**Super==base 逐位元**。
- **ST2 crux** 耦合雙通道遞增：shear 峰 [16, 21.6, 27.2, 33.6]° **且** 非均勻峰 [0.30, 0.40, 0.51, 0.63]
  皆 Super<Mega<Omg<Legend **嚴格遞增**且 Super==base。→ 證「愈高檔位擠壓愈猛」是**兩通道同增**（非只一軸）。
- **ST3 crux** 體積守恆逐檔保持：**每個檔位變體**每個內部極值幀 |scaleX·scaleY−1|≤TOL_VOL + 非均勻 +
  阻尼遞減（復用 G-4'''' 的 `_sq3_eval`，判準與 squash-gen 閘一致）。
- **ST4** 每檔位阻尼 shear（首尾 0、繞 0 變號≥3、相繼極值遞減）+ scale/shear identity 介面。
- **ST5** 負對照 / 守衛：
  - **(a) naive-amplify 守衛（crux）**：對 base squash 以**舊的** `_amp_scale` 放大 Legend 增益 →
    體積守恆**破壞**（5/5 bone，積 →1.15 > TOL_VOL），而正確 vc 放大不破 → **直接展示體積守恆 amplify 必要**。
  - **(b) 平增益守衛**：增益全 1.0 → ST2 遞增 FALSE 且各檔位逐位元 == base（證閘測真遞增非恆真）。
  - **(c) 體積守恆 amplify 單元測**：對合成 (1+q, 1/(1+q)) 對，`volume_conserving=True` → 積≈1、g>1 非均勻變大、
    shear g·v；非守恆模式對同輸入 → 積破壞（單元級鏡射 (a)，證兩模式差異來自 scale 通道）。

端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}`，
`validate_build` round-trip overall_pass（premult MAE 0.031、setup 不變）。

## 副修：`validate_tier_combo_count` K5(c) 判準

把 squash 併入 `MAIN_SHOW_CATS` 後，J-2 的 K5(c)「count 只作用 combo」原以「非-combo beat 峰數各檔位不變」
當代理而**假陽性**：`impact_peaks` 是**幅度**閾值偵測，squash 體積守恆的 scaleX 擠壓在 Super（g=1）低於
impact prominence、放大後才跨過門檻 → 峰數讀成 [0,1,1,1]，被誤判為「count 外洩」。這**不是** count 外洩
（squash 非 count-aware、`tier_combo_hits` 對它無效）。改判準為 **full（gains+counts）vs none_run（gains,
counts=None）逐位元比對**：直接測「count 參數不改變非-combo beat」這個真正不變量，對幅度效應免疫。
squash 兩者逐位元相同 → 無外洩，判準更精確且更強。

## 關鍵發現

1. **體積守恆放大 = 兩軸同指數（v^g）** —— 相似變換（等比 scale, v·s）的對數延伸；一行公式即恆守恆、
   保 identity、保阻尼、隨檔位遞增。避免「識別哪軸是拉長軸」的分支（對稱、對任意 xy≡1 皆成立）。
2. **檔位改強度不改約束**：檔位放大的是擠壓幅度（幅度軸），面積守恆（結構約束）逐檔不破 —— 同 wobble
   同比放大保阻尼簽章、同 (J) 只放大 overshoot 保介面。
3. **幅度閾值偵測器不可當結構代理**：把幅度會變的節拍（squash）拉進既有閘時，「峰數/計數」代理會被幅度
   跨閾誤觸；正解是比對「只改目標變數」的兩次 build（full vs none_run）。

## 回歸（18 閘全綠）

`validate_squash_tier`（新）/ `validate_squash_gen`(G-4'''') / `validate_wobble_tier`(G-4'') /
`validate_wobble_count`(G-4''') / `validate_tier_variants`(J，自動含 squash：J3 scale-overshoot+shear
遞增、J4 落 `else: ok=True`) / `validate_tier_combo_count`(J-2，K5c 已修) / `validate_shear_gen`(G-4') /
`validate_shear_pivot`(G-4) / `validate_scale_pivot`(G-3) / `validate_pivot_rotation`(0i) /
`validate_cascade` / `validate_priors` / `validate_priors_beats` / `validate_priors_combo_charge` /
`validate_priors_cascade` / `validate_more_beats` / `validate_beat_templates` / `validate_deform_gen`
全 PASS + round-trip `validate_build` overall_pass。

## honest boundary（仍在）

- 增益階梯 [1.0, 1.35, 1.70, 2.10] 沿用 (J) 的 g（PROPOSAL，結構簽章客觀、手感留使用者 A 類）。
- `shearY≡0`（squash 只產 shearX；雙軸 shear 為後續，見 STATE 建議 G-4''''''）。
- **squash count-aware 未接**：擠壓段數隨檔位（`gen_squash(nosc=)` 已備參數）—— 比照 J-2/G-4''' 需
  `TIER_SQUASH_CYCLES` + build_animations 依 cat 路由重生成（結構軸，與本次幅度軸正交），為後續。
- 單一真值資產（robot_parts）→ anim-forge 區塊仍 HOLD（運動基元為手感先驗，非學自真值）。
