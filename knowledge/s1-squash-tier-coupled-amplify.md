# S1 (G-4''''') squash 接檔位差異化 — 體積守恆的耦合 amplify

> candidate **G-4'''''**(2026-09-18,`squash_tier_coupled_amplify` L2)。補 G-4'''' 一路留到現在的
> honest boundary:**squash 未接 tier 幅度**。讓 `gen_squash`(shear + 耦合非均勻 scale 的體積守恆擠壓)
> 這個主秀節拍隨檔位遞增,而**放大不破壞體積守恆**(scaleX·scaleY≡1)。
> 圖:`figures/s1_squash_tier.png`。

## 為什麼是這一步(補的 honest boundary)

- **(J)** `tier_variant_amplitude` 讓主秀 beat 依檔位幅度差異化,但增益規則 `_amp_scale` 只放大
  **identity 上方**的 overshoot(`v'=1+g(v−1)` 僅當 v≥1;下方樓地板不動)——這對 hit/combo/reveal
  的**等比** scale(scaleX==scaleY)正確,卻對 squash 的**體積守恆非均勻** scale 致命。
- **(G-4'''')** `gen_squash` 產出耦合的 shear + 非均勻 scale:每個擠壓幀 `scaleX=1+q`(拉長 >1)、
  `scaleY=1/(1+q)`(壓扁 <1),`scaleX·scaleY≡1`。若用 `_amp_scale` 放大:scaleX(>1)被放大、
  scaleY(<1)被**當樓地板保留** → `scaleX·scaleY≠1`,**體積守恆被破壞**(果凍變「膨脹」而非「擠壓」)。
  故當時 squash **刻意不在** `MAIN_SHOW_CATS`(見 STATE G-4'''' 的 honest boundary:「需**耦合 amplify**」)。
- 本次(G-4'''''):補上**耦合 amplify**,squash 得以併入 `MAIN_SHOW_CATS` → 檔位愈高、擠壓愈狠而**體積恆守**。
  又一「檔位機制就緒 ≠ 每個新通道接上」實例(同 E/H/I/J/G-4'/G-4''/G-4''')——這次卡點不是「通道沒被掃到」,
  而是**既有增益規則對這個通道語意錯誤**,需為體積守恆通道另立放大律。

## 核心:耦合體積守恆 amplify(`tier_variants._amp_scale_coupled`)

擠壓幀 `(scaleX, scaleY) = (1+q, 1/(1+q))`,要「更狠地擠壓」= 放大擠壓幅度 q → `q' = g·q`:

```
scaleX' = 1 + g·q          # 拉長更多
scaleY' = 1 / (1 + g·q)    # 由 scaleX' 重生,而非獨立放大既有 scaleY
⇒ scaleX'·scaleY' ≡ 1      # 體積**嚴格**守恆(放大後仍守恆)
  scaleX' ≠ scaleY'        # 非均勻保持(仍是真擠壓)
```

- **g=1(Super)**:`scaleX'=1+1·q=scaleX`、`scaleY'=1/scaleX=scaleY` → **逐位元 == base**(向後相容)。
- **關鍵是「重生 scaleY = 1/scaleX'」而非「獨立放大 scaleY」**:守恆是 scaleX 與 scaleY 的**耦合約束**,
  放大時必須維持該耦合,故 scaleY 由放大後的 scaleX 導出,兩者不可各自為政(這正是 `_amp_scale` 的錯)。

### 幀類型判定(結構簽章,per-frame)

`_amp_scale_coupled` 對每個 scale 幀依**結構**分流,不需 beat 級旗標:
- **體積守恆擠壓幀**(`|scaleX−scaleY|>ε` **且** `|scaleX·scaleY−1|≤_VOL_TOL`)→ 耦合放大。
- **等比/identity 幀**(`scaleX==scaleY`,含首尾 (1,1))→ 退回一般 `_amp_scale`(identity 恆保 identity、
  等比 overshoot 照放大)。→ squash 的首尾 identity 端點自動保持(介面契約),可插 Loop 間。
- **非守恆非均勻幀**(理論上 squash 不產)→ 安全退回逐分量 `_amp_scale`(不會靜默破壞)。

`amplify_bone_tl(b, g, coupled=False)` 新增 `coupled` 旗標;`build_animations` 依
`cat ∈ VOLUME_CONSERVING_CATS`(={"squash"})路由(同 count-aware 依 `COUNT_AWARE_CATS` 路由)。
shear 通道無論 coupled 與否皆 `v'=g·v`,與 scale 同 g 放大 → squash 兩通道放大後**仍同源耦合**
(shear 峰與擠壓幅度以同一 g 放大)。全 additive,g=1 逐位元同舊行為。

## 與其他檔位軸的關係(三軸差異化總覽)

| 軸 | 機制 | 生效類別 | 例 |
|---|---|---|---|
| **幅度(等比 scale/rotate/translate)** | `_amp_scale`/`v'=g·v`(J) | hit/reveal/combo/charge/cascade | overshoot 隨檔位遞增 |
| **幅度(shear)** | `v'=g·v`(G-4'') | wobble/squash | shearX 峰隨檔位遞增 |
| **幅度(體積守恆非均勻 scale)** | `_amp_scale_coupled`(**本次 G-4'''''**) | squash | 擠壓幅度隨檔位遞增而積≡1 |
| **段數/拓樸(count-aware)** | gen 時重生成(J-2/G-4''') | combo(峰數)/wobble(段數) | 連擊/晃動段數隨檔位遞增 |

squash 目前吃「shear 幅度 + 體積守恆 scale 幅度」兩幅度軸(以同 g 耦合);段數(nosc)隨檔位為後續
(count-aware,nosc 參數已就緒,比照 G-4''')。

## 驗收:`validate_squash_tier.py`(5 AC 全 PASS)

從**先驗庫**(slot_bigwin,squash beat)→ `analyze_target` → **真實 build_spine robot 骨架** →
`build_animations(tier_gains=…)` 端到端量。主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章**,
負對照證鑑別力。

- **V1 present + backward-compat**:每檔位 `squash__{tier}` 產出、finite、有 bone、≥1 bone 同時帶
  shear+scale、名經 `beat_category` 仍路由回 squash;base(+In/Loop/Out)帶/不帶 tier_gains 逐位元不變;
  **`squash__Super`(g=1)逐位元 == base squash**。
- **V2 crux — 雙軸單調**:各檔位 (a)峰 |shearX| **且** (b)峰非均勻 |scaleX−scaleY| **兩軸皆** Super<Mega<
  Omg<Legend 嚴格遞增,Super==base。實測 shear [16.0, 21.6, 27.2, 33.6]°、aniso [0.298, 0.394, 0.486, 0.588]。
- **V3 crux — 每檔位體積守恆保持**:每個檔位的每個擠壓極值幀仍 (a)`scaleX·scaleY≈1`(|積−1|≤0.02,
  **耦合 amplify 的核心** —— 放大不破壞守恆);(b)非均勻;(c)擠壓幅度隨極值嚴格遞減。
- **V4 每檔位阻尼 shear 簽章**:每檔位 shearX 仍首尾 0 + 繞 0 變號 ≥3 + 相繼極值遞減。
- **V5 負對照/正交**:(a)**平增益守衛**全 1.0 → V2 兩軸遞增 FALSE 且各檔位逐位元 == base;
  (b)**耦合必要性單元測(crux 守衛)**:對真實 squash scale 幀,`coupled=True` 放大後守恆
  (積 [1.0, 1.00004, 0.99999, 1.00001])且擠壓幅度 = g·q;`coupled=False`(天真 `_amp_scale`)放大後
  **破壞守恆**(積 [1.15, 1.08, 1.04, 1.02] 顯著偏 1)→ **證「耦合」是必要且此機制正是修正**;
  g=1 耦合逐位元 == 原、identity 幀恆保 identity。

**V5(b) 是本次最關鍵的守衛**:它把 honest boundary 的問題(天真放大破壞守恆)與修正(耦合放大守恆)
放進同一個可機讀對照,直接證明「為什麼要耦合」。

## 端到端 & 回歸

- `build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}`,
  每檔位 5 bone 皆帶 dual(shear+scale)通道、3 有關節 bone 帶 pivot 補償(translate);
  `validate_build` round-trip overall_pass(premult MAE 0.031)。
- 回歸:**18 閘全綠**(新增 validate_squash_tier + 既有 17)。**validate_tier_combo_count K5c 更新**——
  該閘的「count 只作用 combo」隔離檢查以 `impact_peaks` 量 scale overshoot 峰數,squash 的 scaleX 擠壓
  被誤計為 impact 峰且隨檔位放大跨過 IMPACT_PROM 門檻使計數變動(邊界 artifact,非 combo count;squash
  恆 4 擠壓極值)→ 以 `VOLUME_CONSERVING_CATS` 排除 squash(同 wobble_tier T4 以 SHEAR_CATS 排除
  shear 產出者的作法),squash 的檔位差異化由 validate_squash_tier 專驗。

## 關鍵發現

- **體積守恆通道需自己的放大律**:等比 scale 的「只放大 identity 上方」對耦合守恆通道語意錯誤;守恆是
  scaleX/scaleY 的耦合約束,放大時必須**放大自由度(q)、重生受約束量(scaleY=1/scaleX)**,而非把兩者
  當獨立分量各自放大。這是「檔位機制就緒 ≠ 每通道接上」的一個新變種:卡點在**規則語意**而非**通道覆蓋**。
- **同 g 放大保持跨通道耦合**:shear 峰與擠壓幅度以同一 g 放大 → 檔位改「更斜更狠地擠」的強度而不改
  「斜與擠同源同阻尼」的結構(誠實地:檔位=強度,非別種運動)。

## honest boundary(仍在,後續候選)

- **squash count-aware**:擠壓段數 nosc 隨檔位(結構軸),nosc 參數已就緒(比照 G-4''' 的 wobble)。
- **shearY≡0**:仍純 shearX 斜拉;雙軸 shear / shear+scale+rotate 三通道同時的運動基元為後續(G-4'''''')。
- 段數/幅度階梯皆 PROPOSAL(手感留使用者 A 類);單一真值資產(robot);cap `squash_tier_coupled_amplify`
  L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
