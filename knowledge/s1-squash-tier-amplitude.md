# S1 — squash 擠壓幅度隨檔位遞增(candidate G-4''''',`squash_tier_amplitude` L2)

> 2026-09-13。把 (G-4'''') 新生成的 **shear + 耦合非均勻 scale 節拍(squash)** 接進 (J) 的**檔位幅度
> 差異化**機制:squash 的擠壓幅度隨檔位(Super→Legend)嚴格遞增,**且體積守恆(scaleX·scaleY≡1)
> 在每個檔位保持**。關鍵是**體積守恆耦合 amplify** —— 各軸獨立放大會破壞守恆,這是 (G-4'''') 明列的
> honest boundary。又一「檔位機制就緒 ≠ 每個新通道接上」實例(同 E/H/I/J/G-4''),此處新「通道」是
> **耦合非均勻 scale 的體積守恆放大**。

## 缺口(honest boundary 的接續)

- **(J)** 讓主秀 beat 依檔位產出 `{beat}__{tier}` 幅度差異化變體,增益規則對 scale 是
  `_amp_scale`:**只放大 identity 上方 overshoot**(`v'=1+g(v−1)` 僅當 v≥1),下方(squash/collapse
  樓地板)不動。這對**等比 pulse**(scaleX==scaleY≥1)正確。
- **(G-4'''')** 讓 `gen_squash` 成為第一個產 **shear + 耦合非均勻 scale** 的生成器:每個 shear 極值施
  體積守恆 squash(scaleX=1+q **>1 拉長**、scaleY=1/(1+q) **<1 壓扁**,scaleX·scaleY≡1)。但對它套
  `_amp_scale`:scaleX>1 被放大、**scaleY<1 被當樓地板保留** → **破壞體積守恆**(scaleX·scaleY≠1)。
  故 squash 當時**不在** `MAIN_SHOW_CATS`,G-4'''' 誠實標記此為 honest boundary(「squash 未接 tier,
  需耦合 amplify」)。
- 本次(G-4''''')正好照那條邊界接上:**scale 通道走體積守恆耦合放大**。

## 做了什麼(全 additive)

1. **`tier_variants._amp_scale_coupled(x, y, g)`**(新):由 scaleX 還原 squash 量 `q = x−1`、以增益
   `g` 放大成 `g·q`,再令 `scaleX' = 1+g·q`、`scaleY' = 1/(1+g·q)` → **scaleX'·scaleY' ≡ 1 精確保持**
   (各軸獨立 `_amp_scale` 做不到);identity 幀(x==1 → q=0)→ (1,1) 不變(端點介面對所有檔位保形);
   `g=1.0` → 原值(向後相容)。squash 保證 q≥0(scaleX≥1)→ `1+g·q>0` 恆不奇異。
2. **`tier_variants.amplify_bone_tl(b, g, coupled=False)`** + **`amplify_anim(anim, g, coupled=False)`**
   加 `coupled` 參數:`coupled=True` 時 scale 走 `_amp_scale_coupled`(兩軸一起體積守恆放大);預設
   `False` → 原各軸 `_amp_scale`(等比 pulse 用)。rotate/translate/**shear** 兩模式相同(對 0 對稱 v'=g*v)。
3. **`tier_variants.MAIN_SHOW_CATS`** 加入 `"squash"` + 新 **`COUPLED_SCALE_CATS = {"squash"}`**。
4. **`gen_animations.build_animations`**:依 cat 路由 —— `cat ∈ COUPLED_SCALE_CATS` → `amplify_anim(coupled=True)`。
5. **`validate_squash_tier.py`**(新,5 AC)。
6. **`validate_tier_combo_count.py`** K5c 修正:原「full 內各檔位峰數相同」會把 squash 的**幅度**效應
   (scaleX 隨檔位放大,combo 的 impact_peaks 偵測器以 prominence 認峰 → 峰數 0→1)**誤判為 count 外洩**;
   改「**full(gains+hits) vs amp_only(gains only)同檔位峰數相等**」→ 差異純為 count 效應(對非-combo beat 應為 0)。
7. **`check_readiness`** 新增 cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(仍 HOLD)。
8. 圖 `knowledge/figures/s1_squash_tier.png`(左:各檔位 scaleX/scaleY 包絡;中:scaleX·scaleY≈1 每檔位守恆;
   右:峰 stretch 遞增 vs 天真放大破壞體積)。

## 驗收(`validate_squash_tier.py` OVERALL PASS,先驗庫→真實 build_spine robot 骨架→build_animations)

- **ST1 present + backward-compat**:squash base 帶 shear + 非均勻 scale;每檔位 `squash__{tier}` 產出、
  finite、≥1 bone **同時**帶 shear + 非均勻 scale、名仍路由回 squash;**base 逐位元不變**;**Super==base 逐位元**。
- **ST2 crux — 守恆 + stretch 遞增**:每檔位、每內部擠壓極值幀 |scaleX·scaleY−1|≤0.02(**放大後仍體積守恆**);
  峰 aniso ≥0.05(仍非均勻);峰 stretch |scaleX−1| = **[0.16, 0.216, 0.272, 0.336]** 嚴格遞增、Super==base。
- **ST3 shear 阻尼簽章逐檔保形 + 峰遞增**:每檔位 squash bone 仍(a)首尾 shearX=0;(b)繞 0 變號 ≥3;
  (c)相繼極值嚴格遞減;峰 |shearX| = **[16, 21.6, 27.2, 33.6]°** 遞增 → shear 與 scale **兩通道一致隨檔位放大**。
- **ST4 crux — 耦合必要性(負對照)**:同一 base squash 套 Legend 增益(g=2.1),**耦合版** max|scaleX·scaleY−1|
  = **0.0001**(守恆),**天真各軸版** = **0.152**(破壞守恆)→ >1500× 分離,證耦合 amplify 必要、且 ST2
  守恆判準有鑑別力(非恆真)。
- **ST5 負對照/隔離**:(a)平增益守衛 全 1.0 → ST2 遞增 FALSE 且各檔位逐位元==base;
  (b)耦合隔離 非-squash 主秀 beat(combo/hit…)之檔位變體 scale 仍**等比**(scaleX==scaleY)→ 耦合放大只作用
  squash、不外洩;(c)加性 移除 squash beat → 其餘 beat 逐位元不變。

回歸:18 閘全綠(shear_gen/squash_gen/wobble_tier/wobble_count/shear_pivot/scale_pivot/pivot_rotation/
tier_variants/tier_combo_count/priors/priors_beats/priors_combo_charge/priors_cascade/cascade/more_beats/
beat_templates/deform_gen/squash_tier)+ round-trip `validate_build` 對 `--tier-variants --shear-pivot`
build overall_pass(premult MAE 0.031、0 orphan)。端到端 `build_spine --animate --tier-variants --shear-pivot`
直出 `squash__{Super,Mega,Omg,Legend}`。

## 關鍵發現

- **體積守恆的正確放大 = 對守恆量 q 放大,而非對兩軸各自放大**。squash 的自由度其實只有一個(q),
  scaleX=1+q、scaleY=1/(1+q) 由它決定。事後 amplify 若把 scaleX、scaleY 當**兩個獨立通道**各自放大
  (尤其 scaleY<1 被 `_amp_scale` 當樓地板),就割裂了這個耦合 → 破壞守恆。**還原單一自由度 q、放大它、
  再重算兩軸**才是保守恆的唯一正確作法(ST4 用 >1500× 分離量化證明)。這與 (G-4'') 對 shear「同比放大
  即保阻尼簽章」異曲同工:**每種簽章各有其「自然保形變換」**,檔位差異化要沿著那個變換走。
- **閘的判準要 channel/effect-aware,否則新節拍上線會假陽性**。K5c 原用 combo 的 impact_peaks 偵測器量
  所有主秀 beat 的「峰數」,對 squash 這種 scaleX 隨幅度放大的節拍,會把幅度效應誤讀成 count 外洩。
  正確隔離是**比「加該效應 vs 不加該效應」**(full vs amp_only),而非「同一 run 內各檔位互比」——
  後者混淆了幅度軸與 count 軸。同 (G-4'') 對 J3 改 channel-aware 的教訓。

## honest boundary(仍在)

- 擠壓幅度階梯沿用 (J) 的增益 `{Super:1.0, Mega:1.35, Omg:1.70, Legend:2.10}`(PROPOSAL,結構簽章客觀
  [守恆+遞增]、手感留使用者 A 類)。
- squash 尚未接 **count-aware**(擠壓**段數** nosc 隨檔位 —— `gen_squash(nosc=)` 已備參數,需比照 (G-4''')
  在 gen 時決定、走重生成路,不能事後 amplify)。
- 仍 **shearY≡0**(單軸 shear);未做 shear+scale+rotate 三通道同時的運動基元(塞滿一般仿射 M 全自由度)。
- 單一真值資產(robot_parts)。與 `spine-anim-forge` 區塊同 **HOLD**(運動基元為先驗手感、防固化)。

## 續(擇一,皆純自主)

- **(G-4'''''')** squash count-aware:擠壓**段數**隨檔位遞增(`gen_squash(nosc=)`,比照 J-2/G-4''' 重生成路)。
- 產 **shearY**(雙軸 shear)/ shear+scale+rotate 三通道同時的運動基元(真正塞滿一般仿射 M 全自由度)。
- **(J-3)** cascade 波速/散佈/件數隨檔位(cascade 的 count-aware:跨件波的第三種檔位軸)。
- **(G-1)** `--rig`×`--pivot-rotate`/`--scale-pivot`/`--shear-pivot` per-bone 語意去重;**(G-2)** 主秀 beat 下 limb 繞關節 AC。
- S5→L3 仍待 **(D) 多 rig 真值**(C/資源類,使用者提供)。
