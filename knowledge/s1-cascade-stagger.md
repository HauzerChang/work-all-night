# S1 candidate 0h — cascade(跨件錯開 reveal):第一個「跨件時序」主秀簽章

> 里程碑 2026-09-04(session 002)。續 0f(hit/reveal)、0g(combo/anticipate_hold)。
> 產出:`beat_templates.gen_cascade_part` + `gen_animations._cascade_beat`(特判)+ `validate_cascade.py`(6 AC)。
> 圖:`knowledge/figures/s1_cascade.png`。

## 為什麼要它(補的缺口)

0d–0g 的所有主秀 beat(pulse/hit/reveal/combo/anticipate_hold)簽章都定義在**單一件**的
時間包絡形狀上(峰數、峰前蓄力佔比、(scale−1) 變號數…)。但大獎主秀常見的一種節奏是
**「件與件之間錯開」**:轉輪/符號/拆件**依序** pop-in、掃出一道波,而不是所有件同時炸開。
這是**跨件(cross-part)時序**,單件包絡簽章完全抓不到 —— 一個「同時 reveal」和一個
「錯開 reveal」的**每一件**包絡可以一模一樣,差別只在**件間相位**。

cascade 補的就是這個維度,與 0g 的單件時序簽章**互補**。

## 設計(確定性、純 CPU)

- **單件包絡**`gen_cascade_part(role, side, radial, onset, width, T)`:reveal 家族介面 ——
  `[0,onset]` collapsed hold(scale≈0.02 / alpha 0)→ `[onset,onset+width]` burst overshoot→阻尼回擺→identity
  →`[onset+width,T]` hold identity。**首幀 collapsed、尾幀 identity**(可接 Loop 之前)。
  onset>0 的件在自己 onset 前保持隱藏。
- **件間相位編排**`_cascade_beat`(在 `build_animations` 特判,**不進 `_DISPATCH`**,因為它不是
  per-bone 包絡而是整個 beat 的跨件排程):把 beat 內可用件依**空間序**排序(bone `x` 主、`y`/名 tie-break),
  第 rank 件 `onset = rank/(n−1) · SPAN · T`(`SPAN=0.5`、`W=0.45T`、末件 onset+W=0.95T<T)。
  → 件峰時間沿空間序遞增,呈左→右掃動。

> **關鍵架構點**:cascade 是本專案第一個「beat 層級」而非「bone 層級」的生成器。既有 `_DISPATCH[cat](role,…)`
> 一次只看一件、無件間資訊;cascade 需要全 beat 的件集合與相對順序,故在 `build_animations` 明確特判分支。

## 跨件簽章(`validate_cascade.py` 量化)

一支 anim 是 cascade ⟺ 兩條件**兼備**:
1. **stagger spread** = (件 scale 峰時間跨度) / dur **≥ 0.25**。
2. **monotone sweep**:峰時間沿空間序(bone x)**嚴格遞增**。

## 驗收結果(6 AC 全 PASS,exit 0;對真實 robot 5 拆件 role 端到端)

| AC | 判準 | 結果 |
|---|---|---|
| C1 well-formed | cascade finite / 時間嚴格遞增 / JSON round-trip | ✅ |
| C2 reveal 介面 | 首幀所有件 collapsed(scale≈0.02/alpha 0)、尾幀所有件 identity | ✅ |
| C3 每件真峰 | 每件 burst 峰 scale ≥1.12(實測 1.177–1.344) | ✅ |
| C4 跨件簽章 | spread=**0.50**≥0.25 且峰時間沿 x 序嚴格遞增(0.286→0.461→0.636→0.811→0.986) | ✅ |
| C5 負對照(5 條) | 見下 | ✅ |
| C6 回歸 reveal | 接上 cascade 特判後,reveal beat 仍為合法 reveal(collapse→identity+真峰) | ✅ |

**C5 負對照(鑑別力)**:
- **正對照**:真 cascade 具簽章 ✅。
- **同時 reveal**(非錯開):spread=**0.0**、非遞增 → 非 cascade ✅(核心內建負對照:件包絡相同、只差相位)。
- **打亂 onset**(逆空間序):spread=**0.5** 仍大**但峰時間遞減** → monotone sweep FAIL → 非 cascade ✅
  —— **證「單調掃向」是必要條件,不是只看跨度大小**(spread 大 ≠ cascade)。
- **單發 hit**:identity 起(非 collapsed)+ 無件間錯開(spread=0.0)→ 非 cascade ✅。

## 關鍵發現

- **cascade 的鑑別子是「件間相位」而非「件包絡形狀」** —— 這是第一個必須看**多件關係**的簽章;
  同時 reveal 與錯開 reveal 的單件包絡可完全相同,只有跨件峰時間分佈能分辨。
- **「跨度大」不足以判 cascade,還要「單調掃向」** —— 打亂 onset 的負對照 spread 一樣大卻被正確判否,
  monotone sweep 才鎖定「有向的掃動」而非「雜亂錯開」。
- **空間序是 pivot** —— onset 依 bone x 指派 → 簽章可直接用 bone x 復現空間序驗證,無需額外標註。

## 誠實界定 / 下一步

- 主秀節奏無唯一正解(先驗手感),閘驗**客觀結構簽章非美感**;掃動方向/快慢手感留使用者(A 類)。
- 目前 cascade 由 fixture storyboard 驅動;若要 `build_spine --animate` 直出,需比照 (E)/(H) 併入
  `genre_priors`(建議 **(H')**:cascade 加進 slot_bigwin/slot_reveal,同步 `validate_priors` 真值覆蓋)。
- `spine-anim-forge` 新增 cap `cascade_stagger` L2 → 區塊**仍 HOLD**(運動基元先驗、單一真值資產,防固化)。

## 產出/更新檔案

- 新增:`tools/analyzer/validate_cascade.py`、`knowledge/s1-cascade-stagger.md`、`knowledge/figures/s1_cascade.png`。
- 更新:`tools/analyzer/beat_templates.py`(`gen_cascade_part` + `CASCADE_KEYWORDS` + `DUR["cascade"]`)、
  `tools/analyzer/gen_animations.py`(cascade 註冊 + `_cascade_beat` + `build_animations` 特判)、
  `tools/check_readiness.py`(cap)、`STATE.md`、`knowledge/README.md`。
