# S1 — twist 扭轉段數隨檔位遞增(candidate G-4''''''-count,`twist_tier_count_aware` L2)

> 2026-09-24。續 (G-4''''''-tier):(G-4''''''-tier) 讓 twist 的**兩條** shear 軸峰**幅度**隨檔位遞增
> (兩軸同一 g 同比 → φ 比值不變),但各檔位仍是**同樣 4 段**反相雙軸阻尼擺(有「擰多狠」沒「擰幾下」)。
> 本次補上 twist 的扭轉**段數** `nosc` 隨檔位嚴格遞增(Super 4 → Mega 5 → Omg 6 → Legend 7)。
> 這是**結構(拓樸)軸**檔位差異化的**第四個通道**(前三:combo 連擊數 J-2、wobble 振盪段數 G-4'''、
> squash 擠壓段數 G-4'''''-c)——與幅度軸正交可疊。

## 缺口(honest boundary 的接續)

- **(G-4''''''-tier)** 把 twist 併入 `MAIN_SHOW_CATS`、讓 `amplify_bone_tl` 以**單一 g** 同時放大兩條
  shear 軸 → **幅度**隨檔位遞增且 φ=shearY/shearX 不變,但誠實標記 honest boundary:
  「twist 未接 count-aware(扭轉段數隨檔位,`gen_twist(nosc=)` 已備參數未接;比照 wobble G-4'''/squash G-4'''''-c)」。
- 本次(G-4''''''-count)正好照那條邊界接上:**扭轉段數也隨檔位遞增**。

## 關鍵:幅度增益加不出「段數」(同 J-2/G-4'''/G-4'''''-c)

段數 = 關鍵幀**拓樸**(繞 0 交替變號的 shearX 極值個數 = 反相 shearY 極值個數)。事後 `amplify_bone_tl`
只能對既有極值**同比放大**(`v'=g*v`),無法多長一個極值 → 段數是**結構**、必須在 `gen_twist` 生成當下
決定。故不走 amplify,而是對 twist 檔位變體以該檔位 `nosc` **重生成**整支 beat,再疊 (G-4''''''-tier) 的
單一-g 幅度增益 g:

- **段數軸**(結構,gen 時決定):`nosc` [4, 5, 6, 7]。
- **幅度軸**(事後 amplify,單一 g 對兩軸):峰 |shearX| [16, 21.6, 27.2, 33.6]°、
  峰 |shearY| [11.2, 15.12, 19.04, 23.52]°(g=[1.0, 1.35, 1.70, 2.10])。
- **兩軸正交可疊**:段數 + 平增益 → 段數遞增·兩軸峰不變·φ 仍不變;增益 + 無段數 → 段數恆 4·兩軸峰遞增。

此模式與 (G-4''')wobble / (G-4'''''-c)squash / (J-2)combo 同構,惟**段數階梯各類別獨立**
(twist → `TIER_TWIST_CYCLES`),`build_animations` 依 `cat` 路由 `_count_maps`。

## twist 獨有的 crux(與 wobble count 的差異):兩條 shear 軸 → 段數 × 幅度 × φ 保形三效正交

wobble count 只有**一條** shear 軸,段數重生成只需保「阻尼振盪簽章」;twist 有**兩條**(反相雙軸)。
段數重生成後兩軸各多長 `nosc` 個阻尼極值,而每個新極值(含段數增多長出的低幅極值 A·rⁱ)仍由
`_twist_env` 建構 `shearY = −TWIST_PHI · shearX`(φ=0.7)—— **φ 比值由建構保證、與段數無關**。故三效必須
**同時**成立,每個檔位不論扭幾段:

1. **段數** == 宣告 [4,5,6,7] 且嚴格遞增(Super==base);
2. **φ 比值**(兩軸峰之比)≈ TWIST_PHI(逐檔、逐段皆不變);
3. **每內部極值反相**(shearX·shearY < 0)。

這與 squash count 的「新擠壓極值也體積守恆」同構:**帶跨通道關係約束的類別 count-aware,要多驗一層
「約束在段數增多後仍成立」**(squash:體積守恆 scaleX·scaleY≡1;twist:φ 比值 + 反相)。因 φ 由 `_twist_env`
建構保證,實測 `max |φ_ratio − 0.7| = 0.0`(4 位捨入無誤差)。

## 做了什麼(全 additive)

1. **`tier_variants.py`**:`twist` 併入 `COUNT_AWARE_CATS`;新增 `TIER_TWIST_CYCLES`
   (`slot_bigwin`: Super4→Legend7,上界 7 同 wobble/squash——共用 `_twist_env`/`_wobble_env` 同窗 +
   阻尼 r=0.5,末極值 finite 可辨)+ `twist_cycles_for(genre)`。
2. **`gen_animations.py`**:`build_animations` 加 `tier_twist_cycles=None` 參數;`_count_maps` 加
   `"twist": tier_twist_cycles`。既有 `_build_beat(count=)` 路由已通用(count 傳給 `gen_twist` 的
   `nosc` 第 4 位置參數),無須改。
3. **`build_spine.py`**:`--tier-variants` 時 `twist_cycles_for(genre)` → `tier_twist_cycles=ttc`。
4. **`validate_twist_count.py`**(新閘,5 AC):見下。
5. **`gen_twist(nosc=)`** 本身不改(G-4'''''' 已備 `nosc` 參數;`_twist_env(A, nosc)` 早已通用)。

## 驗收(`validate_twist_count.py`,先驗庫 → 真實 build_spine robot 骨架 → build_animations)

**5 AC 全 PASS**:
- **TC1 present + backward-compat**:每檔位 `twist__{tier}` 產出、finite、有 bone、≥1 bone 帶**雙軸**
  shear;**base twist 恆 4 段逐位元同無 count**;`ttc=None` 時 twist 變體逐位元同 (G-4''''''-tier) 幅度-only
  (加性 opt-in 零回歸)。
- **TC2 crux — count↑ ∧ φ 不變**:(a) 段數 [4,5,6,7]==宣告嚴格遞增且 Super==base;(b) 每檔位每 bone
  φ 比值 ≈0.7,`max_phi_err = 0.0`。
- **TC3 signature preserved(兩軸)**:每檔位每 twist bone 的 shearX **與** shearY 各自首尾 0 + 繞 0 變號 ≥3
  + 相繼極值遞減(阻尼);且峰 |shearX|、|shearY| 仍隨檔位嚴格遞增、每內部極值仍反相 shearX·shearY<0
  (段數軸不抵消幅度軸、不破反相)。
- **TC4 orthogonality**:(a) 段數 + 平增益(全 1.0)→ 段數遞增·兩軸峰 [16,16,16,16]/[11.2×4] **不**遞增·
  φ 仍 ≈0.7;(b) 增益 + 無段數 → 段數恆 4·兩軸峰遞增。
- **TC5 neg-control**:(a) 平段數(全 4)→ 段數單調性 FALSE;(b) `slot_reveal` `twist_cycles_for` None +
  `gains_for` None → 不產 twist 段數變體;(c) 段數只作用 twist,非-twist 主秀 beat 的 shear 段數各檔位恆定
  (wobble/squash 仍 4 段,不外洩)。

端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 `twist__{Super,Mega,Omg,Legend}`
(pivot 補償後兩軸峰隨檔位遞增 shearX 16→33.6°、φ 逐檔=0.7000)。回歸:`check_readiness.py` 全綠
(22 閘;21 既有 + 新 twist_count),無 GREEN→RED。

## 關鍵發現

- **結構(段數)軸已在 combo / wobble / squash / twist **四通道**成立**;同一 count-aware 概念在
  scale 峰數(combo)、單軸 shear 段數(wobble)、shear+耦合 scale 段數(squash)、反相雙軸 shear 段數(twist)
  皆通用。
- **帶跨通道關係約束的類別,count-aware 要多驗一層「約束在段數增多後仍成立」**:squash 是體積守恆
  (scaleX·scaleY≡1),twist 是 φ 比值 + 反相。兩者都因約束**由 `_env` 建構保證**(每個新極值一出生就滿足),
  段數增多天然不破——這是「沿約束流形生成」的通則(對照 squash tier 的耦合 amplify「沿守恆流形放大」)。
- 阻尼比 r=0.5 對任意段數天然保簽章(等比阻尼 → 相繼極值恆遞減、交替變號 `nosc−1` 次),兩軸共用同一
  r 與同一極值 τ → 段數增多兩軸同步、反相與 φ 逐段守恆。

## honest boundary(仍在)

- **volume-conserving twist**:反相雙軸 `det = cos(shearY−shearX) ≠ 1` → 擰轉仍變面積,尚未接體積守恆
  耦合 scale(shear+scale+rotate 三通道同時=塞滿一般仿射四自由度且守恆,為後續)。
- 段數階梯 / 幅度 / φ 皆 **PROPOSAL**(手感 A 類,留使用者拍板)。
- **單一真值資產**(robot 骨架);運動基元先驗、防固化 → cap `twist_tier_count_aware` L2 併入
  `spine-anim-forge`(**仍 HOLD**)。
