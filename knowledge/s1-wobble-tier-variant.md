# S1 wobble shear 峰隨檔位遞增(接 tier 幅度差異化,G-4'')

> 里程碑 2026-09-09(candidate G-4'')。補 G-4' 的 **honest boundary**:G-4' 讓 `gen_wobble`
> **第一次**產出 shear 通道,但當時 wobble **尚未接 tier 幅度差異化**(shear 峰不隨檔位遞增;
> wobble ∉ `MAIN_SHOW_CATS`)。本次比照 (J) 對 scale/rotate 所做,把 wobble 納入檔位變體:
> `{wobble}__{tier}` 的 shear 峰 **Super<Mega<Omg<Legend 嚴格遞增**,而阻尼振盪簽章與 identity
> 介面對所有檔位保形。
> 工具:`tier_variants.amplify_bone_tl`(+shear)、`tier_variants.MAIN_SHOW_CATS`(+wobble)、
> `validate_wobble_tier.py`、`build_spine --animate --tier-variants --shear-pivot`。

## 動機(接 G-4' 的最後一塊)

G-4'(`s1-shear-channel-generation.md`)把「公式/閘就緒 ≠ 生成器接上」的最後一段接上:讓斜拉 wobble
beat 實際產出 shear 通道並端到端補償。但它的 honest boundary 明言:「tier(檔位)變體尚未接 wobble
(wobble ∉ `MAIN_SHOW_CATS`)—— 可比照 (J) 把 wobble 加進 tier 幅度差異化(shear 峰隨檔位遞增)為後續。」
本 candidate 就是做這一步 —— **檔位愈高、晃愈大**,而怎麼晃(阻尼形狀)不變。

## 幅度增益如何套到 shear 通道

`tier_variants.amplify_bone_tl(b, g)` 原本只放大 scale(上方 overshoot)/rotate/translate。本次加 shear:

```
shear 繞 0(identity=0)阻尼擺動 → 對 0 對稱放大  v' = g * v   （同 rotate/translate）
```

- **端點 0 仍 0** → identity 介面契約對所有檔位保持(可插 Loop 間)。
- **相繼極值同乘 g** → 阻尼比 r=|e_{i+1}/e_i| **逐項不變**(形狀不動、只放大幅度)。
- **峰值隨 g 單調變大** → 檔位簽章(愈高愈晃)。

並把 `"wobble"` 加進 `MAIN_SHOW_CATS`,使 `build_animations(..., tier_gains=…)` 對 wobble beat 產出
`{wobble}__{tier}` 變體(In/Loop/Out 仍檔位無關)。**base=Super g=1.0 → 逐位元 == 無檔位輸出**(向後相容)。

端到端量(role 特效 base 峰 16°,gain 階梯 {Super:1.0,Mega:1.35,Omg:1.70,Legend:2.10}):

```
shear 峰(度):  16.0 → 21.6 → 27.2 → 33.6      = 16 × gain[tier]
```

Legend 峰 33.6° < 90° → `det = cos(shear) > 0`,**無翻面**。

## 驗收 `validate_wobble_tier.py`(先驗庫→真實 build_spine robot 骨架→build_animations,5 AC 全 PASS)

| AC | 內容 | 實測 |
|---|---|---|
| T1 | **present + shear per tier** 每 wobble×每檔位產變體 finite/有 bone/shear 峰 ≥5°;base wobble 逐位元向後相容 | 峰 16/21.6/27.2/33.6、base 不變 |
| T2 | **crux 峰單調** Super<Mega<Omg<Legend 嚴格遞增、==base×gain 階梯、Legend<90° 無翻面 | [16,21.6,27.2,33.6]==expect |
| T3 | **阻尼簽章保形(每檔位)** 首尾 0、繞 0 變號 ≥3、相繼極值嚴格遞減 | 全檔位 PASS |
| T4 | **identity 介面(每檔位)** sample(0)/sample(dur) rotate/scale/translate identity + shear 首尾 0 | PASS(可插 Loop) |
| T5 | **負對照/隔離** (a)平增益→峰單調 FALSE+Super==Legend (b)base 全逐位元不變·shear 只在 wobble (c)阻尼形狀不變 | 全 PASS |

**T5(c) 是本次的誠實邊界指紋**:相繼極值比 |e_{i+1}/e_i| 對 Super 與 Legend **逐項相等**(均勻放大只改
幅度、不改阻尼比 r)→ 檔位改的是「**多晃**」而非「**怎麼晃**」。這與 (J) 的「增益只放大 overshoot、不動
下方樓地板」是同一種誠實:檔位差 = 大獎強度(幅度),不篡改運動的**結構語意**(阻尼形狀/蓄力深度)。

## 端到端(build_spine --animate --tier-variants --shear-pivot)

`build_spine.build(..., animate=True, tier_variants=True, shear_pivot=True)` 產出:

```
wobble__Super   shear_peak=16.00  has_translate(pivot 補償)=True
wobble__Mega    shear_peak=21.60  has_translate=True
wobble__Omg     shear_peak=27.20  has_translate=True
wobble__Legend  shear_peak=33.60  has_translate=True
```

→ 檔位放大後的 shear **仍** 帶 `--shear-pivot` 的 pivot 補償 translate(件繞關節 pivot 做一般仿射而
pivot 不動)。**幅度軸(tier)與 pivot 補償正交**:放大 shear 峰不破壞 pivot 不動性(補償 Δ 由該幀 shear
矩陣算出,自動隨幅度縮放)。round-trip `validate_build` 對此 build AC4 orphan 0.0、overall_pass。

## 關鍵發現 / 踩雷

1. **`SA.sample` 不處理 shear 通道** → wobble 的幅度在 sample 下「隱形」(scale=1/rotate=0)。故:
   - (J) 閘 `validate_tier_variants.py` 的 J3 原用 scale overshoot / rotate amp 量幅度,對 wobble 會得
     `[0,0,0,0]` → `is_strictly_increasing` 判 False → **誤判 FAIL**。修法:J3 改**通道感知** —— 只對
     amp>0 的活躍通道(scale/rotate/**shear**)要求嚴格遞增,且至少一個活躍。scale/rotate beat 行為不變。
   - shear 峰要**直接讀關鍵幀**(`ch["shear"]`),不能經 `SA.sample`/`series`(會漏)。
2. **shear 對 0 對稱,故用 `g*v` 非 `1+g(v−1)`**:shear identity=0(非 scale 的 1)。若誤用 scale 版
   `1+g(v−1)` 會把 0 的幀推成 `1−g`(非 0)→ 破壞端點 identity。對 0 對稱擺動的通道(rotate/translate/
   shear)一律 `g*v`。
3. **均勻放大保阻尼比**:所有極值同乘 g → 比值不變。這讓「檔位改幅度不改形狀」成為可量化的閘(T5c),
   把「愈高檔位愈爆」限縮在幅度、不偷改運動語意 —— 誠實地與美感手感(A 類)分離。
4. **加性 opt-in**:`tier_gains=None` 逐位元同舊行為;把 wobble 加進 `MAIN_SHOW_CATS` 只在**帶 tier_gains
   時**多產 wobble 變體,base 全綠;與 (J)/(J-2) 的 scale/rotate/combo 檔位變體正交共存。

## honest boundary(仍在)

- 斜拉 wobble 的形狀(阻尼比 0.5、role 峰值)與增益階梯(1.0/1.35/1.70/2.10)皆為 **PROPOSAL**
  (結構簽章客觀,手感留使用者 A 類)。
- 仍只 shearX(shearY≡0);未做 count-aware(如「晃幾下」隨檔位,類比 J-2 的 combo 峰數)。
- 單一真值資產(robot);`spine-anim-forge` 仍 **HOLD**(運動基元先驗、未達 L3 端到端真值)。

## 回歸(全綠)

`validate_tier_variants`(J,J3 改通道感知納 shear 仍全綠、wobble shear_amp [16,21.6,27.2,33.6])、
`tier_combo_count`(J-2)、`shear_gen`(G-4')、`shear_pivot`(G-4)、`scale_pivot`(G-3)、`pivot_rotation`(0i)、
全 `priors`/`priors_beats`/`priors_combo_charge`/`priors_cascade`/`more_beats`/`beat_templates`/`cascade`、
`deform_gen`、`anim`(+selftest)、round-trip `validate_build` 對 `--tier-variants --shear-pivot` build 全 PASS。

## cap / skill

新增 cap `wobble_tier_variant` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
