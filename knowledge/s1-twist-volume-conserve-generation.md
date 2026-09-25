# S1 volume-conserving twist:反相雙軸 shear + 均勻體積守恆 scale(擰而不變面積)

> candidate **G-4''''''-vol**(2026-09-25 run 001)。cap `twistvol_volume_conserve` L2 → `spine-anim-forge`(仍 HOLD)。
> 閘 `tools/analyzer/validate_twist_vol.py`(7AC 全 PASS)。回歸 23 閘全綠(22 + 新 twist_vol),0 RED。

## 補的 honest boundary

twist(G-4'''''')是**反相雙軸阻尼 shear**(shearX + 反相 shearY),但**純 shear 會改變面積**。
Spine local bone 的 2×2 行列式:

```
det(M) = scaleX · scaleY · cos(shearX − shearY)     （與 rotate 無關,rotate 為正交 det=1）
```

twist 令 scaleX=scaleY=1、shearY=−φ·shearX(φ=TWIST_PHI=0.7)⇒

```
det = cos(shearX − shearY) = cos((1+φ)·shearX)  < 1
```

body 峰 shearX=16° → (1+0.7)·16 = 27.2° → det = cos27.2° = **0.889**(擰轉峰值時面積收縮 ~11%;
head 最小軸亦 ~8.5%)。這是 twist 一直帶著的 honest boundary(「反相雙軸未接體積守恆耦合 scale」)。

## 解法:均勻體積守恆 scale（crux 與 squash 的區別）

對反相雙軸 shear 每幀施**均勻** scale:

```
scaleX = scaleY = s(τ) = 1 / √( cos(shearX(τ) − shearY(τ)) ) = 1 / √( cos((1+φ)·shearX(τ)) )
⇒ det = s² · cos(shearX − shearY) ≡ 1        （面積守恆）
```

首尾 shearX=shearY=0 → cos(0)=1 → s=1 → scale 首尾 (1,1)(**identity 介面保持**,可插 Loop 間)。

**crux —— 為什麼 twist 用「均勻」而 squash 用「非均勻」**:

| 節拍 | shear | 面積虧損來源 | 守恆 scale 型態 |
|---|---|---|---|
| squash(G-4'''') | 單軸 shearX | 想做「擠壓」(拉一軸壓一軸的**各向異性**形變) | **非均勻** scaleX=1+q、scaleY=1/(1+q)(scaleX≠scaleY) |
| **twistvol(本次)** | 反相雙軸 shearX+shearY | `cos(shearX−shearY)` 是**各向同性**的行列式虧損(不偏好任何軸) | **均勻** scaleX=scaleY=1/√cos(不改長寬比) |

各向同性的行列式虧損,補回它最乾淨的方式就是各向同性(均勻)地放大兩軸 —— 不引入 squash 那種
長寬比改變。**「守恆的 scale 型態由虧損的對稱性決定」** 是本次最一般化的發現。

至此**一般仿射 M 的四自由度(rotate / 均勻或非均勻 scale / shearX / shearY)可同時被生成器產且面積守恆**:
- rotate:0i / G-4 pivot(det=1 天生守恆)
- 非均勻 scale + shearX(各向異性)守恆:squash(非均勻耦合)
- **反相雙軸 shearX+shearY(各向同性)守恆:twistvol(均勻耦合)← 本次**

## 實作(全 additive,零回歸)

- `beat_templates.gen_twistvol(role, side_sign, radial, nosc=4)`:shear 通道**逐鍵完全同 `gen_twist`**
  (scale 純加性,不擾動 shear;TV4(a) 單元逐鍵比對驗證),另加 `scale` 通道每幀
  `x=y=_twistvol_scale(shx,shy)=1/√cos(shx−shy)`。`DUR["twistvol"]=0.8`。`TWISTVOL_KEYWORDS`(不含裸
  'twist',避免與 twist 爭用)。
- `gen_animations`:`_DISPATCH["twistvol"]=gen_twistvol`;`_CAT_KEYWORDS` 把 twistvol 置於 twist 前
  (exact token 'twistvol' 不與 twist 關鍵字相等 → `beat_category('twistvol')` 由 exact 迴圈命中 twistvol)。
- `genre_priors.slot_bigwin`:加 twistvol beat + roles(additive;Award 真值僅 In/Loop/Out → 列
  `prior_beats_unused`,覆蓋率仍 1.0,誠實 PROPOSAL)。
- `tier_variants`:twistvol 併入 `SHEAR_CATS`(合法 shear 產出者,各 shear-isolation 閘認定);
  新增 `SHEARY_CATS = {"twist","twistvol"}`(合法 **shearY** 產出者,集中一處便於後續再加)。
- `validate_twist_gen` TW6(c)「shearY 隔離」改以 `SHEARY_CATS` 認定(原硬編碼 `== "twist"`,加 twistvol
  後會誤判 twistvol 的 shearY 為洩漏;precedent 同 squash/twist 加入 SHEAR_CATS 時的集中化)。
- `build_spine --shear-pivot` **無需改**:`apply_pivots(include_shear=True)` 隱含 `include_scale`,已把
  rotate/scale/shearX/shearY 一起繞關節 pivot 補償(twistvol 同時帶 shear+scale,天然被涵蓋)。

## 閘 `validate_twist_vol.py`(7AC，真值 = robot_parts.psd ⇄ Award 骨架)

- **TV1** present + 雙軸 + scale 產出:shearX 峰 16°、shearY 峰 11.2°(≠0)、補償峰 |s−1|=0.060。
- **TV2** 體積守恆(crux):每關鍵幀 |det−1| ≤ 2e-3(**實測 1e-6**);內建負對照 = 同 shear 但 s≡1(純
  twist)峰值 det=**0.889** < 1−0.02(證閘測守恆,非「有 scale 即可」)。
- **TV3** 均勻 scale(crux vs squash):每幀 scaleX==scaleY(|Δ|≤1e-6);內部極值 s≥1(補償放大)、
  |s−1| 隨極值嚴格遞減(隨 shear 阻尼)。
- **TV4** twist 全簽章保形:(a)twistvol shear 通道逐鍵同 `gen_twist`;(b)兩軸各自阻尼振盪(繞 0 變號≥3
  + 相繼極值遞減);(c)每內部極值反相 shearX·shearY<0;(d)φ=shearY峰/shearX峰≈0.7。
- **TV5** identity 介面:sample(0)/sample(dur) identity;shear 首尾 (0,0)、scale 首尾 (1,1)。
- **TV6** 端到端一般仿射 pivot 不動:`build_spine --shear-pivot` 真實 robot,**在 shearY≠0 且 scale≠1
  同時驅動下** pivot 殘差 <0.02px(右手 0.013 / 頭 0.004 / 左手 0.016)vs 負對照(繞件中心)8.6–29.5px(>1000×)。
- **TV7** 負對照/隔離:(a)純 twist(s≡1)→ 守恆 FALSE;(b)非均勻 scale(squash 樣)→ 均勻 FALSE;
  (c)shearY 隔離到 SHEARY_CATS;(d)加性:移除 twistvol → 其餘 beat 逐位元不變。

端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 `twistvol`(單一 beat,**無 tier 變體**
—— honest boundary,見下);`validate_build` round-trip overall_pass(premult MAE 0.031)。

## honest boundary（仍在，下一步候選）

- **twistvol 未接 tier 幅度 / count-aware**:單一 g 放大兩軸 shear 會改變 det(det=cos((1+φ)·g·shearX)),
  故 scale 須**重算** s'=1/√cos((1+φ)·g·shearX) 而非 g 放大既有 scale —— 需 twistvol **專屬耦合 amplify**
  (比照 squash 的 `_amp_scale_coupled`,但均勻版且與 shear 增益連動)。此為後續(比照 wobble/squash/twist
  各自的 tier→count 分階段)。
- 幅度 / φ 為 **PROPOSAL**(結構簽章客觀,手感留使用者 A 類);單一真值資產(robot rig)。
- 與 `spine-anim-forge` 同 **HOLD**(運動基元為先驗手感、非學自真值,達 L3 前不打包)。
