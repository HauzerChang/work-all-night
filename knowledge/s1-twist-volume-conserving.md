# S1 — twist 反相雙軸 shear 接體積守恆等向耦合 scale(candidate G-4''''''-vol,`twist_volume_conserving` L2)

> 2026-09-26。續 twist 系列(G-4''''''／-tier／-count)。這三支一路都在 honest boundary 明列同一條:
> **「反相雙軸未接體積守恆耦合 scale(`det=cos(shearY−shearX)≠1` → 擰轉變面積,volume-conserving twist 為後續)」**。
> 本次正好照那條邊界接上:讓 twist 在擰的同時**面積守恆**(`det≡1`)。

## 缺口(honest boundary 的接續)

- twist 至今的運動基元是**純反相雙軸阻尼 shear**(shearX 同 wobble 阻尼擺、shearY=−`TWIST_PHI`·shearX 反相),
  **無 scale 通道**(twist 刻意不在 `COUPLED_SCALE_CATS`)。
- Spine local M 的行列式(見 `validate_shear_pivot._M_spine`,其 AC6b 已驗「pure shearX φ 的 det==cos φ」):
  ```
  M = [[cos(θ+shearX)·sx, cos(θ+90+shearY)·sy],
       [sin(θ+shearX)·sx, sin(θ+90+shearY)·sy]]
  det(M) = sx·sy·sin(90+shearY−shearX) = sx·sy·cos(shearY−shearX)
  ```
  純反相雙軸 shear(sx=sy=1)→ `det = cos(shearY−shearX)`。twist 的 `shearY−shearX = −(1+φ)·shearX`,
  peak `(1+φ)|shearX| = 1.7×16° = 27.2°` → `det = cos27.2° ≈ 0.889` → **面積縮 ~11%**(擰轉變面積)。

## 做法:加**等向**耦合 scale 使 det≡1

`gen_twist(vol_conserve=True)`(預設 False → 逐位元同舊行為)在每個 shear 關鍵幀加耦合 scale：
```
Δ = shearY − shearX                 # 度
s = cos(Δ)^(−1/2)                    # s² = 1/cos(Δ)
scaleX = scaleY = s                  # 等向
det = s²·cos(Δ) = 1                  # 擰而不變面積
```
`|Δ| = (1+φ)|shearX| ≤ 27.2° < 90°` → `cos(Δ) > 0` 恆成立(s 實數、良定義);首尾 shearX=shearY=0 →
Δ=0 → cos=1 → **s=1**(identity 介面保住,可插 Loop)。peak s ≈ 1.0603(放大 ~6% 補回 ~11% 的面積損)。

## crux:為什麼取「等向」(sx=sy)—— 與 squash 體積守恆的異同

體積守恆只約束**乘積** `sx·sy = 1/cos(Δ)`,留下 sx/sy 的比值自由。twist 與 squash 都是「帶跨通道關係約束
的耦合」,但**形變的來源不同 → 耦合 scale 的形狀相反**:

| | 形變主體 | 耦合 scale | 理由 |
|---|---|---|---|
| **squash**(G-4'''') | **就是非均勻 scale**(scaleX≠scaleY,shear 是斜向載體) | **非均勻** scaleX=1+q、scaleY=1/(1+q) | squash 的「擠壓」本身要靠 sx≠sy |
| **twist**(本次) | **反相雙軸 shear**(擰) | **等向** sx=sy=1/√cos(Δ) | scale 只做**面積修正**,不該再加形狀 |

取等向解 → 耦合 scale **不引入任何額外各向異性**:件唯一的非相似形變仍**純由扭轉 shear 給**,scale 純粹補面積。
若誤取非均勻(squash 式,同乘積)會憑空多一個拉伸方向(VV4c 量到 anisotropy 0.279 vs 等向 0.0)。

## 體積守恆是「關鍵幀級不變量」(與 squash 同契約,誠實標記)

`det≡1` 在**生成的耦合關鍵幀**上精確成立(VV2 量到每 bone det∈[0.9999, 1.0001],僅 4dp 存檔捨入殘差)。
關鍵幀**之間**用線性內插時,因 `s=1/√cos(Δ)` 對 shearX **非線性**,內插的 scale × 內插的 shear 之 det 會有
**有界小殘差**。這**不是 twist 專屬缺陷**——squash 同樣如此(其 scaleX·scaleY 於關鍵幀=1,中點線性內插 ≈1.0055;
本次量測見負對照佐證)。是「稀疏關鍵幀存非線性耦合」的共通性質。實測:`build_spine --shear-pivot --vol-twist`
的 pivot 補償把時間軸重採樣成 49 幀(線性內插)後,關鍵幀間 det 漂移峰 ≈ 0.037(informational,非 fail)。
若日後要收緊:加密關鍵幀或給 scale 通道上 bezier(共通改良,非本 beat 專屬)。

## 端到端 / 一般仿射的意義

`build_spine --animate --shear-pivot --vol-twist` 直出 twist(shear + 等向 scale + 補償 translate 一起繞
**關節 pivot**):rotate（此 beat=0）/scale/shearX/shearY **三通道同時**被驅動且面積守恆,而件的關節 pivot
精確不動(VV6:fixed 0.004–0.016px vs 負對照繞件中心 8.6–29.5px,>1000×)。這是**一般仿射 M 的 det(面積)
自由度首度被生成器以「耦合守恆」驅動**——先前 det 只是 shear/scale 的被動結果(wobble det=cos·1、squash det≡1
但靠非均勻),此處 twist 主動用等向 scale 把 det 鎖回 1。

## 驗證(`validate_twist_vol.py`,6 AC 全 PASS)

先驗庫 slot_bigwin → **真實 build_spine robot 骨架** → `build_animations(vol_twist=True)` 端到端量:

- **VV1** present + backward-compat + 隔離:vol_twist=False → twist **無** scale;True → **有** scale 且 shear 通道
  逐位元不變(scale 純加性,不改扭轉簽章);vol on/off 僅 twist beat 異、其餘 beat 逐位元不變。
- **VV2 crux** det≡1:每個 twist bone 的每個關鍵幀 `|det−1| < 3e-3`(range [0.9999, 1.0001])。
- **VV3** 等向 + 公式:每幀 sx==sy(|sx−sy|<1e-4)、sx≈cos(Δ)^(−1/2)、首尾 (1,1)、內部極值 sx>1(補放大)。
- **VV4** 負對照:(a)未耦合 plain twist(scale≡1)內部極值 det<0.98(peak 面積損 **0.1106**)→ 守恆 FALSE;
  (b)錯 scale(=1)施於 vol 版 shear → det≡1 FALSE;(c)等向 aniso **0.0** vs 非均勻(squash 式)**0.279**
  → 證等向是 twist 的正確選擇(額外非相似性非來自 scale)。
- **VV5** 扭轉簽章正交保住:vol 版內部極值仍反相(shearX·shearY<0)、φ 比值≈0.7,與 plain twist 逐位元相同。
- **VV6** 端到端:`build_spine --animate --shear-pivot --vol-twist` pivot 不動 0.004–0.016px vs 負對照
  8.6–29.5px(雙軸 shear + 等向 scale 同時驅動下);重採樣關鍵幀間 det 漂移 0.037(informational)。

回歸:23 閘全綠(22 既有 + 新 twist_vol);`check_readiness.py` 退出 0(0 RED,無 GREEN→RED)。
新增 cap `twist_volume_conserving` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。

## 關鍵發現

- **一般仿射 M 的 det(面積)自由度**首度被生成器**主動以耦合守恆**驅動(rotate/scale/shear 三通道同時=用滿
  仿射且守恆)。twist 系列至此把「幅度(tier)× 段數(count)× 面積(vol)」三個正交軸全部接齊。
- **耦合 scale 的形狀由「形變主體」決定**:形變是 scale → 用非均勻(squash);形變是 shear → 用等向(twist)。
  通則:耦合通道只補「守恆」,不該重複引入形變主體已提供的自由度。
- 體積守恆(以及任何非線性跨通道耦合)是**關鍵幀級不變量**;連續守恆需加密關鍵幀/bezier(共通改良)。

## honest boundary(仍在)

- **vol × tier 的耦合 amplify**:放大 shear(tier_gains)後須**重算**耦合 scale 才保 det≡1(比照 squash 的
  `_amp_scale_coupled` 沿守恆流形放大)——本次只驗 base(非 tier)vol twist;vol×tier 為後續。
- 等向解、φ、幅度為 PROPOSAL(手感 A 類,留給使用者);單一真值資產(robot rig)。
- 關鍵幀間 det 連續守恆(見上)為共通改良項。

檔案:`tools/analyzer/beat_templates.py`(`_twist_vol_scale` + `gen_twist(vol_conserve=)`)、
`tools/analyzer/gen_animations.py`(`_build_beat`/`build_animations` 加 `vol_twist=`)、
`tools/analyzer/build_spine.py`(`--vol-twist`)、`tools/analyzer/validate_twist_vol.py`(新閘)。
