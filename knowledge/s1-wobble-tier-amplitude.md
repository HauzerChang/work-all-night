# S1 (G-4'') — wobble(shear 通道)接 tier 幅度差異化(shear 峰隨檔位遞增)

- **結論**:candidate (G-4') 讓生成器**第一次產出 shear 通道**(斜拉 jelly wobble,阻尼 shearX 擺動);
  candidate (J) 讓主秀 beat 依檔位產**幅度差異化**變體 `{beat}__{tier}`。但 (J) 的 `amplify_bone_tl` 只放大
  **scale/rotate/translate**,**沒碰 shear**,且 wobble **∉ `MAIN_SHOW_CATS`** → wobble 檔位變體**未接**。
  honest boundary:**shear 峰不隨檔位遞增**。本次(G-4'')把那段接上——wobble 納入 `MAIN_SHOW_CATS`、
  `amplify_bone_tl` 對 shear 通道放大(對 0 對稱 `v'=g*v`)→ `wobble__{Super,Mega,Omg,Legend}` 的
  shear 峰 **嚴格遞增**(16°→21.6°→27.2°→33.6°,恰 = base × TIER_GAIN 階梯),且**阻尼振盪簽章逐檔保形**。
- **信心**:高。專屬閘 `validate_wobble_tier.py`(先驗庫 → 真實 build_spine robot 骨架 → build_animations)
  **5 AC 全 PASS**;回歸((J) 幅度-only 閘、(G-4') shear 產出閘、priors/tier/beat/pivot 全系列、
  round-trip `--tier-variants --shear-pivot` build)全綠。
- **相關階段**:第 2 階段(用工具鍛鍊 S1);延續 (E)/(H)/(I)/(J)/(J-2)/(G-4') 的 genre 先驗 → 生成器產線化。

## 為什麼 shear 用「對 0 對稱」放大(而非 scale 的「只放大 identity 上方」)

(J) 對不同通道用不同增益規則,關鍵在**該通道的 identity(setup)值**:
- **scale**:identity=1,語意分**上方 overshoot(大獎強度)/下方樓地板(蓄力深度/藏匿,結構語意)** →
  只放大上方 `v'=1+g(v−1) if v≥1`,下方不動(檔位無關,誠實)。
- **rotate/translate/shear**:identity=**0**,對 0 對稱 → `v'=g*v`。wobble 的 shearX 是**繞 0 的阻尼擺動**,
  沒有「樓地板」語意,整條曲線就是運動幅度本身 → 直接 `g*v` 全放大。

**這個選擇讓兩件事同時成立**(shear 版 tier 差異化的正確性核心):
1. **介面契約保持**:shearX 首尾 = 0,`g*0=0` → 每檔位變體首尾仍 shear=0(且 rotate/scale/translate 本就 0)
   → 仍可無縫插在 Loop 之間(T3)。
2. **阻尼振盪簽章保形**:`g>0` 不改變號序列(繞 0 變號次數不變 ≥3),相繼極值 `[A,−rA,r²A,−r³A]` 同乘 g →
   `[gA,−grA,gr²A,−gr³A]`,**相繼幅度嚴格遞減關係(阻尼)完全保留**(T4)。峰值 = gA 隨 g 單調變大(T2)。

> ⇒ **幅度增益放大的是「擺多大」,不是「怎麼擺」** —— 與 (J) 對 scale/rotate「放大 overshoot 不動樓地板/時間軸」
> 同一哲學的 shear 版:對稱通道整體縮放即可,因為它沒有需要保護的樓地板。

## 端到端量測(crux)

`wobble__{tier}` 的峰 |shearX|(真實 robot 骨架,經 build_animations):

| tier | gain (TIER_GAIN) | measured peak | = base × gain |
|---|---|---|---|
| Super  | 1.00 | 16.0° | 16.0° |
| Mega   | 1.35 | 21.6° | 21.6° |
| Omg    | 1.70 | 27.2° | 27.2° |
| Legend | 2.10 | 33.6° | 33.6° |

**嚴格遞增**(T2),且測得峰 == base × 階梯(增益端到端存活到關鍵幀,誤差 0)。base=特效 role(光暈)
`_WOBBLE_SHEAR["特效"]=16°`;Legend 33.6° 幾何合法(pure shearX φ 的 `det=cos φ`,cos 33.6°=0.83>0,無翻面)。

## 實作(全 additive,向後相容逐位元)

- `tier_variants.py`:
  - `MAIN_SHOW_CATS` 加 `"wobble"` → build_animations 對 wobble 也產檔位變體。
  - `amplify_bone_tl` 加 `shear` 迴圈:`f["x"]=round(g*f["x"],4)`、`f["y"]=round(g*f["y"],4)`(對 0 對稱)。
  - **base=Super g=1.0 → `amplify` 為 identity → `wobble__Super` 逐位元 == base wobble**(T5b,向後相容)。
- `validate_tier_variants.py`(J 閘):J3 單調性改**通道感知** —— 加 `_shear_amp`,對「該 beat 實際使用」
  的每個通道(scale/rotate/shear,`max amp>TOL`)要求嚴格遞增,且至少一通道有運動。scale/rotate beat 不受影響
  (仍要求遞增);wobble(只有 shear)不再假陰性。J 全綠且新增 `wobble` 行 shear_amp [16,21.6,27.2,33.6]。

## 專屬閘 `validate_wobble_tier.py`(5 AC)

- **T1 present+routing+BC**:每檔位產 `wobble__{tier}` finite/有 bone/帶 shear;`beat_category` 仍路由回 wobble;
  `tier_gains=None` → 不產 wobble 變體;base wobble 本體逐位元不變。
- **T2 crux shear-peak mono**:峰 |shearX| Super<Mega<Omg<Legend 嚴格遞增;比值 ≈ TIER_GAIN 階梯(RATIO_TOL 0.02)。
- **T3 interface kept /tier**:每檔位 sample(0)/sample(dur) rotate/scale/translate identity + shear 首尾 0。
- **T4 damped-osc kept /tier**:每檔位 shearX 繞 0 變號 ≥3 且相繼極值嚴格遞減(復用 G-4' 閘的判準)。
- **T5 orthogonality/neg**:(a)平增益守衛(全 1.0 → 峰單調 FALSE,證閘真在測遞增);(b)`wobble__Super` byte-identical
  base wobble;(c)**shear 隔離存活於 tiering**——帶 tier_gains 時非 wobble 主秀變體(hit/burst/combo…__tier)
  仍 0 bone 帶 shear(放大只作用 wobble 的 shear)。

## 關鍵發現 / 踩雷

- **加 wobble 到 `MAIN_SHOW_CATS` 會讓 (J) 閘假陰性**:J3 原只量 scale_overshoot / rotate_amp,對只有 shear 的
  wobble 兩者皆 0 → `is_strictly_increasing([0,0,0,0])=False` → J 假 FAIL。修法=J3 **通道感知**(見上),
  對「使用中的通道」才要求遞增。**教訓**:把新運動通道併進既有幅度框架時,量測面也要一起泛化,否則
  gate 對新通道回報假陰性(而非真的檢出問題)。
- **對稱通道縮放天生保簽章**:shear/rotate/translate 這類繞 0 的通道,`g*v` 縮放對「變號序列 + 相繼幅度比」
  皆保形 → 阻尼/振盪/相位等**時序結構簽章**免費保留,只有幅度變。與 scale(需保護樓地板)不同。

## honest boundary(仍在)

- 斜拉 wobble 形狀、TIER_GAIN 階梯值仍為 **PROPOSAL**(結構簽章客觀、手感留使用者 A 類)。
- 仍只產 shearX(shearY≡0);wobble 峰隨檔位遞增用的是與 (J) **同一組** `TIER_GAIN`(未為 shear 另立階梯)。
- cap `wobble_tier_amplitude` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。

## 續(擇一,皆自主)

- (G-4''') 產 shearY / 斜拉 squash(shear + coupled scale;此時兩通道增益規則須各自套=scale 只放上方、shear 對稱);
- wobble 接 count-aware(擺動「次數」隨檔位增,比照 (J-2) combo nhits;需 gen_wobble 帶可變擺動段數重生成);
- (J-3) cascade 波速/散佈/件數隨檔位。

圖:`figures/s1_wobble_tier.png`(左:各檔位 shearX(t) 阻尼擺動疊圖;右:峰 |shearX| 隨檔位遞增 == base×階梯)。
