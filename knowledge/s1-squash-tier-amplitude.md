# S1 — squash 接檔位差異化:體積守恆耦合放大(candidate G-4''''',`squash_tier_amplitude` L2)

> 2026-09-13。續 (G-4''''):(G-4'''') 讓 `gen_squash` 成為**第一個同時產 shear + 耦合非均勻 scale**
> (體積守恆擠壓,scaleX·scaleY≡1 且 scaleX≠scaleY)的生成器,但當時誠實標記 honest boundary:
> 「squash **不在** `MAIN_SHOW_CATS`」—— 因為逐軸 `_amp_scale` 只放大 identity 上方(scaleX>1)卻把
> scaleY<1 當樓地板保留 → **破壞體積守恆**。本次補上:squash 的擠壓幅度隨檔位嚴格遞增,而
> **scaleX·scaleY≡1 恆保持**(shear 峰亦隨檔位遞增 → 雙通道一起放大)。

## 缺口(honest boundary 的接續)

- **(G-4'''')** 補齊了「同時產 shear + 耦合非均勻 scale 的擠壓生成器」,`build_spine --shear-pivot` 端到端
  一般仿射 pivot 不動;但 squash 未接檔位差異化,honest boundary 明寫「需**耦合 amplify**」。
- 本次(G-4''''')正照那條邊界接上:**體積守恆耦合放大** `_amp_scale_coupled`,squash 併入 `MAIN_SHOW_CATS`。

## 關鍵:逐軸放大破壞守恆 → 必須耦合放大(crux)

`_amp_scale(v,g)=1+g(v−1) if v≥1 else v` 對**等比/單向** overshoot 正確(hit/combo 的 scaleX==scaleY≥1),
但對 squash 的**耦合對**(scaleX=1+q>1、scaleY=1/(1+q)<1)會:放大 scaleX、把 scaleY 當樓地板保留
→ scaleX'·scaleY' ≠ 1(**體積守恆壞掉**)。故 squash 的檔位差異化**不能**逐軸放大,必須**耦合放大**:

- **`_amp_scale_coupled(x, g)`**:以 scaleX 復原擠壓量 `q=scaleX−1`、**線性**放大 `q'=g·q`(同 `_amp_scale`
  對 overshoot 的線性增益語意)、重建 `scaleX'=1+q'`、`scaleY'=1/scaleX'`(取整後互為倒數)。
  ⇒ `scaleX'·scaleY'≈1`(**面積守恆**,誤差僅 4-dec keyframe 取整地板 <1e-4)且 `scaleX'≠scaleY'`(**非均勻**)。
- **雙通道**:shear 同 (G-4'') 對 0 對稱放大 `v'=g·v` → shear 峰隨檔位遞增,阻尼振盪簽章保形。

量化(robot 骨架、b_光暈 dual bone,g=[1.0,1.35,1.70,2.10]):
- 擠壓峰 |scaleX−1|:**[0.16, 0.216, 0.272, 0.336]** 嚴格遞增。
- shear 峰 |shearX|:**[16.0, 21.6, 27.2, 33.6]°** 嚴格遞增。
- 體積守恆:各檔位每極值 |scaleX·scaleY−1| ≤ **4.64e-5**(≪ 閘容差 TOL_VOL 0.02)。
- **crux 鑑別(ST6b)**:同一增益(Legend g=2.1)下,coupled 放大 volErr 峰 **5.6e-5** vs
  naive 逐軸放大 volErr 峰 **0.152** → **naive 破壞達耦合地板的 ~2710×**(證耦合放大必要、閘可信)。

## byte-identity:Super==base(g==1.0 零變換捷徑)

耦合重建(`scaleY'=1/scaleX'`)在 g=1.0 會有 4-dec 取整漂移(head 少數幀差 1 個 ulp)→ 若逐幀重算,
`squash__Super` 可能不逐位元等於 base。解法:`amplify_bone_tl` 開頭 **`if g==1.0: return deepcopy(b)`**
(零變換直接沿用)。對現有 scale/rotate/translate/shear 節拍此捷徑與逐幀 `round(1.0*v,·)` 結果相同
(值皆已預取整,零回歸);對 squash 更避開耦合重建漂移 → **Super==base 對所有 role/nosc 恆逐位元成立**。

## 做了什麼(全 additive)

1. **`tier_variants.py`**:`MAIN_SHOW_CATS` 加 `"squash"`;新增 `COUPLED_SCALE_CATS={"squash"}`
   + `coupled_for(cat)`;新增 `_amp_scale_coupled(x,g)`(體積守恆耦合放大);`amplify_bone_tl`/
   `amplify_anim` 加 `coupled=` 旗標 + `g==1.0` 零變換捷徑。
2. **`gen_animations.py`**:`build_animations` 依 `cat in COUPLED_SCALE_CATS` 決定 `_amplify_anim(..., coupled=)`。
3. **`validate_squash_tier.py`**(新,6 AC)。
4. **`validate_tier_combo_count.py` K5c 修正(閘可信)**:舊 K5c 以「非-combo beat 各檔位峰**數**是否相同」
   為 count-隔離 proxy,但 squash 檔位幅度放大會把 head 擠壓峰推過 `IMPACT_PROM` 門檻而改變**計數** →
   誤判為 count 外洩。改為直接的機制隔離:`tier_combo_hits` 之於非-combo 檔位變體須 **full(gains+hits)
   vs gains-only 逐位元相同**(對幅度變化穩健,直測「count 機制對非-combo 零影響」)。
5. **`check_readiness`** 新增 cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(仍 HOLD)。
6. 圖 `knowledge/figures/s1_squash_tier.png`(雙通道峰遞增 / 體積守恆保持 / coupled vs naive crux / 包絡)。

## 驗收(`validate_squash_tier.py`,先驗庫→**真實 build_spine robot 骨架**→build_animations(tier_gains))

**6 AC 全 PASS**:
- **ST1** present + backward-compat:squash base 有 shear+非均勻 scale;每檔位 `squash__{tier}` 產出、
  finite、有 bone、≥1 bone 同時帶 shear+scale、名路由回 squash;**base 逐位元不變**。
- **ST2 crux** dual-channel monotone:擠壓峰 |scaleX−1| 與 shear 峰 |shearX| 皆 Super<Mega<Omg<Legend
  嚴格遞增,Super 兩峰 == base(向後相容)。
- **ST3 crux** volume-conserving coupling preserved per tier:**每個**檔位每極值 (a)scaleX·scaleY≈1
  (≤TOL_VOL)(b)≥1 極值非均勻 |scaleX−scaleY|≥MIN_ANISO (c)擠壓幅度隨極值嚴格遞減(阻尼耦合)。
  復用 squash-gen 的 `_sq3_eval`(同判準 → 閘可信)。
- **ST4** identity interface per tier:每檔位首尾 shearX==0、scale 首尾 (1,1)(可插 Loop)。
- **ST5** shear isolated:僅 `SHEAR_CATS`(wobble/squash)及其 `__tier` 變體帶 shear(補償對象明確、零外洩)。
- **ST6** neg-control:(a) 平增益全 1.0 → 兩峰遞增 FALSE 且各檔位==base;(b) **耦合必要性守衛(crux)**
  naive 逐軸放大 volErr 0.152 > TOL_VOL 且 > coupled(5.6e-5)之 100×(實測 2710×);(c) 耦合隔離
  coupled=False 對等比 pulse 保持 scaleX==scaleY、coupled=True 對 squash 守恆非均勻。

端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}`,
`validate_build` round-trip overall_pass。回歸:squash_gen/wobble_count/wobble_tier/shear_gen/shear_pivot/
scale_pivot/pivot_rotation/tier_variants/tier_combo_count(K5c 修)/priors 系列/cascade/more_beats/
beat_templates/deform_gen **全綠**。

## 關鍵發現

- **耦合通道的檔位放大需「守恆重參數化」**:等比/單向 overshoot 用 `_amp_scale`(逐軸線性),但**耦合對**
  (體積守恆 squash)必須在**守恆參數 q** 上放大再重建兩軸,才能既放大幅度又保 scaleX·scaleY≡1。
  這是繼「幅度軸(J)/結構段數軸(J-2,G-4''')」之後,第三種檔位放大形態:**耦合軸**。
- **crux 不是「誤差 <5e-5」而是「coupled 地板 vs naive 破壞的數量級差」**(~2710×,同 SQ5 pivot 殘差
  vs 負對照 >1000× 的鑑別範式);4-dec keyframe 取整對耦合對有 ~1e-4 地板,故閘容差用 TOL_VOL 0.02
  抓「守恆 vs 破壞」而非鑽取整地板。
- **一個新主秀通道接上常牽動既有閘的 proxy 判準**(K5c):幅度放大把 head 擠壓峰推過 impact 門檻 → 需把
  proxy(峰數)換成直測(機制隔離比對)。同 (G-4'') 對 J 閘 J3 由「量 scale」改「量該 beat 實際通道」。

## honest boundary(仍在)

- 擠壓峰/shear 峰的檔位階梯沿用 (J) 增益(**PROPOSAL**,手感留使用者 A 類);shearY≡0。
- **squash 未接 count-aware**(擠壓段數隨檔位;`gen_squash` 已備 `nosc` 參數,比照 (J-2)/(G-4''')在
  `COUNT_AWARE_CATS`+`TIER_SQUASH_CYCLES` 路由即可,為後續)。
- 三通道同時(shear+非均勻 scale+rotate)塞滿一般仿射 M 全自由度 / shearY 為後續。
- 運動基元先驗、單一真值資產(robot) → cap `squash_tier_amplitude` L2 併入 `spine-anim-forge` **仍 HOLD**。

見圖 `knowledge/figures/s1_squash_tier.png`;前置 `s1-squash-shear-scale-coupling.md`(G-4'''')。
