# S1 wobble shear 峰隨檔位遞增(tier variant on the shear axis,G-4'')

> 里程碑 2026-09-09(candidate G-4'')。續 (G-4') 與 (J):
> - **(J)**(`s1-tier-variant-amplitude.md`)讓主秀 beat 的 **scale/rotate** 幅度隨檔位(Super/Mega/Omg/Legend)
>   嚴格遞增(愈高愈爆),但只覆蓋 scale/rotate 兩軸。
> - **(G-4')**(`s1-shear-channel-generation.md`)讓 `gen_wobble`(斜拉果凍晃)**實際產出 shear 通道**
>   (阻尼 shearX 擺動、首尾 identity),是產線第一個產 shear 的生成器 —— 但**它的 honest boundary #3**
>   明言:「wobble ∉ `MAIN_SHOW_CATS` → tier 變體未接(可比照 (J) 讓 shear 峰隨檔位遞增)。」
> 本 candidate 就是接上那一段:wobble 併入主秀、`amplify_bone_tl` 補上 **shear 軸**,於是
> `build_spine --tier-variants` 讓 wobble 的 **shear 峰隨檔位嚴格遞增**,而阻尼簽章 / 介面契約 /
> 端到端 pivot 不動點對每個檔位保持。
> 工具:`tier_variants.py`(MAIN_SHOW_CATS + shear amplify)、`build_spine --tier-variants --shear-pivot`、
> `validate_wobble_tier.py`、圖 `figures/s1_wobble_tier.png`。

## 動機:把「shear」補成 tier 系統的第三條放大軸

(J) 建立了「檔位 → 主秀幅度增益 g」的機制,但只對 **scale(對 identity 上方 overshoot)** 與
**rotate/translate(對 0 對稱)** 兩類通道放大。(G-4') 帶進了一條全新的運動通道 —— **shear**,
卻沒有接進 tier 系統。結果:同一支斜拉 wobble 在 Super 與 Legend 檔位**shear 峰一模一樣**,
「愈高檔位愈爆」對這條通道失效。本 candidate 補上這條軸,讓 tier 系統覆蓋 wobble 的 shear。

這又是本專案反覆出現的 **「機制/宣告就緒 ≠ 生成器接上」** 模式(同 (E)/(H)/(I)/(J)/(J-2)/(G-4')):
(J) 的增益機制與 (G-4') 的 shear 生成各自就緒,**兩者交叉點(shear × tier)** 仍是空的,直到本次接上。

## 做法(全 additive,兩處生成器改動 + 兩個閘)

### 1. `tier_variants.py` — shear 併入放大機制(核心 2 行語意)

- **`MAIN_SHOW_CATS` 加入 `"wobble"`**:於是 `build_animations(tier_gains=…)` 對 wobble beat 也產出
  `wobble__{tier}` 檔位變體(In/Loop/Out 仍檔位無關,不產)。
- **`amplify_bone_tl` 補 shear 迴圈**:shear 角(度)對 0 對稱,**同 rotate → `v' = g*v`**:
  ```python
  for f in b.get("shear", []):
      f["x"] = round(g * f["x"], 3)
      f["y"] = round(g * f["y"], 3)
  ```
  **關鍵:阻尼振盪簽章對 g>0 保形**。整條 shearX 序列同乘 g:
  - 首尾 0 → g·0 = 0(**identity 介面對所有檔位保持**,可插 Loop 間);
  - 繞 0 變號序列不變(同乘正數不改符號)→ **振盪簽章保留**;
  - 相繼極值幅度 `[16,8,4,2]·g` 仍嚴格遞減 → **阻尼簽章保留**。
  ⇒ shear 峰隨 g 放大,而「阻尼振盪」這個結構語意逐檔不變。
- **產線僅 wobble 帶 shear 通道**(見 G-4' 的 shear 隔離)→ 此 shear 迴圈**只作用於 wobble 變體**,
  對其餘 scale/rotate 主秀 beat 的變體**零回歸**(逐位元不變)。

### 2. 端到端自動接上(build_spine 無需改動)

`build_spine --animate --tier-variants --shear-pivot` 兩步串起來即成立:
1. `build_animations(tier_gains=…)` 產 `wobble__Super/Mega/Omg/Legend`(shear 峰 16→21.6→27.2→33.6°);
2. `apply_pivots(include_shear=True)` 對**每個檔位變體**的 shear 端到端補償 → 件繞關節 pivot 做一般仿射
   而 pivot 精確不動(檔位愈高 shear 愈大、補償 translate 愈大,但殘差仍 <0.06px)。

### 3. 與 (J) 幅度軸**正交**

shear 是與 (J) 的 scale/rotate 幅度軸**互相獨立**的第三條放大軸:wobble 變體在所有檔位
scale overshoot ≡ 0、rotate amp ≡ 0(shear 是 wobble 唯一放大軸);反之 scale/rotate 主秀 beat
不帶 shear。兩軸可各自開關、互不干擾(同 (J-2) 對「幅度 × 連擊數」所立的正交性)。

## 自我驗收閘

### `validate_wobble_tier.py`(本 candidate 主閘,5 AC 全 PASS)

從**先驗庫**(slot_bigwin 含 wobble)→ **真實 build_spine robot 骨架** → `build_animations` /
`build_spine --tier-variants --shear-pivot` 端到端量。斜拉手感為 PROPOSAL(shear 形狀主觀留使用者 A 類);
閘驗**客觀結構簽章非美感**,負對照證鑑別力。

| AC | 內容 | 結果 |
|---|---|---|
| **T1** present + routing + backward-compat | 每檔位 `wobble__{tier}` 產出/finite/有 bone/≥1 bone 帶 shear;變體名仍路由回 `wobble`;帶檔位時**所有 base beat 逐位元不變** | PASS |
| **T2 crux** monotone shear peak | wobble 各檔位 max\|shearX\| **[16.0, 21.6, 27.2, 33.6] 嚴格遞增**,且 == base 16° × 宣告增益(精確非近似) | PASS |
| **T3** signature + interface per tier | **每檔位**每條 shearX 阻尼振盪簽章(首尾 0、變號 ≥3、極值嚴格遞減);sample(0)/sample(dur) 各 bone identity + shear 端點 0(可插 Loop) | PASS |
| **T4** end-to-end pivot-fixed per tier | `build_spine --tier-variants --shear-pivot`:12 個關節-bone×檔位檢查全數 pivot 殘差 <0.06px(Legend 最大 0.058)vs 負對照 8–50px(>850×);端到端 shear 峰仍逐檔遞增(CLI 接線亦驗) | PASS |
| **T5** orthogonality + isolation + guards | (a) shear 軸隔離(非 wobble 皆 0 bone 帶 shear);(b) 與 (J) 正交(wobble 變體 scale/rotate 幅度 ≡0);(c) 平增益守衛(全 1.0 → 峰逐檔相等 → 單調 FALSE、Super==Legend);(d) 向後相容(base wobble shear 逐位元 == wobble__Super) | PASS |

### `validate_tier_variants.py`((J) 閘,已軸無關化,回歸 PASS)

因 wobble 併入 `MAIN_SHOW_CATS`,(J) 閘的 J3(crux 幅度單調)已**軸無關化**:scale/rotate/**shear**
任一實際使用(峰>TOL)的通道皆須嚴格遞增,且至少一條主動軸 —— 既有 beat 恆用 scale(仍強制,純強化),
wobble 只用 shear(該軸受檢)。J4 加 `wobble → 阻尼振盪簽章` 分支。J3 摘要新增 `wobble scale/rotate 0 / shear 遞增`。

## 關鍵發現 / 踩雷

1. **shear 是「同 rotate 的對 0 對稱軸」**:不像 scale 要小心「只放大 identity 上方、下方樓地板不動」
   (避免把 collapse 0.02 在 g>1 推成負值翻面),shear 對 0 對稱,直接 `g*v` 即可,無樓地板問題。
2. **阻尼簽章對正增益保形是 shear 能接 tier 的前提**:因為簽章(變號序列 + 極值遞減)是**比值/符號**性質,
   同乘正數不變 → 放大幅度不破壞語意。若 wobble 用的是「單調 0→A→hold」(G-4' 的 W5a 負對照),
   放大後仍無簽章,tier 變體就沒有可保持的結構 —— 阻尼振盪這個設計讓「可放大且簽章保形」成立。
3. **pivot 殘差隨檔位放大但遠在容差內**:Legend(shear 33.6°)殘差 0.058px vs Super(16°)0.017px,
   ~3.6× 隨 shear 峰線性增(數值離散化誤差正比於位移量),但都 <<0.5px;負對照(未補償)則到 ~50px。
   證「一般仿射補償公式對大 shear 仍精確」在真實檔位幅度下成立。
4. **端到端 CLI 接線需 `--shear-pivot`**:只 `--tier-variants` 會產出 wobble 檔位變體但 shear **未繞關節補償**
   (繞件中心 → pivot 大位移);wobble 節拍的價值要 `--tier-variants --shear-pivot` 併用才完整(T4 驗此)。

## honest boundary(仍在)

- 斜拉 wobble 的 **shear 形狀**(首推方向、阻尼比 r=0.5、峰值階梯)為 PROPOSAL,手感留使用者 A 類;
  閘只保證**結構客觀性質**(阻尼振盪 + 峰隨檔位遞增 + pivot 不動)。
- 目前只放大 **shearX**(shearY≡0,純斜拉);若之後 wobble 產 shearY,`amplify_bone_tl` 的 `f["y"]`
  已一併乘 g,無需再改。
- 增益階梯沿用 (J) 的 `{Super:1.0, Mega:1.35, Omg:1.70, Legend:2.10}`(shear 與 scale/rotate 共用同一階梯);
  Legend shear 峰 33.6°(det=cos33.6°≈0.83>0,無翻面)在幾何上安全。若要 shear 專屬階梯可另立
  `TIER_SHEAR_GAIN`(目前無此需求,共用階梯更一致)。

## 併入 skill 政策

新增 cap `wobble_tier_shear`(L2)併入 `spine-anim-forge`,但 anim-forge **仍 HOLD**
(運動基元先驗、單一真值資產,防固化)—— 同 (G-4')/(J)/(J-2) 的判斷,不打包。

## 檔案

- 生成器:`tools/analyzer/tier_variants.py`(MAIN_SHOW_CATS + shear amplify)。
- 閘:`tools/analyzer/validate_wobble_tier.py`(5 AC)、`validate_tier_variants.py`(J3 軸無關化 + J4 wobble 分支)。
- 圖:`tools/analyzer/fig_wobble_tier.py` → `knowledge/figures/s1_wobble_tier.png`。
