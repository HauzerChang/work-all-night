# S1 — squash 擠壓段數隨檔位遞增(candidate G-4''''',`squash_count_generation` L2)

> 2026-09-17。續 (G-4''''):(G-4'''') 讓 `gen_squash` 成為**第一個同時產 shear + 耦合非均勻 scale**
> (體積守恆擠壓)的生成器,但 squash **不接檔位差異化**。本次 (G-4''''') 補上 squash 的擠壓**段數**
> `nosc` 隨檔位嚴格遞增(Super 4 → Mega 5 → Omg 6 → Legend 7)。這是繼 (J-2) combo 連擊數、(G-4''')
> wobble 振盪段數之後,**count-aware 概念第三次落在新通道**(combo=scale 峰數、wobble=shear 振盪段數、
> squash=體積守恆擠壓段數)。

## 缺口(honest boundary 的接續)

- **(G-4'''')** 的 honest boundary 白紙黑字寫著:「squash 未接 tier(需**耦合 amplify**:`_amp_scale`
  只放大 identity 上方會破壞守恆);count-aware nosc 未接」。
- squash 有**兩條**可能的檔位軸:**幅度**(放大 squash 深度 Q)與**段數**(擠幾下)。
- **幅度軸被不變量擋住**:squash 的簽章是體積守恆(scaleX·scaleY≡1)。事後 `_amp_scale(v,g)=1+g(v−1)`
  只放大 identity **上方**(scaleX>1 被放大),下方樓地板(scaleY<1)不動 → 積 ≠ 1,**破壞守恆**;
  就算改成兩軸都放大,shear 與 squash 同源同阻尼、單放大 shear 又會**解耦**兩通道。故 squash 未進
  `MAIN_SHOW_CATS`(不吃 (J) 幅度增益)—— 幅度軸的**耦合 amplify** 仍為 honest boundary。
- **段數軸不受此限**:本次沿段數軸接上檔位差異化,**繞過**幅度耦合難題。

## 關鍵(crux):段數軸天然體積守恆,幅度軸才破守恆

段數 = 關鍵幀**拓樸**(繞 0 交替變號的 shear 極值個數)。事後 `amplify_bone_tl` 只能同比放大既有極值、
加不出一段 → 段數是**結構**、必須在 `gen_squash` 生成當下決定。故不走 amplify,而是對 squash 檔位變體
以該檔位 `nosc` 用 `gen_squash(nosc=k)` **重生成**整支 beat。

**與幅度軸的關鍵對照** —— 重生成的包絡對**任意** nosc 天然守恆:

- `_squash_env(A,Q,nosc)` 第 i 極值:`scaleX=1+q_i`、`scaleY=1/(1+q_i)`,`q_i=Q·rⁱ`(r=0.5)。
  → 每極值 `scaleX·scaleY = (1+q_i)·1/(1+q_i) ≡ 1`,**代數恆等,與 nosc 無關**。
- squash 幅度 `|scaleX−1|=q_i=Q·rⁱ` 逐極值嚴格遞減(阻尼),shearX 峰 `A·rⁱ` 同源同阻尼。
- 故**段數增多不破守恆**(prod≡1 逐檔位保持);而幅度軸(放大 Q)會離開這條恆等 → 破守恆。

實測(role=特效,nosc 4→7):段數 [4,5,6,7]、峰 |shearX| **恆 16.0°**、峰非均勻 **恆 0.298**、每檔位
每極值 `|scaleX·scaleY−1| < 5e-5`。**振幅跨檔位恆定** → 這是**純結構(段數)軸**。

## 段數軸遞增 ⟂ 幅度軸恆定(誠實界定範圍)

對比 (G-4''') wobble:wobble 段數**與**幅度**雙軸**遞增(段數 [4,5,6,7] × 峰幅 [16,21.6,27.2,33.6]°)。
squash 只有段數軸遞增、**幅度軸恆定**(峰 shear 16°、峰非均勻 0.298 跨四檔位相等)。這不是缺陷,而是
**誠實地標記**:squash 的幅度耦合差異化仍為 boundary,不假裝已解 —— 段數軸能在幅度軸被不變量擋住時
仍提供檔位差異化,且天然保持不變量(**重生成 vs 事後放大**是這裡的分水嶺)。

## 做了什麼(全 additive)

1. **`tier_variants.py`**:
   - `COUNT_AWARE_CATS` 加 `"squash"`(→ `{combo, wobble, squash}`)。
   - 新增 `COUNT_ONLY_CATS = {"squash"}` —— **只**以段數(結構軸)差異化、**不**套幅度增益的類別。
   - 新增 `TIER_SQUASH_CYCLES`(slot_bigwin Super4→Legend7)+ `squash_cycles_for(genre)`。
2. **`gen_animations.py`**:
   - `build_animations(..., tier_squash_cycles=None)` —— `_count_maps` 加 `"squash": tier_squash_cycles`。
   - tier-variant 產出閘由 `cat in MAIN_SHOW_CATS` 擴為 `... or cat in COUNT_ONLY_CATS`;
     **count-only 類別(squash)只重生成段數、`g` 不作用**,且僅在有段數宣告(cnt)時才產變體
     → 無 `tier_squash_cycles` 時 squash **不產任何檔位變體**(向後相容,同 G-4'''' 前)。
3. **`build_spine.py`**:`--tier-variants` 時一併帶 `squash_cycles_for(genre)`。
4. **`validate_squash_count.py`**(新,5 AC,復用 squash-gen/shear-gen 判準)。
5. **`check_readiness`** 新增 cap `squash_count_generation` L2 併入 `spine-anim-forge`(仍 HOLD)。
6. 圖 `knowledge/figures/s1_squash_count.png`(左:各檔位阻尼包絡段數遞增·峰幅恆定;中:scaleX·scaleY≡1
   逐檔位保持;右:段數 bar 遞增 ⟂ 峰幅雙線恆定)。

## AC(`validate_squash_count.py` 5 AC 全 PASS)

- **Q1 present + backward-compat**:每檔位 `squash__{tier}` finite/有 bone/**雙通道**(shear+scale);
  **base squash 恆 4 段且逐位元同無檔位**;**無 `tier_squash_cycles` 時 squash 不產任何變體**
  (向後相容);且加此參數不改動任何非-squash beat(零回歸)。
- **Q2 crux — count monotone**:各檔位段數 == 宣告 [4,5,6,7] 嚴格遞增,Super 段數 == base(4)。
- **Q3 signature preserved**:每檔位仍 (a) shear 首尾 0、繞 0 變號 ≥3、相繼極值嚴格遞減(阻尼);
  **且 (b) 體積守恆耦合逐檔位保持**(每極值 |scaleX·scaleY−1|≤TOL_VOL、非均勻峰 ≥ MIN_ANISO、squash
  幅度嚴格遞減)—— **段數增多不破守恆**。
- **Q4 amplitude-flat(crux honesty)**:峰 |shearX|(16°)、峰非均勻(0.298)**跨檔位恆定** → 證純段數軸,
  幅度耦合差異化仍為 boundary;並驗正交(段數 + 平增益 g=1.0 → 段數仍遞增)。
- **Q5 neg-control**:(a) 平段數(全 4)→ 單調性 FALSE;(b) 無宣告的 slot_reveal → `squash_cycles_for`
  None → 不產 squash 變體;(c) 段數只作用 squash(非-squash beat 段數跨檔位恆定,不外洩);
  (d) 體積守恆守衛:合成非守恆擠壓(兩軸皆拉長,積≠1)經 Q3 判準 → 守恆 FALSE(證閘真的在量守恆)。

端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super4,Mega5,Omg6,Legend7}`,
`validate_build` round-trip **overall_pass**。

## 回歸(17 閘全綠)

`validate_squash_gen`(G-4'''')/`wobble_count`(G-4''')/`wobble_tier`/`tier_combo_count`/`tier_variants`/
`shear_gen`/`shear_pivot`/`scale_pivot`/`pivot_rotation`/`cascade`/`priors`/`priors_beats`/
`priors_combo_charge`/`priors_cascade`/`more_beats`/`beat_templates`/`deform_gen` 全 PASS。

## 關鍵發現

- **結構(段數)軸與幅度軸可分離**:當幅度軸受不變量(體積守恆)阻擋時,段數軸仍能提供檔位差異化,
  且**天然保持不變量**。分水嶺是**重生成 vs 事後放大** —— 重生成從天然守恆的參數化家族取新成員
  (`gen_squash(nosc=k)` 的每個 k 都守恆),事後放大則會把值推離守恆流形。
- **count-aware 概念的第三次落地**(combo=scale 峰數、wobble=shear 振盪段數、squash=體積守恆擠壓段數)
  → 印證這是可推廣的檔位差異化模式;各類別段數階梯獨立(`build_animations` 依 cat 路由)。

## honest boundary(仍在)

- 段數階梯 [4,5,6,7] 為 **PROPOSAL**(結構簽章客觀,擠幾下的手感留使用者 A 類)。
- **幅度耦合 amplify 仍為 boundary**:squash 振幅跨檔位恆定;要讓 squash 深度也隨檔位遞增需
  **耦合 amplify**(scaleX/scaleY 一起以體積守恆放大,不破 scaleX·scaleY==1),為後續。
- shearY≡0(仍只單軸 shear);單一真值資產(運動基元先驗、防固化)→ `spine-anim-forge` 仍 **HOLD**。
