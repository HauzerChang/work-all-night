# S1 — squash 擠壓/斜拉強度隨檔位遞增(candidate G-4''''',`squash_tier_coupled_amplify` L2)

> 2026-09-12。續 (G-4''''):(G-4'''') 讓 `gen_squash` 成為第一個同時產 **shear + 體積守恆非均勻 scale**
> (scaleX·scaleY==1)的生成器,但它一直被擋在 `MAIN_SHOW_CATS` **之外** —— 因為 (J) 的 per-axis 幅度
> 增益 `_amp_scale` 只放大 identity 上方(scaleX>1 被放大)、下方樓地板不動(scaleY<1 不變)→ 會
> **破壞體積守恆**。本次補上 squash 專屬的**耦合 amplify**,使其**擠壓/斜拉強度隨檔位嚴格遞增而體積
> 守恆逐檔位保持**,可安全併入 `MAIN_SHOW_CATS`。

## 缺口(honest boundary 的接續)

(G-4'''') 明確標記:「squash 未接 tier 幅度(`_amp_scale` 只放大 identity 上方 → 破壞體積守恆,需
**耦合 amplify**,後續)」。本次(G-4''''')正照那條邊界接上。

## 關鍵:per-axis 放大會破壞守恆 → 需耦合 amplify

squash 的 scale 通道每個極值是 `(scaleX, scaleY)=(1+q, 1/(1+q))`(體積守恆非均勻)。若用 (J) 的
per-axis `_amp_scale`:
- `scaleX'=1+g·q`(>1,被放大)、`scaleY'=1/(1+q)`(<1,樓地板不動)
- ⇒ `scaleX'·scaleY'=(1+g·q)/(1+q) ≠ 1` → **面積不守恆**(g=2, q=0.16 → 積 1.138)。

**耦合 amplify**(`tier_variants._amp_scale_coupled(x, y, g)`)改為:
- 放大**拉長軸**相對 identity 的偏移:`x'=1+g·(x−1)`;
- **另一軸取倒數**:`y'=1/x'` → `x'·y'≡1`(面積守恆,由建構強制,不受生成器 4 位小數捨入殘差影響)。
- identity(x==1)→ (1,1)(介面契約對所有檔位保持);g=1.0 → x'=x、y'=1/x(4 位小數下逐值同 base)。

只有 squash 屬此(`COUPLED_SCALE_CATS={"squash"}`)—— hit/combo/reveal 的 scaleY<1 是 anticipation/
collapse 語意**樓地板**(結構,非體積守恆),須保留給 per-axis `_amp_scale`,**不可耦合**。

## 這是「幅度軸」而非「結構軸」(對照 G-4'')

同 (G-4'') 對 wobble 做的是**幅度**差異化(shear 峰隨檔位),本次對 squash 也是**幅度**軸:拉長峰 q
與 shear 峰同比隨 g 放大。squash 的**結構軸**(擠壓段數 nosc 隨檔位,比照 G-4''')是後續 honest
boundary —— `gen_squash(nosc=)` 參數已備、未接。

## 做了什麼(全 additive)

1. **`tier_variants.py`**:
   - `MAIN_SHOW_CATS` 加 `"squash"`;新增 `COUPLED_SCALE_CATS={"squash"}`。
   - 新增 `_amp_scale_coupled(x, y, g)`;`amplify_bone_tl(b, g, coupled_scale=False)` /
     `amplify_anim(anim, g, coupled_scale=False)` 加 `coupled_scale` 參數(True → scale 走耦合放大)。
   - shear/rotate/translate 通道與 `coupled_scale` 無關(皆對 0 對稱 `v'=g*v`)。
2. **`gen_animations.build_animations`**:主秀變體迴圈依 `cat in COUPLED_SCALE_CATS` 自動決定
   `coupled_scale`,轉給 `_amplify_anim` → squash 走耦合、其餘走 per-axis。
3. **`validate_squash_tier.py`**(新,5 AC)。
4. **`validate_tier_combo_count.py` K5(c) 修正**:舊檢查用 `_min_peaks`(combo 專用 impact 峰計數)
   要求非-combo 主秀 beat 的峰數各檔位不變;squash 加入 `MAIN_SHOW_CATS` 後,其放大的 scaleX 隨檔位
   跨過 `IMPACT_PROM`(1.10)會讓峰數變動 —— 那是**幅度**效應(count 機制未動 squash 的 nosc)非
   count 外洩。改為**逐位元比對** full(gains+hits) vs amp_only(gains-only)對非-combo beat 相同 →
   精確隔離 count 機制、對所有主秀 beat 皆正確且更嚴。
5. **`check_readiness`** 新增 cap `squash_tier_coupled_amplify` L2 併入 `spine-anim-forge`(仍 HOLD)。
6. 圖 `knowledge/figures/s1_squash_tier.png`(左:各檔位耦合 squash scaleX/scaleY 隨檔位遞增而積恆 1;
   右:拉長峰/shear 峰雙軸遞增疊圖 + 耦合 vs per-axis 守恆對照)。

## 自我驗收(`validate_squash_tier.py`,5 AC 全 PASS)

從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(tier_gains)` 端到端量:

- **X1 present + backward-compat**:squash base dual-channel;每檔位 `squash__{tier}` finite/有 bone/
  ≥1 bone 同時帶 shear+scale/名經 `beat_category` 仍路由回 squash;**base 逐位元不變**。
- **X2 crux — 強度單調 + 體積守恆**:各檔位**拉長峰** max|scaleX−1| == **[0.16, 0.216, 0.272, 0.336]**、
  **shear 峰** |shearX| == **[16, 21.6, 27.2, 33.6]°** Super<Mega<Omg<Legend 嚴格遞增,Super==base;
  **且每檔位每個極值幀 scaleX·scaleY≈1(vol_dev <1e-4,體積守恆不被檔位破壞)** —— 這正是耦合 amplify
  補上、per-axis 做不到的關鍵。
- **X3 耦合+阻尼簽章逐檔位保形**:每檔位 squash bone 仍(a)shear 阻尼振盪(繞 0 變號 ≥3 + 相繼極值
  嚴格遞減);(b)體積守恆耦合(SQ3 判準:每極值積≈1、≥1 極值非均勻、squash 幅度隨極值嚴格遞減)。
- **X4 端到端一般仿射 pivot 不動**:`build_spine --tier-variants --shear-pivot` 產 `squash__{tier}` 帶補償;
  放大後(Legend)有關節 pivot 的 bone 殘差 <0.08px(右手 0.057 / 頭 0.023 / 左手 0.081)vs 負對照
  (未補償繞件中心)20–71px → 證放大後的耦合非均勻 scale+shear 仍精確錨在 pivot。
- **X5 負對照**:(a) 平增益全 1.0 → X2 遞增 FALSE 且各檔位峰 == base;(b) **耦合 vs per-axis 單元測**:
  對合成 squash scale 幀,`amplify_bone_tl(coupled_scale=True)` → 積 **1.00003**(守恆)且拉長峰放大,
  而 `coupled_scale=False`(per-axis `_amp_scale`)→ 積 **1.138**(**破壞守恆**)—— 證耦合 amplify 是本次
  補上的關鍵、亦證閘測的是「守恆下放大」。

## 關鍵發現 / 踩雷

- **「檔位機制就緒 ≠ 每個通道接上」再現,惟 squash 需專屬耦合**:同 J/G-4''/G-4''' —— 但 squash 的 scale
  是**耦合**(守恆)而非 per-axis,所以不能沿用 (J) 的 `_amp_scale`;直接套會破壞守恆,**必須新增耦合
  amplify** 才接得上。這是「每個新通道各有其保形變換」的又一實例(shear=v'=g·v 對 0 對稱;耦合 squash=
  拉長軸放大+另一軸取倒數)。
- **閘的度量隨產線演進會失準**:`validate_tier_combo_count` K5(c) 的 `_min_peaks` 峰數判準隱含假設「非-combo
  主秀 beat 不跨 impact 門檻」,squash 入 MAIN_SHOW_CATS 後此假設破 → **改逐位元隔離**是更本質、更嚴的
  隔離判準(直接測「count 機制不碰非-combo beat」,不受幅度效應干擾)。
- **耦合 amplify 讓體積守恆成為檔位不變量**:base 與所有檔位的 `scaleX·scaleY≡1` 皆由建構保證
  (y'=1/x'),故守恆不是靠捨入僥倖,而是結構上恆真(vol_dev 純為 4 位小數捨入 <1e-4)。

## honest boundary(仍在)

- squash **count-aware**(擠壓段數 nosc 隨檔位,比照 G-4''')未接(`gen_squash(nosc=)` 參數已備)。
- 只產 **shearX**(shearY≡0)。
- 拉長峰/shear 峰的檔位階梯沿用 (J) 幅度增益 g=[1.0,1.35,1.70,2.10](**PROPOSAL**,結構簽章客觀、
  多擠才對味的手感留使用者 A 類)。
- 單一真值資產(robot_parts)、運動基元先驗 → `spine-anim-forge` 區塊**仍 HOLD**(防固化)。

## 下一步(擇一,皆純自主)

- **squash count-aware**(擠壓段數隨檔位,nosc 已備參數,比照 G-4''')—— 補本次的 honest boundary。
- 產 **shearY**(雙軸 shear)/ shear+scale+rotate 三通道同時的運動基元(塞滿一般仿射 M 所有自由度)。
- **(J-3)** cascade 波速/散佈/件數隨檔位(cascade 的 count-aware:跨件波的第三種檔位軸)。
- **(G-1)** `--rig`×pivot 各 flag per-bone 語意去重;**(G-2)** 主秀 beat 下 limb 繞關節 AC。
- S5→L3 仍待 **(D) 多 rig 真值**(C/資源類,使用者提供)。
