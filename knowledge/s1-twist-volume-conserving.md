# S1 (G-4''''''-vol) 體積守恆扭轉(volume-conserving twist:反相雙軸 shear + 均勻面積補償 → 完整仿射 det≡1)

- **結論**:把 (G-4'''''') 的 `twist`(反相雙軸阻尼 shear)加一支**均勻(isotropic,sx=sy)面積補償 scale**
  `s = 1/√cos(shearX−shearY)`,使 Spine local **完整**仿射行列式 `det(M) = scaleX·scaleY·cos(shearX−shearY) ≡ 1`
  ——「擰而不變面積」。新生成器 `gen_twist_vol` 經先驗庫直出 `voltwist` beat,`build_spine --shear-pivot` 端到端
  把 rotate/scale/shearX/shearY 一起繞關節 pivot 補償。**這是產線第一個令完整局部仿射行列式守恆的節拍**。
- **信心**:高(端到端經 `build_animations`/真實 build_spine robot 骨架量測,`validate_twist_vol.py` 7 AC + 負對照全
  PASS;23 回歸閘全綠,無 GREEN→RED;round-trip `validate_build --shear-pivot` overall_pass)。
- **相關階段**:專案第 2 階段(S1 反推分析器 / anim-forge)。cap `twist_volume_conserving` L2 併入 `spine-anim-forge`
  (仍 HOLD,防固化)。

## 為什麼是這個 bounded chunk

twist 一路(G-4''''''/tier/count)的 honest boundary 每次都明列同一句:**「反相雙軸未接體積守恆耦合 scale
(`det=cos(shearX−shearY)≠1` → 擰轉變面積,volume-conserving twist 為後續)」**。至今所有產 shear 的節拍
沒有一個令**完整** det≡1:

| 節拍 | shear | scale | 完整 det = sx·sy·cos(shx−shy) |
|---|---|---|---|
| wobble | 純 shearX | 無 | cos(shearX) < 1 |
| squash | shearX | 非均勻 scaleX·scaleY≡1(**scale 通道自身**守恆) | 1·cos(shearX) < 1 |
| twist | 反相雙軸 shearX/Y | 無 | cos((1+φ)·shearX) < 1 |
| **voltwist(本次)** | 反相雙軸 shearX/Y | **均勻** sx=sy=1/√cos(shx−shy) | **≡ 1** |

**關鍵區別(voltwist vs squash)**:squash 的「體積守恆」指 **scale 通道自身** scaleX·scaleY≡1(拉一軸壓一軸),
但完整仿射 det 仍被 shear 的 cos 因子壓到 <1;voltwist 守恆的是**完整 det≡1**,做法是用**等向** scale 抵消
shear 的 cos 因子。且 scale 均勻(sx=sy)是與 squash(sx≠sy)的第二個乾淨分界。

## 幾何(公式來源)

Spine local 2×2 一般仿射(見 `validate_shear_pivot.transform_matrix_full`):兩基底夾角 = 90 + shearY − shearX,
故 `det(M) = scaleX·scaleY·cos(shearX − shearY)`(度)。twist 反相時 shearX − shearY = shearX − (−φ·shearX)
= (1+φ)·shearX ≠ 0 → cos 因子 <1 → 面積縮(特效峰 shearX=16° → span 27.2° → det=cos27.2°=0.889,縮 ~11%)。
補**均勻** scale s 使 `s²·cos(shx−shy) ≡ 1` → **s = 1/√cos(shx−shy)**:
- 端點 shx=shy=0 → cos0=1 → s=1 → scale 端點 (1,1)(**identity 介面保持**,可插 Loop 間);
- 每個 shear 極值 s>1(等向微脹,恰補回面積)⇒ 完整 det ≡1。
- |shx−shy| 峰 =(1+φ)·A ≤ 27.2° < 90° → cos>0 恆非奇異。

## 實作(全 additive,重點在驗證)

- `tools/analyzer/beat_templates.py`:新增 `_twist_vol_scale(shx,shy)=1/√cos(shx−shy)`;`gen_twist` 加
  `volume_conserve=False` 參數(預設 False → 逐位元同原輸出,向後相容),True 時額外產均勻 scale 通道;
  薄包裝 `gen_twist_vol` = `gen_twist(..., volume_conserve=True)`。新增 `VOLTWIST_KEYWORDS`(整詞,gen_animations
  的 `_CAT_KEYWORDS` 將 voltwist 置於 twist **之前**,確保 beat 名 'voltwist' 的整詞不被 twist 的子字串 'twist' 搶去)。
- `tools/analyzer/gen_animations.py`:import `gen_twist_vol`/`VOLTWIST_KEYWORDS`;`_DISPATCH["voltwist"]`;`_CAT_KEYWORDS`
  加 `voltwist`(置 twist 前);`DUR["voltwist"]` 同 twist 窗長。
- `tools/analyzer/genre_priors.py`:`_BIGWIN_ROLES["voltwist"]` + slot_bigwin beats 加 voltwist(additive、coverage 仍 1.0)。
- `tools/analyzer/tier_variants.py`:voltwist 併入 `SHEAR_CATS`(合法 shear 產出者 → 各 shear-isolation 閘自動接受);
  新增中央 `SHEARY_CATS = {"twist","voltwist"}`(合法 shearY 產出者)。**voltwist 刻意**不加入 `MAIN_SHOW_CATS` /
  `COUNT_AWARE_CATS` / `COUPLED_SCALE_CATS`(見 honest boundary:tier 放大 shear 後補償 scale 需依放大後 shear 重算)。
- `tools/analyzer/validate_twist_gen.py`:TW6(c) shearY-isolation 由硬編碼 `=="twist"` 改用中央 `TV.SHEARY_CATS`
  (voltwist 亦合法產 shearY → 一併排除;集中一處,避免每加一個 shearY 節拍就改硬編碼)。
- `tools/analyzer/validate_twist_vol.py`:新閘(7 AC)。復用 `validate_shear_gen`(阻尼簽章)+ `validate_twist_gen`
  (`_shear_y`/`_shear_xy`/`_interior_shear`/`_tw3_eval`/`_has_shear_y`,雙軸讀取與反相判準)+ `validate_shear_pivot._world`。
- `tools/check_readiness.py`:註冊 cap `twist_volume_conserving` L2(pipeline)。

## crux(閘的鑑別力來源)

**完整 det≡1** 是一個**新不變量**,必須與已有的兩種「守恆」乾淨分開:

- **VV3 完整 det 守恆**:每幀 `|scaleX·scaleY·cos(shearX−shearY) − 1| ≤ 1e-3`(實測 <5e-6)。
- **負對照 (a) 純 twist 守衛**:同 shearX/Y 但無補償 scale(視 sx=sy=1)→ 完整 det=cos(shx−shy)<1 → 守恆 **FALSE**
  (證閘測的是「完整 det≡1」,不是「有 scale 即可」;5 個真 twist bone 全被正確判非守恆)。
- **負對照 (b) squash 守衛**:合成非均勻 scaleX·scaleY≡1 但 shearY≡0(squash 樣)→ 完整 det=cos(shearX)≠1 →
  VV3 **FALSE**,且 VV4 均勻 **FALSE** —— 一次證明「完整 det≡1」≠ squash 的「scale 通道自身守恆」,且**均勻性**把
  voltwist(sx=sy)與 squash(sx≠sy)分開。
- **VV4 均勻補償**:每幀 |scaleX−scaleY|≤1e-3(等向)+ 內部極值 scale>1(真有補償)+ 端點 (1,1)。

## 驗證結果(量化)

- `validate_twist_vol.py` **7 AC 全 PASS**。VV1 shearX 峰 16°、shearY 峰 11.2°;VV3 各 bone det∈{0.999999…1.000001};
  VV4 均勻 |sx−sy|=0;VV6 端到端 pivot 殘差 <0.016px(右手 0.0131/頭 0.0042/左手 0.0158)vs 負對照 24–29px(>1000×)。
- 端到端 `build_spine --animate --shear-pivot` 直出 `voltwist`(pivot 補償後每幀完整 det 仍≡1),`validate_build` round-trip overall_pass。
- **23 回歸閘全綠**(22 既有 + 新 twist_volume_conserving);`check_readiness.py` 退出 0(0 RED,無 GREEN→RED)。

## 關鍵發現

- **完整仿射四自由度(rotate / 非均勻 scale / shearX / shearY)生成端不僅全數被驅動過(G-4''''''),更首度可令其
  完整行列式守恆** —— 用**等向 scale 抵消 shear 的 cos 因子**是「塞滿一般仿射且面積守恆」的通則(對照 squash 的
  「沿 scaleX·scaleY≡1 守恆流形生成」是**局部**守恆,voltwist 是**全域**完整 det 守恆)。
- **一種運動可有多種守恆語意**:squash 守 scale 自身、voltwist 守完整 det;閘必須用**負對照**把它們分開,否則
  「有 scale 又守恆」會誤放行(gate credibility 的來源)。

## honest boundary(仍在)

- voltwist 未接 **tier / count-aware**:tier 放大兩軸 shear(shearX'=g·shearX、shearY'=g·shearY)後,面積補償 scale
  必須依**放大後** shear 重算(s'=1/√cos(g·(shx−shy)))才續守恆 —— 逐軸/單一-g amplify 對 scale 走 `_amp_scale`
  不會給出這個值,故需一支**「shear-耦合」scale amplify**(比照 squash G-4'''' → G-4''''' 的分步:先 gen,再 tier)。
- **均勻補償是等積扭轉的一種**:另有非均勻等積解(把補償攤到兩軸不同),此處選等向(最單純、與 squash 乾淨分界)。
- 幅度為 PROPOSAL(手感 A 類);單一真值資產(robot_parts,防固化 → cap 併入 `spine-anim-forge` 仍 HOLD)。
