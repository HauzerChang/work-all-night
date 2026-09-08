# S1 wobble shear 峰隨檔位遞增(shear 通道接 tier 幅度差異化,G-4'')

> 里程碑 2026-09-08 session 003(candidate G-4'')。續 G-4'(`gen_wobble` 為**第一個產 shear
> 通道的生成器**)與 (J)(主秀 beat 依檔位幅度差異化,但當時 `amplify_bone_tl` 只放大 scale/rotate)。
> 補 G-4' 的 honest boundary:wobble ∉ `MAIN_SHOW_CATS` 且 `amplify_bone_tl` 不動 shear →
> **wobble 的 shear 峰不隨檔位遞增**(各檔位共用同一斜拉幅度)。本次把 wobble 併入主秀、讓
> `amplify_bone_tl` 也放大 shear → shear 峰隨檔位遞增,而阻尼振盪簽章與 identity 介面對所有檔位保形。
> 工具:`tier_variants.py`(`MAIN_SHOW_CATS`+`amplify_bone_tl`)、`build_spine --tier-variants`、
> `validate_wobble_tier.py`、圖 `figures/s1_wobble_tier.png`。

## 動機(接 G-4' 的最後一塊)

G-4'(`s1-shear-channel-generation.md`)讓 `gen_wobble` 實際產出 shear 通道並端到端補償
(`build_spine --shear-pivot`)。它的 honest boundary #2 明言:「tier(檔位)變體尚未接 wobble
(wobble ∉ `MAIN_SHOW_CATS`)—— 可比照 (J) 把 wobble 加進 tier 幅度差異化(shear 峰隨檔位遞增)。」
本 candidate 就是做這一步 —— 又一「公式/模板就緒 ≠ 生成器接上」模式的實例(同 (E)/(H)/(I)/(J)/(J-2)/(G-4'))。

## 缺口精確定位:兩處都沒接 shear

(J) 的 `tier_variants.amplify_bone_tl` 逐通道放大:
- **scale**:只放大 identity 上方 overshoot(`v'=1+g(v−1)` 僅 v≥1;下方樓地板不動);
- **rotate/translate**:繞 0 對稱 `v'=g·v`;
- **color/alpha**:不動。

**沒有 `shear` 分支** → 即使 wobble 在 `MAIN_SHOW_CATS`,tier 變體的 shear 也不會被放大(deepcopy
原樣保留)。而且 wobble **根本不在** `MAIN_SHOW_CATS`(G-4' 只加到 `gen_animations` 的 `_DISPATCH`/
`_CAT_KEYWORDS`,沒動 tier 側)→ 連 `{wobble}__{tier}` 變體都不會產。故本次要動**兩處**。

## 改動(全 additive,2 行語意)

1. `MAIN_SHOW_CATS` 加 `"wobble"` → `build_animations(tier_gains=…)` 對 wobble beat 產 `wobble__{tier}` 變體。
2. `amplify_bone_tl` 加 **shear 分支**:shear 繞 0(=identity)對稱擺動,故如 rotate/translate `v'=g·v`
   (x/y 皆乘;shearY 目前恆 0,乘 g 仍 0)。

```
shearX 包絡  [0, A, −rA, r²A, −r³A, 0]   ── amplify(g) ──▶   [0, gA, −grA, gr²A, −gr³A, 0]
```

**為何 `v'=g·v` 對 shear 是正確且保形的**:
- `g·0 = 0`(round 後仍 0)→ **首尾/過零關鍵幀恆守 identity**(介面契約:可插 Loop 間,對所有檔位)。
- 相繼極值 `[A, rA, r²A, r³A]` 同乘 g → **阻尼比 r 不變**(波形/阻尼軸與幅度軸正交)、
  **繞 0 變號數不變**(阻尼振盪簽章保形)、**峰值隨 g 單調變大**(檔位簽章)。
- base=Super g=1.0 → `g·v=v`、round 到 4 位同原值 → **逐位元向後相容**。

無新增益路徑:shear 走的就是 (J) 既有的 `amplify_bone_tl`,與 scale/rotate 同源。

## 驗收 `validate_wobble_tier.py`(先驗庫→真實 build_spine robot 骨架→build_animations,5 AC 全 PASS)

| AC | 內容 | 實測 |
|---|---|---|
| X1 | present+routing+backward-compat 每 wobble beat×每檔位產帶 shear 變體、路由回 "wobble"、base 與 `tier_gains=None` 逐位元不變、In/Loop/Out 不產 wobble 變體 | PASS |
| X2 | **crux** shearX 峰 Super<Mega<Omg<Legend 嚴格遞增且 == base×宣告增益階梯 | **[16.0, 21.6, 27.2, 33.6]** == 16×[1.0,1.35,1.70,2.10] |
| X3 | **每檔位**阻尼簽章保持:每 wobble bone shearX 首尾 0、繞 0 變號 ≥3、相繼極值嚴格遞減 | 全 PASS(20 bone×tier) |
| X4 | **每檔位** identity 介面:sample(0)/sample(dur) 各 bone rotate/translate/scale identity + shear 首尾 0 | PASS |
| X5 | 負對照/正交 (a)平增益全 1.0→X2 單調 FALSE (b)shear 隔離:非 wobble 變體不憑空長 shear (c)阻尼比 r 跨檔位相同 | 全 PASS |

**X5(c) 是本能力的正交性宣告**:相繼極值比 r 對所有檔位**完全相同**(幅度改變、波形/阻尼不變)——
與 (J) 的「樓地板不動」、(J-2) 的「連擊數正交於幅度」同一家族的誠實性斷言:tier 只改「多斜」不改「怎麼晃」。

## 端到端(build_spine 直出)

`build_spine --animate --tier-variants`(robot)產出的 `skeleton.json` 含 `wobble__Super/Mega/Omg/Legend`,
5 bone 全帶 shear,峰值 16.0/21.6/27.2/33.6°;round-trip `validate_build` overall_pass(premult MAE 0.031、setup 不變)。

## 回歸波及點:J 閘改「通道感知」(必要且不減弱)

wobble 併入 `MAIN_SHOW_CATS` 後,`validate_tier_variants.py`(J)的 `main_beats` 會納入 wobble。原 J3
只量 scale overshoot / rotate 幅度,wobble **兩者皆無**(只有 shear)→ 會假陰性。故把 J3/J4 改**通道感知**:
- **J3**:對每 beat **實際存在**的幅度通道(scale / rotate / shear)各要求嚴格遞增,且至少一通道存在。
  既有 scale-based beat 皆有 scale → 與舊判準**等價**(不減弱);wobble 只有 shear → 改以 shear 峰遞增為 crux。
- **J4**:cat=="wobble" 檢查阻尼 shear 簽章(復用 `validate_shear_gen` 的 `_sign_changes_zero`/
  `_extrema_mags_decreasing`,判準與 G-4' 閘一致)。

其餘回歸全綠:`tier_combo_count`(J-2)、`shear_gen`(G-4')、`shear_pivot`(G-4)、`pivot_rotation`(0i)、
`scale_pivot`(G-3)、`priors`/`priors_beats`/`priors_cascade`/`priors_combo_charge`、`cascade`/`more_beats`/
`beat_templates`/`deform_gen`、`anim`(+selftest)、round-trip `validate_build`(--tier-variants --shear-pivot)。

## 關鍵發現 / 踩雷

1. **shear 的對稱增益 `v'=g·v` 天生保形**:因 wobble shear 繞 0 擺動(不像 scale 繞 1),放大規則比 scale 更單純
   (不需「只放大上方」的樓地板保護),且過零點 `g·0=0` 自動守住 identity 介面 —— shear 的幾何結構讓保形免費。
2. **併入主秀會波及既有 milestone 閘**:凡把新類別加進 `MAIN_SHOW_CATS`,所有掃 `MAIN_SHOW_CATS` 的閘
   (此處 J)都會自動納入該類別。若閘的度量只認舊通道 → 假陰性。**通道感知**(present-then-require)是通用解:
   對存在的通道要求性質、缺席的通道略過,對舊 beat 等價、對新 beat 正確。
3. **正交性可量化**:阻尼比 r 跨檔位逐一相等(X5c)把「幅度軸 ⟂ 波形軸」從口號變成可驗的負對照。

## honest boundary(仍在)

- 斜拉幅度階梯(增益 1.0/1.35/1.70/2.10,沿用 (J) 的 `TIER_GAIN`)是 **PROPOSAL**(結構簽章客觀、手感留使用者 A 類)。
- 仍只 **shearX**(shearY≡0);wobble 尚未接「連擊數/波速」類的結構性檔位差異(shear 只有幅度一軸有意義)。
- 單一真值資產(robot);`spine-anim-forge` 仍 **HOLD**(運動基元先驗、未達 L3 端到端真值)。

## cap / skill

新增 cap `tier_variant_shear` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
