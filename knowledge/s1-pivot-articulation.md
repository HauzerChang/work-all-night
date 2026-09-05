# S1 (e) / candidate 0i — 關節 pivot 接 keyframe:件繞關節轉而非件中心

> 里程碑 2026-09-05。把 **S5 的接觸縫關節 pivot** 餵回 **S1 keyframe 生成器**,讓 limb/head 以
> 關節為軸擺盪,而非像唱盤一樣繞件中心自轉。純 CPU、確定性,含端到端評估器 + 內建負對照。

## 問題

非 rig 的 `build_spine` 把每件 bone 放在**件中心**(`x=cx, y=H-cy`,parent=root)。因此
`gen_animations` 產的 limb `rotate` 是「繞件中心旋轉」——手臂會整支自轉,關節(肩/頸/髖)被拖走,
不符解剖。S5 已能推斷關節 pivot(`infer_pivots` 接觸縫,見 `s5-rig-pivot-inference.md`),
但先前只用在 `--rig`(**結構性**把 bone 搬到關節);keyframe 路徑(扁平骨架)沒接上。

`--rig` vs 本能力(0i)的差別:
- `--rig`:改**骨架結構**(bone 搬到關節、reparent、attachment 頂點加 delta 保 setup)。
- **0i(本能力)**:**不動骨架**(bone 仍在件中心),在**動畫層**用補償平移做出「繞關節轉」的視覺。
  適用非 rig 素材;是 keyframe 級技巧,不是結構重組。

## 數學(扁平骨架:parent=root、root 單位變換、bone setup rot=0、rotate 通道 scale=1)

bone 原點 `O`(件中心世界座標),關節 pivot `P`(世界座標)。對某幀角 θ,補償平移

```
Δ(θ) = (R(θ) − I)(O − P)
```

則綁在 bone 的任一點 `v` 動畫世界座標 `v' = O + Δ(θ) + R(θ)(v − O)`;代入 `v=P`:

```
P' = O + (R(θ)−I)(O−P) + R(θ)(P−O) = O − (O−P) = P   ← P 為不動點(關節)
```

**負對照(不補償,Δ=0)**:`P' = P + (I−R(θ))(O−P)`,位移量 `= 2·sin(θ/2)·|O−P| ≠ 0`
→ 件繞中心轉會把關節拖走。這就是評估器的內建鑑別子。

R 用 CCW 正(與 Spine runtime 一致)→ **產出的 timeline 在真引擎也正確**,不只在自家 sampler 自洽。

## 實作

- **`tools/analyzer/articulate.py`**(新,核心 primitive):
  - `rot_apply(deg, vx, vy)` — R(θ) 的**單一真相來源**(generator/validator 共用 → 不動點與 CW/CCW 無關)。
  - `pivot_translate(θ, oxp, oyp)` — Δ=(R(θ)−I)(O−P)。
  - `articulate_about_pivot(rotate_frames, O, P, base_translate=None, samples=24)` — 把 rotate 通道
    (任意 curve)與既有 translate **共同密取樣**到同一均勻時間格(線性段),每格點上 (rotate, translate)
    自洽 → **格點上 P 精確不動**;格點間殘差 O(step²),由 `samples` 控制。首尾沿用原端點(θ=0→Δ=0)
    → setup/介面不擾動、可無縫串接。既有 translate(如 gen_in 徑向)會被**疊加保留**。
  - `world_point(O, sampled_bone, v)` — 扁平骨架下綁 bone 的點世界座標(驗證用,與 generator 同 R)。
- **`tools/analyzer/gen_animations.py`**(擴充,向後相容):`build_animations(skeleton, storyboard, pivots=None)`
  新增 `pivots` 參數 = `{safe_part_name: (Px,Py)}`。有 pivot 且該件產了 `rotate` → 把 rotate 改繞關節轉
  (`O=(bd.x,bd.y)` 件中心,`P=pivots[sname]`)。**預設 None → 原行為**(既有 validator 不受影響)。
- **`tools/analyzer/build_spine.py`**(擴充):`--pivot-articulate` 旗標(需 `--animate`,非 rig 亦可)。
  pivot 取自 `rig_layout` 的接觸縫關節(`joint==True` 的件);餵給 `build_animations(pivots=)`。

## 驗收(`validate_pivot_articulation.py`:6 AC 全 PASS,exit 0)

端到端:真實 Award 機器人 5 拆件幾何 → `infer_pivots` 推關節 → 造扁平骨架(bone 在件中心)→
經 `build_animations(pivots=)` 產動畫 → `spine_anim` 取樣 + `world_point` 算關節世界座標逐幀。

| AC | 判準 | 結果 |
|---|---|---|
| A1 端到端不動點 | `build_animations(pivots)` 各結構子件關節逐幀漂移 < 0.5px | ✅ 頭 0.0025 / 左手 0.0068 / 右手 0.0018 |
| A2 負對照(繞件中心)| `pivots=None` 至少一件關節漂移 > 5px | ✅ 左手 10.24(頭 3.87/右手 2.9;\|O−P\| 小者天然小)|
| A3 件確實在轉 | 離 pivot 最遠點移動 > 3px 且到 P 距離守恆 < 0.5px(純旋轉)| ✅ move 8.3/19.8/44.3,radius_drift ≤ 0.006 |
| A4 介面保留 | 首尾 rotate≈0 且 Δ≈0 → setup 不擾動、可串接 | ✅ |
| A5 疊加 base translate | 合成 rotate+base(無 scale),扣 base 後 P 恆等原 P(格點)< 0.01px | ✅ 0.0095(dense 0.034 為 O(step²) 資訊值)|
| A6 primitive 大角度精確 | 合成 45°:格點不動點 < 0.01px、半徑守恆、不補償位移 == 2sin(θ/2)\|O−P\| 解析 | ✅ fix 0.002 / nc 133.88 == analytic 133.88 |

回歸:`validate_anim`(+`--selftest`)對 `build_spine --animate` 與 `--animate --pivot-articulate` 皆 PASS;
`validate_cascade`/`validate_more_beats`/`validate_beat_templates`/`validate_priors_beats` 全 PASS
(pivots=None 預設路徑未動)。

## 關鍵發現

- **繞件中心 vs 繞關節在扁平骨架可純用 keyframe 解決**——不必動骨架(對照 `--rig` 的結構重組);
  補償平移 Δ=(R(θ)−I)(O−P) 讓 bone 留在件中心也能「繞關節轉」,且產物在真 Spine 引擎正確(R=CCW)。
- **不動點性質在格點精確,格點間 O(step²)**——共同密取樣讓 rotate/translate 在格點自洽;`samples`
  是精度旋鈕(A5:32 格點殘差 0.034px、64 格點 0.012px)。硬性判準取格點(數學定義處),
  dense 值列資訊性,誠實不掩蓋。
- **評估器自信 = 解析核對**——A6 的不補償位移實測 133.8845 == `2sin(θ/2)|O−P|` 解析 133.8845
  (差 <1e-6)→ 閘的度量本身可信、且能鑑別(A2 用同度量抓到繞中心版漂移)。
- **beat 命名會誤中類別子字串**(再現「模板/命名陷阱」):`"loop_swing"` 因含 `"in"`(sw**in**g)
  被 `beat_category` 判為 **intro**(帶 scale/translate 汙染純旋轉測)。validator 改用精確 beat 名
  `"loop"` 並 `assert beat_category=="loop"`。

## 誠實限制 / 下一步

- 本能力只消除 **rotation** 對 pivot 的位移;**scale-pop**(gen_in/gen_pulse 的 scale)仍繞件中心脹縮
  → pop 時關節仍會被 scale 拉動。若要「連 scale 都繞關節」需對 scale 亦補償(另一議題,幅度小,列為 boundary)。
- pivot 來源 = S5 接觸縫**草案**;沿肢體軸精確落點、為手感偏離幾像素屬美術微調(RULES A 類,留使用者)。
- 單一真值資產(Award 機器人),與 S5 同一 honest boundary;多 rig/多素材真值仍屬使用者資源。
- 新增 cap `pivot_articulation` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。

## 產出檔案

- 新增:`tools/analyzer/articulate.py`、`tools/analyzer/validate_pivot_articulation.py`、本檔。
- 更新:`tools/analyzer/gen_animations.py`(`build_animations` 加 `pivots`)、`tools/analyzer/build_spine.py`
  (`--pivot-articulate`)、`tools/check_readiness.py`(cap)、`STATE.md`、`knowledge/README.md`。
