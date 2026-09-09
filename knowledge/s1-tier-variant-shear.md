# S1 斜拉 wobble 接 tier 幅度差異化:shear 峰隨檔位遞增(G-4'')

> 里程碑 2026-09-09(candidate G-4'')。補 G-4' 的 honest boundary:G-4' 讓 `gen_wobble` **產出
> shear 通道**並經先驗庫直出、`--shear-pivot` 端到端補償,但 **wobble 不在檔位變體集合**
> (`tier_variants` 只放大 scale/rotate/translate,且 wobble ∉ `MAIN_SHOW_CATS`)→ shear 擺幅不隨
> 檔位變化。本次比照 (J) 對 scale/rotate 所做,讓 wobble 的 **shear 擺幅峰值隨檔位嚴格遞增**,
> 而**阻尼振盪簽章與 identity 介面對每個檔位皆保形**。
> 工具:`tier_variants`(新 `SHEAR_SHOW_CATS`/`TIER_VARIANT_CATS` + `amplify_bone_tl` 的 shear 分支)、
> `build_spine --animate --tier-variants`、`validate_tier_shear.py`、圖 `figures/s1_tier_shear.png`。

## 動機(把 G-4' 的最後一塊接上)

(J)(`s1-tier-variant-amplitude.md`)讓主秀 beat 依檔位(Super/Mega/Omg/Legend)產**幅度差異化**變體
`{beat}__{tier}`,但增益只作用在 **scale/rotate/translate** 通道;(G-4')(`s1-shear-channel-generation.md`)
新增的 wobble beat 幅度**全在 shear 通道**,且 wobble 不在 `MAIN_SHOW_CATS` → 檔位變體完全略過它。
於是「檔位愈高愈爆」對斜拉果凍晃**無效**:Legend 的 wobble 與 Super 一樣晃。這是本專案反覆出現的
**「宣告/公式/模板就緒 ≠ 生成器接上」** 模式的又一實例(同 (E)/(H)/(I)/(J)/(J-2)/(G-4'))——
tier 機制與 shear 生成各自就緒,**兩者接起來**才把價值兌現。

## 機制(全 additive,對 (J)/(J-2) 零回歸)

關鍵設計取捨:**不把 `wobble` 併進既有 `MAIN_SHOW_CATS`**,而是**另立** shear 主秀集合。

- **為何不併進 `MAIN_SHOW_CATS`**:(J) 的閘 `validate_tier_variants.py` 用 `_scale_overshoot` /
  `_rotate_amp`(scale/rotate 通道)度量檔位單調性,且以 `TV.MAIN_SHOW_CATS` 圈定要檢的 base beat。
  wobble 是 **shear-only**(無 scale/rotate),若併進去,(J) 閘會把它當「零幅度」→ scale overshoot
  對所有檔位皆 0 → **`is_strictly_increasing([0,0,0,0])` FALSE** → (J) 的 J3 誤 FAIL。**通道不同,度量
  不能共用** —— 這是本 candidate 的核心踩雷點。
- **解法**:`tier_variants.py` 新增
  - `SHEAR_SHOW_CATS = {"wobble"}`(shear 通道幅度的主秀類別);
  - `TIER_VARIANT_CATS = MAIN_SHOW_CATS | SHEAR_SHOW_CATS`(**所有**產檔位變體的類別)。
  `MAIN_SHOW_CATS` **維持原 6 類不動** → (J)/(J-2) 閘的 base 集合與度量逐位元不受影響。
- `build_animations` 的產變體條件由 `cat in MAIN_SHOW_CATS` 改為 `cat in TIER_VARIANT_CATS`
  → wobble 現在也產 `{wobble}__{tier}`;其餘 6 類判定不變。
- `amplify_bone_tl` 新增 **shear 分支**:shear 是**角度量(度)、對 0 對稱**,同 rotate → `v' = g*v`
  (x/y 同乘 g)。既有 6 類無 shear 通道 → 此分支對它們是 no-op(逐位元不變)。

## 為何 `v'=g*v` 讓 shear 峰隨檔位遞增又保形(關鍵不變量)

wobble 的 shearX 包絡是**阻尼振盪** `0 → +A → −rA → +r²A → −r³A → 0`(r=0.5)。對整條乘以 g>0:

| 性質 | 為何保形 |
|---|---|
| **端點 identity** | 0·g = 0 → 首尾 shearX 仍 0 → 可插 Loop 間(介面契約檔位無關) |
| **符號序列不變** | g>0 不改號 → 繞 0 變號次數不變(仍 ≥3 振盪) |
| **阻尼(遞減)** | \|A\|>\|rA\|>… 同乘 g 後大小關係不變 → 相繼極值仍嚴格遞減 |
| **峰值單調** | 峰 = g·A,g 嚴格遞增(1.0/1.35/1.70/2.10)→ 峰嚴格遞增(**檔位簽章**) |
| **shearY≡0** | 0·g = 0 → 純斜拉維持 |

即:**增益放大擺幅峰值,但不改振盪/遞減結構** —— 檔位簽章 = 更大的斜拉幅度,而「阻尼果凍晃」的
運動語意對所有檔位一致(誠實:晃法不變、只是晃得更兇)。與 (J) 的「只放大 identity 上方 overshoot、
不動下方樓地板」是同一種**保形增益**哲學,只是這裡的不變量是「0 對稱」而非「identity 樓地板」。

端到端量測(真實 robot 骨架,`b_光暈` 峰 A=16°):

```
Super  g=1.00  peak 16.0°
Mega   g=1.35  peak 21.6°
Omg    g=1.70  peak 27.2°
Legend g=2.10  peak 33.6°     （嚴格遞增；cos(33.6°)=0.83>0 → 無翻面，--shear-pivot 補償仍可逆）
```

## 驗收閘 `validate_tier_shear.py`(5 AC,全 PASS)

從**先驗庫**(slot_bigwin,含 wobble beat)經 `analyze_target` → **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains=…)` 端到端量:

- **S1 present+routing+base**:每 wobble beat × 每檔位皆產 `{beat}__{tier}`、finite/有 bone/≥1 bone
  帶 shear、名仍路由回 wobble;**base(tiers=None)逐位元不變**。
- **S2 identity interface**:每檔位各 bone sample(0)/sample(dur) 皆 setup identity 且 shear 首尾 0。
- **S3 crux shear monotone**:每 wobble beat 的 max\|shearX\| **Super<Mega<Omg<Legend 嚴格遞增**(核心宣稱)。
- **S4 damped signature kept**:每檔位每 bone shearX (a)首尾 0、(b)繞 0 變號 ≥3、(c)相繼極值嚴格遞減。
- **S5 neg-control/isolation**:(a)**平增益守衛**——增益全 1.0 → S3 單調 FALSE(證閘真在測遞增);
  (b)base=Super 逐位元 == 無檔位 wobble;(c)**shear 隔離**——scale/rotate 主秀 beat 的檔位變體不含
  shear 通道(shear 放大不外洩);(d)`MAIN_SHOW_CATS` 未被污染(仍原 6 類,wobble 只在 `SHEAR_SHOW_CATS`)。

## 關鍵發現 / 踩雷

1. **通道不同,幅度度量不能共用**:shear-only 節拍併進 scale/rotate 的主秀集合會被舊閘當「零幅度」
   而誤判單調性 FAIL。正解是**按通道分集合**(`MAIN_SHOW_CATS` vs `SHEAR_SHOW_CATS`),各用各的度量。
2. **保形增益的不變量隨通道而異**:scale 增益守「identity 樓地板」、shear/rotate 增益守「0 對稱」。
   兩者都讓「端點=identity + 結構簽章」對所有檔位保持,只是保的東西不同。
3. **上界安全**:Legend 峰 33.6° 的 shear 仍 det=cos(33.6°)>0(無面積翻面),`--shear-pivot` 的仿射
   補償仍可逆;更高增益若逼近 90° 需另設上限(目前檔位階梯最大 2.1× 安全)。

## honest boundary(仍在)

- 斜拉 wobble 的**形狀**仍是 PROPOSAL(結構簽章客觀、手感留使用者 A 類);目前只產 shearX(shearY≡0)。
- 只驗**關鍵幀級** shear 峰的檔位單調 + 阻尼簽章;端到端 `--shear-pivot` × `--tier-variants` 的
  **每檔位** pivot 不動點未在本閘逐一量(G-4' 已證 base wobble 的端到端不動點;增益只放大擺幅、
  補償公式 `Δ=(M−I)(O−P)` 對放大後的 M 同樣成立,故理論上保持,但未逐檔位量化)。→ 續作候選 (G-4''')。
- wobble 尚無 count-aware 結構差異(如「擺動次數隨檔位增加」);目前只差幅度(同 (J) 對 (J-2) 的關係)。

## 回歸

`validate_tier_variants`(J)、`validate_tier_combo_count`(J-2)、`validate_shear_gen`(G-4')、
`validate_shear_pivot`(G-4)、`validate_scale_pivot`(G-3)、`validate_pivot_rotation`(0i)、
`validate_priors`/`priors_beats`/`priors_combo_charge`/`priors_cascade`/`cascade`/`more_beats`/
`beat_templates`/`deform_gen`、round-trip `validate_build`(對 `--tier-variants` build,overall_pass)
全 PASS。

## 續作候選(皆自主)

- **(G-4''')** 端到端 `--shear-pivot` × `--tier-variants` 的**每檔位** pivot 不動點 AC(把 G-4' 的 W4
  推廣到每個檔位變體)。
- **(G-4'''')** wobble 的 **count-aware**:擺動次數 / 阻尼段數隨檔位遞增(比照 (J-2) 對 combo)。
- 產 **shearY** / 斜拉 squash(shear + 耦合 scale)。
