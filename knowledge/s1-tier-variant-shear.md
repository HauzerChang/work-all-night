# S1 wobble shear 峰隨檔位遞增 — candidate G-4''

> 里程碑 2026-09-10。把 G-4'(第一個產 shear 的生成器 `gen_wobble`)接上檔位(tier)幅度差異化:
> 斜拉 jelly wobble 的 **shear 峰隨檔位(Super→Legend)單調遞增**,而首尾 0 介面契約與阻尼振盪
> 簽章對所有檔位保形。補上 (J) 幅度差異化「只覆蓋 scale/rotate/translate、漏了 shear」的缺口。

## 動機:又一個「模板/宣告就緒 ≠ 生成器接上」

兩段各自完成、卻沒接在一起:

- **(J) tier_variant_amplitude**(2026-09-07):主秀 beat 依檔位產 `{beat}__{tier}` 幅度變體,
  但 `amplify_bone_tl` 只處理 **scale/rotate/translate** 三通道。
- **(G-4') shear_channel_generation**(2026-09-08):`gen_wobble` 成為**第一個產 shear 通道**的
  生成器,但其 honest boundary 明說 **wobble ∉ `MAIN_SHOW_CATS` 且 tier 變體未接**。

合起來的缺口:wobble 是唯一由 **shear** 驅動的節拍,但 (J) 的增益機制看不到 shear → 就算把 wobble
納入主秀,檔位變體的斜拉幅度也**全部一樣**。G-4'' 補上這最後一段。

## 修法(兩處,皆 additive、base=Super 逐位元不變)

`tools/analyzer/tier_variants.py`:

1. **`MAIN_SHOW_CATS` 加入 `"wobble"`** —— 斜拉是主秀花式節拍,理應吃檔位增益。
   (`gen_animations` 的 `_MAIN_SHOW_CATS` 由此匯入 → 單一真相來源,自動生效。)
2. **`amplify_bone_tl` 對 `shear` 通道套增益** `v' = g·v`(x、y 皆是,4 位小數同 `gen_wobble`):

   | 通道 | 規則 | 保形理由 |
   |---|---|---|
   | **shear**(新) | `v' = g·v`(對 0 對稱,identity = 0 shear) | ① 首尾 shearX=0 幀 g 後仍 0(介面契約可插 Loop);② 相繼極值 `[A, rA, r²A, r³A]` 同乘 `g>0` → 仍嚴格遞減(阻尼)、繞 0 變號數不變(g>0 不改符號)→「振盪+遞減」兩條件並存;③ shear 峰 = base 峰 × g 隨檔位單調遞增(wobble 檔位簽章) |

增益階梯沿用 `TIER_GAIN["slot_bigwin"] = {Super:1.0, Mega:1.35, Omg:1.70, Legend:2.10}`。
base 特效 role 峰 16° × Legend 2.10 = **33.6°**,`det = cos(33.6°) = 0.83 > 0`(無翻面),安全。

### 為什麼 shear 用「對 0 對稱 v'=g·v」而非 scale 的「只放大 identity 上方」

scale 的 identity 在 **1**、且下方(squash/collapse)是**結構語意樓地板**(蓄力深度/藏匿),
所以只放大上方 overshoot。shear 不同:identity 在 **0**、正負代表左右斜拉方向,沒有「樓地板」
語意 —— 它與 **rotate/translate** 同類(對 0 對稱的運動幅度),故直接 `v'=g·v`。這也自動保住
阻尼振盪簽章:同乘正增益既不改符號序列(變號數不變)、也保序(遞減關係不變)。

## 端到端接線

- `build_spine.py --animate --tier-variants` 直出 `wobble__{tier}`;實測 shear 峰:

  | tier | Super | Mega | Omg | Legend |
  |---|---|---|---|---|
  | shear 峰(°) | 16.0 | 21.6 | 27.2 | 33.6 |
  | 峰比 vs base | 1.00 | 1.35 | 1.70 | 2.10 |

  峰比與 `TIER_GAIN` 階梯逐項相符(誤差 0)。
- 與 `--shear-pivot` 併用:tier 變體先產、`apply_pivots` 再掃全部 animation(含 `wobble__{tier}`)→
  放大後的斜拉 shear 亦繞關節 pivot 做一般仿射補償。`--tier-variants --shear-pivot` round-trip
  `validate_build` overall_pass。
- 變體名經 `beat_category` 仍路由回 `"wobble"`(主秀類別置前於 `_CAT_KEYWORDS`)→ 不破壞產線路由。

## 驗收閘 `validate_tier_wobble.py`(真實 robot 骨架,5 AC 全 PASS)

從**先驗庫**(slot_bigwin 含 wobble beat)→ `analyze_target` → **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains=…)`:

- **TW1 present+routing+shear**:每 wobble beat × 每檔位皆產 `{beat}__{tier}`、finite/有 bone、
  ≥1 bone 帶 shear 且峰 ≥5°;變體名仍路由回 `wobble`;base wobble beat 逐位元不變。
- **TW2 crux monotone shear**:每 wobble beat 的 max|shearX| 峰 Super<Mega<Omg<Legend **嚴格遞增**,
  且峰比 ≈ `TIER_GAIN`(誤差 <0.02)。
- **TW3 damped per tier**:每個檔位 shearX 序列(a)首尾 0;(b)繞 0 變號 ≥3;(c)相繼極值嚴格遞減。
- **TW4 interface+isolation**:(a)每檔位 sample(0)/sample(dur) 各 bone identity;(b)shear 端點 0;
  (c)**通道隔離**——wobble 變體只動 shear(不冒出 scale/rotate/translate),且非 wobble 主秀變體 0 帶 shear。
- **TW5 neg-control/guard**:(a)平增益全 1.0 → 峰恆定 → TW2 單調性 FALSE(證閘測遞增非恆真);
  (b)**shear-blind 守衛(crux)**——若 amplify 不碰 shear(僅動 scale/rotate/translate)→ 峰跨檔位恆定 →
  單調性 FALSE ⇒ 證「本次補上的 shear 處理」正是讓 TW2 通過的原因(非其他通道);(c)加性 In/Loop/Out
  與無 tier 的 slot_reveal 不產變體。

**回歸全綠**:validate_tier_variants(J,J3 改**通道無關**涵蓋 shear-only wobble、J4 加 wobble
阻尼分支後仍 PASS)/ shear_gen(G-4')/ tier_combo_count(J-2)/ 全 priors 系列 / beat_templates /
more_beats / cascade / pivot_rotation / scale_pivot / shear_pivot / deform_gen / anim(+selftest)/
round-trip validate_build(`--tier-variants` 與 `--tier-variants --shear-pivot` build 皆 overall_pass)。

## `validate_tier_variants.py` 的同步擴充(避免 wobble 入主秀後假陰性)

wobble 併入 `MAIN_SHOW_CATS` 後,原 J 閘會把它納入 main_beats。原 **J3** 只量 scale/rotate 幅度,
對 shear-only 的 wobble 會量到 [0,0,0,0] → 假陰性。故把 J3 改為**通道無關**:對該 beat **實際驅動**
的通道(scale/rotate/shear 中 max>TOL 者)各要求嚴格遞增、至少一個驅動 —— 這是更本質的判準
(「beat 的實際運動幅度隨檔位遞增」與通道無關),對既有 scale/rotate 驅動的 beat 行為不變。
**J4** 加 `wobble` 分支驗阻尼振盪簽章逐檔位保形;**J5(c)** 平增益守衛擴及 shear 通道。

## 誠實界定

- 斜拉 wobble 形狀與增益階梯數值為 **PROPOSAL**,閘驗**客觀結構簽章**(阻尼振盪、峰單調、峰比=階梯、
  通道隔離)非美感;手感留使用者(A 類)。
- 目前只放大 **shearX**(shearY≡0,同 G-4' 邊界)。
- 單一真值資產(Award/robot);新增 cap `tier_variant_shear` L2 併入 `spine-anim-forge`
  (**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。

## 檔案

- `tools/analyzer/tier_variants.py` —— `MAIN_SHOW_CATS` 加 wobble、`amplify_bone_tl` 加 shear 通道。
- `tools/analyzer/validate_tier_wobble.py` —— 5 AC 整合閘(**新**)。
- `tools/analyzer/validate_tier_variants.py` —— J3 通道無關、J4 加 wobble 分支、J5(c) shear-aware。
- `tools/check_readiness.py` —— 新 cap `tier_variant_shear`。

## 續(擇一,皆自主)

- **(G-4''') 產 shearY / 斜拉 squash**(shear + 耦合 scale 的 2D 斜壓);
- **(J-3) cascade 波速/散佈/件數隨檔位**(結構軸,非只幅度);
- **(G-1)** `--rig`×`--pivot`/`--scale-pivot`/`--shear-pivot` per-bone 語意去重;**(G-2)** 主秀 beat 下 limb 繞關節 AC。
