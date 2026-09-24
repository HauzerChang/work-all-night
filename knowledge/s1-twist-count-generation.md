# S1 (G-4''''''-count) twist 扭轉段數隨檔位遞增(count-aware × 幅度 × φ 保形三效正交)

> 里程碑 2026-09-24 run 001。candidate G-4''''''-count。cap `twist_tier_count_aware` L2(pipeline),併入 `spine-anim-forge`(仍 HOLD)。

## 缺口 / 動機

candidate (G-4''''''-tier)(`s1-twist-tier-amplitude.md`)讓 twist 的**兩條** shear 軸峰**幅度**隨大獎檔位遞增
(愈高檔位擰愈狠),而 φ 比值(shearY/shearX≡−`TWIST_PHI`=0.7)由「單一 g 對兩軸同比」保持。但各檔位仍是
**同樣 4 段**反相雙軸阻尼擺動 —— 有「擰多用力」沒「擰幾下」。這正是 (G-4''''''-tier) 明列的 honest boundary
(「twist 未接 count-aware(扭轉段數隨檔位,`gen_twist(nosc=)` 已備參數未接;比照 wobble G-4'''、squash
G-4'''''-c)」)。本次補上 twist 的扭轉**段數** nosc **隨檔位嚴格遞增**(Super 4 → Mega 5 → Omg 6 → Legend 7)。

這是「結構(段數)軸」的第四個通道:combo(J-2,impact 峰數)、wobble(G-4''',shear 振盪段數)、
squash(G-4'''''-c,耦合擠壓段數)之後,twist 的反相雙軸扭轉段數。

## 關鍵原理

- **幅度增益加不出段數**:段數是關鍵幀**拓樸**(繞 0 交替的極值個數),必須在 `gen_twist` 生成當下決定;
  事後 `amplify_bone_tl` 只能同比放大既有極值、無法多長一段。故不走 amplify,而是對 twist 檔位變體以該檔位
  nosc **重生成**整個 beat,再疊 (G-4''''''-tier) 的幅度增益 g。段數(結構,gen 時定)與幅度(事後 amplify)
  **正交可疊**。此模式同 (G-4''')wobble、(G-4'''''-c)squash、(J-2)combo,惟段數階梯各類別獨立
  (twist→`TIER_TWIST_CYCLES`,`build_animations` 依 cat 路由 `_count_maps`)。

- **twist 獨有 crux(與 wobble count 的差異、同 squash count 的精神)**:twist 帶**跨軸關係約束**
  shearY/shearX ≡ −`TWIST_PHI`。`_twist_env(A, nosc)` 對每個極值 i **同時**產
  `shearX = (−1)ⁱ·A·rⁱ` 與 `shearY = −φ·shearX`(r=`WOBBLE_DAMP`=0.5),故段數重生成後兩軸極值**成對**增生、
  φ 比值**由建構保證**逐檔不變。段數×幅度×**φ 保形**三效必須**同時**成立:每個檔位、每個(新增的)反相雙軸
  極值都要 (a)反相(shearX·shearY<0)且 (b)φ 比值 ≈ φ。段數增多會多長出低幅極值(A·rⁱ 隨 i 遞減,Legend
  nosc=7 最末極值 A·r⁶=A/64),閘須證這些新極值仍反相且維持 φ(不只是原 4 段)。

- 對照 squash count(`s1-squash-count-generation.md`):squash 的跨通道約束是**體積守恆**(scaleX·scaleY≡1,
  段數重生成後每個新擠壓極值仍由 `_squash_env` 建構 `(1+q_i, 1/(1+q_i))`);twist 的跨軸約束是 **φ 比值**
  (段數重生成後每個新極值仍由 `_twist_env` 建構 `(shearX, −φ·shearX)`)。**通則:同源重生成(單一包絡對相關
  通道成對/耦合產極值)= 約束保形**;帶約束的類別 count-aware 都要多驗一層「約束在段數增多後仍成立」。

## 實作(全 additive、opt-in)

- `tools/analyzer/tier_variants.py`:
  - `twist` 加入 `COUNT_AWARE_CATS`(現 `{combo, wobble, squash, twist}`)。twist 純 shear(**不**在
    `COUPLED_SCALE_CATS`)→ 重生成後走**逐軸**(非耦合)amplify 的 shear 迴圈(`v'=g*v`,兩軸同一 g)。
  - 新增 `TIER_TWIST_CYCLES = {"slot_bigwin": {Super:4, Mega:5, Omg:6, Legend:7}}` + `twist_cycles_for(genre)`。
    上界 7:twist 與 wobble/squash 共用 `_twist_env`→`_wobble_env` 的同窗 [LEAD,TAIL] 與阻尼 r=0.5,nosc≤7 極值
    時間嚴格遞增、末極值 finite 且可辨(比照 `TIER_WOBBLE_CYCLES`/`TIER_SQUASH_CYCLES` 上界論證)。
- `tools/analyzer/gen_animations.py`:`build_animations(..., tier_twist_cycles=None)` 新增第 5 個 count 參數;
  `_count_maps` 加 `"twist": tier_twist_cycles`。既有 count-aware 路由(`_build_beat(count=cnt)` 重生成 →
  `_amplify_anim(variant, g)`)**無須改動**即支援 twist(twist∈`COUNT_AWARE_CATS`、不在 `COUPLED_SCALE_CATS`
  → `coupled=False`)。
- `tools/analyzer/build_spine.py`:`--tier-variants` 時 `twist_cycles_for(genre)` → `ttc` → 傳入 `build_animations`。
- `gen_twist(nosc=)` / `_twist_env(A, nosc)`(beat_templates.py)**早已就緒**(G-4'''''' 已備參數),本次才接上。

## 自我驗收 — `tools/analyzer/validate_twist_count.py`(5 AC 全 PASS)

真值界定同 (E/H/I/J/J-2/G-4'/G-4''''/G-4''''''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章**
非美感。從**先驗庫**(slot_bigwin)→ **真實 build_spine robot 骨架** → `build_animations(tier_gains, tier_twist_cycles)`
端到端量,與 (J)/(G-4''''''-tier) 同一 fixture。

- **TC1 present + backward-compat**:每檔位 `twist__{tier}` 產出/finite/有 bone/≥1 bone 同時帶 shearX+shearY;
  **base twist 恆 4 段逐位元不變**;`tier_twist_cycles=None` 時 twist 變體逐位元同 (G-4''''''-tier) 幅度-only(加性零回歸)。
- **TC2 crux — count↑ ∧ φ 保形**:(a) 段數 x[4,5,6,7]==y[4,5,6,7]==宣告 且嚴格遞增、Super==base(向後相容)、
  兩軸段數相等(成對增生);(b) 每檔位每 bone φ 比值(shearY 峰/shearX 峰)≈ 0.7(誤差 ≤2e-3)。
- **TC3 signature preserved**:每檔位每 twist bone shearX 與 shearY 各自 首尾 0 + 繞 0 變號≥3 + 相繼極值遞減
  (阻尼)+ 每內部極值幀 shearX·shearY<0(反相);且峰 |shearX| 與峰 |shearY| 仍隨檔位嚴格遞增(段數軸不破幅度階梯)。
- **TC4 orthogonality**:(a) 段數+平增益(全 g=1.0)→ 段數仍遞增·兩軸峰不遞增·**φ 仍保持**(段數單獨作用不破 φ);
  (b) 增益+無段數(ttc=None)→ 段數恆 4·兩軸峰遞增(兩軸可獨立開關)。
- **TC5 neg-control**:(a) 平段數(全 4)→ 段數單調性 FALSE(證閘測遞增非恆真);(b) slot_reveal → `twist_cycles_for`
  None + `gains_for` None → 不產 twist 段數變體;(c) 段數只作用 twist:非-twist 主秀 beat 的 shear 段數各檔位恆定
  (不外洩;wobble 仍 4 段)。

### 量化結果

- 段數 per tier:shearX [4,5,6,7]、shearY [4,5,6,7](成對),base 4;φ 逐檔恆 0.7。
- 峰(來自疊加的 (G-4''''''-tier) 幅度增益):shearX [16,21.6,27.2,33.6]°、shearY [11.2,15.12,19.04,23.52]°(仍遞增)。
- 端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 `twist__{Super4,Mega5,Omg6,Legend7}`,shearY 經關節
  pivot 補償仍存活、段數仍 [4,5,6,7];`validate_build` round-trip overall_pass(premult MAE 0.031)。
- **回歸 22 閘全綠**(21 既有 + 新 twist_count);`check_readiness.py` 退出 0(無 GREEN→RED)。

## honest boundary(仍在)

- 段數/幅度/φ 階梯皆 PROPOSAL(手感 A 類)。
- 反相雙軸未接體積守恆耦合 scale(`det=cos(shearY−shearX)≠1` → 擰轉變面積;volume-conserving twist 為後續,
  即 G-4''''''-vol)。
- 單一真值資產(robot_parts);`spine-anim-forge` 區塊仍 HOLD(運動基元為手感先驗,達 L3 前不打包)。

## 下一步候選(擇一,皆純自主)

- **(G-4''''''-vol)** volume-conserving twist:反相雙軸 shear 接體積守恆耦合 scale(`sx·sy=1/cos(shearY−shearX)`
  → 擰而不變面積;shear+scale+rotate 三通道同時且守恆,塞滿一般仿射四自由度)。
- **(J-3)** cascade 波速/散佈/件數隨檔位(cascade 的 count-aware,簽章在件之間)。
- **(G-4'''''-charge)** charge 蓄力段數等第四個節拍的 count-aware。
