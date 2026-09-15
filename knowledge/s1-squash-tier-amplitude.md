# S1 (G-4''''') squash 接檔位幅度差異化 —— **體積守恆耦合 amplify**

> candidate G-4'''''(2026-09-15)。續 G-4''''(squash 生成器)。補上 G-4'''' 留下的 honest boundary:
> **「squash 未接 tier 幅度(需耦合 amplify:scaleX/scaleY 一起以體積守恆放大,不破壞 scaleX·scaleY==1)」**。

## 一句話

squash(斜拉果凍擠壓)的 scale 通道是**體積守恆耦合對**(scaleX·scaleY≡1、scaleX≠scaleY)。天真的
`_amp_scale`(僅放大 identity 上方 overshoot)會放大 scaleX>1、卻讓 scaleY<1 的壓扁樓地板不動 → **破壞
面積守恆**。本次以**耦合 amplify**(log 空間 `v' = v**g`)把 squash 併入 `MAIN_SHOW_CATS`,使**擠壓幅度
與 shear 峰隨檔位嚴格遞增**,而**體積守恆在每個檔位精確保持**。

## 為什麼是這一步(補的 honest boundary)

- **(J)** `tier_variant_amplitude`:主秀 beat 依檔位幅度差異化,但增益只作用 scale(上方 overshoot)/rotate/translate。
- **(G-4'')** `wobble_tier_amplitude`:把 wobble 的 **shear** 峰接上檔位(shear 對 0 對稱 → `v'=g*v`)。
- **(G-4'''')** `squash_shear_scale_coupling`:生成器第一次產**耦合 shear + 非均勻 scale**;但當時
  **squash 刻意留在 MAIN_SHOW_CATS 之外** —— 因為它的 scale 是體積守恆對,套天真 `_amp_scale` 會破壞守恆。
- **本次(G-4''''')**:補上這個缺口 —— 設計出**不破壞體積守恆的 amplify**,才能讓「檔位愈高擠壓愈強」。
  又一「檔位機制就緒 ≠ 每個新通道接上」實例(同 E/H/I/J/G-4'/G-4''/G-4''')。

## 關鍵洞見:體積守恆的 amplify = **log 空間線性放大**

體積守恆 = 乘性約束 `scaleX·scaleY = 1`,在 **log 空間**即加性約束 `ln scaleX + ln scaleY = 0`
(兩軸 log 對 0 對稱)。要「放大擠壓強度但仍守恆」= 把 log 值乘以增益 g(保持和 = 0):

```
_amp_scale_coupled(v, g) = v ** g          # log 空間: ln v' = g · ln v
```

- 對體積守恆對 `(s, 1/s)`:`s**g · (1/s)**g == (s · 1/s)**g == 1**g == 1` → **積精確守恆**(逐項獨立套用即可,無需成對處理)。
- `|ln v'| = g·|ln v|` → 擠壓幅度隨 g **單調放大**(檔位愈高擠壓愈強)。
- `identity (v=1) → 1**g == 1`(介面契約保持,可插 Loop)。
- 等比對 `(v, v) → (v**g, v**g)` **仍等比**(不憑空造非均勻;見 ST5(c) 守衛)。
- `g=1.0 → v**1.0 == v` → identity 變換(向後相容;`round(..., 4)` 消去 pow 浮點殘差保 byte-identical)。

這是 rotate/shear 的**加性** `v'=g*v`(對 0 對稱)在**乘性體積守恆約束**下的自然對應。三種幅度軸各得其所:

| 通道 | 對稱點 | 約束 | amplify |
|---|---|---|---|
| rotate / translate / shear | 0 | 無 | `v' = g·v`(加性) |
| scale(hit/combo/… 等比 overshoot) | identity=1 | 僅放大上方樓地板不動 | `v' = 1 + g·(v−1) if v≥1` |
| **scale(squash 體積守恆對)** | identity=1 | **積 = 1** | **`v' = v**g`(log 線性)** |

## 實作(全 additive、確定性)

- `tier_variants.py`:
  - `squash` 加入 `MAIN_SHOW_CATS`;新增 `COUPLED_SCALE_CATS = {"squash"}`。
  - 新增 `_amp_scale_coupled(v, g) = v**g`。
  - `amplify_bone_tl(b, g, coupled_scale=False)` / `amplify_anim(anim, g, coupled_scale=False)`:
    `coupled_scale=True` 時 scale 走耦合路徑,shear/rotate/translate 兩路徑相同(`v'=g*v`)。
- `gen_animations.build_animations`:squash 檔位變體以 `coupled_scale=(cat in COUPLED_SCALE_CATS)` 路由
  (squash → True)。squash **非** count-aware(段數 count-aware 為後續);故走「amplify base 變體」路徑。

## 端到端量測(真實 robot 骨架,`_光暈` bone,特效 Q=0.16、A=16°)

| tier | g | stretch peak\|scaleX−1\| | shear peak (°) | scaleX·scaleY(4 極值) |
|---|---|---|---|---|
| Super | 1.00 | 0.160 | 16.0 | ~1.0000(≤1.3e-4) |
| Mega | 1.35 | 0.222 | 21.6 | ~1.0000 |
| Omg | 1.70 | 0.287 | 27.2 | ~1.0000 |
| Legend | 2.10 | 0.366 | 33.6 | ~1.0000 |

擠壓幅度與 shear 峰皆嚴格遞增;體積守恆殘差 ≤1.3e-4 ≪ TOL_VOL(0.02)於所有檔位。Super==base(向後相容)。

## 自我驗收閘 `validate_squash_tier.py`(5 AC 全 PASS)

- **ST1** present + backward-compat:每檔位 `squash__{tier}` 產出/finite/有 bone/≥1 bone 同帶 shear+scale/
  名路由回 squash;所有 base beat 帶/不帶 tier_gains 逐位元不變。
- **ST2 crux**:擠壓峰 |scaleX−1| **與** shear 峰 |shearX| 皆 Super<Mega<Omg<Legend 嚴格遞增,Super==base。
- **ST3 crux**:**每個檔位**每個 scale 極值幀 (a)scaleX·scaleY≈1(守恆)、(b)非均勻 |scaleX−scaleY|≥0.05、
  (c)擠壓幅度隨極值嚴格遞減(阻尼)、(d)shear 阻尼振盪(繞 0 變號≥3 + 遞減)—— 耦合 amplify 同比放大 → 三簽章保形。
- **ST4**:每檔位 shear 首尾 0 + scale 首尾 (1,1)(可插 Loop)。
- **ST5 neg-control**:(a)平增益全 1.0 → ST2 遞增 FALSE 且各檔位逐位元 == base;
  **(b) crux 天真放大守衛**:同一 base squash bone 用天真 `_amp_scale`(coupled_scale=False)於 Legend g=2.1
  放大 → 積 [1.152, 1.081, 1.042, 1.022] **體積守恆 FALSE**;耦合版同資料 → 積 ≈1.0 **守恆 TRUE**
  ——**證耦合 amplify 是必要的、且本閘偵測得到該破壞**;(c)耦合 amplify 單元測(等比→仍等比、守恆對→積仍==1)。

## 回歸

- 18 閘全綠:squash_tier(新)/squash_gen/wobble_count/wobble_tier/tier_variants(J)/**tier_combo_count(J-2)**/
  shear_gen/shear_pivot/scale_pivot/pivot_rotation/priors/priors_beats/priors_combo_charge/priors_cascade/
  cascade/more_beats/beat_templates/deform_gen。
- round-trip `validate_build` 對 `--tier-variants --shear-pivot` build overall_pass(premult MAE 0.031)。
- ⚠️ **修了 J-2 閘的一個 proxy**:`validate_tier_combo_count` K5(c)「count 隔離」原以「非-combo beat 峰數各檔位
  不變」為 proxy;squash 加入主秀後,其 scaleX 擠壓峰隨**幅度**增益成長會跨越 `IMPACT_PROM`(1.10)門檻 →
  峰數隨檔位變(head base 峰恰 1.10:Super 1.10 不計、Mega+ >1.10 計 → [0,1,1,1])。那是**幅度效應非 count
  外洩**。改為直接比對「帶 tier_combo_hits」vs「幅度-only」兩份 build 的非-combo 變體逐位元相同 —— 精準測
  **count 機制**的隔離,不受幅度門檻跨越干擾(閘更正確)。

## 新增 cap

`squash_tier_amplitude` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。

## honest boundary(仍在)

- squash **count-aware**(擠壓段數 nosc 隨檔位遞增)為後續:`gen_squash(nosc=)` 參數已備、耦合 amplify 與
  段數軸正交(比照 G-4''' 對 wobble、J-2 對 combo);本次只做**幅度軸**(nosc 固定 4)。
- `shearY≡0`(雙軸 shear 為後續 G-4'''''');擠壓幅度階梯沿用 (J) 增益(PROPOSAL,手感留使用者 A 類)。

見圖 `knowledge/figures/s1_squash_tier.png`(4 子圖:耦合 scale/守恆殘差/雙峰遞增/天真-vs-耦合負對照)。
