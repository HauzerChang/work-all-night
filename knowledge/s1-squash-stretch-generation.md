# S1 candidate G-4'''' — squash & stretch:體積守恆的耦合非均勻 scale

> 里程碑 2026-09-11(session 002)。續 (G-4''')。cap `squash_stretch_generation` L2 併入 `spine-anim-forge`(仍 HOLD)。
> 工具:`tools/analyzer/beat_templates.py`(`gen_squash`/`_squash_frames`/`_SQUASH_STRETCH`)、
> `gen_animations.py`(註冊 `_DISPATCH["squash"]`)、`genre_priors.py`(slot_bigwin 加 squash beat)、
> 閘 `validate_squash.py`(5 AC)。圖 `figures/s1_squash_stretch.png`。

## 缺口:運動基元庫沒有「squash & stretch」——12 動畫原理之首

至此(0d→G-4''')所有 beat 的 **scale 皆 x==y**(等比縮放):`gen_hit`/`gen_combo`/`gen_cascade`/
`gen_pulse`/`gen_loop` 的 `_scale_frames` 硬把 `x==y`。但**壓扁拉伸(squash & stretch)**——Disney 動畫
12 原理排第一——的定義正是 **sx≠sy 且體積(面積)守恆**:拉長一軸就等比例壓扁另一軸,質量感/彈性感
全靠它。整個運動基元庫此前**完全沒有**這個原理。這是又一個「模板/宣告就緒 ≠ 生成器接上」的鄰居問題:
不是接既有軸,而是**補一個全新的耦合通道 + 一條不變量**。

## 運動基元:體積守恆的阻尼 squash-stretch 彈跳

以「拉伸因子」λ(τ) 繞 1 **阻尼振盪**驅動,每幀:

```
sy = λ        (拉伸軸)
sx = 1 / λ    (壓扁軸)   ⇒   sx · sy ≡ 1   (面積/體積精確守恆,pre-round)
```

λ 包絡(τ,role peak 依 `_SQUASH_STRETCH`,body 1.30 / 特效 1.35 / head 1.18 / limb 1.22):

```
1.000 →(蓄力壓扁)0.880 →(命中拉伸)peak →(回彈壓扁)0.930 →(回彈拉伸)1.060 → 0.985 → 1.000
```

- λ=1 → identity(sx=sy=1);λ>1 → 縱拉橫壓;λ<1 → 縱壓橫拉。
- round 到 4 位小數後每幀 **|sx·sy−1| < 6e-5**(閘實測 body 5.5e-5),遠低於容差 1e-3。
- 純 **scale** 通道(無 shear/rotate/color)→ 耦合非均勻 scale **孤立可辨**(產線僅 squash 有 sx≠sy)。

### 結構簽章(可量化、非美感)

1. **體積守恆(crux 不變量)**:每個 scale 關鍵幀 sx·sy≈1 —— squash & stretch 的**定義**。
2. **耦合非均勻**:命中幀 sx<1<sy 且 |sx−sy|≥0.2(縱拉橫壓)——所有既有 beat 皆 sx==sy。
3. **squash-stretch 時序**:anticipation(命中前 λ<1 壓扁)+ 阻尼 settle((sy−1) 繞 0 變號≥3、命中為
   全域最大幅度、命中後相繼極值嚴格遞減);r 型阻尼回擺同 hit/combo。
4. 首尾 **identity**(sx=sy=1)→ 可插在 Loop 循環間(同其他主秀 beat)。

## 關鍵發現:非均勻 ≠ 體積守恆(閘的鑑別力核心)

天真的「只拉伸不壓扁」(sy=λ,**sx=1**)也**非均勻**(sx≠sy),但面積 = λ ≠ 1。若閘只測「有非均勻 scale」
就形同虛設。故 Q2 直接測**不變量** |sx·sy−1|,並用負對照證明:

| 對照 | 各向異性(sx≠sy) | 體積守恆(sx·sy=1) |
|---|---|---|
| squash(耦合,本 cap) | ✅ | ✅ |
| 真實 hit(x==y 等比) | ❌ | ❌(=λ²) |
| 天真只拉伸(sx=1) | ✅ | ❌(=λ)← **crux 鑑別** |
| 等比拉伸(sx=sy=λ) | ❌ | ❌(=λ²) |

「天真只拉伸」是關鍵鑑別列:各向異性 TRUE 但體積守恆 FALSE → 證閘測的是**耦合不變量**,不是
「有非均勻即可」。這與 (G-4') 的「阻尼簽章需振盪+遞減兩條件並立」同一種閘可信度論證。

## 誠實邊界

- **關鍵幀間線性內插不保體積守恆**:sx=1/λ 是凸函數,線性內插 sx、sy 後乘積在幀間**鼓起**
  (body 實測取樣最大偏差 ~4.6%)。閘 **gate 關鍵幀**(設計保證處)、**報告**取樣偏差(不 gate)——
  同 (G-4) 的「純關鍵幀量化非公式限制」。要幀間也嚴格守恆需更密取樣或 log-空間內插,屬後續。
- **squash ∉ `MAIN_SHOW_CATS` → tier 幅度變體暫未接**:逐軸 `_amp_scale` 有「identity 下方樓地板不動」
  規則,對 sx(<1)、sy(>1)不對稱處理會**破壞 sx·sy=1**。要接 tier 須改成**體積感知的 λ 增益**
  (放大 λ−1 後重算 sx=1/λ′、sy=λ′),留下一個 candidate —— 同 G-4' 先 introduce wobble、G-4'' 才接
  tier 的節奏。
- λ 包絡為 **PROPOSAL**(手感/彈性留使用者 A 類);shearY≡0(本 cap 不動 shear);單一真值資產。

## 驗收(`validate_squash.py`,從先驗庫→真實 build_spine robot 骨架→build_animations)

- **Q1 present + additive**:squash 產出/finite/每 bone 有 scale;**不產** squash__tier 變體;加入 squash
  先驗後其餘 beat 逐位元不變(含 tier 變體)。
- **Q2 crux 體積守恆**:每 scale 關鍵幀 |sx·sy−1|≤1e-3(實測 5.5e-5);報告取樣偏差 ~4.6%(誠實)。
- **Q3 簽章**:命中幀耦合非均勻(sx<1<sy,|sx−sy|≥0.2)+ anticipation 壓扁 + 阻尼 settle(變號≥3、命中
  全域最大、命中後極值遞減)+ 首尾 identity。
- **Q4 隔離**:耦合非均勻只在 squash(其餘 base beat 恆 sx==sy);squash bone 只帶 scale。
- **Q5 負對照**:見上表(真實 hit / 天真只拉伸 / 等比拉伸)。

端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 squash 段,`validate_build` round-trip
overall_pass。回歸:wobble_count/wobble_tier/shear_gen/tier_variants/tier_combo_count/全 priors/beat/pivot
系列 **16 閘全綠**。

## 待續(擇一,皆自主)

- **(G-4''''') squash 接 tier**:體積感知的 λ 增益(放大 λ−1 後重算 sx=1/λ′、sy=λ′)→ 檔位愈高彈性愈大,
  仍保 sx·sy=1(把 squash 併入 MAIN_SHOW_CATS 需先寫 squash 專屬 amplify)。
- **耦合 squash+shear**(斜拉 squash,對角壓扁):sx·sy=1 疊 shearX → 一般仿射且 det=cos(shear)·1。
- 幀間體積守恆(log-空間內插 / 更密取樣)。
