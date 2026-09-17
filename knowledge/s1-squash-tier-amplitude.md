# S1 — squash 雙軸幅度隨檔位遞增(candidate G-4''''',`squash_tier_amplitude` L2)

> 2026-09-17。把 (G-4'''') 新生成的**耦合 shear + 體積守恆非均勻 scale 節拍(squash)** 接進 (J) 的
> **檔位幅度差異化**機制:squash 的 shearX 峰**與**擠壓非均勻 |scaleX−scaleY| 峰**雙軸**隨檔位
> (Super→Legend)嚴格遞增,同時**每個檔位仍體積守恆**(scaleX·scaleY≡1)。
> 又一「檔位機制就緒 ≠ 每個新通道接上」實例(同 E/H/I/J/G-4'/G-4''/G-4''''),且首度需要**耦合 amplify**。

## 缺口(G-4'''' 明列的 honest boundary 的接續)

- **(J)** 讓主秀 beat 依檔位產出 `{beat}__{tier}` 幅度差異化變體,`tier_variants._amp_scale` 對 scale 通道
  **只放大 identity 上方 overshoot**(`v≥1 → 1+g(v−1)`;`v<1` 樓地板不動,語意=蓄力/藏匿深度檔位無關)。
- **(G-4'''')** 讓 `gen_squash` 產出**耦合的 shear + 體積守恆非均勻 scale**(每擠壓極值 scaleX=1+q 拉長、
  scaleY=1/(1+q) 壓扁 ⇒ scaleX·scaleY≡1)。但 squash **不在** `MAIN_SHOW_CATS` —— 因為若對它套天真
  `_amp_scale`:scaleX>1 被放大、scaleY<1 是樓地板不動 → **scaleX·scaleY≠1,體積守恆被破壞**。
  G-4'''' 誠實標記此為 honest boundary(「squash 未接 tier,需耦合 amplify」)。
- 本次(G-4''''')正好照那條邊界接上:**scale 通道走耦合 amplify**(把 scaleX/scaleY 當一對一起放大)。

## 做了什麼(全 additive)

1. **`tier_variants._amp_scale_coupled(scx, scy, g)`**(新):把 (scx, scy) 視為 **scaleX·scaleY≡1** 的擠壓
   對,以 `q=scx−1` 為擠壓量放大 `q→g·q` → `scaleX'=1+g·q`、`scaleY'=1/(1+g·q)`。保形性質:
   - ① `scaleX'·scaleY'≡1`(**體積守恆**)—— 天真逐分量 `_amp_scale` 無此性質(這是關鍵鑑別點)。
   - ② `q=0`(identity)→ (1,1) 不動(**介面契約保持**,可插 Loop)。
   - ③ `q` 符號不變(拉長軸恆拉長)、`|q|` 隨 `g` 單調放大(**擠壓幅度=檔位簽章**)。
2. **`tier_variants.amplify_bone_tl(b, g, coupled=False)`**:`coupled=True` 時 scale 通道走
   `_amp_scale_coupled`;**scaleY 由已四捨五入的 scaleX 導出**(`=1/scaleX`,體積守恆的定義)→ 存檔對
   維持積≡1 最緊(殘差僅來自 scaleY 一次 4dp,同 base ≈5.6e-5)。shear 通道續用 (G-4'') `v'=g*v`。
   `g=1.0` 且 `q` 在 4dp 可精確表示 → **逐位元 == base**(Super 向後相容)。
3. **`tier_variants.MAIN_SHOW_CATS`** 加入 `"squash"`;新增 **`COUPLED_SCALE_CATS={"squash"}`**
   標記 scale 通道為體積守恆耦合對的類別。
4. **`gen_animations.build_animations`**:對 `cat∈COUPLED_SCALE_CATS` 的 tier 變體傳 `coupled=True`
   給 `amplify_anim`(其餘 scale 節拍如等比 pulse/overshoot 仍走獨立 `_amp_scale`)。
5. **`validate_squash_tier.py`**(新,5 AC)。
6. **`validate_tier_combo_count.py`**(J-2 閘)K5c 改法(見下「回歸修正」)。
7. **`check_readiness`** 新增 cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(仍 HOLD)。
8. 圖 `knowledge/figures/s1_squash_tier.png`(左:各檔位 shearX 阻尼包絡;中:耦合 scaleX 拉長/scaleY 壓扁;
   右:雙軸峰值遞增 bar + 體積殘差 log 線恆 <TOL_VOL)。

## 驗收(`validate_squash_tier.py` OVERALL PASS,先驗庫→真實 build_spine robot 骨架→build_animations)

- **ST1 present + backward-compat**:squash base 有 dual channel(shear+非均勻 scale);每檔位
  `squash__{tier}` 產出、finite、有 bone、≥1 bone 同時帶 shear+scale、名仍路由回 squash;
  **base 帶/不帶 tier_gains 逐位元不變**;**Super(g=1)逐位元 == base squash**。
- **ST2 crux — 雙軸幅度遞增**:峰 |shearX| = **[16.0, 21.6, 27.2, 33.6]°**、峰非均勻 |scaleX−scaleY| =
  **[0.298, 0.394, 0.486, 0.588]** 皆 Super<Mega<Omg<Legend 嚴格遞增,且 Super == base(向後相容)。
  **兩軸同時遞增才算檔位差異化**(耦合 amplify 一次帶動 shear 與擠壓兩幅度)。
- **ST3 crux — 體積守恆逐檔保**:每檔位每個內部擠壓極值 (a)`|scaleX·scaleY−1|≤TOL_VOL`(實測 <5.6e-5);
  (b)≥1 極值非均勻 ≥MIN_ANISO;(c)squash 幅度 |scaleX−1| 隨極值嚴格遞減;且 shear 仍阻尼振盪
  (首尾 0、繞 0 變號≥3、相繼極值遞減)。→ **耦合 amplify 放大幅度但不破壞體積守恆**。
- **ST4 耦合隔離**:全 storyboard(含所有 `__tier` 變體)只有 squash 及其變體同時帶 shear 且非均勻 scale
  → 耦合對象仍只鎖 squash。
- **ST5 負對照**:(a)**平增益守衛** 全 1.0 → ST2 雙軸遞增 FALSE 且各檔位逐位元==base;
  (b)**耦合 vs 天真單元測(閘可信)**:同一體積守恆對,`coupled=True` → 積殘差 **6.4e-5**(守恆、通過閘)
  且 q 放大;`coupled=False`(天真 `_amp_scale`)→ 積殘差 **0.123**(> TOL_VOL,**破守恆閘**)。
  證耦合路徑是體積守恆的**必要條件**、且閘測的是「守恆放大」非「有 scale 即可」。

回歸:全 19 閘綠 + round-trip `validate_anim`(+selftest)/`validate_build` 對 `--tier-variants
--shear-pivot` build overall_pass(squash__{tier} 5 dual-bone 端到端經 pivot 補償仍載入)。

## 回歸修正:tier_combo_count K5c 去除幅度混淆

squash 併入 `MAIN_SHOW_CATS` 後,舊 K5c(「非-combo 主秀 beat 的 impact **峰數**在各檔位不變」以隔離
count 機制)出現**假陽性**:squash 是 scale-overshoot 主秀 beat,其耦合放大的 scaleX 峰會隨檔位跨
`impact prominence` 門檻 → **峰數改變(幅度效應,非 count 機制)**。改法:直接比 `full`(幅度+連擊數)vs
`amp_only`(僅幅度)對非-combo 主秀 beat 各檔位變體**逐位元相同**(count 參數對其零影響)—— 更強且不受
幅度干擾地隔離 `tier_combo_hits` 機制本身。此為**閘的正確一般化**(移除只在「有 scale-overshoot 主秀 beat」
時才暴露的混淆),非放寬。

## 關鍵發現

- **耦合放大是體積守恆的自然保形變換**。體積守恆 squash 的簽章 = 「scaleX·scaleY≡1 **且** scaleX≠scaleY」
  兩獨立條件(G-4'''' 的 SQ3/SQ6)。逐分量獨立放大會破前者;把 (scaleX,scaleY) 當一對、只放大擠壓量
  `q→g·q` 並令 scaleY=1/scaleX,則兩條件都保 → **檔位改的是擠壓強度、不是體積結構**(誠實)。
  這與 (J) 對 overshoot「只放大 identity 上方」、(G-4'') 對 shear「同比 v'=g*v」是同一哲學的第三種變奏:
  **每個通道各有其「保簽章的放大方式」**(overshoot=單邊、shear=對稱、squash=體積守恆耦合)。
- **雙軸幅度一次帶動**:squash 的 shear(對稱放大)與擠壓(耦合放大)由同一增益 g 驅動 → 兩軸峰值同步
  遞增(ST2)。這是首個**單一 g 同時放大兩個不同保形律通道**的檔位差異化。
- **閘可信性靠「耦合 vs 天真」對照**:ST5b 不只證耦合有效,更證天真會破守恆(積 0.123)—— 沒有這條
  負對照,「體積守恆」的 AC 可能被一個剛好也守恆的天真實作蒙混;有了它,ST3 測的確是耦合放大之功。

## honest boundary(仍在)

- 檔位增益階梯沿用 (J) 的 `{Super:1.0,Mega:1.35,Omg:1.70,Legend:2.10}`(PROPOSAL,結構/守恆簽章客觀、
  手感留使用者 A 類)。
- 仍只產 **shearX**(shearY≡0)。
- squash 尚未接 **count-aware**(「擠壓段數隨檔位」——`gen_squash(nosc=)` 參數已備,需在 gen 時決定段數,
  比照 J-2 對 combo / G-4''' 對 wobble,不能事後 amplify)。
- 單一真值資產(robot_parts)。與 `spine-anim-forge` 區塊同 **HOLD**(運動基元為先驗手感、防固化)。
