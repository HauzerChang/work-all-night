# S1 — squash 接檔位差異化:耦合 amplify(candidate G-4''''',`squash_tier_coupled_amplify` L2)

> 2026-09-20。續 (G-4''''):(G-4'''') 讓 `gen_squash` 成為第一個同時產 **shear + 非均勻 scale** 的
> 生成器(斜拉果凍擠壓,每極值幀 scaleX=1+q、scaleY=1/(1+q) 體積守恆),但誠實標記 honest boundary:
> **squash 未接 tier —— 因為逐軸 `_amp_scale` 只放大 identity 上方 overshoot,會破壞 scaleX·scaleY==1**。
> 本次(G-4''''')正好照那條邊界接上:squash 的**擠壓幅度與 shear 峰一起隨檔位遞增**,而**體積守恆逐檔位
> 保持** —— squash 是**首個需耦合放大(coupled amplify)** 的主秀節拍。

## 缺口(honest boundary 的接續)

- **(G-4'''')** 產出耦合 shear + 非均勻 scale 的 squash beat,但 squash **不在** `MAIN_SHOW_CATS` →
  檔位機制 (J) 不碰它。原因:(J) 的 `_amp_scale(v,g)=1+g(v−1) if v≥1 else v` 逐軸放大 —— 對 squash pair
  (scaleX=1+q>1、scaleY=1/(1+q)<1)會**放大拉長軸、保留壓扁軸樓地板** → scaleX·scaleY≠1(破壞體積守恆)。
- 本次(G-4''''')補上:引入**耦合 amplify**,squash 隨檔位放大而守恆不破。

## 關鍵:體積守恆 scale pair 不能逐軸放大 → 耦合 amplify

squash 的每個極值幀是 (scaleX=1+q, scaleY=1/(1+q)) 的**體積守恆 pair**(積≡1、非均勻)。逐軸 `_amp_scale`
只放大值≥1 那軸 → 破壞守恆。正解 = **`_amp_scale_pair(scx, scy, g)`**:擠壓量 q 取**拉長軸**(值較大者)之
`(v−1)`,放大成 `g·q` → 拉長軸 = `1+g·q`(與 `_amp_scale` 對 overshoot **完全同式**),另一軸取倒數還原守恆
= `1/(1+g·q)`。⇒

- ① identity(1,1)→ 不變(g 無關,首尾介面契約對所有檔位保形);
- ② **scaleX·scaleY≡1 逐檔位保持**(耦合 → 體積守恆簽章不被檔位放大破壞,**crux**);
- ③ 擠壓幅度(aniso=|scaleX−scaleY|)隨 g **單調變大**(檔位簽章);
- ④ 各極值 q_i=Q·rⁱ → 放大後 g·q_i 仍**嚴格遞減**(阻尼簽章保形,共同正因子 g)。

shear 通道則同 wobble 走 `v'=g*v`(對 0 對稱,不需耦合)。故 squash 的**兩通道同檔位增益 g 一起放大**
(耦合擠壓 + 斜拉),是**雙通道**幅度差異化。

> **與 (J)/(G-4'') 的區別**:(J) scale 逐軸(overshoot 樓地板規則)、(G-4'') shear 逐幀 `v'=g*v` —— 都是
> **單軸各自獨立**放大;squash 首次要求**一對 scale 值聯動**放大以維持一條不變量(積==1),故新增
> `COUPLED_SCALE_CATS` 把「需耦合放大的 scale 節拍」集中一處(同 SHEAR_CATS 集中 shear 產出者)。

## 做了什麼(全 additive)

1. **`tier_variants.py`**:
   - `MAIN_SHOW_CATS` 加 `"squash"`(使其產 `{beat}__{tier}` 變體)。
   - 新增 `COUPLED_SCALE_CATS = {"squash"}`(需耦合放大 scale 的節拍)。
   - 新增 `_amp_scale_pair(scx, scy, g)`(拉長軸 `1+g·q`、另軸取倒數;均勻/identity 退回逐軸 `_amp_scale`;
     數值 round 4 位對齊 `gen_squash`/`_amp_scale` → g=1.0 逐位元同 base)。
   - `amplify_bone_tl(b, g, coupled_scale=False)` / `amplify_anim(anim, g, coupled_scale=False)` 加參數:
     `coupled_scale=True` → scale 走 `_amp_scale_pair`;預設 False → 逐軸 `_amp_scale`(其餘節拍不變)。
2. **`gen_animations.py`**:`build_animations` 對主秀 beat amplify 時傳 `coupled=(cat in COUPLED_SCALE_CATS)`。
3. **`validate_squash_tier.py`**(新,5 AC)。
4. **`validate_tier_combo_count.py`**:K5c「count 只作用 combo」改以 **full(gains+combo_hits) vs
   amp_only(gains-only)** 逐位元比對(見下「踩雷」)。
5. **`check_readiness`** 新增 cap `squash_tier_coupled_amplify` L2 併入 `spine-anim-forge`(仍 HOLD)。
6. 圖 `knowledge/figures/s1_squash_tier.png`(左:各檔位 scaleX/scaleY 曲線;中:體積積逐檔位≈1;右:
   shear 峰 + 擠壓 aniso 雙軸皆隨檔位遞增)。

## 自我驗收(`validate_squash_tier.py`,5 AC 全 PASS)

從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(tier_gains)` 端到端量:

- **Q1 present + backward-compat**:每檔位 `squash__{tier}` finite/有 bone/≥1 bone **同時**帶 shear 與非均勻
  scale、名經 `beat_category` 仍路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains 的 base + In/Loop/Out
  相同 → 純加性 opt-in)。
- **Q2 crux — dual-channel 單調**:各檔位峰 |shearX| **[16, 21.6, 27.2, 33.6]°** 與峰擠壓量
  aniso **[0.298, 0.394, 0.486, 0.588]** 皆 Super<Mega<Omg<Legend **嚴格遞增**,且 Super(g=1)兩峰 == base。
- **Q3 crux — 逐檔位體積守恆**:**每個檔位**的 squash bone 內部極值幀仍 (a)|scaleX·scaleY−1|≤2e-2
  (實測 ~1e-4,4 位捨入下);(b)非均勻(max aniso≥0.05);(c)擠壓幅度 |scaleX−1| 相繼遞減(阻尼保形)。
  → **耦合放大不破壞守恆**,本 candidate 的核心。
- **Q4 identity 介面**:每檔位 squash bone 首尾 scale==(1,1) 且 shear==0(對所有檔位可插 Loop 間)。
- **Q5 負對照**:
  - (a) **平增益守衛**:增益全 1.0 → Q2 兩軸遞增 FALSE 且各檔位逐位元 == base;
  - (b) **naive-amplify 守衛(crux 鑑別)**:對同一守恆 pair(1.16, 1/1.16)走**逐軸**
    `amplify_bone_tl(coupled_scale=False)`(g=2.1)→ 積 = **1.152 破壞守恆**(|−1|>2e-2);耦合路徑積 = 1.0
    維持 → **證「耦合放大」必要、且閘測得出差異**;
  - (c) **耦合單元測**:`_amp_scale_pair` 對 identity(1,1)→ 不變;對守恆 pair → 仍守恆(積≈1)且擠壓量
    放大(拉長軸=1+g·q);對均勻 overshoot(1.3,1.3)→ 退回逐軸 `_amp_scale`。

**端到端**:`build_spine --animate --tier-variants --shear-pivot` 直出
`squash__{Super,Mega,Omg,Legend}`,`validate_build` round-trip **overall_pass**(premult MAE 0.031)。

## 關鍵發現 / 踩雷

- **耦合不變量 = 新的放大保形類型**:(J)/(G-4'') 的放大都是「單軸各自 `v'=1+g(v−1)` 或 `g·v`」;squash
  首次要求「一對值聯動放大以守住 scaleX·scaleY==1」。抽象出來就是:**放大幅度時要放大的是「語意量」
  (擠壓量 q)、不是「原始通道值」** —— 一旦通道間有不變量耦合,就必須在語意量上放大再重建通道值。
- **naive-amplify 守衛是最有力的鑑別子**:直接示範舊逐軸路徑(coupled_scale=False)會把積推到 1.15,證明
  這不是「換個寫法」而是**必要的正確性修正**,且閘對正確/錯誤兩路都測得出(閘可信)。
- **踩雷:新 cat 進 MAIN_SHOW_CATS 會擾動別的 count/幅度閘**。squash 的 scale 幅度隨檔位遞增後,
  `validate_tier_combo_count` 的 K5c(原「非-combo 主秀 beat 各檔位峰數相同」)誤報 squash 外洩 ——
  因為 squash 的 scale overshoot 在高檔位跨過 impact 峰偵測門檻(那是**幅度軸**造成、非 combo 連擊數外洩)。
  **正解:把連擊數效果與幅度效果分離** —— K5c 改比 **full(gains+combo_hits) vs amp_only(gains-only)**
  是否逐位元相同(相同即證 combo_hits 未外洩到 combo 以外)。同 (G-4'') 把 J 閘 J3 改 channel-aware 的教訓:
  **每次有新通道/新 cat 接上,量測型負對照要重新確認量的是「該效果」而非被新效果污染的代理量**。
- **round 4 位剛好夠**:守恆容差 TOL_VOL=0.02,4 位捨入誤差 ~1e-4 遠在其內;且 4 位對齊 `gen_squash`
  的 scale 精度 → g=1.0 時耦合路徑逐位元 == base(backward-compat 靠這點成立)。

## honest boundary(仍在)

- 檔位增益階梯 g=[1.0,1.35,1.70,2.10] 為 **PROPOSAL**(客觀簽章=擠壓/斜拉隨檔位遞增;多爆才對味的手感
  留使用者 A 類)。
- squash **count-aware**(擠壓段數隨檔位,`gen_squash(nosc=)` 已備參數未接,比照 G-4''')為後續。
- 只產 **shearX**(shearY≡0);雙軸 shear / rotate+scale+shear 三通道同時的運動基元為後續。
- 單一真值資產(robot_parts)、運動基元先驗 → `spine-anim-forge` 區塊**仍 HOLD**(防固化)。

## 下一步(擇一,皆純自主)

- **squash count-aware**(擠壓段數隨檔位,nosc 已備參數,比照 G-4''')—— 完成 squash 的雙軸檔位差異化。
- 產 **shearY**(雙軸 shear)/ shear+scale+rotate 三通道同時的運動基元(塞滿一般仿射 M 的所有自由度)。
- **(J-3)** cascade 波速/散佈/件數隨檔位(cascade 的 count-aware:跨件波的第三種檔位軸)。
- **(G-1)** `--rig`×pivot 各 flag per-bone 語意去重;**(G-2)** 主秀 beat 下 limb 繞關節 AC。
- S5→L3 仍待 **(D) 多 rig 真值**(C/資源類,使用者提供)。
