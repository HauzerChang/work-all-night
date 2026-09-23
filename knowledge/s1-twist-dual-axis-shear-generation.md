# S1 (G-4'''''') twist 反相雙軸 shear —— 生成器首度驅動 shearY(用滿一般仿射的第二條 shear 軸)

- **結論**:新增節拍 `gen_twist`(斜扭果凍扭轉)是**產線第一個驅動 `shearY`(第二條 shear 軸)** 的生成器,
  補齊 wobble(G-4')/squash(G-4'''')一路留到現在的最後一條 shear 通道 honest boundary(**shearY≡0**)。
  至今所有產 shear 的節拍(wobble 純 shearX、squash shearX + 耦合非均勻 scale)都令 shearY≡0,故 Spine local
  一般仿射 M 的 y 軸 skew 自由度從未被**生成器**驅動 —— 公式/閘早就吃 `shy`(G-4 的
  `transform_matrix_full(...,shy)` / `pivot_channels_affine` / `apply_pivots(include_shear=True)` 以**合成**
  shy 驗過管路),生成端這次才接上。
- **運動基元 = 反相(counter-phase)雙軸阻尼 shear**(像擰毛巾:x 軸與 y 軸往相反方向 skew):
  - `shearX(τ)`:同 wobble 阻尼擺動 `0 → +A → −rA → +r²A → … → 0`(繞 0 變號、相繼極值遞減,r=0.5)。
  - `shearY(τ)`:**反相**且獨立幅度 φ `0 → −φA → +rφA → −r²φA → … → 0`(φ=`TWIST_PHI`=0.7,≠1 → 獨立通道;
    負號 → 與 shearX 反相)。兩軸極值 τ 同點、共用阻尼 → 同源同衰減但反相。
- **關鍵幾何(為何反相)**:Spine local 兩基底夾角 = `90 + shearY − shearX`。反相(shearX=+a、shearY=−φa)時
  **夾角偏離 = (1+φ)·a 被放大**(平行四邊形沿對角擰緊)= 真正的雙軸 shear;若**同相**(shearX==shearY)夾角
  恆 90°(基底仍正交)→ 只是旋轉,非 shear —— 這正是負對照(證簽章測「真雙軸 shear」非「旋轉偽裝」)。
- **依據/來源**:`tools/analyzer/beat_templates.py`(`gen_twist`/`_twist_env`/`_TWIST_SHEARX`/`TWIST_PHI`/
  `TWIST_KEYWORDS`)、`gen_animations.py`(`_DISPATCH["twist"]` + `_CAT_KEYWORDS` 註冊)、
  `genre_priors.py`(slot_bigwin 新增 `twist` beat + `_BIGWIN_ROLES["twist"]`,additive)、
  `tier_variants.py`(`SHEAR_CATS` 加 `twist` → shear-isolation 閘認定合法 shear 產出者)、
  自我驗收閘 `tools/analyzer/validate_twist_gen.py`(**6 AC 全 PASS**)。真值/fixture 同 (E/H/I/J/G-4'/G-4'''')
  一致:從**先驗庫**(slot_bigwin)→ **真實 build_spine robot 骨架** → `build_animations` 端到端量。

## 6 AC(客觀、可量測)—— 全 PASS

- **TW1 present + dual-axis(crux)**:twist beat 直出、finite、有 bone;≥1 bone 帶 shear,shearX 峰 ≥5° **且**
  shearY 峰 ≥5° → 量得 shearX 峰 **16.0°**、shearY 峰 **11.2°**(=0.7×16,**shearY 不再 ≡0**)。
- **TW2 兩軸皆阻尼振盪**:每個 twist bone 的 shearX **與** shearY 各自:(a)首尾 0;(b)繞 0 變號 ≥3;
  (c)相繼極值幅度嚴格遞減(阻尼)—— 復用 G-4' `_sign_changes_zero`/`_extrema_mags_decreasing`,與 shear-gen 閘一致。
- **TW3 反相雙軸耦合(crux)**:每個內部極值幀 (a)shearX·shearY **< 0**(反號);(b)夾角偏離 |shearY−shearX| ≥8°
  (反相 → =|shearX|+|shearY|)。實測各件內部極值乘積全負(如 b_光暈 `[-179.2,-44.8,-11.2,-2.8]`)、偏離峰 **27.2°**。
- **TW4 identity 介面**:sample(0)/sample(dur) 各 bone identity,shear 首尾 (x,y)=(0,0) → 可插 Loop 間。
- **TW5 端到端一般仿射 pivot 不動**:`build_spine --shear-pivot` 產出 twist 帶補償;凡有關節 pivot 的 bone,
  **在 shearY≠0 驅動下** pivot 殘差 **<0.015px**(右手 0.0147、頭 0.0042、左手 0.0145)vs 內建負對照
  (未補償=繞件中心,含雙軸 shear)**≈24px**(>1000× 餘裕)→ 證補償把「用滿兩條 shear 軸的一般仿射」也錨在 pivot。
- **TW6 負對照/隔離**:(a)**同相守衛** 合成 shearX==shearY(純旋轉)→ 反相 FALSE(證測「真雙軸 shear」非旋轉偽裝);
  (b)**單軸守衛** 合成 shearY≡0(wobble 樣)→ 雙軸 FALSE(乘積=0 非 <0);(c)**雙軸隔離** 非 twist beat 皆
  shearY≡0(wobble/squash 有 shearX 無 shearY、其餘無 shear → twist 獨佔第二條 shear 軸);(d)**加性** 移除 twist
  storyboard → 其餘 beat 逐位元不變(零回歸)。

## 回歸 / 端到端

- **20 回歸閘全綠**(19 既有 + 新 twist_gen)。**踩雷**:twist 產 shear → shear-isolation 閘(shear_gen W5b /
  wobble_tier T4)原以 `SHEAR_CATS={wobble,squash}` 認定「合法 shear 產出者」,會把 twist 誤判為洩漏 →
  把 `twist` 併入 `SHEAR_CATS`(集中一處,避免每加一個 shear 節拍就改多個閘的硬編碼)後兩閘復綠。
- 端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 `twist` 段(shearY 經 pivot 補償仍存活,峰 11.2°);
  `validate_build` round-trip overall_pass(premult MAE 0.031)。
- 新增 cap `twist_dual_axis_shear` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。

## 關鍵發現

- **一般仿射 M 的 4 個自由度,生成端至此全數被真實 beat 驅動過**:rotate(0i/G-4 pivot)、非均勻 scale(G-3/squash)、
  shearX(wobble/squash)、**shearY(twist,本次)**。公式/閘(Δ=(M−I)(O−P) 對任意 2×2 成立)早通用,
  這條線(G-4→G-4'''''')逐一把「公式就緒 ≠ 生成器接上」的每條通道接齊。
- **真簽章常需兩獨立條件並立**:twist 的「真雙軸 shear」= (a)兩軸皆非零 且 (b)反相(夾角偏離放大)——
  同 squash「體積守恆 且 非均勻」、cascade「散佈 且 遞增」。同相(shearX==shearY)是**旋轉的偽裝**,
  故「有兩條 shear 通道」不足以判雙軸,必須驗反相(基底非正交)—— 這是本閘的鑑別力來源。

## honest boundary(仍在)

- twist 未接 tier 幅度 / count-aware(比照 wobble G-4''/G-4''' 為後續;`gen_twist(nosc=)` 已備參數未接)。
- **反相雙軸 shear 未接體積守恆**:純雙軸 shear(sx=sy=1)的 `det = cos(shearY−shearX) ≠ 1` → 擰轉會變面積
  (物理上合理,如擰毛巾投影縮小),volume-conserving twist(耦合 scale 使 sx·sy=1/cos(shearY−shearX))為後續。
- 幅度 / φ 皆為 PROPOSAL(手感 A 類);單一真值資產(robot_parts);anim-forge 仍 HOLD。
