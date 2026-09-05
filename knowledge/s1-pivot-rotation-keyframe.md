# S1 candidate 0i — 件繞關節 pivot 轉 keyframe(把 S5 接觸縫 pivot 接進 S1 keyframe)

> 里程碑 2026-09-05。補 STATE「下一個 bounded chunk」建議 **(G)**:把 S5 的接觸縫 pivot
> 餵進 S1 keyframe 生成器,讓件**繞關節 pivot 轉**而非件中心。第一個把 **S5(rig 幾何)→ S1(keyframe)**
> 跨子系統接起來的能力。工具:`tools/analyzer/pivot_rotation.py`、`validate_pivot_rotation.py`、
> `build_spine --pivot-rotate`。圖:`knowledge/figures/s1_pivot_rotation.png`。

## 問題

`gen_animations`(0d)產出的 `rotate` timeline 是「bone 繞**自身原點**旋轉」。非 `--rig` 組裝時,
每件 bone 原點落在**件中心 O**(`build_spine` 非 rig 分支 `bone.x/y = 件中心`),所以 limb/head 的
`rotate` 會讓件**繞件中心**轉 —— 對肢體不物理(手臂該繞肩、頭該繞頸,不是繞自己中心打轉)。

兩條解法:
- **`--rig`(結構性,已存在)**:把 bone 搬到關節接觸縫 pivot,attachment 以 delta 位移保 setup;
  然後 plain `rotate` 自然繞關節轉。改動的是**骨架結構**。
- **`--pivot-rotate`(keyframe 級,本能力)**:bone **留在件中心**,額外加一條**補償 translate**,
  使淨效果 = 件繞關節 pivot P 轉。**完全不動骨架結構**。兩者互補:要保持既有骨架/綁定時用後者。

## 數學(剛體「繞任意點旋轉」分解,確定性、無 ML)

設 bone setup 原點在 O(parent 座標)、動畫旋轉角 θ。要讓貼在該 bone 的幾何繞 pivot P(同 parent
座標)旋轉 θ,只需在原 `rotate θ` 外加平移

```
Δ(θ) = (R(θ) − I)(O − P)          R(θ)=2D 旋轉矩陣
```

**推導**:bone 加 rotate θ + translate Δ 後,setup 局部座標 ℓ 的附著點世界座標 =
`(O + Δ) + R(θ)·ℓ`。pivot 的附著局部點 ℓ_P = P − O。代入:
`(O + Δ) + R(θ)(P−O) = O + (R−I)(O−P) + R(P−O) = O + (P−O) = P`(∀θ)→ **P 為不動點**。
θ=0 時 Δ=0 → **setup / loop 端點 / In-Out 介面全保持 identity**(0d 無縫性不被破壞)。

## 實作要點(踩到的一個雷)

Δ(θ) 對 θ **非線性**。若只在原 rotate keyframe 放 Δ,兩幀之間 translate **線性內插 ≠ 真值**,
pivot 在**幀間**會漂。修法:把 rotate 通道**加密重取樣**成均勻密網格(`dt=1/60`),rotate/translate
**同時間點、皆線性** → 幀間內插一致。殘差 ~ `(1/8)|O−P|·(dθ_rad)²`,dt=1/60 下 << 0.1px(閘實測)。
已存在的 translate(如 In 的徑向歸位)會被**疊加**(先在密網格重取樣再加 Δ),兩種位移語意共存。

- `pivot_delta(θ, O, P)` = Δ 公式;`pivot_channels(rot, O, P, dt, existing_translate)` = 產密 rotate+translate;
- `apply_pivots(anim, bone_origin, pivot_of, dt)` = 就地把「有 pivot 且有 rotate 通道」的 bone 轉成繞 pivot 版
  (pivot 與件原點 <0.5px 時跳過,避免多餘 translate)。
- `build_spine --animate --pivot-rotate`(非 rig)**復用 `rig_layout` 的樹 + 接觸縫推斷**取 pivot
  (`bone_origin=件中心 center`、`pivot=接觸縫 world`),非 rig 下 bone 皆 root 子 → parent 座標 = 世界座標,公式直接成立。

## 驗收(`validate_pivot_rotation.py`,7 AC 全 PASS)

真值 = 真實 Award **左手**世界輪廓(42 頂點,mesh 保真)+ `infer_pivots` 推得的**肩 pivot**
(|O−P|=117px)。純 Python 模擬 bone 世界變換,在**密集測試網格**(400+ 點)逐點量測:

| AC | 內容 | 實測 | 門檻 |
|---|---|---|---|
| AC1 | pivot 不動點殘差(補償版) | **0.0115px** | <0.5 |
| AC2 | **負對照**:繞件中心(不補償)pivot 位移 | **48.83px**(>>AC1) | ≥10, >20×AC1 |
| AC3 | 件最遠點確有位移(沒凍住) | **94.33px** | ≥8 |
| AC4 | θ=0 幀 Δ=0(identity 介面保持) | **0/0** | <1e-6 |
| AC5 | 剛性(所有件點到 P 距離絕對偏差,等距) | **0.0115px** | <0.5 |
| AC6 | **端到端**經真實 `build_animations` 產 loop→`apply_pivots`:有限/無縫/pivot 不動;內建負對照未套用會動 | 殘差 0.0003px vs 負對照 9.75px | — |
| AC7 | rotate 帶緊湊 bezier 緩動時 AC1 仍成立 | **0.0596px** | <0.5 |

**負對照設計**:AC2 = 同一 swing 不加補償(繞件中心)→ pivot 漂 48px,證閘有鑑別力、補償真的有效;
AC6(d)= build_animations 生成的 loop 未套用 apply_pivots → pivot 漂 9.75px。

**回歸**:`validate_anim`(+`--selftest` 負對照)對 `--pivot-rotate` build **overall_pass**(0d 的
loop 無縫/In 尾 identity/Loop 首 identity/Out 首 identity 全保持);round-trip `validate_build` 對
`--pivot-rotate` build **4AC PASS**(setup pose 與源 PSD 完全一致 —— 補償在 setup=identity 時為 0)。

## 關鍵發現

1. **「模板/幾何就緒 ≠ 生成器接上」再現**:S5 早就能推接觸縫 pivot(2026-08-29),但 keyframe 生成器
   一直繞件中心轉;真正把 pivot 用到 keyframe 需這條補償 translate。與 0h(cascade 逼出 phase threading)
   同型:每個「接上」都是獨立工作塊。
2. **非線性 Δ 必須加密**:繞任意點旋轉的補償量對 θ 非線性,線性內插會在幀間漏 → densify 是正確性要件,非美化。
3. **與 --rig 正交互補**:結構性搬骨(--rig)vs keyframe 補償(--pivot-rotate)得到相同視覺(繞關節轉),
   但後者不動綁定,適合「已有骨架只想改動作」的情境。

## 誠實界定 / honest boundary

- 閘驗的是**幾何不動點**(客觀:P 是否固定、件是否剛性繞 P)。「繞 pivot 是否更貼手感、θ 幅度多少」
  屬美術微調(RULES **A 類**),留使用者。
- pivot 本身的真值仍是 S5 的接觸縫**草案**(軸向精修屬美術);且 Award 僅機器人一件可拆肢體 rig
  (多 rig 真值屬使用者資源)。故 cap `pivot_rotate_keyframe` L2 併入 `spine-anim-forge`,**區塊仍 HOLD**
  (運動基元先驗、單一真值資產,防固化)。
- 目前 build_spine 只在**非 rig** 下套用(rig 已把 bone 搬到關節,pivot-rotate 冗餘);兩者併用非本塊範圍。
