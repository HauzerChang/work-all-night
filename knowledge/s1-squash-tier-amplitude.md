# S1 — squash 擠壓深度隨檔位遞增(candidate G-4''''',`squash_tier_amplitude` L2)

> 2026-09-17。續 (G-4''''):(G-4'''') 讓 `gen_squash` 成為第一個**同時產 shear + 耦合非均勻 scale**
> (體積守恆擠壓)的生成器,但誠實標記 honest boundary:「squash 未接 tier 幅度差異化 —— 單軸
> `_amp_scale` 只放大 identity 上方,會放大 scaleX 卻保留 scaleY 樓地板 → 破壞體積守恆」。
> 本次(G-4''''')補上**耦合 amplify**,讓 squash 的擠壓深度與 shear 峰**雙通道**隨檔位嚴格遞增,
> 而 **scaleX·scaleY≡1 對所有檔位保持**。

## 缺口(honest boundary 的接續)

- **(G-4'''')** 為避免破壞體積守恆,把 squash **排除在 `MAIN_SHOW_CATS` 外** → squash 完全不隨檔位
  變化(檔位愈高主秀愈爆,唯獨斜拉擠壓強度不變=不一致,同 (G-4') wobble 當時的處境)。
- 本次正好照那條邊界接上:**擠壓深度也隨檔位遞增**,但用對的 amplify 規則。

## 關鍵:耦合 scale 不可用單軸 amplify

squash 的一幀 scale = `(scaleX=1+q, scaleY=1/(1+q))`,`q`=擠壓量 ≥0 —— **scaleX·scaleY≡1**(面積守恆)、
`scaleX≠scaleY`(非均勻)。擠壓量 `q` 是 scaleX/scaleY **綁定的單一自由度**。

- **單軸 `_amp_scale(v,g)`**(J 對等比 scale 的規則):只放大 identity 上方(`v≥1 → 1+g(v−1)`;`v<1`
  樓地板不動)。對 squash → scaleX(>1)被放大成 `1+g·q`,scaleY(<1)被當樓地板**保留** →
  `scaleX·scaleY = (1+g·q)/(1+q) ≠ 1`。**破壞體積守恆**(g=2.1、q=0.16 時 |積−1|=0.15,即 15% 體積誤差)。
- **耦合 `_amp_scale_coupled(x,g)`**(本次新增):從 scaleX 取 `q=x−1`、放大 `q'=g·q`、scaleY 依
  `1/(1+q')` **重算** → `scaleX'·scaleY' = (1+q')·1/(1+q') ≡ 1`(守恆對所有檔位保持)、非均勻隨 g 加大。
  `x==1`(identity 端點)→ `q=0` → (1,1) 不動(介面契約保持)。**等同以 `Q→g·Q` 重生成 squash**
  (與生成器一致,非事後 hack)。

> **三種通道專屬 amplify 規則**(至此齊備):等比 scale(J,只放大上方)· 純 shear/rotate/translate
> (G-4'',對 0 對稱 `v'=g*v`)· **耦合體積守恆 scale(本次,兩軸綁定放大 q)**。

## 幅度軸 vs 段數軸(本次只做幅度)

| 軸 | 機制 | squash 現況 |
|---|---|---|
| **幅度**(檔位愈高愈爆) | 事後 amplify(耦合 q 放大) | ✅ 本次:深度 0.298→0.588、shear 16°→33.6° |
| **段數**(擠壓幾下) | gen 時決定(`gen_squash(nosc=)` 已備參數) | ⬜ 後續(比照 (J-2) combo / (G-4''') wobble) |

`gen_squash` 的 `nosc` 參數已就緒;count-aware(擠壓段數隨檔位)為下一候選,與本幅度軸正交可疊。

## 做了什麼(全 additive)

1. **`tier_variants._amp_scale_coupled(x, g)`** — 體積守恆耦合 scale 幅度增益(見上)。
2. **`tier_variants.amplify_bone_tl(b, g, coupled_scale=False)`** — `coupled_scale=True` 時 scale 走耦合
   amplify(捨入 4 位,同生成器精度 → g=1.0 時逐位元 == base;守恆誤差最壞 ~1e-4 ≪ TOL_VOL=0.02);
   `False`(預設)走原單軸 `_amp_scale`。shear/rotate/translate 兩路徑相同。`amplify_anim` 透傳旗標。
3. **`tier_variants.MAIN_SHOW_CATS`** 加入 `squash`;新增 **`COUPLED_SCALE_CATS={squash}`**。
4. **`gen_animations.build_animations`** — 產 tier 變體時 `coupled = cat in COUPLED_SCALE_CATS`,透傳給
   `amplify_anim(..., coupled_scale=coupled)`(其餘等比 scale 節拍仍走單軸)。
5. **`validate_squash_tier.py`**(新,6 AC)。
6. **`validate_tier_combo_count.py` K5c** — 排除 `SHEAR_CATS`:`impact_peaks` 是 combo 專屬衝擊峰偵測器
   (有 prominence 門檻),對 squash 的耦合擠壓 scaleX 會因幅度隨檔位跨過門檻誤數 [0,1,1,1] —— 那是
   **幅度效應非 count 外洩**(squash 的段數各檔位其實恆定)。同 (G-4'''') 抽 `SHEAR_CATS` 的集中化維護。
7. **`check_readiness.py`** 新增 cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`;重生成 `skills/READINESS.md`。
8. 本 knowledge + 索引;圖 `knowledge/figures/s1_squash_tier.png`。

## 驗收結果(`validate_squash_tier.py` OVERALL PASS,6 AC)

- **ST1 present + backward-compat**:每檔位 `squash__{tier}` finite/有 bone/**同時**帶 shear+scale、名路由回
  squash;base(In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變。
- **ST2 crux 雙通道遞增**:擠壓深度 |scaleX−scaleY| 峰 [0.298, 0.394, 0.486, 0.588] **且** shear 峰
  [16.0, 21.6, 27.2, 33.6]° 皆 Super<Mega<Omg<Legend 嚴格遞增;Super(g=1)兩者 == base。
- **ST3 crux 體積守恆對所有檔位保持**:每檔位每個 scale 極值幀 |scaleX·scaleY−1| < 1e-4(≪ TOL_VOL=0.02)、
  非均勻 ≥ MIN_ANISO、擠壓幅度 |scaleX−1| 隨極值嚴格遞減(阻尼耦合保形)。
- **ST4 shear 阻尼振盪保形 + scale identity 介面**:每檔位 shear 首尾 0 + 繞 0 變號 ≥3 + 極值遞減;scale 首尾 (1,1)。
- **ST5 shear 隔離**:shear 只在 `SHEAR_CATS`(wobble/squash)及其 `__tier` 變體。
- **ST6 負對照**:(a) 平增益 → ST2 遞增 FALSE 且變體逐位元 == base;
  (b) **crux 天真守衛**:對真實 squash 極值施單軸 `_amp_scale` → |scaleX·scaleY−1|=0.152 ≫ TOL_VOL
  而耦合=0(**證 ST3 的守恆檢查有鑑別力、耦合 amplify 必要**);(c) 耦合單元測(coupled 守恆+放大+端點 identity、
  noncoupled 破壞守恆、shear 兩路徑同 `v'=g*v`)。
- **回歸全綠(17 閘)** + 端到端 `build_spine --animate --tier-variants --shear-pivot` 直出
  `squash__{Super,Mega,Omg,Legend}`,`validate_build` round-trip overall_pass。

## 關鍵發現

- **通道的 amplify 規則由該通道的「幾何自由度結構」決定**,不能一體適用。等比 scale 是「上方 overshoot」
  單向自由度、純 shear 是「對 0 對稱」自由度、**耦合擠壓是「scaleX/scaleY 綁定的單一 q」自由度** ——
  三者的保形放大各不相同。用錯規則(單軸放大耦合 scale)會破壞該通道的不變量(體積守恆)。
- **honest boundary 逐條接上的價值**:G-4'''' 明確標記「squash 未接 tier(需耦合 amplify)」→ 本次不必重新
  發現問題,直接照邊界補上,且新閘的 crux 負對照(ST6b)正是把「為什麼不能用舊 amplify」變成可機讀守衛。

## honest boundary(仍在)/ 下一步

- 擠壓深度階梯沿用 (J) 增益 [1.0, 1.35, 1.70, 2.10](PROPOSAL,手感留使用者 A 類)。
- shearY≡0(斜拉只在 X);**squash count-aware(擠壓段數 nosc 隨檔位)為後續**(參數已備,比照 (G-4''')/(J-2))。
- 單一真值資產(robot);與 `spine-anim-forge` 同 HOLD(運動基元先驗、防固化)。

見圖 `knowledge/figures/s1_squash_tier.png`、閘 `tools/analyzer/validate_squash_tier.py`。
