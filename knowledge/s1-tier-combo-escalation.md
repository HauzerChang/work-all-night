# S1 combo 連擊數隨檔位遞增 — candidate (J-2)

> 里程碑 2026-09-07 session 002。續 (J)(檔位**幅度**差異化),讓 combo 主秀的檔位變體
> 連擊**數**也隨檔位遞增(Super 3 連 → Legend 6 連),幅度增益(J)仍疊加其上。
> 用整合閘證明「連擊數隨檔位遞增」是 cascade(跨件時序)之外的**第二個跨參數結構簽章**,
> 並以「平峰數守衛」證閘可信。

## 動機:J 只放大高度,沒放多連擊

(J) 把檔位轉成一個主秀**幅度增益** `g`,只縮放既有峰的**高度**;所有檔位的 combo 仍是
**同樣 3 連**。但大獎檔位在真實 slot 表演裡不只「打得更重」,常常是「連擊**更多**」
(Super 三連 → Legend 六連的華麗連段)。J-2 補上這個維度:combo 的檔位變體改用
**該檔位宣告的連擊數**重生成,再套 (J) 的幅度增益。峰**高**(J)與峰**數**(J-2)正交,可疊加。

## 兩處實作(皆純 CPU、確定性、對 base 保形)

### 1) `beat_templates.gen_combo(role, side_sign, radial, npeaks=3)`

新增 `npeaks` 參數 = impact 峰**數**:

- **`npeaks==3` 走原三連路徑,逐位元不變**(向後相容 —— base `combo` beat、`validate_more_beats`、
  `validate_priors_combo_charge`、(J) 的 `combo__*` 皆不受影響)。
- `npeaks>=4` 走**通用 N 連佈局**:連擊區佔 `τ∈[0,0.66]` 等分成 N 個 slot,每擊 = 蓄力 dip
  →(遞增)峰 → 部分回落;峰值 `p_i = 1 + q·(0.66 + 0.34·i/(N−1))`(`q = role_peak−1`),
  故 `p_0 ≈ 1+0.66q ≥ 1.119`(穩過 impact 門檻 1.10)、`p_{N−1} = role_peak`(finale)。
  尾段共用阻尼 settle(越過 identity 的回擺,峰 < IMPACT_PROM 1.10 → 不被誤計為 impact)。
  role rotate/color 通道亦依 N 產遞增擺盪/亮閃。首尾皆 setup identity(可插 Loop 間)。

### 2) `tier_variants.TIER_COMBO_PEAKS` + `combo_peaks_for(genre)`

`{"slot_bigwin": {Super:3, Mega:4, Omg:5, Legend:6}}`(嚴格遞增;base=Super=3 → gen_combo 走原路徑)。

### 3) `build_animations(..., tier_gains, tier_combo_peaks=None)` + `build_spine --tier-combo-escalate`

`build_animations` 抽出 `_build_beat_anim(...)`(可帶 `combo_npeaks` 覆寫)。combo 主秀的檔位變體:
若帶 `tier_combo_peaks` → **依該檔位連擊數重生成**(結構性)再套幅度增益 `g`;否則(=None,預設)
沿用 (J) 的**僅幅度**路徑(連擊數皆 3)。**opt-in**:`build_spine` 需同時給 `--tier-variants --tier-combo-escalate`。

**保形鏈**:`combo__Super`(npeaks=3, g=1.0)→ 重生成走 npeaks==3 原路徑 = base combo,
再套 g=1.0(identity 變換)→ **逐位元 == base combo**。不帶 `tier_combo_peaks` 時整支
`build_animations` 逐位元同 (J) → (J) 閘 `validate_tier_variants.py` 不受擾動。

## 為什麼峰**數**是「第二個跨參數簽章」

單看一支 `combo__Legend` 曲線,無法判斷它「比較高檔」——它就是一支合法 6 連 combo。
「隨檔位遞增」只在**跨檔位比峰數**時才顯現(3<4<5<6),正如 cascade 的跨件相位只在
**跨件比峰時刻**時才顯現。故 J-2 需獨立整合閘,且必須有「把峰數階梯壓平 → 單調性應消失」
的守衛,否則單調檢查可能恆真。

## 整合閘 `validate_tier_combo.py`(真實 robot 骨架端到端,5 AC 全 PASS)

從**先驗庫** → `analyze_target` → **真實 build_spine robot 骨架** → `build_animations(tier_gains, tier_combo_peaks)`:

- **K1 present+routing**:每檔位皆產 `combo__{tier}`、finite/有 bone、名仍路由回 combo;
  base combo 不變、`combo__Super` 逐位元 == base combo。
- **K2 interface契約**:每檔位 combo__{tier} 首尾 bone 皆 setup identity(可插 Loop 間)。
- **K3 crux 峰數單調**:每檔位每 bone 的 impact 峰**數** == 宣告連擊數,且各檔位
  **Super<Mega<Omg<Legend 嚴格遞增**(端到端實測 `[3,4,5,6]`)。
- **K4 簽章+幅度**:每檔位仍 `has_combo_signature`(遞增 impact 峰)且**非** charge(互斥);
  且 (J) 幅度單調仍成立 —— finale(全域峰)幅度隨檔位嚴格遞增(實測 `[1.347,1.463,1.582,1.718]`)。
  **峰數增加不破壞幅度增益**(兩簽章正交)。
- **K5 負對照**:(a) **平峰數守衛**——連擊數階梯全設 3 → K3 峰數單調性 FALSE(證閘真在測峰數遞增);
  (b) 不帶 `tier_combo_peaks` → 各檔位皆 3 峰(非單調)、仍具 combo 簽章(證峰數遞增源於 J-2);
  (c) **escalate 不外洩**——非 combo 主秀 beat(hit/burst/charge/cascade)各檔位峰數與 base 同、
  In/Loop/Out 不產變體(峰數遞增只作用於 combo);(d) 無宣告的 genre → `combo_peaks_for` 回 None。

## 關鍵發現

1. **結構性檔位差異必須「重生成」,不能「後製縮放」**:(J) 的 `amplify_anim` 只逐通道乘增益,
   無法**增加關鍵幀/峰數**;峰數是拓樸量,只能在生成當下決定。故 J-2 把 combo 檔位變體從
   「amplify(base)」改成「regenerate(npeaks) → amplify(g)」。這是「幅度 vs 結構」兩類檔位差異的分界。
2. **幅度增益對峰數保形**:`v'=1+g(v−1)`(v≥1)是單調遞增映射 → N 個遞增峰經增益後仍是 N 個遞增峰、
   dip/settle(<1)不動 → 峰**數**與峰**序**都保留。故 J(幅度)與 J-2(峰數)可安全疊加。
3. **通用 N 連的峰值下限要撐過 impact 門檻**:`p_0` 係數取 0.66(而非 (J) 三連的 0.60)確保
   最小 role(q=0.18)下 `p_0 ≈ 1.119`,dense 取樣低估後仍穩 ≥ 1.10 而被 `impact_peaks` 計入
   —— N 越大峰間隔越窄(Legend 6 連 limb 間隔 ~0.012),下限與可分離性是通用佈局的正確性要件。

## 檔案

- `tools/analyzer/beat_templates.py`(`gen_combo` +`npeaks`)、`tools/analyzer/tier_variants.py`
  (`TIER_COMBO_PEAKS`/`combo_peaks_for`)、`tools/analyzer/gen_animations.py`
  (`_build_beat_anim`/`build_animations(...,tier_combo_peaks=)`)、`tools/analyzer/build_spine.py`
  (`--tier-combo-escalate`)。
- 閘:`tools/analyzer/validate_tier_combo.py`。圖:`knowledge/figures/s1_tier_combo.png`。
- cap `tier_combo_escalation`(L2)併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
