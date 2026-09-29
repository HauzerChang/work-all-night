# S1 — volume-conserving twist 接檔位差異化(tier 放大 shear → 重算等向補償 scale)

> 結論先行 / candidate **G-4''''''-vol-tier** / 里程碑 2026-09-29 / 信心:**高**(閘 6 AC + 負對照 + 回歸全綠)
> 相關階段:專案第 2 階段(S1 反推分析器 → 分鏡→動畫 keyframe 生成器);運動基元庫 `spine-anim-forge`(HOLD)。

## 結論

補上 (G-4''''''-vol) 明列的**最後一條** honest boundary:「vol 僅作用 base twist;tier 變體仍 shear-only。
vol 隨檔位放大需**重算補償 scale** 以維持 det≡1」。本次讓 twist 的**體積守恆**在檔位放大下保持:tier 以同一
`g` 放大兩軸 shear(`v'=g·v`)→ `shearX − shearY` 變成 `g·(shearX − shearY)` → `cos(shearX−shearY)` 非線性
變小 → 補償 scale 必須從**放大後**的 shear 重算:

```
s' = 1/√cos( g·(shearX − shearY) )          # 對放大後的兩軸 shear 反推等向補償
det = (s'·s')·cos(g·(shearX − shearY)) ≡ 1  # 任一檔位皆守恆(擰而不變面積)
```

至此 **twist 系列的 honest boundary 全數清空**:生成端**一般仿射四自由度(rotate / 非均勻 scale / shearX /
shearY)+ 體積守恆 + tier 幅度 + tier 段數**全通,且三效(段數 × 幅度 × 守恆)正交可疊。

## 與 squash 耦合 amplify 的**機制對比**(關鍵鑑別點)

| | squash tier(G-4''''') | volume-conserving twist tier(本次) |
|---|---|---|
| 守恆約束 | scaleX·scaleY≡1(scale **內部**耦合) | det=(s·s)·cos(shearX−shearY)≡1(scale **由 shear 決定**) |
| 放大做法 | 放大拉長軸 overshoot、壓縮軸取**倒數** | 放大兩軸 shear 後,依放大後 shear **重算**等向 s |
| scale 各向 | **非均勻**(scaleX≠scaleY) | **等向**(scaleX==scaleY) |
| 補償來源 | scale 自身即擠壓 | scale 純補償 shear 造成的面積變化 |

→ 兩者都是「沿守恆流形放大」,但 squash 沿 scale 內部流形、twist 沿「shear→scale」映射流形。

## 為什麼**不能**用逐軸線性放大既有 s(crux)

`_amp_scale(s, g) = 1 + g·(s−1)` 是對既有補償 s 做**線性**放大。但正確補償 `s' = 1/√cos(g·Δ)`(Δ=shearX−shearY)
是 g 的**非線性**函式(透過 cos)。兩者在高檔位嚴重分歧 —— 實測(特效 role,base Δ=27.2°):

| 檔位 | g | 放大後 Δ | 正確 s'(重算) | 逐軸線性 s | 逐軸線性的 det | \|det−1\| |
|---|---|---|---|---|---|---|
| Super | 1.0 | 27.2° | 1.060 | 1.060 | 1.000 | 9e-5 |
| Mega | 1.35 | 36.72° | 1.118 | 1.081 | 0.937 | 0.063 |
| Omg | 1.70 | 46.24° | 1.204 | 1.102 | 0.841 | 0.159 |
| Legend | 2.10 | 57.12° | 1.357 | 1.127 | 0.689 | **0.311** |

Legend 逐軸線性放大 |det−1|≈0.31,重算 ≤9.7e-5 → **>3000× 分離**。這正是閘 TVT2 的負對照。

## 實作(全 additive、預設逐位元向後相容)

- `tier_variants._twist_vol_scale(shx, shy)`:等向補償 `s=1/√cos(shx−shy)`(與 `beat_templates._twist_scale_env`
  同式,單一真相;此處對**放大後**的 shear 重算)。捨入 4 位對齊 `gen_twist` 寫檔精度。
- `tier_variants.amplify_bone_tl(b, g, coupled=False, twist_vol=False)`:`twist_vol=True` 時 scale 不逐軸放大,
  而在 shear 放大後、依放大後兩軸 shear **逐幀重算**等向補償 s(scale/shear 關鍵幀同 τ,依 time 配對重寫)。
  `coupled`(squash)與 `twist_vol`(twist)互斥。`amplify_anim` 透傳 `twist_vol`。
- `tier_variants.TWIST_VOL_CATS = {"twist"}`(文件用,標記此耦合;實際路由由 build_animations 依
  `twist_volume and cat=="twist"` 決定)。
- `gen_animations.build_animations(..., twist_volume=True)`:對 twist tier 變體計 `tvol=twist_volume and
  cat=="twist"`,重生成時帶 `twist_vol=tvol`(該檔位段數的補償 scale)、amplify 時帶 `twist_vol=tvol`
  (依放大後 shear 重算)→ base 與**每個** tier 變體皆守恆。
- 端到端沿用 `build_spine --animate --tier-variants --twist-volume --shear-pivot`(無新 CLI 旗標:既有
  `--twist-volume` 現同時作用於 base 與 tier 變體)。

## 閘 `validate_twist_volume_tier.py`(6 AC 全 PASS,真實 robot 骨架)

- **TVT1** present + backward-compat:base twist(vol)雙軸 shear + 等向 scale;每檔位 `twist__{tier}` 皆產出、
  finite、dual-axis shear + 等向 scale、路由回 twist;base 帶/不帶 tier_gains 逐位元不變;**twist_volume=False →
  tier 變體無 scale**(關掉 vol 零回歸)。
- **TVT2** crux — per-tier 體積守恆:每檔位每內部極值 |det−1| ≤ 2e-4(實測 ≤9.7e-5);**負對照** = 同一 base vol
  beat 以 `amplify_bone_tl(twist_vol=False)`(逐軸線性放大既有 s)→ Mega/Omg/Legend |det−1| 0.063/0.159/0.311
  破守恆 → 證重算補償必要、閘測「真體積守恆」非「有 scale 即可」。
- **TVT3** crux — 雙軸峰遞增 + φ 不變:shearX[16,21.6,27.2,33.6]°、shearY[11.2,15.12,19.04,23.52]° 皆嚴格遞增
  (Super==base)、φ 逐檔≈0.7 不變 → 體積耦合**不擾動** twist 檔位簽章。
- **TVT4** 雙軸反相阻尼簽章 per tier:每檔位每 bone 兩軸各自(首尾 0、繞 0 變號≥3、相繼極值遞減)+ 每內部極值反相。
- **TVT5** identity 介面 per tier:每檔位 shear 首尾 (0,0)、scale 首尾 (1,1)。
- **TVT6** 端到端 pivot + 隔離:`--tier-variants --twist-volume --shear-pivot` 三通道補償 pivot 殘差 <0.5px
  (Legend 最強一般仿射 0.32px)vs 負對照繞件中心 18–74px(≥150×);twist tier scale 等向 vs squash tier
  scale 非均勻(兩種守恆機制不同源、互不外洩)。

## honest boundary(仍在)

- **twist 系列 honest boundary 至此清空**(生成端一般仿射四自由度 + 體積守恆 + tier 幅度 + tier 段數全通)。
- 幅度增益 / φ 比值 / 段數階梯數值皆為 **PROPOSAL**(手感 A 類,留使用者);單一真值資產(防固化);
  `spine-anim-forge` 仍 **HOLD**。
- 端到端 pivot 殘差隨檔位增大(Legend 0.32px):一般仿射愈強、Δ 對 θ 的非線性重取樣殘差愈大,仍 < TOL_FIX 0.5px
  且遠小於負對照(繞件中心)—— pivot 錨定為真。若未來要更緊,可提高 apply_pivots 的重取樣密度。

## 一句話心法

**跨通道約束(det≡1)在幅度×段數×守恆三軸全開下於任一檔位保持,靠的是「依放大後的 shear 反推補償 scale」——
squash 沿 scale 內部流形放大,twist 沿『shear→scale』映射流形放大;守恆恆由建構(反推)保證,非由巧合。**
