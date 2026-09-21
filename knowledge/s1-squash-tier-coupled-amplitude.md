# S1 — squash 接檔位差異化:體積守恆的耦合 amplify(candidate G-4''''')

> 里程碑 2026-09-21。補 **G-4''''**(`gen_squash` 產耦合 shear + 非均勻體積守恆 scale)留下的
> honest boundary:**squash 未接 tier 檔位差異化**。

## 缺口(honest boundary)

(J) 讓主秀 beat 依檔位**幅度**差異化(愈高檔位愈爆),(G-4'') 再把 wobble 的 shear 峰接上檔位。
但 **squash 一直被排除在 `MAIN_SHOW_CATS` 之外** —— 因為 (J) 的幅度增益 `_amp_scale(v,g)` 是
**各軸獨立**的「只放大 identity 上方 overshoot」規則:

```
_amp_scale(v, g) = 1 + g*(v−1)   if v ≥ 1   else   v   (下方樓地板不動)
```

squash 的 scale 是**體積守恆**對:`scaleX = 1+q`(拉長,>1)、`scaleY = 1/(1+q)`(壓扁,<1)。
對這對各軸獨立套 `_amp_scale`:拉長軸(>1)被放大成 `1+g·q`,壓縮軸(<1)是樓地板→**保持不變**。
結果 `scaleX·scaleY = (1+g·q)·(1/(1+q)) ≠ 1` → **破壞面積守恆**(squash & stretch 的物理核心)。

## 解法:耦合 amplify(`_amp_squash_pair`)

**關鍵洞見:體積守恆通道的檔位增益是一個「耦合」變換 —— 兩軸不獨立。**
放大**拉長軸**(沿用 `_amp_scale` 的 overshoot 規則),**壓縮軸取拉長軸的倒數**:

```python
def _amp_squash_pair(sx, sy, g):
    if g == 1.0:            # 向後相容:精確 identity(不引入倒數捨入誤差)
        return sx, sy
    if sx >= sy:            # squash 恆 scaleX≥1≥scaleY;取 max 對兩軸皆穩健
        sx2 = _amp_scale(sx, g)   # = 1 + g*(sx−1)
        return sx2, 1.0 / sx2
    sy2 = _amp_scale(sy, g)
    return 1.0 / sy2, sy2
```

保形性質(全部客觀可量測):
- **面積守恆**:`scaleX'·scaleY' = sx2 · (1/sx2) ≡ 1`(對任意 g)。
- **非均勻**:`scaleX' ≠ scaleY'`(q≠0 時)→ 仍是真擠壓,非等比 pulse。
- **identity 介面**:`(1,1) → (1,1)` → 首尾仍可插 Loop 間。
- **阻尼耦合**:各極值 `q_i = Q·rⁱ` 同比放大成 `g·q_i` → 相繼 |scaleX−1| 仍嚴格遞減(阻尼簽章保形)。
- **檔位單調**:峰擠壓幅度 max|scaleX−1| 隨 g 遞增。
- **shear 軸**:沿用 (G-4'') 的 `v'=g*v` → shear 峰亦隨檔位遞增。

⇒ 端到端:squash 的 **擠壓幅度 [0.16, 0.216, 0.272, 0.336] 與 shear 峰 [16, 21.6, 27.2, 33.6]° 皆
Super<Mega<Omg<Legend 嚴格遞增**,而每檔位 `scaleX·scaleY≡1`。

## 接線(全 additive)

- `tier_variants.py`:`squash` 併入 `MAIN_SHOW_CATS`;新增 `VOLUME_PRESERVING_CATS={"squash"}`;
  `_amp_squash_pair`;`amplify_bone_tl(b,g,coupled_scale=False)` / `amplify_anim(anim,g,coupled_scale=False)`。
- `gen_animations.py`:`build_animations` 依 `cat ∈ VOLUME_PRESERVING_CATS` 決定
  `amplify_anim(coupled_scale=…)`。squash 非 count-aware(nosc 已備參數未接,honest,後續)。
- `build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{tier}`;pivot 補償只加
  translate → scale 通道不動 → 體積仍守恆、幅度仍遞增。

## 自我驗收閘 `validate_squash_tier.py`(5 AC 全 PASS)

- **V1** present + backward-compat:每檔位產 `squash__{tier}`、finite、有 bone、同時帶 shear+scale、
  路由回 squash;**base(含 In/Loop/Out)逐位元不變**。
- **V2 crux** 體積守恆耦合**每檔位**保持:每極值幀 |scaleX·scaleY−1|≤2e-2 + 非均勻 + squash 幅度遞減
  (復用 G-4'''' 的 `_sq3_eval`,跨閘判準一致)。
- **V3 crux** 兩軸峰皆遞增:擠壓幅度與 shear 峰皆嚴格遞增、Super==base、每檔位阻尼簽章保形。
- **V4** identity 介面每檔位:shear 首尾 0 + scale 首尾 (1,1)。
- **V5** 負對照:
  - **(a) 耦合 vs 樸素(crux 鑑別)**:對真實 squash bone 套**樸素**各軸獨立增益(g=Legend)→ 體積守恆
    **FALSE**(|scaleX·scaleY−1|=0.15);**耦合** → TRUE(4e-5)→ 證耦合 amplify 必要且閘可辨。
  - (b) 平增益全 1.0 → 兩軸峰遞增 FALSE 且各檔位 == base(證閘測遞增非恆真)。
  - (c) 耦合單元測:`_amp_squash_pair` 對 (1,1)→(1,1)、對 (1.2,1/1.2) g=2 → 拉長軸 1.4、積≈1、非均勻。

## 連帶修正:`validate_tier_combo_count.py` K5(c)

squash 併入 `MAIN_SHOW_CATS` 後,`tier_combo_count` 的 K5(c)「count 只作用於 combo」原以
「非-combo 主秀 beat 各檔位 `_min_peaks` 是否相同」判定,對 squash **假陽性**:squash 的體積守恆
scaleX 幅度被檔位增益放大後,在較高檔位越過 impact-peak prominence 門檻 → 峰數各檔位不同([0,1,1,1]),
**但那是幅度效應(amp_only 亦然)、非連擊數旋鈕外洩**。修法=count 隔離判準改**比對 full vs amp_only**
(加上 `tier_combo_hits` 後非-combo 節拍須逐位元不變)—— 與 (G-4'') 對 (J) J3 改 channel-aware 同類:
**新節拍加入時,舊閘的量測維度可能對它假陽/假陰,須把判準收斂到真正的機制軸**。

## 關鍵發現

**體積守恆通道的檔位增益是耦合變換,不能沿用各軸獨立增益** —— 又一「檔位機制就緒 ≠ 每個通道接上」
實例(同 (E)/(H)/(I)/(J)/(G-4')/(G-4''))。耦合的要點:「放大一軸、另一軸隨之取倒數」以維持不變量
(scaleX·scaleY≡1),對比樸素獨立增益破壞不變量。此模式可推廣到任何帶**代數不變量**的多通道運動基元。

## honest boundary(仍在)

- 擠壓幅度階梯沿用 (J) 增益(PROPOSAL,手感留使用者 A 類)。
- shearY≡0(單軸 shear)。
- squash **count-aware**(擠壓段數隨檔位,`gen_squash(nosc=)` 已備參數未接,比照 G-4''')為後續。
- 單一真值資產;`spine-anim-forge` 仍 **HOLD**(運動基元先驗、防固化)。

圖:`knowledge/figures/s1_squash_tier.png`(擠壓幅度 × shear 峰隨檔位遞增 + 體積守恆恆線)。
