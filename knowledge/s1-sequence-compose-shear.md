# S1 序列組合 shear 通道覆蓋 — candidate (L-2)

> 2026-10-04 run 002。把 candidate (L) 的序列組合閘(接點無縫 / 回切逐幀還原 / in-context 簽章)
> 從 **5/7 通道**補到 **7/7**(含兩條 shear 軸),關掉 L 誠實列出的 shear 盲點。
> 這是**驗證器覆蓋修正、非新生成能力** —— 無改任何 beat 生成/產線值。

## 補的缺口(candidate L 自列的 honest boundary)

candidate (L) 的 `validate_sequence_compose` 用 `spine_anim.sample()` 做接點(前 beat 尾幀 vs 後
beat 首幀)與回切(composed vs 孤立 clip)比對。但 **`sample()` 原本只取 rotate/translate/scale/
alpha,不取 shear**。自 G-4'(wobble)起,wobble/squash/twist 三個斜拉節拍會產出 `shear` timeline
(shearX/shearY),而 L 的正向序列 `In→hit→combo→charge→cascade→Loop→Out` **刻意只用無 shear 的
節拍**繞過這個盲點,並在 STATE/knowledge/cap note 誠實記下:

> 「shear beat(wobble/squash/twist)之 shear 通道不被 `sample()` 覆蓋,正向序列採無 shear 的
> hit/combo/charge/cascade」。

本 run 把這條 boundary 補上。

## 選題理由(延續 L / G-2 的整合閘精神,刻意不加參數軸)

近期里程碑多為「單一 robot 加一軸」(tier / count / cascade-dir;J~J-7、charge count)。L / G-2
已刻意轉向整合/組合閘。**L-2 連一條生成軸都不加** —— 只關掉一個**已知的驗證盲點**,讓序列組合閘對
一般仿射四自由度(rotate / 非均勻 scale / **shearX / shearY**)**全覆蓋**,而非只覆蓋 5/7 通道。
價值在「compose 真能把一整櫃主秀 beat(**含斜拉節拍**)組成可播放大獎序列,且無縫性被完整驗過」。

## 做了什麼(全 additive)

1. **`spine_anim.sample()` 納入 shear**:per-bone 回傳新增 `shearX`/`shearY`(預設 0 = setup
   identity)。shear timeline 存法同 translate/scale(x/y 鍵,單位度),以同一 `_interp` 內插。
   - **加性 / 零回歸**:既有呼叫端索引既有鍵(`["rotate"]`/`["scaleX"]`…)者逐位元不變;以 setup
     預設補缺的通用 diff(如 L 的 `_state_diff` 迭代其**本地** `IDENT` 5 鍵)也不受影響;對無 shear
     的 beat(兩端 shear 皆 0)diff 不變。→ `validate_sequence_compose`(L)等既有閘逐一仍 PASS。
2. **新閘 `validate_sequence_compose_shear.py`(L-2,5 AC)**:含 shear 序列
   `In→wobble→squash→twist→Loop→Out`(三斜拉節拍全帶 shear,皆 identity 介面),從**先驗庫 →
   真實 build_spine robot 骨架 → build_animations** 端到端(與 L / J / charge 同一 fixture)。

## 5 AC(全 PASS)

- **LS1 present + shear 真被驅動**:composed 保有 `shear` timeline;`sample()` 現已輸出
  shearX/shearY 鍵;≥1 shear 段回切後 bone `|shearX|` 峰 ≥ 5°(實測 wobble/squash/twist 皆 ~15.27°)
  → 確認在測**真** shear 非空驗。
- **LS2 crux — 接點無縫(含 shear)**:含 shear 序列每內部接點 **shear-aware** 殘差 `0.0` < 1e-3
  (三斜拉節拍皆首尾 shear==0 → 接點含 shear 仍無縫)。
- **LS3 faithful concat(含 shear)**:回切每段**逐幀** shear-aware 還原孤立 clip(含 shearX/shearY)
  殘差 `0.0` < 1e-4 → 證 compose 的時間平移 + 接點去重對 **shear 通道**亦**無損**(compose 本就通道
  無關,此首次在 shear 上釘住)。
- **LS4 in-context shear 簽章**:從 composed 回切 wobble / twist 段,shearX **阻尼振盪**簽章仍成立
  (繞 0 變號 ≥3 + 相繼局部極值遞減)且 twist **兩軸反相**(極值處 shearX·shearY < 0)在序列脈絡中
  仍成立,且 in-context shearX 序列 == 孤立 clip(純平移無扭曲)。
- **LS5 crux — 盲點負對照(本 run 核心)**:構造「5 非 shear 通道全無縫、**只 shear 通道不連續**」
  的接點 —— wobble 尾 shearX=0(其餘 identity)→ 合成 `held` clip 首 shearX=12°(其餘 identity):
  - (a) **shear-aware** diff = `12.0` > 10×SEAM_TOL → 擴充後正確判**非無縫**,肇因接點指認 `wobble->__held`;
  - (b) **crux** 模擬擴充前盲點的 **non-shear** diff = `0.0` < SEAM_TOL → 擴充前**會誤判無縫**
    → 證 shear 覆蓋補掉一個**真實**接點盲點(非冗餘);
  - (c) 守衛:純 identity(零 shear)合成接點在 shear-aware diff 下仍 `0` → shear 覆蓋不會把真無縫
    接點誤判成不連續。

## 迭代踩雷(預算內自修)

- **稠密取樣序列不能直接套關鍵幀版阻尼判準**:初版 LS4 把 N=48 **稠密取樣**的 shearX 序列直接丟
  `_extrema_mags_decreasing`(validate_shear_gen 的 helper,原設計吃**關鍵幀**極值序列)→ `damped`
  恆 False(稠密序列每個峰附近有多個相近樣本,非嚴格遞減)。修法:新增 `_signed_extrema` 先從稠密
  序列抽**帶號局部極值**(左右鄰都 ≥/≤ 且至少一側嚴格、|v|>dead),再對極值序列套變號 / 遞減判準
  —— 等同 validate_shear_gen 對關鍵幀所做。

## 關鍵發現

1. **一個驗證器的「取樣器覆蓋通道數」決定它能看見哪些不連續**:`sample()` 漏 shear 使**所有以它為
   基石**的閘(接點無縫、回切還原、in-context 簽章)對 shear **一律盲**。補一條通道 = 補所有下游閘
   對該通道的鑑別力。盲點不在各閘的邏輯,而在共用的量測基石。
2. **要證「擴充補掉真盲點」,須在同一接點上同時跑擴充前 / 後兩種 diff**:LS5 在同一個 shear-only
   不連續接點上,擴充前(non-shear diff)回 0.0 誤判無縫、擴充後(shear-aware diff)回 12.0 正確判
   不連續 —— **兩者對照**才證「補的是真盲點」,只證「擴充後會響」不足(可能本來就非冗餘)。這是
   「負對照要證鑑別力」的一個變體:這裡鑑別的對象是**驗證器自己擴充前後的能力差**。
3. **稠密取樣 vs 關鍵幀:套結構簽章判準前先確認量測粒度相容**(抽局部極值,勿把稠密序列當極值序列)。

## honest boundary(仍在)

- 這是**驗證器覆蓋修正、非新生成能力**:無改任何 beat 的生成 / 產線值;`compose_sequence` 本就通道
  無關(iterate 所有 `chans` 含 shear),本 cap 只補 `sample()` + 新閘。
- beat **排序**仍 PROPOSAL(手感 A 類);shear 節拍的手感為美術(A 類)。
- 單一真值資產(robot)。cap `sequence_composition_shear` L2 併入 `spine-anim-forge`(仍 HOLD)。

## 檔案

- `tools/analyzer/spine_anim.py` — `sample()` 納入 shear(shearX/shearY)。
- `tools/analyzer/validate_sequence_compose_shear.py` — L-2 閘(5 AC)。
- `tools/check_readiness.py` — 新增 cap `sequence_composition_shear`。
