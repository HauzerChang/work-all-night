# S1 (G-4''''''-vol) twistvol —— 全仿射行列式守恆的反相雙軸 twist(scale 補償 shear 的 det 損失)

- **結論**:新增節拍 `gen_twistvol`(斜扭果凍守恆扭轉)在 twist(G-4'''''')的反相雙軸 shear 上疊一條
  **耦合等軸 scale** 使**全 2×2 仿射行列式守恆**(det≡1),補齊 twist 明白列出的 honest boundary —— twist 的
  反相雙軸 shear 令 `det(M)=cos(shearY−shearX)≠1`(**擰轉會變面積**:峰 Δφ=(1+φ)|shearX|=27.2° →
  det=cos=0.889 → 面積剩 ~89%)。twistvol 讓件**擰而不變面積**,是產線第一個做到「全仿射行列式守恆」的節拍。
- **運動基元 = twist 的反相雙軸阻尼 shear + 每極值疊等軸 scale s_i**:
  - `shearX/shearY(τ)`:同 `gen_twist`(反相雙軸阻尼,shearY=−φ·shearX,φ=0.7,首尾 0)。
  - `scale(τ)`:每 shear 極值 i 施等軸 `scaleX=scaleY=s_i=1/√(cos(shearY_i−shearX_i))`;
    shearY_i−shearX_i=−(1+φ)shearX_i,cos 偶 → `s_i=1/√(cos((1+φ)|shearX_i|)) ≥ 1`(等軸膨脹,隨 shear 阻尼
    一起收回 1)。首尾 (1,1)。
- **關鍵幾何(為何 det=sx·sy·cos)**:真實 Spine local 2×2(`transform_matrix_full(0,sx,sy,shx,shy)`)的行列式
  `det = sx·sy·cos(shearX−shearY)`(shear 令兩基底夾角偏離 90° → 平行四邊形面積 ×cos(夾角偏離);等軸 scale
  ×sx·sy)。令 `sx=sy=s` 且 `s²·cos(Δ)=1` ⇒ `s=1/√(cos Δ)` → **det≡1**(擰而不變面積)。shear→0 時 cos→1、
  s→1 → 首尾 identity 自然保持。
- **與 squash 體積守恆的層級區別(crux)**:
  - **squash**(G-4''''):守 `scaleX·scaleY≡1`(**scale 通道自守**)、shearY≡0、scale **非均勻**(scaleX≠scaleY)
    → 其**全** det = 1·cos(shearX) ≠ 1(squash 本身仍因 shearX 微幅變面積,它守的是 scale 產物而非全矩陣)。
  - **twistvol**:守 **全 2×2 仿射 det≡1**(scale 精確補償 shear 造成的 det 損失)、shearY≠0(反相雙軸)、
    scale **等軸**(scaleX==scaleY,等軸膨脹)。
  ⇒ 兩者「體積守恆」不同層級;twistvol 的 scale 是**為補償 shear det 而生**(非獨立擠壓),且等軸而非非均勻。
- **依據/來源**:`tools/analyzer/beat_templates.py`(`gen_twistvol`/`_twistvol_env`/`TWISTVOL_KEYWORDS`,沿用
  `_TWIST_SHEARX`/`TWIST_PHI`)、`gen_animations.py`(`_DISPATCH["twistvol"]` + `_CAT_KEYWORDS` 置最前註冊)、
  `genre_priors.py`(slot_bigwin 新增 `twistvol` beat + `_BIGWIN_ROLES["twistvol"]`,additive)、
  `tier_variants.py`(`SHEAR_CATS` 加 `twistvol` → shear-isolation 閘認定合法 shear 產出者)、
  自我驗收閘 `tools/analyzer/validate_twistvol_gen.py`(**6 AC 全 PASS**)。真值/fixture 同 (G-4'/G-4''''/G-4'''''')
  一致:從**先驗庫**(slot_bigwin)→ **真實 build_spine robot 骨架** → `build_animations` 端到端量。

## 6 AC(客觀、可量測)—— 全 PASS

- **TV1 present + 雙軸 shear + 耦合 scale**:twistvol beat 直出、finite、有 bone;≥1 bone 同時帶 shear 與 scale;
  shearX 峰 **16.0°**、shearY 峰 **11.2°**、scale 最大膨脹 **0.0603**(=s−1,補償 shear det<1)。
- **TV2 兩軸阻尼振盪 + 反相**:每 bone 的 shearX 與 shearY 各自(a)首尾 0;(b)繞 0 變號 ≥3;(c)相繼極值嚴格遞減
  (阻尼,復用 G-4' `_sign_changes_zero`/`_extrema_mags_decreasing`);且每內部極值 shearX·shearY<0(確為 twist)。
- **TV3 全仿射 det 守恆 + 等軸(crux)**:每內部極值幀(a)`det=sx·sy·cos(shearX−shearY)≈1`(實測 |det−1|<1e-5,
  各件如 b_光暈 det `[1.000001,0.999999,1.0,1.0]`);(b)scaleX==scaleY(|差|=0,**等軸**);(c)scaleX>1;
  (d)**去掉 scale**(sx=sy=1)後峰值 det=cos ≤ 0.98(各件 `det_noscale` 峰 0.889/0.915/0.937/0.956)→ 證守恆由
  等軸 scale 補償真 det 損失達成,非 shear 自守。
- **TV4 identity 介面(可插 Loop)**:sample(0)/sample(dur) 各 bone identity;shear 首尾 (0,0)、scale 首尾 (1,1)。
- **TV5 端到端 pivot 不動**:`build_spine --shear-pivot`(真實 robot)產出 twistvol 帶補償;有關節 pivot 的 bone
  pivot 殘差(**在 shearY≠0 + scale 同時驅動下**)右手 0.013 / 頭 0.004 / 左手 0.016 px < 0.5;內建負對照(未補償,
  繞件中心)8.6–29.5 px(>1000×)→ 證補償把「全仿射守恆扭轉」錨在關節 pivot。
- **TV6 負對照/隔離**:(a)**shear-only 守衛**:雙軸 shear 但 scale≡(1,1)→ 全 det=cos<1 → 守恆 FALSE
  (證等軸 scale 在做 det 補償);(b)**squash 式 scale 守衛**:`scaleX·scaleY≡1` 但非均勻 + 雙軸 shear →
  全 det=1·cos≠1 → 守恆 FALSE 且非等軸(證守的是**全矩陣** det 非 scale 產物、且 twistvol 為等軸);
  (c)**同相守衛**:shearX==shearY(純旋轉)→ 反相 FALSE;(d)**隔離**:非 twistvol beat 皆非「同時 shearY≠0 且
  等軸膨脹 scale」(twist 有 shearY 無 scale、squash 有 scale 但非均勻且 shearY≡0);(e)**加性**:移除 twistvol
  storyboard → 其餘 beat 逐位元不變(零回歸)。

## 端到端 & 回歸

- **端到端**:`build_spine --animate --tier-variants --shear-pivot` 直出 `twistvol`(shearY 峰 11.2° 經 pivot
  補償仍存活);`validate_build` round-trip **overall_pass**(premult MAE 0.031)。
- **回歸 21 閘全綠**(20 既有 + 新 twistvol_gen)。**回歸踩雷(同 twist 模式)**:twistvol 產 shearY → twist 閘
  TW6(c) shearY-isolation 原以 `beat_category==twist` 認定合法 shearY 產出者,會誤判 twistvol 洩漏 → 改為
  `in (twist, twistvol)`;並把 `twistvol` 併入 `SHEAR_CATS`(shear-isolation 閘認定,集中一處避免多閘硬編碼)。
  squash 閘 SQ6(c) 用 `_has_aniso_scale`(**非均勻** scale)判定,twistvol 為**等軸** → 天然不觸發、無需改。

## 關鍵發現

- **「體積守恆」有層級之分,要指明守的是哪個量**:squash 守 scale 通道產物 `scaleX·scaleY`,twistvol 守**全 2×2
  仿射行列式** `det=sx·sy·cos(Δshear)`。全 det 守恆更嚴(把 shear 造成的面積損失也算進去,用 scale 精確抵銷)。
  → 閘的 crux 必須驗**全矩陣 det**,並用「squash 式 scale(product=1 但 aniso)配雙軸 shear → 全 det≠1」的負對照
  把兩層級鑑別開。
- **真簽章常需兩獨立條件並立**(延續 squash/cascade/charge 的觀察):twistvol = **全 det≡1** 且 **scale 等軸**
  —— 只有 det≡1 不足以與 squash 式守恆分開(需再驗等軸),只有等軸不足以與純膨脹分開(需再驗 det≡1 且 shearY≠0)。
- **「補償型」通道 vs「獨立」通道**:twistvol 的 scale 不是獨立美術意圖,而是**由 shear 反推的守恆補償**
  (`s=1/√cos`);故負對照要證「去掉 scale 則 det 破」(scale 在做真工作),而非只證「有 scale」。
- **一般仿射四自由度的守恆版收尾**:rotate / 非均勻 scale / shearX / shearY 各自已被生成端驅動過(G-4→G-4'''''');
  twistvol 是第一個把 **shearX+shearY+等軸 scale 三通道同時**驅動、且**全仿射行列式守恆**的節拍(rotate 由 pivot
  補償另加)—— 從「用滿四自由度」推進到「用滿且守恆」。

## honest boundary(仍在)

- **未接 tier 幅度 / count-aware**:twistvol 未併入 `MAIN_SHOW_CATS`(無 `__tier` 變體)、未接 count-aware
  (`gen_twistvol(nosc=)` 已備參數未接;段數隨檔位遞增比照 wobble G-4''/G-4''' 為後續)。接 tier 時須注意 shear
  幅度增益 g 後 `s=1/√cos((1+φ)·g·|shearX|)` 仍要重算(scale 非簡單 v'=g·v,是 shear 的守恆函式 → 需**耦合**
  amplify,類比 squash 的 `_amp_scale_coupled` 但目標為全 det 而非 scale product)。
- 幅度 A / φ / 等軸選擇為 PROPOSAL(手感 A 類);等軸是眾多「補償 det」中最簡的一種(亦可非均勻補償,但等軸
  最乾淨且與 squash 分離最清楚)。單一真值資產(robot_parts)。
- cap `twistvol_full_affine_conserved` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
