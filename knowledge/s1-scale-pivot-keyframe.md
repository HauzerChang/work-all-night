# S1 candidate 0i 延伸(G-3)— 件繞關節 pivot 縮放(scale-about-pivot)

> 里程碑 2026-09-05(session 002)。補 STATE「下一個 bounded chunk」建議 **(G-3)**:把 0i 的
> 「繞關節 pivot **轉**」推廣到「繞關節 pivot **縮放**」。工具:`tools/analyzer/pivot_rotation.py`
> (延伸)、`validate_scale_pivot.py`、`build_spine --scale-pivot`。圖:`knowledge/figures/s1_scale_pivot.png`。

## 問題(0i 的另一半)

`gen_animations` 給件的不只 `rotate`,還有 `scale`:**In** 由 `s≈0.02→1`(件長大)、**Out** 收 `→0`、
**pulse/hit** 峰 `1.08`(彈一下)。非 `--rig` 組裝下,每件 bone 原點落在**件中心 O**,所以這些 `scale`
會讓件**繞件中心脹縮** —— 對肢體不物理:手臂該**從肩伸長**(In 時像一根從肩長出來的手臂),不是
從自己中心整個放大。0i 只補償了 `rotate`,`scale` 仍繞件中心。

## 數學(把「繞任意點旋轉」推廣到含 scale 的仿射)

設 bone 世界(parent 座標)變換 = 平移 `T` + `M·local`,其中 Spine TRS 序給出

```
M = R(θ) · diag(sx, sy)          # 先 scale 再 rotate
```

要讓 pivot 的附著局部點 `ℓ_P = P − O` 對**任意 (θ, s)** 都固定在世界點 P,解 `T`:

```
(O + T) + M·ℓ_P = P
⟹  T = P − O − M(P−O)
⟹  Δ = (M − I)(O − P)            # 補償 translate
```

- **退化**:純旋轉(S=I)⟹ `Δ=(R−I)(O−P)`,正是 0i;`θ=0,sx=sy=1` ⟹ `M=I` ⟹ `Δ=0`(identity 介面/無縫保持)。
- **純均勻 scale 約 pivot 是相似變換**:`world(x)−P = s·(x−P)` ⟹ `∀x |world(x)−P| = s·|x−P|`。
  這是 scale 版的「等距」——取代 0i 剛性 AC 的判準(見 AC5)。

實作(`pivot_rotation.py`):
- `transform_matrix(θ, sx, sy)` = M；`pivot_delta_full(θ, sx, sy, O, P)` = Δ 公式(`pivot_delta` 為 s=1 特例)。
- `pivot_channels_srt(rotate, scale, O, P, dt, existing_translate)` = 在 rotate/scale **時間跨度聯集**的
  密網格上,同時重取樣 rotate/scale、算 Δ、疊加既有 translate → 產同時間點、皆線性的三通道。
- `apply_pivots(anim, bone_origin, pivot_of, dt, include_scale=False)`:
  - `include_scale=False`(預設)= **0i 行為逐位元不變**(只補償有 rotate 的 bone)。
  - `include_scale=True` = 凡有 pivot 且有 rotate **或** scale 的 bone 皆按 M=R·S 補償。
- `build_spine --animate --scale-pivot`(非 rig)復用 `rig_layout` 的樹 + 接觸縫推斷取 pivot,
  對每支 animation 呼叫 `apply_pivots(..., include_scale=True)`(`--scale-pivot` 含 `--pivot-rotate` 語意)。

**踩雷(同 0i)**:`Δ` 對 θ、s 皆**非線性** → 只放在原 keyframe 會幀間漏;故 rotate **和** scale 都在
密網格重取樣(`dt=1/60`),三通道同時間點皆線性 → 幀間內插一致。

## 驗收(`validate_scale_pivot.py`,7 AC 全 PASS)

真值 = 真實 Award **左手**世界輪廓(42 頂點)+ `infer_pivots` 推得**肩 pivot**(|O−P|=117px)。
純 Python 模擬 bone 世界變換(M=R·S),密集測試網格(400 點)逐點量測:

| AC | 內容 | 實測 | 門檻 |
|---|---|---|---|
| AC1 | 純 scale swing(峰 1.6)pivot 不動點殘差 | **0.0001px** | <0.5 |
| AC2 | **負對照**:繞件中心縮放 pivot 位移 = \|1−s\|·\|O−P\| | **70.46px**(>>AC1) | ≥10, >20×AC1 |
| AC3 | 件最遠點到 P 距離峰值相對變化(證有縮放) | **0.600**(=s−1) | ≥0.1 |
| AC4 | s=1 端點 Δ=0(identity 介面保持) | **0/0** | <1e-6 |
| AC5 | **相似**:∀點 \|world(x)−P\| = s·\|x−P\| 逐點逐幀絕對偏差 | **0.0001px** | <0.5 |
| AC6 | **rotate 24° + scale 1.6 同時**作用 pivot 仍不動(證 M=R·S 組合正確) | **0.037px** vs 負對照 93.7px | <0.5 |
| AC7 | **端到端**經真實 `build_animations` 產 pulse(limb scale+rotate,無 translate)→`apply_pivots(include_scale)`:有限/無縫/pivot 不動;內建負對照未套用會動 | 殘差 0.014px vs 負對照 22.14px | — |

**負對照設計**:AC2 = 同一 scale swing 不補償(繞件中心)→ pivot 漂 70px(=0.6×117);
AC6 負對照 = rotate+scale 都不補償 → 93.7px;AC7(d)= build_animations 的 pulse 未套用 → 22.14px。

**回歸(全綠)**:0i `validate_pivot_rotation.py` **逐 AC PASS**(include_scale 預設 False → 舊路徑不變);
`validate_anim`(+`--selftest`)對 `--scale-pivot` build **overall_pass**;round-trip `validate_build`
對 `--scale-pivot` build **4AC PASS**(setup pose 與源 PSD 完全一致 —— 補償在 setup=identity 時為 0)。
端到端 build 確認 In/burst/hit/Out 的 `b_左手` 皆帶密 scale+translate 補償通道。

## 關鍵發現

1. **一條公式吃兩種運動**:`Δ=(M−I)(O−P)` 用 `M=R·S` 把 0i(旋轉)與 G-3(縮放)統一;
   0i 是 `S=I` 特例。「繞關節旋轉」與「繞關節伸縮」不是兩套程式,是同一仿射補償的兩個分量。
2. **相似 ≠ 等距**:0i 的判準是「到 P 距離**不變**」(等距);scale 版是「到 P 距離**等比 s 倍**」(相似)。
   AC5 用 `|world(x)−P| = s·|x−P|` 逐點驗,才抓得住「真的繞 P 縮放」而非別的位移剛好讓 pivot 不動。
3. **「模板/幾何就緒 ≠ 生成器接上」再現**:scale 通道 0d 就在產(In/Out/pulse),但一直繞件中心縮放;
   接上關節 pivot 需這條含 scale 的補償(與 0i 同型的獨立工作塊)。
4. **非線性必須加密**:Δ 對 s 也非線性 → scale 通道與 rotate 一樣要 densify,否則幀間漏(正確性要件)。

## 誠實界定 / honest boundary

- 閘驗**幾何不動點/相似性**(客觀:P 是否固定、件是否等比繞 P 縮放)。「縮放幅度多少、彈多重」
  屬美術微調(RULES **A 類**),留使用者。
- pivot 真值仍是 S5 接觸縫**草案**;Award 僅機器人一件可拆肢體 rig(多 rig 真值屬使用者資源)。
- 只在**非 rig** 下套用(rig 已把 bone 搬到關節,補償冗餘);與 `--rig` 併用(per-bone 語意去重,建議 G-1)
  非本塊範圍。sx≠sy 的**非均勻**縮放仍正確補償(Δ 公式通用),但 AC5 相似性只對均勻 scale 成立
  (生成器目前只出均勻 scale)。故 cap `scale_pivot_keyframe` L2 併入 `spine-anim-forge`,**區塊仍 HOLD**
  (運動基元先驗、單一真值資產,防固化)。
