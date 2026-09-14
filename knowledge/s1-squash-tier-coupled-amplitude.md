# S1 — squash 接檔位差異化:體積守恆耦合 amplify(candidate G-4''''',`squash_tier_coupled_amplitude` L2)

> 2026-09-14。續 (G-4''''):(G-4'''') 讓 `gen_squash` 成為第一個**同時**產出 `shear` 與非均勻 `scale`
> (體積守恆擠壓)的生成器,但它**不在** `MAIN_SHOW_CATS` —— 因為舊的幅度增益 `_amp_scale`(只放大
> identity 上方 overshoot、下方樓地板不動)會**破壞體積守恆**。本次補上那條 honest boundary:squash 併入
> `MAIN_SHOW_CATS`,scale 通道改走**體積守恆耦合放大**,使檔位愈高擠壓愈強而 `scaleX·scaleY≡1` 恆成立。

## 缺口(honest boundary 的接續)

- **(G-4'''')** 誠實標記:「squash 未接 tier 幅度(`_amp_scale` 只放大 identity 上方 → 破壞體積守恆,
  需**耦合 amplify**)」。squash 的 scaleX=1+q>1 會被 `_amp_scale` 放大、scaleY=1/(1+q)<1 樓地板不動
  → `scaleX·scaleY≠1`(不再是擠壓,而是「拉長 + 微壓」的變形)。
- 本次(G-4''''')照那條邊界接上:**擠壓強度隨檔位遞增**且**面積恆守恆**。

## 關鍵:squash 的檔位差異化必須「兩軸耦合」,不能逐軸獨立

體積守恆 squash 的兩軸不是獨立幅度,而是**一個**擠壓量 q 的兩面(scaleX=1+q 拉長、scaleY=1/(1+q) 壓扁)。
放大擠壓 = 放大 q,兩軸必須**一起**變:

- **耦合放大**(`_amp_squash_pair`):把拉長量 `q=scaleX−1` 放大 g 倍 → `scaleX'=1+g·q`,scaleY **重建**
  為 `1/(1+g·q)` ⇒ `scaleX'·scaleY'≡1`(重建保證精確守恆)且 `scaleX'≠scaleY'`(仍非均勻)。
  此式**等價於「以 Q'=g·Q 重跑 `gen_squash`」**(把整體擠壓強度乘 g)。
- **逐軸放大**(舊 `_amp_scale`,錯誤示範):只動 scaleX>1(放大)、scaleY<1 樓地板不動 → 積≠1 破壞守恆
  (Legend g=2.1 下 |積−1| 實測達 0.15 → 見 V5b 判別子)。

介面/簽章保形:`q=0`(identity 幀)→ (1,1) 不動(可插 Loop);`g=1.0`(Super)→ scaleX'=scaleX、
scaleY'=1/scaleX == base scaleY(**逐位元向後相容**);uniform g 不改「|scaleX−1| 隨極值遞減」的阻尼耦合。
與 (J) 的 shear/scale/rotate 幅度軸**正交可疊** —— shear 峰仍用 `amplify_bone_tl` 的 `v'=g·v` 一併遞增。

## 做了什麼(全 additive)

1. **`tier_variants.py`**:`MAIN_SHOW_CATS` 加 `"squash"`;新增 `COUPLED_SCALE_CATS={"squash"}`;
   新增 `_amp_squash_pair(sx, sy, g)`(體積守恆耦合放大);`amplify_bone_tl(b, g, coupled_scale=False)` /
   `amplify_anim(anim, g, coupled_scale=False)` 加旗標 —— `coupled_scale=True` 時 scale 走耦合放大,否則
   逐軸 `_amp_scale`(其餘主秀 beat 不變)。
2. **`gen_animations.py`**:`build_animations` 對主秀 beat 依 `cat ∈ COUPLED_SCALE_CATS` 決定 `coupled`,
   透傳給 `_amplify_anim`。無 import 迴圈、純旗標路由。
3. **`validate_squash_tier.py`**(新,5 AC)。
4. **`validate_tier_combo_count.py`**:K5(c) 由「非-combo beat 各檔位峰數不變」改為「帶/不帶
   `tier_combo_hits` 的變體逐位元相同」(full vs amp_only)—— squash 入 MAIN_SHOW 後其 scaleX overshoot
   會隨檔位跨過 impact 門檻(1.10)使 `_min_peaks` 峰數變動,但那是**幅度**效應非 count 外洩;逐位元比對
   只認 count 真正改動結構,對所有非-combo 主秀 beat robust(判準更精確,非放寬)。
5. **`check_readiness`** 新增 cap `squash_tier_coupled_amplitude` L2 併入 `spine-anim-forge`(仍 HOLD)。
6. 圖 `knowledge/figures/s1_squash_tier.png`(左:各檔位 scaleX↑/scaleY↓ 扇開;中:scaleX·scaleY≡1;
   右:shear/拉長/非均勻三軸峰皆遞增)。

## 自我驗收(`validate_squash_tier.py`,5 AC 全 PASS)

從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(tier_gains=…)` 端到端量:

- **V1 present + backward-compat**:squash base 為雙通道(≥1 bone 同時帶 shear+非均勻 scale);每檔位
  `squash__{tier}` finite/有 bone/仍雙通道/名經 `beat_category` 路由回 squash;base 逐位元不變;
  **Super(g=1)逐位元 == base squash**。
- **V2 crux — 耦合幅度單調**:各檔位 Super<Mega<Omg<Legend **嚴格遞增**且 Super==base:
  (a)shear 峰 [16, 21.6, 27.2, 33.6]°;(b)拉長峰 |scaleX−1| [0.16, 0.216, 0.272, 0.336];
  (c)非均勻峰 |scaleX−scaleY| [0.298, 0.394, 0.486, 0.588]。
- **V3 crux — 每檔位守恆**:**每個檔位**的 squash bone、**每個** scale 極值幀 (a)|scaleX·scaleY−1|≤0.02
  (實測 <5e-5);(b)至少一極值 |scaleX−scaleY|≥0.05(仍真擠壓);(c)|scaleX−1| 隨極值嚴格遞減(阻尼耦合)。
- **V4 阻尼 + identity 介面**:**每檔位** shear (a)首尾 0、(b)繞 0 變號 ≥3、(c)相繼極值遞減;scale 首尾 (1,1)。
- **V5 負對照**:(a) **平增益守衛**:全 1.0 → V2 遞增 FALSE 且各檔位逐位元 == base;
  (b) **耦合判別子(crux)**:對 base squash scale 施**舊逐軸** `_amp_scale`(Legend g)→ 守恆 FALSE
  (|積−1| 達 0.15);真正耦合變體(同 g)→ 守恆 TRUE。**證閘測「耦合守恆放大」非「有 scale 放大即可」**;
  (c) **單元測**:`_amp_squash_pair` 對守恆對施同 g → 積==1(精確)、q=0 →(1,1)不動;
  `amplify_bone_tl(coupled_scale=True)` 保守恆、`coupled_scale=False`(逐軸)破壞守恆(同 bone、同 g)。

**端到端**:`build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}`
(shear-pivot 補償經 **translate** 通道,scale 通道不受影響 → 守恆存活),`validate_build` round-trip
**overall_pass**(premult MAE 0.031、0 孤兒)。

## 關鍵發現 / 踩雷

- **體積守恆是「耦合約束」,不是兩個獨立幅度**:同 (G-4'''') 的洞見「真簽章常需兩獨立條件並立」的
  對偶面 —— 檔位放大時,守恆(兩軸積=1)與非均勻(兩軸不等)必須**同時**維持,唯一辦法是把兩軸綁成
  單一 q 的函數(重建 scaleY=1/scaleX),逐軸獨立放大必破壞守恆。這是**第一個需要「耦合 amplify」的檔位軸**
  (前面 J=scale overshoot、G-4''=shear 皆逐軸/單通道對 0 對稱即可)。
- **重建優於逐軸微調**:由 scaleX 唯一決定 q、scaleY 直接重建 → 積**精確**為 1(round4 後 <5e-5),
  比「兩軸各自套某公式再期望積≈1」更穩;`g=1` 時 `1/scaleX` 與 base scaleY 逐位元吻合(因 scaleX=1+q 的
  q=Q·rⁱ 於 [0.1,0.16]×{1,0.5,0.25,…} 皆 round 乾淨 → 1+q 精確、1/(1+q) 與 base 同)。
- **新主秀 beat 進 MAIN_SHOW → 掃全主秀的舊閘可能假陽性**:K5(c) 用「峰數跨檔位不變」認 count 隔離,
  squash 的 scaleX overshoot 跨 impact 門檻使峰數變動被誤判為 count 外洩。修法是把隔離判準換成**更精確的
  逐位元對比(帶/不帶該旗標)**,而非放寬 —— 隔離的本義就是「該旗標對此 beat 零影響」。同 (G-4'') 對 J3
  改 channel-aware、(G-4'''') 對 shear-isolation 改用 `SHEAR_CATS`:每加一個新通道/新 beat,掃全主秀的閘
  都要檢一次假設是否仍成立。

## honest boundary(仍在)

- 檔位增益階梯 g=[1.0,1.35,1.70,2.10] 為 **PROPOSAL**(結構/守恆客觀、擠多爆的手感留使用者 A 類)。
- squash **count-aware**(擠壓段數 nosc 隨檔位,`gen_squash(nosc=)` 已備參數,比照 G-4''')仍未接。
- 目前只產 **shearX**(shearY≡0);**shearY / 三通道(rotate+非均勻 scale+雙軸 shear)同時**塞滿一般仿射 M
  的所有自由度為後續。
- 單一真值資產(robot_parts)、運動基元先驗 → `spine-anim-forge` 區塊**仍 HOLD**(防固化)。

## 下一步(擇一,皆純自主)

- **squash count-aware**(擠壓段數隨檔位;nosc 已備,比照 G-4''')—— 補完 squash 的「幅度軸 × 結構軸」雙軸。
- 產 **shearY**(雙軸 shear)/ rotate+scale+shear 三通道同時的運動基元(塞滿一般仿射)。
- **(J-3)** cascade 波速/散佈/件數隨檔位(cascade 的第三種檔位軸)。
- **(G-1)** `--rig`×pivot 各 flag per-bone 語意去重;**(G-2)** 主秀 beat 下 limb 繞關節 AC。
- S5→L3 仍待 **(D) 多 rig 真值**(C/資源類,使用者提供)。
