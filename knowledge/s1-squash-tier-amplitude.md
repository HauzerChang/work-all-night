# S1 — squash 接檔位幅度差異化(耦合體積守恆放大)(candidate G-4''''')

> 日期 2026-09-19。cap `squash_tier_amplitude` L2(併入 `spine-anim-forge`,仍 HOLD)。
> 閘:`tools/analyzer/validate_squash_tier.py`(5 AC 全 PASS)。

## 補的缺口(G-4'''' 明列的 honest boundary)

G-4''''(`gen_squash`)是第一個同時產 **shear + 非均勻 scale**(體積守恆擠壓)的生成器,但當時
明列 honest boundary:**「squash 未接 tier 幅度」**。原因是一般幅度增益 `_amp_scale`(candidate J)
只放大 identity **上方**的 overshoot(`v'=1+g(v−1)` 僅當 `v≥1`;下方 squash/collapse 樓地板不動):

- squash 每極值 = `scaleX=1+q`(拉長,>1)、`scaleY=1/(1+q)`(壓扁,<1)、`scaleX·scaleY≡1`。
- 套 `_amp_scale`:scaleX>1 被放大、scaleY<1 **不動** → 兩軸增益不對稱 → **體積守恆壞掉**
  (`scaleX'·scaleY'≠1`)。實測 Legend g=2.1 下 |積−1|≈**0.152**(見 S5b 負對照)。

故 squash 當時無法進 `MAIN_SHOW_CATS`(進了就會被 `amplify_bone_tl` 破壞守恆),沒有檔位變體。

## 解法:對 scale 通道**耦合放大**(volume-preserving coupled amplify)

`tier_variants._amp_squash_scale(scaleX, g)`:以 `q=scaleX−1` 為擠壓量,`q'=g·q`,回傳
`scaleX'=1+q'`、`scaleY'=1/(1+q')`。

- ⇒ `scaleX'·scaleY'≡1`(**體積守恆對所有檔位保持**,由建構式保證,非靠巧合)。
- ⇒ `scaleX'≠scaleY'`(非均勻仍在;擠壓量 q 隨 g 放大)。
- `q=0` 幀(首尾 identity)→ 仍 `(1,1)`(**介面契約保持**,可插 Loop 間)。
- `g=1.0` → **逐位元同 base**(向後相容;因 Q·rⁱ 諸值 ≤4 位小數,round 穩定,見閘 S1)。

shear 通道同 wobble(`v'=g·v`,阻尼振盪簽章保形);rotate/translate 亦 `v'=g·v`(squash 無此二通道)。
`amplify_squash_bone_tl` / `amplify_squash_anim` 包裝之。

## 路由:COUPLED_AMP_CATS(不入 MAIN_SHOW_CATS)

squash 因需**耦合** amplify,**故意不入** `MAIN_SHOW_CATS`(避免被 J 的 `amplify_anim` 破壞守恆,
也避免擾動 J/tier 系列閘對 MAIN_SHOW 的認定)。改新增 `tier_variants.COUPLED_AMP_CATS={"squash"}`,
`build_animations` 對此集合的 beat 走 `amplify_squash_anim`(與 MAIN_SHOW 的 `amplify_anim` 互斥,擇一)。
增益階梯沿用 `TIER_GAIN`(Super1.0/Mega1.35/Omg1.70/Legend2.10)—— squash 的「愈爆」與其他主秀同軸。

## 結果(端到端:先驗庫 → 真實 build_spine robot 骨架 → build_animations)

| tier | 擠壓量 q 峰 | shear 峰(°) | 體積 |scaleX·scaleY−1| 峰 |
|---|---|---|---|
| Super(=base) | 0.16 | 16.0 | ≤5e-5 |
| Mega | 0.216 | 21.6 | ≤5e-5 |
| Omg | 0.272 | 27.2 | ≤5e-5 |
| Legend | 0.336 | 33.6 | ≤5e-5 |

兩通道(shear + 非均勻 scale)**雙雙隨檔位嚴格遞增**,體積守恆與非均勻與首尾 identity 在每檔位保持。

## 5 AC(`validate_squash_tier.py`)

- **S1 present + backward-compat**:base squash 帶 shear+非均勻 scale;每 `squash__{tier}` finite/有 bone/
  ≥1 bone 同時帶 shear 與 scale/名經 `beat_category` 仍路由回 squash;base(含 In/Loop/Out)逐位元不變。
- **S2 crux — 擠壓量遞增**:峰 q Super<Mega<Omg<Legend 嚴格遞增,Super==base。
- **S3 crux — 體積守恆@所有檔位**:每極值幀 |scaleX·scaleY−1|≤TOL_VOL + 非均勻峰≥MIN_ANISO +
  首尾 scale==(1,1) 且 shearX==0(介面)。
- **S4 shear 遞增 + 阻尼保形**:峰 |shearX| 亦遞增;每檔位首尾 0 / 繞 0 變號≥3 / 相繼極值遞減(阻尼)。
- **S5 負對照**:(a) 平增益 1.0 → S2 遞增 FALSE 且各檔位逐位元 == base;(b) **破壞守恆守衛** —— 一般
  `amplify_bone_tl` 對 squash bone 體積 err **0.152 ≫ TOL** 而耦合 `amplify_squash_bone_tl` err **4e-5 ≤ TOL**
  → 證**耦合 amplify 必要**且閘抓得到破壞。

## 關鍵發現 / 誠實限制

- **squash 的『幅度軸』=雙軸一起以體積守恆放大**:shear(對 0 對稱直接放大)+ 非均勻 scale(q 耦合放大)。
  這與 wobble(G-4'',單一 shear 幅度軸)不同 —— squash 的兩通道**耦合**,不能各自獨立放大。
- 至此 squash 的**幅度軸**完成;**結構軸**(count-aware:擠壓段數 nosc 隨檔位,`gen_squash(nosc=)` 參數已備)
  為後續,比照 (G-4''') wobble count-aware。兩軸正交可疊(同 J×J-2、G-4''×G-4''')。
- 增益階梯數值(1.0/1.35/1.70/2.10)為 PROPOSAL(結構簽章非美感;手感留使用者 A 類)。
- shearY≡0(單軸 shear);單一真值資產(main_draw 唯一含 mesh deform,robot 為合成 rig)。與 anim-forge 同 HOLD。

## 產出/更新檔案

- 新增:`tools/analyzer/validate_squash_tier.py`、本檔。
- 更新:`tools/analyzer/tier_variants.py`(`COUPLED_AMP_CATS`/`_amp_squash_scale`/`amplify_squash_bone_tl`/
  `amplify_squash_anim`)、`tools/analyzer/gen_animations.py`(build_animations 路由 COUPLED_AMP_CATS)、
  `tools/check_readiness.py`(註冊 cap)、`STATE.md`、`knowledge/README.md`、`skills/READINESS.md`。
