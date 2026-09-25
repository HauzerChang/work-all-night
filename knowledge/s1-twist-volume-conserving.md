# S1 (G-4''''''-vol) 體積守恆斜扭 twistvol —— 反相雙軸 shear + 各向同性面積補償(守恆完整仿射面積)

- **結論**:新增節拍 `gen_twistvol`(體積守恆斜扭)補上 twist(G-4'''''')一路留到現在的 honest boundary
  ——**反相雙軸 shear 未接體積守恆**。twist 純雙軸 shear 令 Spine local 2×2 行列式 `det = cos(shearY−shearX) < 1`
  → 擰轉會**縮面積**(像擰毛巾投影變小);twistvol 加一條**各向同性**補償 scale `sx=sy=1/√cos(shearY−shearX)`
  使**完整** local det ≡ 1(含兩條 shear 軸的真面積守恆)→ **產線第一個守恆完整仿射面積的節拍**。
  至此**一般仿射 M 的四自由度(rotate / scale / shearX / shearY)生成端全數被真實 beat 驅動過,且達完整面積守恆**
  ——「shear + scale + rotate 三通道同時、塞滿一般仿射四自由度且守恆」這句 STATE 目標就此成立。

## 關鍵幾何(det 公式與各向同性補償)

- Spine 3.8 bone local 2×2(`pivot_rotation.transform_matrix_full`,度數):
  `a=cos(rot+shx)·sx, c=sin(rot+shx)·sx, b=cos(rot+90+shy)·sy, d=sin(rot+90+shy)·sy`。
  → **det = a·d − b·c = sx·sy·sin(90 + shy − shx) = sx·sy·cos(shy − shx)**(rotate 不影響面積,消去)。
- twist(sx=sy=1):`det = cos(shearY−shearX)`。反相時 `shearY=−φ·shearX` → `shy−shx=−(1+φ)·shearX`,
  `cos((1+φ)|shearX|) < 1`(峰 (1+φ)·16°=27.2° → cos≈0.889)→ **面積縮 ~11%**。
- twistvol:令 `sx=sy=s`,要 `det = s²·cos(shy−shx) ≡ 1` → **s = 1/√cos(shearY−shearX)**(≥1,把 shear 縮掉的面積補回)。
  首尾 shear=0 → cos(0)=1 → s=1(**identity 介面保持**)。實測完整 det 逐幀 ∈ [0.999999, 1.000001](~1e-6 餘裕)。

## 與 squash 的鑑別(本閘的鑑別力來源)——「守子塊 ≠ 守完整 det」

- squash(G-4'''')用**非均勻** scale(`sx≠sy`、`scaleX·scaleY=1`)做擠壓,**只守 scale 子塊**;其完整
  det = `(sx·sy)·cos(shearX) = cos(shearX) < 1` → **squash 仍縮面積**(過去「squash 體積守恆」實指 scale 子塊守恆)。
- twistvol 用**各向同性** scale(`sx==sy`)做面積回補,守恆**完整** det(含兩條 shear 軸)。
- 兩者是**兩種正交的面積策略**:squash 非均勻擠壓(改形狀、子塊守恆);twistvol 各向同性回補(不改長寬比、完整守恆)。
- 三者對照(閘的三支判準):
  | 節拍 | scale | 完整 det | 各向同性 |
  |---|---|---|---|
  | 純 twist | sx=sy=1 | cos<1(縮) | 是 |
  | squash 式 | sx≠sy、sx·sy=1 | cos(shearX)<1(仍縮) | 否 |
  | **twistvol** | sx=sy=1/√cos | **≡1(完整守恆)** | 是 |

## 依據 / 來源

- `tools/analyzer/beat_templates.py`:`gen_twistvol` / `_twistvol_scale` / `TWISTVOL_KEYWORDS`(shear 通道同 `gen_twist`
  的 `_twist_env`,再加各向同性補償 scale;`gen_twist` **逐位元不變**,零風險)。
- `gen_animations.py`:`_DISPATCH["twistvol"]` + `_CAT_KEYWORDS`(**twistvol 排在 twist 之前**,避免名含 "twist"
  子字串被 twist 吞掉)。
- `tier_variants.py`:`SHEAR_CATS` 加 `twistvol`(合法 shear 產出者);新增 **`SHEARY_CATS={twist,twistvol}`**
  (集中管理 shearY-isolation,取代 `validate_twist_gen` 對 'twist' 的硬編碼)。
- `genre_priors.py`:slot_bigwin 新增 `twistvol` beat + `_BIGWIN_ROLES["twistvol"]`(additive,coverage 仍 1.0)。
- 自我驗收閘 `tools/analyzer/validate_twist_volume.py`(**7 AC 全 PASS**),真值/fixture 同 (E/H/I/J/G-4'/G-4''''/
  G-4'''''')一致:先驗庫 → **真實 build_spine robot 骨架** → `build_animations` 端到端量。

## 7 AC(客觀、可量測)—— 全 PASS

- **VT1 present + dual-axis + scale(crux)**:twistvol beat 直出、finite、有 bone;≥1 bone **同時**帶 shear
  (shearX 峰 **16.0°**、shearY 峰 **11.2°**,皆 ≥5°)與 `scale` 通道 → 產線第一次「雙軸 shear + 體積補償 scale」。
- **VT2 兩軸皆阻尼振盪**(承 twist):shearX 與 shearY 各自首尾 0 / 繞 0 變號 ≥3 / 相繼極值遞減。
- **VT3 反相雙軸耦合**(承 twist,復用 `_tw3_eval`):每內部極值 shearX·shearY<0 且夾角偏離 |shearY−shearX|≥8°。
- **VT4 完整面積守恆 + 各向同性(crux)**:每幀 (a)完整 det=scaleX·scaleY·cos(shearY−shearX)≈1(|det−1|~1e-6);
  (b)各向同性 |scaleX−scaleY|~0;(c)內部至少一幀補償拉伸 scaleX>1.005(shear 縮 → scale 補)。
- **VT5 identity 介面**:sample(0)/sample(dur) identity,shear 首尾 (0,0)、scale 首尾 (1,1)→ 可插 Loop 間。
- **VT6 端到端一般仿射 pivot 不動**:`build_spine --shear-pivot` 產出 twistvol 帶補償,pivot 殘差 **0.004–0.016px**
  (右手 0.0131 / 頭 0.0042 / 左手 0.0158)vs 內建負對照(繞件中心)**8.57–29.48px**(>1000×)。
- **VT7 負對照 / 隔離**:(a)**純 twist 守衛**:identity scale → 完整守恆 FALSE(det=cos<1);(b)**squash 式守衛**:
  非均勻 sx·sy=1 → 完整 det=cos(shearX)<1(volume FALSE)且各向同性 FALSE;(a2)正對照單元 twistvol 補償 → volume+iso+stretch TRUE;
  (c)**耦合隔離**:唯 twistvol 帶「shearY≠0 且 scale 通道」(twist 有 shearY 無 scale、squash 有 scale 無 shearY);
  (d)**加性**:移除 twistvol → 其餘 beat(含**純 twist 逐位元不變**,證未改 gen_twist)逐位元不變(零回歸)。

## 回歸 / 端到端

- **23 閘全綠**(22 既有 + 新 twist_volume;`check_readiness` 0 RED、無 GREEN→RED)。
- **順帶修復一個 pre-existing RED**(非本 chunk 引入):`validate_analyzer_award.py` 的 `4_storyboard_structure`
  原用 **exact-equality**(`proposed_beats == {In,Loop,Out}`),但 slot_bigwin 先驗庫刻意過度提案主秀節拍
  (burst/hit/combo/…/twist)→ 自那些節拍加入起該 check 恆 FALSE(與本 repo「prior_beats_unused 是誠實」的一貫設計矛盾,
  且 `validate_priors` 覆蓋率=1.0 已驗多提案不損覆蓋)。改為**召回**語意(`Award beats ⊆ proposed_beats`,同
  `1_parts_recall`),多出的提案列 `beats_extra_unused` 透明揭露 → analyze_target 由 RED 轉 GREEN(這是修正過嚴判準,非 gaming)。
- 新增 cap `twist_volume_conserve` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。

## 關鍵發現

- **det = sx·sy·cos(shearY−shearX)**:shear 貢獻面積因子 cos(shy−shx),故「守恆」有兩個層次 —— **scale 子塊守恆**
  (squash:sx·sy=1)與**完整矩陣守恆**(twistvol:sx·sy·cos=1)。過去 squash 的「體積守恆」是前者,twistvol 首度達後者。
- **各向同性補償 vs 非均勻擠壓是兩條正交的面積軸**:同一份雙軸 shear 可配「各向同性回補」(守完整 det,twistvol)
  或「非均勻擠壓」(改長寬比、守子塊,squash 式)—— 兩者可日後結合成同一節拍(twistvol 疊 squash 的非均勻)。

## honest boundary(仍在)

- 各向同性補償(twistvol)與非均勻擠壓(squash)結合成單一節拍(雙軸 shear + 非均勻 + 完整守恆同時)為後續。
- twistvol 未接 tier 幅度 / count-aware(比照 twist G-4''''''-tier/-count;`gen_twistvol(nosc=)` 已備參數未接)。
- 幅度 / φ / 補償策略皆為 PROPOSAL(手感 A 類);單一真值資產(robot_parts);anim-forge 仍 HOLD。
