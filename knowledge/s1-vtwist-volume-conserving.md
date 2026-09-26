# S1 (G-4''''''-vol) 體積守恆扭轉 —— 反相雙軸 shear + 耦合 uniform scale 使 full-matrix det≡1

- **結論**:新增節拍 `gen_vtwist`(體積守恆扭轉)補上 twist(G-4'''''')一路留到現在的最後一條 honest
  boundary —— **反相雙軸 shear 會變面積**。twist 的反相雙軸 shear(shearY=−φ·shearX)本身完整 local 仿射
  `M=transform_matrix_full(0, sx, sy, shearX, shearY)` 的 `det = sx·sy·cos(shearX−shearY)`;在純雙軸 shear
  (sx=sy=1)時 `det = cos(Δ)`(Δ=shearX−shearY=(1+φ)·shearX)**< 1** → 擰轉會**縮面積**(物理上合理,
  像擰毛巾投影變小;峰 Δ≈27° → cos≈0.889 → 掉 ~11%)。本次在反相雙軸 shear 上加一層**耦合 uniform scale**
  s=1/√cos(Δ) 使 `sx·sy = s² = 1/cos(Δ)` ⇒ **整個 local 仿射 det ≡ 1**(擰而不變面積)—— 至此塞滿一般
  仿射四自由度(rotate / 非均勻 scale / shearX / shearY,由 pivot 補償組合)且**整體體積守恆**。

- **運動基元 = 反相雙軸阻尼 shear(同 gen_twist)+ 每極值耦合 uniform scale**:
  - `shearX(τ)` / `shearY(τ)`:完全同 `_twist_env`(shearX 阻尼擺、shearY=−TWIST_PHI·shearX 反相,首尾 0)。
  - `scale(τ)`:每個 shear 極值時刻 i 施 **uniform** `s_i = 1/√cos(Δ_i)`(Δ_i=shearX_i−shearY_i=(1+φ)·shearX_i)
    → full det = `s_i²·cos(Δ_i) ≡ 1`;首尾 scaleX==scaleY==1(identity 介面)。scale 與 shear 同源(同極值 τ)→ 耦合。

- **與 squash(G-4'''')的關鍵差異 —— 兩種不同的「體積守恆」**:
  - **squash**:用**非均勻** scale(`scaleX=1+q`、`scaleY=1/(1+q)` → `scaleX·scaleY≡1`),守的是 **scale 通道**
    的積;但其純 shearX 仍使 full det = `1·cos(shearX) ≠ 1` → **整個矩陣面積不守恆**(shearX 本身縮面積)。
  - **vtwist**:用**均勻** scale(scaleX==scaleY),守的是 **full-matrix** det ≡ 1 —— uniform scale 恰好補回
    反相雙軸 shear 造成的面積損失。
  - ⇒ 兩者以「scale 是否 uniform」乾淨分離、互不洩漏(squash isolation 閘查**非均勻** scale,不誤傷 vtwist 的
    uniform scale;vtwist 閘查 uniform,負對照用 squash 式非均勻證鑑別力)。

- **依據/來源**:`tools/analyzer/beat_templates.py`(`gen_vtwist`/`_vtwist_env`/`_vtwist_det_scale`/`VTWIST_KEYWORDS`,
  沿用 `_TWIST_SHEARX`/`TWIST_PHI`)、`gen_animations.py`(`_DISPATCH["vtwist"]` + `_CAT_KEYWORDS` 註冊,置
  twist **之前**避免子字串爭用;`beat_category` 兩段式:精確 token 優先、再子字串)、`genre_priors.py`
  (slot_bigwin 新增 `vtwist` beat + `_BIGWIN_ROLES["vtwist"]`,additive)、`tier_variants.py`
  (`SHEAR_CATS` 加 `vtwist` = 第四個 shear 產出者;scale 均勻故**不**入 `COUPLED_SCALE_CATS`)、
  自我驗收閘 `tools/analyzer/validate_vtwist_gen.py`(**6 AC 全 PASS**)。真值/fixture 同 (E/H/I/J/G-4'/G-4''''/
  G-4'''''') 一致:從**先驗庫**(slot_bigwin)→ **真實 build_spine robot 骨架** → `build_animations` 端到端量。

## 6 AC(客觀、可量測)—— 全 PASS

- **VT1 present + dual-channel(crux)**:vtwist beat 直出、finite、有 bone;≥1 bone 帶 shear(shearX 峰 **16.0°**、
  shearY 峰 **11.2°**,反相雙軸)**且**帶 scale(峰 |s−1| **0.0603**)—— 耦合守恆 scale 實際存在。
- **VT2 兩軸阻尼振盪 + 反相**:每 vtwist bone 的 shearX 與 shearY 各自(a)首尾 0、(b)繞 0 變號≥3、(c)相繼極值
  嚴格遞減(阻尼);且每內部極值 shearX·shearY<0(反相)。復用 twist/shear-gen 判準。
- **VT3 full-matrix 體積守恆(crux)**:每 vtwist bone 每內部極值幀 (a)完整 local M 的 det ≈ 1(|det−1|≤3e-3,
  **實測 <9e-5**);(b)scale **uniform**(|scaleX−scaleY|≤1e-4,實測 **aniso=0.0**,異於 squash 非均勻);
  (c)拿掉 scale(純雙軸 shear)det=cos(Δ) 峰面積損失 ≥2%(**實測峰 0.889 → 損失 11%**)→ 證 scale 正是守恆來源。
- **VT4 identity 介面**:sample(0)/sample(dur) 各 bone identity,shear 首尾 (0,0)、scale 首尾 (1,1) → 可插 Loop 間。
- **VT5 端到端守恆仿射 pivot 不動**:`build_spine --shear-pivot` 產出 vtwist 帶補償;有關節 pivot 的 bone pivot 殘差
  **<0.016px**(右手 0.0130/頭 0.0042/左手 0.0157)vs 內建負對照(未補償=繞件中心,含雙軸 shear+scale)
  **8–29px**(>1000× 餘裕)→ 證補償把守恆一般仿射也錨在 pivot。
- **VT6 負對照/隔離**:(a)**無 scale 守衛** 純雙軸 shear(s≡1,即 twist)→ full det=cos(Δ)≠1 → 守恆 FALSE
  (證 scale 是守恆來源);(b)**非均勻 scale 守衛** squash 式 scaleX≠scaleY(積=1)→ uniform FALSE(證閘測
  「uniform 守恆 scale」非「任意耦合 scale」);(c)**shearY 隔離** 非 twist/vtwist beat 皆 shearY≡0;
  (d)**加性** 移除 vtwist → 其餘 beat 逐位元不變(零回歸);(e)**跨 beat 鑑別(crux)** 同一份 build 內
  squash beat 的 full det 偏離 1 達 **0.0387**(守 scale 積非整個矩陣)vs vtwist full det 偏離 **8.8e-5** → 量化
  兩種「體積守恆」的差異。

## 回歸 / 端到端

- **回歸踩雷(同 twist_gen 的 SHEAR_CATS 模式)**:vtwist 是新的 **shearY 產出者** → `validate_twist_gen.py` 的
  TW6(c) shearY-isolation 原以 `beat_category==\"twist\"` 認定合法 shearY 產出者,會把 vtwist 誤判為洩漏 → 改為
  `in (\"twist\",\"vtwist\")`。vtwist 亦是新的 **shear 產出者** → 併入 `tier_variants.SHEAR_CATS`(集中一處,
  各 shear-isolation 閘 shear_gen W5b / wobble_tier T4 / twist_tier TT6c 以此認定,無須逐一改硬編碼)。
- vtwist 的 scale 為 **uniform**,故 squash 的非均勻 scale isolation(SQ6c 用 `_has_aniso_scale`)天然不誤傷;
  squash_tier c_coupled 只查 `__tier` 變體、vtwist 未入 MAIN_SHOW_CATS 故無 tier 變體 → 不受影響。
- 端到端 `build_spine --animate --shear-pivot` 直出 `vtwist`(scale+雙軸 shear 經 pivot 補償仍守恆存活);
  新增 cap `vtwist_volume_conserving` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。

## 關鍵發現

- **full-matrix 體積守恆 ≠ scale-通道守恆**:squash 守 `scaleX·scaleY≡1`(scale 通道),但整個 local 矩陣
  `det=cos(shearX)≠1`(shear 仍縮面積);vtwist 守整個矩陣 `det≡1`,用 **uniform** scale 補反相雙軸 shear 的
  面積損失。兩種守恆以「scale 是否 uniform」乾淨分離、可量化區別(同 build 內 squash 偏離 0.039 vs vtwist 8.8e-5)。
- **真簽章常需兩獨立條件並立**(再次印證):vtwist 的「體積守恆扭轉」= (a)full det≡1 且 (b)scale uniform 且
  (c)純 shear 本身不守恆(否則 scale 是多餘的)—— 同 twist「反相雙軸=兩軸非零 且 反相」、squash「非均勻 且
  scale 積=1」、cascade「散佈 且 遞增」。
- **一般仿射的面積自由度至此被守恆地填滿**:rotate/scale/shearX/shearY 四通道生成端皆已驅動過(twist 系列),
  vtwist 再讓「反相雙軸 shear + 耦合 scale」的組合在**整個矩陣層級**守恆 —— 擰而不變面積是「擰毛巾但投影面積不變」
  的乾淨數學實現(uniform scale = 各向同性補償,不引入額外非均勻)。

## honest boundary(仍在)

- vtwist 未接 tier 幅度 / count-aware(比照 twist G-4''''''-tier / -count 為後續;`gen_vtwist(nosc=)` 已備參數
  未接)。接 tier 時 crux:兩軸同比放大 g → Δ'=(1+φ)·g·shearX 改變 → 守恆 scale 需**隨 g 重算** s=1/√cos(Δ')
  (不能沿用 base 的 s;守恆約束在放大後要重新滿足 —— 同 squash tier 的「沿守恆流形放大」但這裡是 full-det 流形)。
- **uniform 守恆是一種選擇**:亦可用**非均勻** scale 同時守 full det ≡1(把 twist 的雙軸 shear 與 squash 的
  非均勻擠壓耦合成「擰+擠且整體守恆」),為更飽滿的一般仿射變體(後續)。
- 幅度 / φ 皆為 PROPOSAL(手感 A 類);單一真值資產(robot_parts);anim-forge 仍 HOLD。
