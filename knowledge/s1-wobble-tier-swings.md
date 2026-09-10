# S1 — wobble 搖擺「段數」隨檔位遞增(candidate G-4''',`wobble_tier_swings` L2)

> 2026-09-10 session 002。續 (G-4''):把 wobble 的**檔位差異化**從「更斜」(shear 峰幅度)推廣到
> 「晃更多下」(阻尼振盪**段數** nswing)。搖擺段數隨檔位(Super→Legend)嚴格遞增,同時阻尼振盪
> 簽章在每個檔位保形,且與 (G-4'') 的**幅度**軸**正交可疊**。
> 與 (J)→(J-2) 對 combo 完全同構:「更爆」(幅度)vs「連幾下」(峰數)。

## 缺口(honest boundary 的接續)

- **(G-4'')** 讓 wobble 的 shearX 峰**幅度**隨檔位遞增(Super 16°→Legend 33.6°),但每個檔位仍是
  **同樣 4 段**阻尼振盪(`gen_wobble` 固定 4 極值)——「更斜」有了、「晃幾下」沒有。
- 這正是 (J-2) 補 (J) 對 combo 的同一種缺口:(J) 讓 combo「更爆」但恆三連擊,(J-2) 讓連擊**數**
  隨檔位遞增。本次(G-4''')對 wobble 補同一維度:**搖擺段數**隨檔位遞增。

## 關鍵:段「數」是結構、加不出來(同 J-2)

搖擺段數是關鍵幀**拓樸**。事後 amplify(`amplify_bone_tl` 對 shear 同比 `v'=g*v`)只能**同比放大
既有段**、無法多長一段。故不走 amplify,而是對 wobble 檔位變體以該檔位 `nswing` **重生成**整個 beat,
**再**疊 (G-4'') 幅度增益 → 與幅度軸**正交可疊**:段數走 `tier_wobble_swings`、幅度走 `tier_gains`,
兩者在 `build_animations` 獨立開關。

## 做了什麼(全 additive)

1. **`beat_templates.gen_wobble(role, side_sign, radial, nswing=4)`** 加 `nswing` 參數 +
   通用 `_wobble_env(A, r, nswing)`:極值 τ 於內窗 `[0.16, 0.80]` **均分**、正負**交替**(首推 +)、
   `|極值| = A·r^i` **嚴格遞減**(r=0.5 阻尼),首尾 shearX=0。
   - **`nswing=4` 特例逐位元同 (G-4') 手調 golden**(向後相容;base wobble 恆走此路)。
   - 任意 nswing≥1:首尾 0、繞 0 變號 = nswing−1、相繼極值遞減 → **阻尼振盪簽章對任意段數保持**。
2. **`tier_variants`**:`COUNT_AWARE_CATS` 加入 `"wobble"`;新增 `TIER_WOBBLE_SWINGS`
   (`slot_bigwin: {Super:4, Mega:5, Omg:6, Legend:7}`)+ `wobble_swings_for(genre)`。
3. **`gen_animations`**:`_build_beat` 的 `combo_hits` 泛化為 `count`(None → 走生成器預設,
   combo nhits=3 / wobble nswing=4);`build_animations` 加 `tier_wobble_swings=`,以
   `_count_map = {"combo": tier_combo_hits, "wobble": tier_wobble_swings}` 對 COUNT_AWARE 的**各**類別
   查其檔位「數」→ 重生成再套增益。兩 count 對映皆 None → 逐位元同舊行為(向後相容)。
4. **`build_spine`**:`--tier-variants` 時多帶 `tier_wobble_swings=wobble_swings_for(genre)`。
5. **`validate_wobble_swings.py`**(新,5 AC)。
6. **`check_readiness`** 新增 cap `wobble_tier_swings` L2 併入 `spine-anim-forge`(仍 HOLD)。
7. 圖 `knowledge/figures/s1_wobble_swings.png`(左:各檔位 shearX 阻尼包絡,段數遞增;右:nswing bar [4,5,6,7])。

## 驗收(`validate_wobble_swings.py` — OVERALL PASS)

從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(tier_gains, tier_wobble_swings)` 端到端量:

- **N1 present + backward-compat**:每檔位產 `wobble__{tier}` finite/有 bone/帶 shear;base wobble
  恆 nswing=4 且逐位元不變;**`tier_wobble_swings=None` 時 wobble 變體逐位元同 (G-4'') 幅度-only**
  → (G-4''') 為加性 opt-in、對 (G-4'') 零回歸。
- **N2 swing count monotone(crux)**:段數 **[4,5,6,7] == 宣告** 且 Super<Mega<Omg<Legend **嚴格遞增**;
  每檔位仍阻尼振盪(繞 0 變號≥3 + 相繼極值遞減)。
- **N3 signature + amplitude kept**:每檔位仍阻尼簽章保形,且 shear **峰幅度**仍
  [16, 21.6, 27.2, 33.6]° 單調(證與 (G-4'') 幅度軸疊加不衝突)。
- **N4 orthogonality**:(a) 段數 + **平增益**(1.0)→ 段數仍遞增且各檔位 shear 峰 == base 峰
  (幅度軸關掉、結構軸獨立);(b) 幅度 + **無段數**(None)→ 段數恆 4、峰遞增 → 兩軸獨立開關。
- **N5 neg-control**:(a) **平段數**(全 4)→ N2 段數單調 FALSE(證閘測遞增非恆真);
  (b) `slot_reveal` 無宣告 → `wobble_swings_for` None → 不產 wobble 變體;
  (c) **swing 只作用 wobble**:同時帶 wobble swings + combo hits,combo 檔位變體逐位元不受影響、
  連擊峰數仍由 `tier_combo_hits` 決定 → swing 不外洩到 combo。

**回歸全綠**:validate_wobble_tier(G-4'')、tier_combo_count(J-2)、tier_variants(J)、shear_gen(G-4')、
全 priors/beat/pivot 系列;round-trip `validate_build` 對 `--tier-variants --shear-pivot` build
(`overall_pass`、premult MAE 0.031、setup 不變),wobble__{Super,Mega,Omg,Legend} 直出。

## 關鍵發現

- **count-aware 是 tier 差異化的第二軸,對 shear 通道同樣適用**:combo 的「連擊數」與 wobble 的
  「搖擺段數」是同一類結構性差異化(關鍵幀拓樸,gen 時決定),`_build_beat` 的 count 參數對兩者
  一致 —— 泛化 `combo_hits→count` + `_count_map` 讓 build_animations 對**任意** COUNT_AWARE 類別
  查各自的檔位「數」對映,零 combo 回歸。
- **通用 `_wobble_env` 保阻尼簽章於任意段數**:內窗均分 τ + 交替符號 + `A·r^i` 幾何遞減 →
  對任意 nswing,首尾 0 / 變號 nswing−1 / 遞減三條件天然成立(結構不依段數),故段數變、簽章不變。
- **兩軸正交是「結構 gen 時定、幅度事後疊」的自然結果**:重生成決定段數(拓樸),amplify 同比放大
  決定幅度(度量);兩者作用在不同層 → N4 (a)(b) 證可獨立開關。

## Honest boundary(仍在)

- 搖擺段數階梯 `{4,5,6,7}` 為 **PROPOSAL**(結構簽章客觀、手感/節奏留使用者 A 類)。
- 段內 τ **均分**(非手感節奏曲線);`shearY ≡ 0`(純斜拉,同 G-4');單一真值資產(robot)。
- → cap `wobble_tier_swings` L2 併入 `spine-anim-forge`,區塊**仍 HOLD**(運動基元先驗、防固化)。

## 下一步候選(擇一,皆純自主)

- 產 **shearY** / 斜拉 squash(shear + coupled scale 雙通道耦合,補純 shearX 的維度)。
- **(J-3)** cascade 波速/散佈/件數隨檔位(cascade 的 count/spread-aware,cascade 是最後一個未接 tier 的主秀類別)。
- **(G-1)** `--rig`×pivot 各 flag per-bone 語意去重;**(G-2)** 主秀 beat 下 limb 繞關節 AC。
- S5→L3 仍待 **(D) 多 rig 真值**(C/資源類,使用者提供)。
