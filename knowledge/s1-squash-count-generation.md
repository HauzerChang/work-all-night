# S1 — squash 擠壓段數隨檔位遞增（candidate G-4'''''-c，`squash_count_generation` L2）

> 2026-09-21 run 002。續 (G-4''''')：(G-4''''') 讓 squash 的 shearX 峰**幅度**與非均勻 scale 擠壓
> 強度隨檔位遞增（耦合 amplify，體積守恆），但各檔位仍是**同樣 4 段**阻尼擠壓（有「擠多重」沒
> 「擠幾下」）。本次補上 squash 的擠壓**段數** `nosc` 隨檔位嚴格遞增（Super 4 → Mega 5 → Omg 6 →
> Legend 7）。這是繼 (J-2) combo 連擊數、(G-4''') wobble 振盪段數之後，第三個**結構（拓樸）軸**的
> 檔位差異化 —— 但**第一個發生在同時帶跨通道守恆約束的通道上**。

## 缺口（honest boundary 的接續）

- **(G-4''''')** 把 squash 併入 `MAIN_SHOW_CATS`、以 `_amp_scale_coupled` 讓 squash 的擠壓**幅度**
  隨檔位遞增而體積守恆，但誠實標記 honest boundary：「squash count-aware（段數）未接，
  `gen_squash(nosc=)` 已備參數但 `build_animations` 未路由」。
- 本次（G-4'''''-c）正好照那條邊界接上：**擠壓段數也隨檔位遞增**。

## 關鍵：幅度增益（即使是耦合）加不出「段數」

段數 = 關鍵幀**拓樸**。squash 的每個 shearX 阻尼極值處施一次體積守恆擠壓（`_squash_env` 讓
shear 極值與 scale 極值**同點耦合** → shear 繞 0 交替極值數 == scale 內部極值數 == `nosc`）。
事後 `amplify_bone_tl`（逐軸或耦合）只能對既有極值**同比放大**，無法多長一個極值 → 段數是
**結構**、必須在 `gen_squash` 生成當下決定。故不走 amplify，而是對 squash 檔位變體以該檔位
`nosc` **重生成**整支 beat，再疊 (G-4''''') 的**耦合**幅度增益 g。

## crux：段數 × 幅度 × 守恆 **三效正交**

squash 是**第一個同時 ∈ `COUNT_AWARE_CATS` 與 `COUPLED_SCALE_CATS` 的節拍**，故它比 wobble
count-aware（G-4'''）多一條約束軸。三條軸必須互不破壞：

- **段數軸**（結構，gen 時重生成）：`nosc` [4,5,6,7]（shear 段數 == scale 內部極值數）。
- **幅度軸**（事後耦合 amplify）：峰 |shearX| [16, 21.6, 27.2, 33.6]°、峰非均勻 |scaleX−scaleY|
  [0.30, 0.39, 0.49, 0.59]、峰拉長 scaleX−1 [0.16, 0.22, 0.27, 0.34]（g=[1.0,1.35,1.70,2.10]）。
- **守恆軸**（跨通道不變量）：**每一個（含新長出的）scale 極值**仍 `scaleX·scaleY≡1`。

實測：重生成把極值數變多、耦合 amplify 把每個極值放大之後，各檔位每個 scale 極值
`|scaleX·scaleY−1| ≤ 4.6e-5`（閘門檻 2e-4）—— 三效彼此正交，互不干擾。

> 為何天然成立：`gen_squash` 產出時每極值 `(1+q_i, 1/(1+q_i))` 積恆為 1（對任意 `nosc`）；
> 耦合 amplify `_amp_scale_coupled` 由 `sx'` 反推 `sy'=1/sx'` → 守恆**由建構保證**，與極值個數無關。
> 段數只是多產幾個「同樣守恆」的極值，故段數軸與守恆軸天然正交；幅度軸沿守恆流形走（G-4''''' 已證）。

## 做了什麼（全 additive）

1. **`tier_variants.py`**：
   - `squash` 加入 `COUNT_AWARE_CATS`（現 `{combo, wobble, squash}`）—— squash 同時仍在
     `COUPLED_SCALE_CATS`，故走「先重生成、後耦合 amplify」。
   - 新增 `TIER_SQUASH_CYCLES = {slot_bigwin: {Super:4, Mega:5, Omg:6, Legend:7}}` + `squash_cycles_for(genre)`。
     上界 7 同 wobble（共用同窗 DUR=0.8、`WOBBLE_LEAD/TAIL`、r=0.5）→ 末極值 `q=Q·r⁶` 於 6 位小數
     仍與前一極值可辨。
2. **`gen_animations.py`**：`build_animations(..., tier_squash_cycles=None)`；`_count_maps` 加
   `"squash": tier_squash_cycles`。既有的 count-aware 路由（`_build_beat(count=)` → `gen_squash(role,
   side_sign, radial, nosc)`）泛化即通用，無須改分派邏輯。
3. **`build_spine.py`**：`--tier-variants` 路徑取 `squash_cycles_for(genre)` 傳入 `tier_squash_cycles`。
4. **`validate_squash_count.py`**：新閘（5 AC，見下）。

## 自我驗收（`validate_squash_count.py`，先驗庫 → 真實 build_spine robot 骨架 → build_animations）

**5 AC 全 PASS**：

- **SC1 present + backward-compat**：每檔位 `squash__{tier}` 產出、finite、有 bone、≥1 bone 同時帶
  shear+scale；**base squash 恆 4 段**（shear 段數與 scale 極值數皆 4）逐位元同無檔位；`tsc=None`
  時 squash 變體逐位元 == (G-4''''') 耦合幅度-only（加性 opt-in 零回歸）。
- **SC2 crux — count↑ × 守恆**：各檔位 shear 段數**與** scale 內部極值數皆 == [4,5,6,7]、嚴格遞增、
  Super==base；**且每檔位每 scale 極值 |scaleX·scaleY−1|≤2e-4**（三效正交）。
- **SC3 signature preserved**：每檔位仍（a）shear 首尾 0；（b）繞 0 變號≥3；（c）shear 相繼極值遞減；
  （d）squash 幅度 (scaleX−1) 相繼遞減（阻尼擠壓）。且峰 |shearX| / 非均勻 / 拉長仍隨檔位嚴格遞增
  （段數軸不抵消幅度軸）。
- **SC4 orthogonality**：（a）段數 + 平增益（全 1.0）→ 段數遞增、峰幅（shear/非均勻）不遞增；
  （b）耦合增益 + 無段數（tsc=None）→ 段數恆 4、峰幅遞增。
- **SC5 neg-control**：（a）平段數（全 4）→ 段數單調性 FALSE；（b）無宣告的 genre（slot_reveal）→
  `squash_cycles_for` None → 不亂加段數變體；（c）段數只作用 squash，非-squash 主秀 beat 段數各檔位恆定。

端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super4, Mega5, Omg6,
Legend7}`（pivot 補償後 pivot-preserved bone 段數仍 [4,5,6,7]），`validate_build` round-trip
overall_pass（premult MAE 0.031）。

## 回歸

19 閘全綠：新 `squash_count` + 既有 18（squash_tier / squash_gen / wobble_count / wobble_tier /
tier_combo_count / tier_variants / shear_gen / shear_pivot / scale_pivot / pivot_rotation / cascade /
priors / priors_beats / priors_combo_charge / priors_cascade / more_beats / beat_templates / deform_gen）。

## 關鍵發現

- **count-aware 三度推廣、且首度與跨通道守恆疊加**：同一「段數是拓樸、須 gen 時決定；幅度是事後
  amplify；兩軸正交可疊」模式已在 combo（scale 峰數，J-2）、wobble（shear 振盪段數，G-4'''）、
  squash（擠壓段數，本次）三個不同通道成立。squash 額外證明：當通道帶跨通道守恆不變量
  （`scaleX·scaleY≡1`）時，段數軸仍與守恆軸天然正交 —— 因為重生成只是多產「同樣守恆」的極值。
- **各類別段數階梯彼此獨立**：`TIER_COMBO_HITS` / `TIER_WOBBLE_CYCLES` / `TIER_SQUASH_CYCLES`，
  `build_animations` 依 `cat` 經 `_count_maps` 路由。

## honest boundary（仍在）

- 段數階梯 [4,5,6,7] 為 PROPOSAL（手感留使用者 A 類）。
- `shearY≡0`（純 shearX 斜拉；雙軸 shear / 三通道同時的一般仿射運動基元為後續 G-4''''''）。
- anim-forge 仍 HOLD（運動基元先驗、單一真值資產，防固化）；S5→L3 仍待多 rig 真值（C/資源類）。

cap `squash_count_generation` L2 併入 `spine-anim-forge`。圖 `figures/s1_squash_count.png`。
