# S1 — volume-conserving twist(candidate G-4''''''-vol,`twist_volume_conserving` L2)

> 2026-09-25。補 twist 一路(G-4'''''' → -tier → -count)留到現在的**最後一條 honest boundary**:
> 反相雙軸 shear 的擰轉會**改變面積**。本次讓 `gen_twist(vol_conserve=True)` 補一條**均勻** scale
> 使 Spine local `det ≡ 1`(**擰而不變面積** = 體積守恆)。至此生成器把 **shear(兩軸)+ 均勻 scale
> 兩通道同時驅動且守恆**。

## 缺口(honest boundary 的接續)

- twist(G-4'''''')是反相雙軸阻尼 shear:`shearX` 同 wobble 阻尼擺、`shearY = −φ·shearX`(φ=0.7,反相)。
- Spine local 2×2 的行列式(rotate=0、無 scale 通道):
  `det(M) = scaleX·scaleY·cos(shearY − shearX)`,純 shear 時 `= cos(−(1+φ)·shearX) < 1`。
- 故**擰轉使面積縮小**(件在扭轉極值瞬間變小)。實測 base twist 峰 `det`:特效 0.889、body 0.915、
  limb 0.937、head 0.956 —— 最深 ~11% 面積損失。這是 (G-4''''''-count) 誠實標記的最後邊界:
  「反相雙軸未接體積守恆耦合 scale」。

## 做法:均勻補償 scale(而非 squash 的非均勻)

面積守恆只約束 scale 的**乘積** `scaleX·scaleY`。要 `det = scaleX·scaleY·cos(shearY−shearX) ≡ 1`,
補一條逐幀 scale:

```
s = 1 / √cos(shearY − shearX)      →   det = s² · cos(shearY−shearX) ≡ 1
scaleX = scaleY = s                 (均勻;首尾 shear=0 → cos0=1 → s=1,identity 介面不變)
```

- **均勻(sx=sy=s)是關鍵**:只補償面積損失、不引入任何**非均勻**(scaleX≠scaleY)簽章。
- 這與 squash(G-4'''')的體積守恆是**兩種不同的守恆幾何**:
  - **squash**:`scaleX=1+q`、`scaleY=1/(1+q)`(**非均勻倒數對**,`scaleX·scaleY≡1`)—— 拉一軸壓一軸,
    本身就守恆,shear 只是伴隨的斜拉;
  - **twist(本次)**:shear 造成面積損失,補一條**均勻放大** `s>1` 抵銷 —— scale 是**補償**、非主體。
- 補償 scale 峰:特效 1.060、body 1.045、limb 1.033、head 1.023(= `1/√det_base`,恰抵銷 base 的面積損失)。

`--shear-pivot`(`include_scale` 隱含於 `include_shear`)端到端把 rotate/scale/shearX/shearY 一起繞關節
pivot 補償 → 件做**用滿 shear 兩軸 + 均勻 scale 的一般仿射**而 pivot 精確不動,且 `det≡1`(面積守恆)。

## 做了什麼(全 additive,opt-in)

1. **`beat_templates.gen_twist(..., vol_conserve=False)`**:`vol_conserve=True` 時加 `b["scale"]`
   逐幀 `s=1/√cos(shearY−shearX)`(均勻)。**預設 False → 逐位元同舊 twist(無 scale 通道,向後相容)**。
2. **`gen_animations.py`**:`_build_beat(..., twist_vol_conserve=False)` 以 `cat=="twist"` 守衛把
   `vol_conserve` 傳給 `gen_twist`(只有 `gen_twist` 接此 kw);`build_animations(..., twist_vol_conserve=False)`
   貫穿到 base 與段數重生成兩路。
3. **`build_spine.py`**:新增 `--twist-volume-conserve` 旗標 → `twist_vol_conserve=True`。
4. **`validate_twist_vol.py`**(新閘,6 AC):見下。

## 驗收(`validate_twist_vol.py`,先驗庫 → 真實 build_spine robot 骨架 → build_animations)

**6 AC 全 PASS**:
- **VC1 present + dual-axis + scale 通道(crux)**:vol-conserve twist beat 直出、finite、有 bone;≥1 bone
  同時帶 shear(shearX 峰 16°、shearY 峰 11.2°、反相)**與** scale 通道且峰 scale > 1.01(真補償 1.060,非 identity)。
- **VC2 體積守恆(crux)**:每個 twist bone 每個關鍵幀 `|det − 1| ≤ 1e-3`(實測 worst 1e-6)。
- **VC3 均勻補償 + s≥1 + 阻尼保形**:每個 scale 幀 `|scaleX−scaleY|=0`(均勻,非 squash 非均勻)、
  `scale ≥ 1`(補償只放大不縮)、峰 scale 幀 == 峰 `|shearY−shearX|` 幀(scale 跟隨 shear);兩 shear 軸各自
  仍阻尼振盪(繞 0 變號≥3 + 相繼極值遞減)。
- **VC4 identity 介面**:sample(0)/sample(dur) identity、shear 首尾 (0,0)、scale 首尾 (1,1)(可插 Loop)。
- **VC5 端到端一般仿射 pivot 不動**:`build_spine --animate --shear-pivot --twist-volume-conserve`,凡有關節
  pivot 的 bone pivot 殘差 <0.5px(實測右手 0.013 / 頭 0.004 / 左手 0.016px)vs 內建負對照(繞件中心,含雙軸
  shear+均勻 scale)8.6–29.5px(>1000×)—— 證補償把「shear 兩軸 + scale」錨在 pivot。
- **VC6 負對照/隔離/加性**:(a)**非守恆守衛**:base twist(vol_conserve=False)峰 det 0.889 < 1 → VC2 對
  base FALSE(證閘測真守恆非恆等於 1);(b)**非均勻守衛**:合成 squash 式非均勻對(scaleX≠scaleY)→ 均勻判準
  FALSE(證 VC3 拒 squash 式補償);(c)**向後相容/隔離/加性**:vol_conserve=False 逐位元同無旗標預設、
  vol_conserve=True 下**非 twist** beat 逐位元同 False(旗標只作用 twist)、移除 twist storyboard → 其餘 beat
  逐位元不變(零回歸)。

回歸:`check_readiness.py` 全綠(23 閘;22 既有 + 新 twist_volume_conserving),無 GREEN→RED。

## 關鍵發現

- **一般仿射 M 的四自由度(rotate / 非均勻 scale / shearX / shearY)生成端全數驅動過之後,twist 再補上
  「shear 兩軸 + 均勻 scale 兩通道同時且守恆」** —— 這是第一個**用 scale 去補償 shear 面積效應**的節拍
  (squash 的 scale 是主體、twist 的 scale 是補償)。
- **體積守恆有多種幾何**:同一個 `scaleX·scaleY≡const` 約束,squash 走**非均勻倒數對**、twist 走**均勻放大** ——
  約束在乘積,幾何自由度(均勻 vs 非均勻)由運動語意決定。均勻補償由建構(`s=1/√cos`)保證逐幀守恆,
  對照 squash count 的「新極值一出生就守恆」= **沿守恆流形生成**的通則再現。
- 補償量 `s=1/√det_base` 只與當幀 shear 夾角有關 → 首尾 shear=0 自動 s=1,identity 介面天然不破。

## honest boundary(仍在)

- **vol_conserve × tier 幅度 amplify**:tier 對 vol-conserve twist 的 scale/shear 各自 `×g` 是**非線性破守恆**
  (shear ×g → 需要的補償 `1/√cos(g·Δ)` ≠ `1+g(s−1)`)。需比照 squash 的**耦合 amplify**(沿守恆流形放大)
  重算補償 → **G-4''''''-vol-tier 為後續**。本旗標與 `tier_gains` 併用時變體暫不再守恆(已於 docstring/STATE 標記)。
- 均勻補償(而非把面積損失留著、或用非均勻補)是**手感 PROPOSAL**(A 類,留使用者拍板)。
- **單一真值資產**(robot 骨架);運動基元先驗、防固化 → cap `twist_volume_conserving` L2 併入
  `spine-anim-forge`(**仍 HOLD**)。
