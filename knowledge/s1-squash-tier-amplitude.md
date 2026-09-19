# S1 — squash 接檔位幅度差異化:耦合放大(candidate G-4''''',`squash_tier_amplitude` L2)

> 2026-09-19。續 (G-4''''):(G-4'''') 讓 `gen_squash` 成為第一個同時產 **shear + 耦合體積守恆非均勻
> scale** 的生成器,但誠實標記 honest boundary:「squash 未接 tier —— `_amp_scale` 逐軸只放大 identity
> 上方會破壞體積守恆」。本次正照那條邊界接上:**squash 的兩個幅度軸(shear 峰 + 擠壓量)隨檔位嚴格遞增,
> 且 scaleX·scaleY≡1 在每個檔位保持**。這是首次讓**耦合雙通道**同步隨檔位放大。

## 缺口(honest boundary 的接續)

- **(G-4'''')** 產出 squash 節拍(shearX 阻尼擺 + 體積守恆 squash:scaleX=1+q、scaleY=1/(1+q)、
  scaleX·scaleY≡1、非均勻),但 squash **不在** `MAIN_SHOW_CATS`。原因:(J) 的 scale 幅度增益
  `_amp_scale(v,g) = 1+g·(v−1) if v≥1 else v` —— 逐軸只放大 identity **上方** overshoot。
- 套到 squash:scaleX>1(拉長)被放大,而 scaleY<1(壓扁)是「下方樓地板」→ **保持不變**。
  兩軸不再互補 → **scaleX·scaleY ≠ 1(破壞體積守恆)**,果凍擠壓變成單軸拉伸(見負對照 P5b:
  逐軸放大 g=2.1 後 product 衝到 1.02–1.14)。
- 本次(G-4''''')補上:squash 的 scale 走**耦合放大**(coupled amplify),守住體積守恆。

## 關鍵:耦合雙通道的檔位放大須在「自然座標」放大(而非各軸獨立)

squash 的 scale 對由**單一自由度** q 參數化:`(scaleX, scaleY) = (1+q, 1/(1+q))`。體積守恆
`scaleX·scaleY≡1` 是這條參數化的**內建物理約束**。逐軸獨立放大會離開這條約束曲面;正確做法是在
**自然座標 q(squash 量)裡放大**,再回推兩軸:

```
_amp_squash_pair(sx, sy, g):
    q  = sx − 1                       # 自 scaleX 還原 squash 量(gen_squash 恆以 scaleX 為拉長軸,q≥0)
    q' = g · q                        # 線性放大(同專案 scale 慣例 v'=1+g·(v−1),伴軸改由守恆式重建)
    scaleX' = 1 + q'                  # 以 gen_squash 同式重建兩軸
    scaleY' = 1 / (1 + q')
```

性質(全部可量測):
- **體積守恆**:`scaleX'·scaleY' ≡ 1`(任意 g,誤差僅雙重 round 底噪 ~4e-5,同 base squash SQ3)。
- **非均勻**:q'>0 時 scaleX'≠scaleY'(真擠壓,非等比 pulse)。
- **identity 介面**:q=0 → (1,1)(首尾可插 Loop 間)。
- **g=1 精確 identity**:與 gen_squash 同雙重 round → base squash 逐位元不變(向後相容)。
- **阻尼耦合保形**:q 隨極值嚴格遞減 → q'=g·q 亦嚴格遞減(擠壓阻尼簽章保形)。

shear 通道則同 wobble 走 `v'=g·v`(對 0 對稱)→ 峰隨檔位遞增、阻尼振盪簽章保形。故 **shear 峰 + 擠壓量
兩軸同步隨檔位放大**(耦合雙通道)。

## 做了什麼(全 additive)

1. **`tier_variants.py`**:
   - `MAIN_SHOW_CATS` 加 `"squash"`(使其產檔位變體)。
   - 新增 `VOLUME_CONSERVING_CATS = {"squash"}`(scale 對為體積守恆、須耦合放大的類別集)。
   - 新增 `_amp_squash_pair(sx, sy, g)`(耦合放大;見上)。
   - `amplify_bone_tl(b, g, coupled_scale=False)` / `amplify_anim(anim, g, coupled_scale=False)`:
     `coupled_scale=True` → scale 走 `_amp_squash_pair`;否則逐軸 `_amp_scale`(hit/combo… 不變)。
2. **`gen_animations.py`**:`build_animations` 對 `cat ∈ VOLUME_CONSERVING_CATS` 的檔位變體
   傳 `coupled_scale=True` 給 `_amplify_anim`。
3. **`validate_squash_tier.py`**(新,5 AC)。
4. **`validate_tier_combo_count.py`**:K5(c) 對 `VOLUME_CONSERVING_CATS` 豁免 combo 專用 impact-峰計數器
   —— squash 的 scale 是體積守恆阻尼伴軸(非脈衝列),耦合放大會讓其阻尼峰跨越 prominence 門檻造成
   **假外洩**;squash 的振盪段數本身各檔位恆定(非 count-aware),另由其自身閘驗。
5. **`check_readiness.py`**:新增 cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(仍 HOLD)。
6. 圖 `knowledge/figures/s1_squash_tier.png`。

## 自我驗收(`validate_squash_tier.py`,5 AC 全 PASS)

從**先驗庫**(slot_bigwin 已含 squash beat)→ **真實 build_spine robot 骨架** →
`build_animations(tier_gains)` 端到端量:

- **P1 present + backward-compat**:每檔位 `squash__{tier}` finite/有 bone/**同時**帶 shear 與非均勻
  scale(雙通道)、名經 `beat_category` 仍路由回 squash;**base 逐位元不變**(含 In/Loop/Out)。
- **P2 crux — 雙軸單調**:(a) 峰 |shearX| **[16, 21.6, 27.2, 33.6]°**、(b) 峰擠壓量 |scaleX−1|
  **[0.16, 0.216, 0.272, 0.336]**,皆 Super<Mega<Omg<Legend **嚴格遞增**且首檔(Super,g=1)== base。
- **P3 crux — 體積守恆 + 簽章保形(每檔位)**:每 squash bone 每擠壓幀 (a) |scaleX·scaleY−1|≤0.02
  (**此即 `_amp_scale` 會破壞、耦合放大保住的關鍵**);(b) 非均勻峰 ≥0.05;(c) 擠壓量隨極值嚴格遞減;
  (d) shear 首尾 0 + 繞 0 變號 ≥3 + 相繼極值遞減;(e) scale 首尾 identity。
- **P4 耦合隔離**:全 storyboard(含所有變體)中,**只有 squash 及其 `__tier`** 同時帶 shear + 非均勻
  scale(wobble 帶 shear 無非均勻 scale、其餘等比 scale 無 shear)→ 耦合放大路徑零外洩。
- **P5 負對照**:(a) **平增益守衛**:增益全 1.0 → P2 雙軸遞增皆 FALSE 且各檔位逐位元 == base
  (證 g=1 耦合路徑為精確 identity);(b) **耦合 vs 逐軸單元測(crux)**:合成體積守恆對用
  `_amp_squash_pair` 放大 → product ≡ 1 且擠壓量遞減;同一對用逐軸 `_amp_scale` 放大 → product
  1.02–1.14 **明顯破壞守恆** → 證耦合放大確實在做事(補上的 honest boundary)。

**端到端**:`build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}`;
extreme 關鍵幀體積守恆精確保留(0 違反),densify 中間插值幀偏差(Legend ~1.3e-2)同 (G-4'''') 為
`apply_pivots` 既有非線性密網格重取樣的插值特性(逐軸插值一條守恆曲線不逐點守恆),非本次引入;
`validate_build` round-trip **overall_pass**(premult MAE 0.031)。

## 關鍵發現 / 踩雷

- **耦合雙通道的檔位放大須在自然座標放大**:squash 的 scale 對只有一個自由度 q,體積守恆是內建約束;
  逐軸獨立放大離開約束曲面 → 破壞守恆。正確做法 = 還原 q → 放大 q → 回推兩軸(留在約束曲面上)。
  這與 (J-2)/(G-4''') 的洞見互補:**結構軸(段數/峰數)須 gen 時決定;守恆約束軸須放大時耦合**——
  兩者都是「事後逐軸/同比 amplify 做不到、必須換更本質的操作」。
- **g=1 精確 identity 靠同式重建**:耦合放大以 gen_squash 同一雙重 round(`round(round(·,6),4)`)重建
  兩軸,故 g=1 時逐位元 == base(否則 1/scaleX 的單次 round 可能與 base 差 1 個 4dp 單位)。
- **combo 專用計數器套錯對象 = 假外洩**:把 squash 加進 `MAIN_SHOW_CATS` 後,combo 閘 K5(c) 用
  `impact_peaks`(prominence 門檻)量 squash 的 scaleX 阻尼峰,耦合放大讓其跨越門檻 → 峰計數變動 →
  被誤判為 count 外洩。修法:該 combo 專用計數器對 `VOLUME_CONSERVING_CATS` 豁免(squash 的 count
  由其自身閘驗)。教訓:**新節拍加進共用集合時,借用的量測器可能對它語意不符,需 scope 清楚**。

## honest boundary(仍在)

- 增益階梯數值沿用 (J)([1.0, 1.35, 1.70, 2.10])為 **PROPOSAL**(結構/守恆簽章客觀、手感留使用者 A 類)。
- 目前只產 **shearX**(shearY≡0)。
- **squash count-aware**(擠壓段數隨檔位,`gen_squash(nosc=)` 參數已備,比照 (G-4''') 對 wobble)為後續。
- 單一真值資產(robot_parts)、運動基元先驗 → `spine-anim-forge` 區塊**仍 HOLD**(防固化)。

## 下一步(擇一,皆純自主)

- **squash count-aware**:擠壓段數隨檔位(nosc 已備,結構軸,同 (G-4''') 對 wobble;與本次幅度軸正交可疊)。
- 產 **shearY**(雙軸 shear)/ shear+scale+rotate 三通道同時的運動基元(塞滿一般仿射 M 全自由度)。
- **(J-3)** cascade 波速/散佈/件數隨檔位(cascade 的 count-aware:跨件波的第三種檔位軸)。
- **(G-1)** `--rig`×pivot 各 flag per-bone 語意去重;**(G-2)** 主秀 beat 下 limb 繞關節 AC。
- S5→L3 仍待 **(D) 多 rig 真值**(C/資源類,使用者提供)。
