# S1 — 體積守恆扭轉:反相雙軸 shear 接均勻耦合體積守恆 scale(candidate G-4''''''-vol)

> 里程碑 2026-09-26 run 001。補 (G-4'''''') 一路留到現在的**最後一條 twist honest boundary**:反相雙軸
> shear 令 `det=cos(shearX−shearY)≠1` → 擰轉會變面積。本次讓 twist 節拍(`twist_vol`)加**均勻耦合體積守恆
> scale** 使 Spine local `det≡1` → **擰而不變面積**。cap `twist_volume_conserving` L2,`spine-anim-forge` 仍 HOLD。

## 一句話

`gen_twist(vol=True)` 在反相雙軸阻尼 shear 之外,對每個 shear 極值施**均勻** scale
`scaleX=scaleY=1/√cos(shearX−shearY)`,使一般仿射 `det = scaleX·scaleY·cos(shearX−shearY) ≡ 1`
——**擰而不變面積**;shear 與 scale 兩通道同時被生成器驅動、塞滿一般仿射四自由度且體積守恆。

## 背景 / 補的缺口

一般仿射 2×2 有 4 自由度。到 (G-4''''''-count) 為止,生成端已逐一驅動過:rotate(0i/pivot)、非均勻
scale(squash)、shearX(wobble)、shearY(twist)。但 **twist 的反相雙軸 shear 會改面積**:

Spine 3.8 bone local(θ=0,`transform_matrix_full`)的行列式
```
det = scaleX·scaleY·cos(shearX − shearY)
```
純雙軸 shear(scale=identity)時 `det = cos(shearX−shearY)`。twist 反相(shearX=+a、shearY=−φa)⇒
`shearX−shearY = (1+φ)a`,故 `det = cos((1+φ)a) < 1`(a≠0)—— **擰毛巾愈用力、面積縮愈多**(實測 effect
峰 a=16° 時 |det−1|=0.11、head a=10° 時 0.044)。這是 (G-4'''''') / (G-4''''''-tier) / (G-4''''''-count) 三份
milestone 都明列的 honest boundary:「反相雙軸未接體積守恆耦合 scale」。

## 解法:均勻耦合體積守恆 scale

要 `det≡1`,只需 `scaleX·scaleY = 1/cos(shearX−shearY)`。**行列式只約束 scaleX·scaleY 之積,不約束比值**。
取**均勻** split `scaleX = scaleY = 1/√cos(shearX−shearY)`:
```
det = (1/√cos)² · cos = 1   （由建構保證,任一 shear 值皆成立）
```
`_twist_vol_scale(shx,shy) = round(1/√cos(radians(shx−shy)), 4)`。首尾 shear=0 → cos0=1 → s=1 → scale (1,1)
identity 介面(可插 Loop)。shear 阻尼衰減 → s 逐極值趨近 1(scale 亦阻尼保形)。

### 為何均勻(sx==sy)而非 squash 的非均勻(crux 的設計抉擇)

- 均勻 split 是**唯一不另引入任意各向異性**的守恆補償:一般仿射的**非相似性(斜切/各向異性)全由兩條
  shear 軸給定**,coupled scale 只補回 shear 造成的面積損失、不加新形狀通道。
- 非均勻 split(選某各向異性比使積仍 =1/cos)守恆同樣成立,但**「選哪個比」屬手感 A 類主觀決定** ——
  留給使用者(honest boundary,非本 cap 客觀簽章)。
- **與 squash(G-4'''')的分工**:squash = shearX + **非均勻**耦合 scale(scaleX≠scaleY,`scaleX·scaleY≡1`);
  twist_vol = 反相**雙軸** shear + **均勻**耦合 scale(scaleX==scaleY,`det≡1`)。兩者皆體積守恆但幾何互補
  (squash 斜拉擠壓、twist_vol 等積扭轉)。**兩者的守恆量也不同**:squash 是 `scaleX·scaleY`(shear 不進 det
  因 squash 只驅 shearX 而 head/其它… 其實 squash 的 det=scaleX·scaleY·cos(shearX)、守恆靠 scaleX·scaleY=1 而
  cos(shearX)≈1 近似;twist_vol 直接把 cos(shearX−shearY) 用 scale 抵掉,是**精確** det≡1)。

## 實作(全 additive,向後相容)

- `beat_templates.py`:`gen_twist(..., vol=False)` 加 `vol` 旗標 + `_twist_vol_scale` helper。
  `vol=False`(預設)**逐位元同舊 twist**(只有 shear 通道);`vol=True` 額外產 `b["scale"]`。
- `gen_animations.py`:`_build_beat(..., vol=False)`;`build_animations` 以 beat 名判 `vol=(cat=="twist" and
  "vol" in name)`,傳入 base build;**tier 變體迴圈 `not vol` 略過**(vol 為 base-only,honest boundary)。
- `genre_priors.py`:`slot_bigwin` 加 `twist_vol` beat(additive、coverage 仍 1.0、`beat_category` 以 "twist"
  子字串仍路由回 twist)+ `_BIGWIN_ROLES["twist_vol"]`。
- `validate_twist_vol.py`:新閘 6 AC。復用 `validate_shear_gen`(阻尼簽章)+ `validate_twist_gen`(雙軸讀取/
  反相判準)+ `validate_shear_pivot._world`(端到端)+ `pivot_rotation.transform_matrix_full`(det)。
- `check_readiness.py`:註冊 cap `twist_volume_conserving` L2(pipeline)。

## 驗證(`validate_twist_vol.py` 6 AC 全 PASS)

- **VV1** present + tri-channel(crux):`twist_vol` 直出、finite、5 bone 同時帶 shear(shearX 峰 16°·shearY 峰
  11.2°)+ scale 通道。
- **VV2** twist 簽章保持:兩軸各自阻尼振盪(首尾 0+變號≥3+極值遞減)+ 每內部極值反相(加 scale 不擾扭轉幾何)。
- **VV3** 體積守恆(crux):每 shear 關鍵幀 |det−1| ≤ 2e-4(worst **8.8e-5**;scale 4 位捨入)。
- **VV4** 負對照 / 均勻守衛(crux):(a)純 shear(scale=identity,即舊 twist)峰 |det−1|=**0.11** ≥0.02 → 耦合
  scale 是守恆關鍵;(b)只放大一軸(sx=1/√cos、sy=1,積≠1/cos)峰 |det−1|=**0.057** ≥0.02 → 需**特定**
  `sx·sy=1/cos` 耦合、非任意 scale;(c)均勻守衛:twist_vol scale 逐幀 scaleX==scaleY(等向,非 squash 非均勻)。
- **VV5** identity 介面 + 向後相容:shear 首尾(0,0)·scale 首尾(1,1)·sample identity;**純 twist beat 逐位元不變
  且無 scale 通道**(vol opt-in);加性移除 twist_vol → 其餘 beat 逐位元不變。
- **VV6** 端到端守恆存活:`build_spine --shear-pivot` 產 twist_vol 帶補償,pivot 殘差 <0.02px vs 負對照 8–29px;
  **守恆端到端存活**:非重取樣 bone(光暈/身體)|det−1| ≤2e-4 精確、關節 bone 於極值時刻 |det−1| ≤5e-3
  (密網格重取樣內插殘差,仍 >20× 低於未守恆 0.11)。

端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 `twist_vol`(不產 `twist_vol__{tier}`);
`validate_build` round-trip overall_pass(premult MAE 0.031)。回歸 23 閘全綠(22 既有 + 新 twist_vol)。

## 踩雷 / 回歸

1. **base-only 節拍破壞「每主秀 beat 皆有 tier 變體」假設**:`twist_vol` ∈ MAIN_SHOW 類別(cat=twist)但無
   `twist_vol__{tier}`(honest boundary)→ 多個閘的 `_main_beats`/`_base_beats`/`_twist_beats` 迴圈索引
   `{beat}__{tier}` 會 KeyError。修法:在 `validate_tier_variants`(`_base_beats`)、`validate_squash_count`/
   `validate_wobble_count`/`validate_tier_combo_count`(`_main_beats`)、三支 twist 閘(`_twist_beats`)一律
   **排除名含 "vol" 的 base-only 節拍**。(`validate_twist_count` 的 `_main_beats` 不需改:其隔離迴圈 `cat=="twist"
   → continue` 已天然排除 twist_vol。)
2. **端到端守恆是「極值/關鍵幀」性質、非「逐密網格幀」**:`--shear-pivot` 對關節 bone 把 shear/scale **密網格
   重取樣**(Δ 對 shear/scale 非線性,需 densify 求 translate);相鄰兩守恆極值間的**線性內插** scale 不等於
   `1/√cos(內插 shear)`(耦合非線性)→ 中間幀 |det−1| 達 0.037。這與 squash 相同(squash 亦只在極值守恆、
   `--shear-pivot` 只 round-trip/pivot-fixed 驗)。故 VV6 於**原極值時刻取樣**量 det(守恆最嚴處),非逐密網格幀。

## honest boundary(仍在)

- 守恆補償的 **split 自由度(均勻 vs 非均勻)** 是新的 A 類手感選擇;均勻為預設,非均勻體積守恆扭轉為後續。
- `twist_vol` **未接 tier / count-aware**:體積守恆的 tier amplify 需依**放大後**的 shear 角重算 scale
  `=1/√cos(g·angle)`(cos 非線性,不能沿用單一-g 對 scale 同比放大)→ 為後續 (G-4''''''-vol-tier);count-aware
  同理需重生成後重算 scale。
- 關節 bone 端到端有密網格內插殘差(同 squash `--shear-pivot`);運動基元為 PROPOSAL(手感);單一真值資產。

## 關鍵發現

**一般仿射四自由度(rotate / 非均勻 scale / shearX / shearY)+ 體積守恆(det≡1)生成端全數成立** ——
twist_vol 是最後一塊(反相雙軸 shear 且守恆)。**行列式只約束 scale 之積 → 守恆補償的 split(均勻/非均勻)
是獨立於守恆的手感自由度**;均勻是「不引入任意各向異性」的最小客觀選擇。與 squash 一致:**跨通道守恆約束
由 `_env` 建構保證(sx·sy=1/cos)則任一 shear 幅度天然不破**,但**端到端經密網格重取樣後守恆只在關鍵幀精確**
(線性內插不守恆,是 keyframe 動畫的內在性質,非生成器缺陷)。
