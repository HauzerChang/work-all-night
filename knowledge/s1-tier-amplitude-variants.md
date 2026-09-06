# S1 (J) — tier(檔位)變體幅度差異化(`build_spine --animate --tiers` 直出各檔位遞增幅度)

> 里程碑 2026-09-06(claude/focused-dirac-mzum4e)。續 (E)/(H)/(I) 把主秀 beat 接進先驗庫之後,
> 補上先驗庫早已宣告、卻一直未被生成器使用的維度:**檔位(tier)**。讓
> `build_spine --animate --tiers` 對主秀節拍依檔位序位產出**差異化幅度**的變體,
> 愈高檔位主秀愈誇張。

## 動機 / 缺口

`genre_priors.slot_bigwin` 從一開始就宣告 `tiers = [Super, Mega, Omg, Legend]`(對齊真實 Award
的 `Award_<Tier>_In/Loop/Out` 命名),但這欄位至今**只是 metadata**:`analyze_target.build_storyboard`
把它塞進 `tier_variants` 供人看、`validate_priors` / `validate_analyzer_award` 拿它對真值檔名做召回,
**生成器(`build_animations`)完全不看它** —— 所有檔位共用同一組 beat 幅度。這是「先驗宣告 ≠ 生成器
使用」的又一實例(與 (E)/(H)/(I) 的「模板就緒 ≠ 生成器接上」同型,只是這次缺的維度是檔位)。

大獎演出的直覺:Legend(最高檔)的主秀該比 Super(最低檔)**更誇張**——更大的 pop、更狠的甩、
更深的蓄力。這是**客觀可量**的(幅度單調遞增),而「該多誇張才貼手感」才是主觀(留使用者 A 類)。

## 機制:單參數幅度增益,對幾何 excursion 一致縮放

核心是 `beat_templates.py` 新增的 `apply_tier_gain(b, s, g)`:對**單件**的 timeline,把**幾何
excursion**依增益 `g` 一致縮放:

- `scale` : 對 identity=1 縮放 `v → max(0, 1 + (v−1)·g)`(clamp≥0:reveal 起始的 collapsed
  `~0.02` 是**向下** excursion,放大後可能 <0,夾 0 仍= 隱藏,合法)。
- `rotate` / `translate` : 對 0 縮放(`×g`)。
- `color`/`alpha` : **不動** —— 呈現/閃光通道,與「幅度」正交,且保 reveal 的 collapsed→identity
  alpha 介面不被破壞。

增益曲線 `g = 1 + STEP·序位`(`TIER_STEP = 0.35`):**Super 1.0 / Mega 1.35 / Omg 1.70 / Legend 2.05**。

### 兩個不變量**自動**成立(所以不必改任何 `gen_*` 模板)

1. **介面契約保留**:identity 幀不受 `g` 影響(`scale==1 → 1+(1−1)g = 1`;`rotate/translate==0 → 0·g = 0`)。
   故首尾/hold 的 identity 仍精確 identity,reveal 的 collapsed 起點仍保持隱藏 → 各檔位變體仍可與
   In/Loop/Out 無縫串接。
2. **結構簽章保留**:一致縮放 excursion **不改變峰的相對次序/數目/時刻**。combo 的「遞增峰數」、
   charge 的「峰前蓄力時間佔比」、cascade 的「各件峰時刻」、hit 的「單峰」全是次序/時刻/佔比量,
   對正向縮放不變 → 放大不會把一個 beat 變成另一個 beat 的簽章。

### `g == 1.0` 是逐位元 no-op

`apply_tier_gain` 在 `g==1.0` 時直接回傳(不動 timeline)。因此:
- **Super(序位 0 → g=1.0)clip 與未分檔 build 的該 beat 逐位元相同**。
- `build_animations(..., tiers=False)`(預設)完全走原路徑,產出與分檔前**逐位元相同** → 既有閘全數不受擾。

## 產線接法(opt-in,default off)

`build_animations(skeleton, storyboard, tiers=False)`:
- `tiers=False`(預設):每 beat 一支 clip,名=beat 名(與分檔前相同)。
- `tiers=True` 且 storyboard 宣告 `tier_variants`:**主秀**(`_TIERABLE =
  {hit, reveal, combo, charge, cascade}`)beat 依各檔位增益 `g` 產出**每檔位一支** clip,名
  `<beat>_<Tier>`(如 `hit_Super … hit_Legend`);**非主秀** beat(In/Loop/Out=結構入場/待機/退場)
  仍單支、名不變(結構節拍不隨檔位放大)。

CLI:`build_spine.py --animate --tiers`(亦 `gen_animations.py --tiers`)。

## 驗收閘 `validate_tier_variants.py`(5 AC 全 PASS)

從 **genre 先驗庫** 經 `analyze_target.build_storyboard`(真實 robot 5 拆件 role + 件序)→
**真實 `build_spine` 骨架** → `build_animations(tiers=True)`:

- **J1 present+routing**:每主秀 beat 恰產 `len(tiers)` 支 `<beat>_<Tier>`,各路由到正確類別;
  In/Loop/Out 仍單支、無 `_Tier` 後綴。
- **J2 幅度單調遞增**:每主秀 beat 的 **pop overshoot 幅度**(各 bone `max_t scaleX − 1` 取最大)依
  宣告檔位序**嚴格遞增**;且**量化增益吻合** —— Legend/Super excess 比 = **2.05** = `g_Legend`(證是真實
  幾何增益,非任意數);rotate 幅度亦非遞減。
  - ⚠️ 度量用**正向 overshoot**(`max scaleX − 1`)而非 `|scaleX−1|`:reveal 的 collapsed 起點(向下、
    放大後 clamp 飽和)不是「愈高檔位愈誇張」的主秀幅度,真正隨檔位放大的是**向上的 pop**。這是本次
    踩到並修正的度量陷阱。
- **J3 介面契約(逐檔位)**:每檔位變體仍保 setup identity 介面——hit/combo/charge/cascade 首尾
  identity;reveal(burst)首 collapsed(alpha≈0)尾 identity。
- **J4 結構簽章(逐檔位)**:放大**不跨越**簽章——combo 仍遞增峰≥3、charge 仍長蓄力佔比≥0.35 且
  squash(峰前最低 >0.5,非塌陷)、cascade 仍跨件峰時刻遞增+散佈、hit/burst 仍**非** combo/charge。
- **J5 regression+負對照**:(a) Super clip 與未分檔 build 逐位元相同、In/Loop/Out 分檔前後逐位元相同;
  (b) `tiers=None` 的 genre(slot_reveal)以 `tiers=True` build **產 0 支** `_Tier` clip(fallback 單支);
  (c) 鑑別力:各檔位峰值**全相異**(真差異化非共用)且依宣告序遞增(降序排序≠宣告序 → 方向有意義)。

回歸:`validate_priors` / `validate_priors_beats` / `validate_priors_combo_charge` /
`validate_priors_cascade` / `validate_beat_templates` / `validate_more_beats` / `validate_cascade` /
`validate_pivot_rotation` / `validate_scale_pivot` 全 PASS;round-trip `validate_build` 與
`validate_anim`(+selftest)對 `--animate --tiers` build 全 PASS(setup pose 不變、loop 無縫、beat 串接)。

## 關鍵發現

1. **「先驗宣告 ≠ 生成器使用」** —— `tiers` 欄位宣告已久卻從未驅動幾何,與 (E)/(H)/(I) 的「模板就緒 ≠
   生成器接上」同型;把宣告接上生成器又推進一步。
2. **保結構的一致縮放** —— 對 excursion 一致縮放(scale 繞 identity、rotate 繞 0)讓幅度變成單旋鈕,
   而介面契約與結構簽章**自動**保留(identity 是縮放不動點、次序/時刻對正向縮放不變),故不必改任何模板、
   `g=1.0` 逐位元 no-op 使既有閘零風險。
3. **度量陷阱:reveal 的 collapsed 是結構性向下 excursion,非主秀幅度** —— 用 `|scaleX−1|` 會被 collapse
   主宰且 clamp 飽和;改用正向 pop overshoot 才量到真正隨檔位放大的主秀幅度(J2/J5 初版即因此抓到並修正)。

## 誠實界定

- 主秀運動仍是**先驗手感**(非學自真值);檔位→幅度增益曲線(`STEP=0.35` 線性)是**提案**——
  Award 各檔位的幅度差**無量化真值**(真值檔僅名字帶檔位,無「Legend 比 Super 大多少」的可量對照),
  故驗的是**客觀性質**(單調遞增、量化增益吻合設定、介面/簽章保結構),非美感。
- 單一真值資產(Award robot);與 `spine-anim-forge` 同 **HOLD**(運動基元為手感先驗、防固化)。

## 檔案

- `tools/analyzer/beat_templates.py`:`TIER_STEP` / `tier_amp_gain` / `tier_gain_for` / `apply_tier_gain`。
- `tools/analyzer/gen_animations.py`:`build_animations(..., tiers=False)` + `_TIERABLE` + `_build_beat_clip`/`_pack`。
- `tools/analyzer/build_spine.py`:`build(..., tiers=False)` + `--tiers` CLI。
- `tools/analyzer/validate_tier_variants.py`:5 AC 整合閘。
- 圖:`knowledge/figures/s1_tier_variants.png`。
- cap:`tier_amplitude_variants` L2,併入 `spine-anim-forge`(仍 HOLD)。
