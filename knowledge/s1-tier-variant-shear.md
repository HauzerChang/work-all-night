# S1 wobble(shear 通道)接檔位幅度差異化(shear 峰隨檔位遞增,G-4'')

> 里程碑 2026-09-09(candidate G-4'')。補 G-4' 的 honest boundary:G-4' 讓 `gen_wobble` 產出
> **shear 通道**(阻尼 shearX 擺動),但收尾時明列「wobble ∉ MAIN_SHOW_CATS → tier 變體未接」——
> wobble 的檔位幅度差異化沒接上產線。本次讓 wobble 的 **shearX 峰隨檔位(Super/Mega/Omg/Legend)
> 嚴格遞增**,且**端到端**(`build_spine --tier-variants --shear-pivot`)放大後的 shear 仍繞關節
> pivot 精確不動。
> 工具:`tier_variants.SHEAR_SHOW_CATS`/`amplify_bone_tl`(shear 分支)、`build_spine --tier-variants
> --shear-pivot`、`validate_tier_variant_shear.py`、圖 `figures/s1_tier_variant_shear.png`。

## 動機(把 shear 幅度接進檔位系統)

三條前置能力就緒但彼此沒接:
- (J)(`s1-tier-variant-amplitude.md`):scale/rotate 主秀 beat 依檔位產 `{beat}__{tier}` 幅度變體。
- (J-2)(`s1-tier-variant-combo-count.md`):combo 的連擊「數」隨檔位遞增(結構軸,與幅度正交)。
- (G-4')(`s1-shear-channel-generation.md`):wobble 產出 shear 通道 + `--shear-pivot` 端到端補償。

缺口:wobble 的幅度落在 **shear** 通道,而 (J) 的增益/度量只認 scale/rotate,故 wobble 從未被檔位系統
覆蓋(G-4' 的 honest boundary)。本 candidate 把「shear 幅度」接進檔位增益,是「宣告/公式/模板就緒 ≠
生成器接上」模式的又一實例(同 (E)/(H)/(I)/(J)/(J-2)/(G-4'))。

## 關鍵設計:平行的 shear 主秀集合(讓 (J) 閘範圍逐位元不變)

**踩雷點**:直接把 `wobble` 塞進 `MAIN_SHOW_CATS` 會**打壞 (J) 閘**。因為 `spine_anim.sample()`
**完全不讀 shear 通道**(只讀 rotate/translate/scale),對 shear-only 的 wobble bone 取樣恆回 identity
→ (J) 的 `_scale_overshoot`/`_rotate_amp` 對它量到 0 → J3「幅度嚴格遞增」對 wobble **假陰性**。

**解法**:在 `tier_variants.py` 開一個**平行集合**,與 scale/rotate 主秀分開:
```
MAIN_SHOW_CATS  = {hit, reveal, burst, combo, charge, cascade}   # scale/rotate 幅度主秀
SHEAR_SHOW_CATS = {wobble}                                        # shear 幅度主秀(candidate G-4'')
TIER_VARIANT_CATS = MAIN_SHOW_CATS | SHEAR_SHOW_CATS             # build_animations 判定用
```
`build_animations` 的產變體條件由 `cat in MAIN_SHOW_CATS` 改為 `cat in TIER_VARIANT_CATS`。因為 (J) 閘
(`validate_tier_variants.py`)只迭代 `MAIN_SHOW_CATS` 的 beat,wobble 不在其中 → **(J) 閘逐位元不受影響**
(實測回歸 PASS,零改動);wobble 走本 candidate 專屬的 shear 幅度閘。教訓:**度量不適用的類別不要硬塞進
同一個閘的範圍**,平行集合比「擴充既有閘去容納異質類別」更乾淨、回歸風險更低。

## shear 幅度增益規則(對阻尼振盪簽章保形)

`amplify_bone_tl` 新增 shear 分支:對 0(identity)**對稱**放大 `v' = g*v`(同 rotate/translate):
- shearX=0 的首尾幀 → `g*0=0` 仍 0 → **identity 介面契約保持**(可插 Loop 間,對所有檔位)。
- 阻尼振盪相繼極值 `[A, rA, r²A, r³A]` 同乘 g → `[gA, grA, gr²A, gr³A]`:
  **繞 0 變號數不變**(g>0 不改符號)、**相繼極值仍嚴格遞減**(r 不變)→ 阻尼振盪簽章**對所有檔位保形**,
  只有幅度隨 g 變大。**阻尼比 r 對檔位不變**(增益只改幅度、不改結構)—— 這是本能力的「幅度⟂結構」。
- shearY≡0 → `g*0=0`(純斜拉恆保持)。既有 scale/rotate beat 無 shear 通道 → 此分支 no-op(零回歸)。

`TIER_GAIN` 階梯沿用 (J) 的 `{Super:1.0, Mega:1.35, Omg:1.70, Legend:2.10}`(base=Super g=1.0 →
`wobble__Super` 逐位元 == base wobble,向後相容)。端到端各 bone shear 峰:
`光暈 [16,21.6,27.2,33.6] · 身體 [14,18.9,23.8,29.4] · 手 [12,16.2,20.4,25.2] · 頭 [10,13.5,17,21]`。

## 端到端不動點(放大幅度 ≠ 破壞 pivot)

`build_spine` 的 `apply_pivots` 迴圈本就掃**所有** animations(含 `{beat}__{tier}` 變體),且
`pivot_channels_affine` 讀的是**該變體當下的 shear 通道**。故 `--tier-variants --shear-pivot` 併用時,
放大後的 wobble 變體會用**放大後的 shear** 算補償 Δ=(M−I)(O−P) → pivot 精確不動,per tier。這是本能力的
真正兌現點,也是 (J)/(G-4') 各自不覆蓋的新面:**檔位愈高 = shear 愈大 = 但 pivot 仍釘死**。

## 自我驗收(`validate_tier_variant_shear.py`,6 AC 全 PASS)

真值/fixture 同 (E/H/I/J/G-4'):先驗庫 → 真實 build_spine robot 骨架 → build_animations 端到端量。

- **L1 present + backward-compat**:每 wobble beat × 每檔位皆產 `wobble__{tier}`、finite/有 bone/≥1 帶
  shear;變體名經 `beat_category` 仍路由回 wobble;base 逐位元不變;**`wobble__Super` 逐位元 == base**。
- **L2 crux 峰單調 + 精確縮放**:每 bone |shearX| 峰 Super<Mega<Omg<Legend 嚴格遞增,且 == 宣告增益 ×
  base 峰(非只單調,是**精確 ×g**)。
- **L3 每檔位簽章 + 介面**:每檔位每 bone shearX 首尾 0、繞 0 變號 ≥3、相繼極值嚴格遞減(阻尼);
  identity 介面(sample rotate/trans/scale 首尾 identity + shear 首尾 0)對所有檔位保持。
- **L4 正交 + 隔離**:(a) **阻尼比 r 對檔位不變**(Super 與 Legend 的相繼極值比序列逐項相同 → 增益只改
  幅度不改結構);(b) shear 隔離:帶檔位建構下,**非 wobble** 的 beat/變體皆 0 bone 帶 shear(增益不注入 shear)。
- **L5 端到端 pivot 不動 / 檔位**:`--tier-variants --shear-pivot`,每檔位 `wobble__{tier}` 凡有關節
  pivot 的 bone,pivot 殘差 < 0.5px(實測 Super 0.013→Legend 0.058px,隨檔位微增但遠 < 門檻),內建負對照
  (未補償繞件中心)16–50px、比值 >800×。證放大後的 shear(至 Legend ~24° 於密網格)仍繞關節精確不動。
- **L6 負對照**:(a) 平增益全 1.0 → L2 單調性 FALSE(證閘真在測遞增);(b) In/Loop/Out 不產 wobble/shear
  變體;(c) 加性:tier_gains=None → 無 `wobble__{tier}` 且 base 相同;移除 wobble storyboard → 其餘 beat
  的檔位變體逐位元不變(零回歸)。

**回歸**:validate_tier_variants(J,scale/rotate 主秀)/tier_combo_count(J-2)/shear_gen(G-4')/
priors 全系列 /beat_templates/cascade/more_beats/pivot_rotation/scale_pivot/shear_pivot/deform_gen/
anim(+selftest)、round-trip `validate_build` 對 `--tier-variants --shear-pivot` build(overall_pass、
premult MAE 0.031、setup 不變)**全 PASS**。

## honest boundary(仍在)

- 斜拉 wobble 形狀 + 增益階梯為 **PROPOSAL**(結構/單調客觀,手感留使用者 A 類)。
- 只作用 shearX(shearY≡0);shearY / 斜拉 squash(shear+coupled scale)未做。
- 運動基元先驗、單一真值資產 → cap `tier_variant_shear` L2 併入 `spine-anim-forge`(**仍 HOLD**,防固化)。

## 結論(可重用)

1. **度量異質的類別 → 平行集合而非塞進同一個閘**:shear 幅度與 scale/rotate 幅度是不同通道,分開列
   `SHEAR_SHOW_CATS` 讓既有 (J) 閘零回歸,新能力有自己的閘。`sample()` 不讀 shear 是這個決策的直接原因。
2. **對 0 對稱的通道,線性增益 `g*v` 對「振盪+遞減」簽章天然保形**:繞 0 變號數與相繼極值遞減比皆不受
   正的 g 影響 → 幅度軸與結構軸正交(同 (J-2) 的正交結論,換到 shear/幅度軸)。
3. **端到端補償對放大幅度免疫**:`apply_pivots` 讀當下通道值,故不論檔位多高,pivot 補償都對得上 →
   「放大幅度 ≠ 破壞不動點」是 Δ=(M−I)(O−P) 對任意仿射 M 成立的直接推論。
