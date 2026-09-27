# S1 — volume-conserving twist 接檔位差異化(tier 放大重算等向補償維持 det≡1)

> 結論先行 / candidate **G-4''''''-vol-tier** / 里程碑 2026-09-27 (run 002) / 信心:**高**(閘 6 AC + 負對照 + 回歸全綠)
> 相關階段:專案第 2 階段(S1 反推分析器 → 分鏡→動畫 keyframe 生成器);運動基元庫 `spine-anim-forge`(HOLD)。

## 結論

補上 (G-4''''''-vol) 明列的**最後一條 honest boundary**:「vol 僅作用 base twist;tier 變體 vol 隨檔位
放大需**重算**補償 scale 維持 det≡1,比照 squash 耦合 amplify」。本次讓 twist 檔位變體(`twist__{tier}`)
與 tier_gains 併用時,補償 scale 依**放大後 shear** 於同 τ **重算**,使每個檔位的全域 local 行列式都保持
`det ≡ 1`(擰而不變面積)。至此 twist 系列的**幅度(tier)/ 段數(count)/ 體積守恆(vol)三軸皆接檔位**,
且 vol 與 tier 幅度、count 段數、φ 比值**四效正交可疊**。

## crux — 為何不能沿用逐軸 `_amp_scale`(這是本 chunk 的全部難點)

補償 `s = 1/√cos(shearX − shearY)` 是 **shear 的函式(跨通道)**。tier 幅度把兩軸 shear 同比 ×g
(shearX'=g·shearX、shearY'=g·shearY),於是

```
cos(shearX' − shearY') = cos(g·(shearX − shearY))     # 非線性隨 g 改變
```

- **錯法(逐軸 `_amp_scale`)**:`s_naive = 1 + g·(s_base − 1)` —— 只是把「為 base shear 算的」補償
  **線性拉長**,與放大後的新 shear 不匹配 → 破守恆。實測(特效 role,shearX 峰 16°、φ=0.7):

  | tier | g | 正確 s | 逐軸 s_naive | 逐軸 det |
  |---|---|---|---|---|
  | Super | 1.00 | 1.0603 | 1.0603 | 1.0000 |
  | Mega | 1.35 | 1.1169 | 1.0815 | 0.9375(|det−1|=0.06) |
  | Omg | 1.70 | 1.2024 | 1.1026 | 0.8408(0.16) |
  | Legend | 2.10 | 1.3572 | 1.1267 | 0.6892(**0.31**) |

- **對法(重算)**:`s' = 1/√cos(g·(shearX − shearY))`,以**放大後** shear 重算 → `det = s'²·cos ≡ 1` 逐檔保持。
  補償 s 峰隨檔位嚴格遞增(Super 1.06 → Legend 1.36)—— 證 scale **真被重算**,非凍結/線性拉長。

## 與 squash 耦合 amplify(G-4''''')的機制對比(關鍵鑑別)

| | squash 耦合 amplify(G-4''''') | volume-conserving twist tier(本次) |
|---|---|---|
| 守恆放大由 | scale **自身另一軸反推**(`sy'=1/sx'`) | **同幀 shear** 重算(`s'=1/√cos(shearX'−shearY')`) |
| 補償形態 | **非均勻**(scaleX≠scaleY) | **等向**(scaleX==scaleY) |
| 依賴通道 | 只看 scale 通道 | **跨通道**(scale 依賴 shear) |
| 約束 | `scaleX·scaleY ≡ 1` | `s²·cos(shearX−shearY) ≡ 1` |

→ 兩種同是體積守恆、放大後仍守恆,但**不同源**;閘 VL3 以「twist scale 等向 vs squash 檔位變體非均勻」互證隔離。

## 實作(全 additive、預設逐位元向後相容)

- `tier_variants.amplify_bone_tl(b, g, coupled=False, twist_vol=False)`:新增 `twist_vol`。True 時
  **先**把 shear 兩軸 ×g,再用 `_twist_vol_scale(shx', shy')` 由放大後 shear **重算**等向補償 scale
  (捨入同 `gen_twist`:env round 6 → beat round 4 → g=1.0 逐位元同 base)。三路互斥:twist_vol 優先、
  其次 coupled(squash 非均勻)、否則逐軸 `_amp_scale`。
- `tier_variants.amplify_anim(..., twist_vol=False)`:透傳。新增文件用集合 `VOL_CONSERVE_CATS = {"twist"}`。
- `gen_animations.build_animations`:tier 迴圈以 `tvol = (cat=='twist' and twist_volume)` 路由 `twist_vol=` 給
  `amplify_anim`;count-variant 重生成也帶 `twist_vol=twist_volume`(段數重生成的 twist 變體亦掛守恆補償)。
- `build_spine --twist-volume --tier-variants --shear-pivot` 端到端:各檔位 twist 變體帶 shear+scale+rotate
  三通道,一起繞關節 pivot 補償。

## 閘 `validate_twist_volume_tier.py`(6 AC 全 PASS,真實 robot 骨架)

- **VL1** present + backward-compat:每檔位 dual-axis shear + 等向 scale;base(In/Loop/Out + base twist vol)
  帶/不帶 tier_gains 逐位元不變;**Super(g=1)== base twist(vol)逐位元**。
- **VL2** crux 逐檔守恆 + s 遞增 + 負對照:每檔位每內部極值 `|det−1| ≤ 9.6e-5`;s 峰嚴格遞增 1.06→1.36;
  **負對照** = 逐軸 `_amp_scale`(對 base vol scale 線性拉長)→ Legend `|det−1| 0.31`(破守恆)→ 證重算是關鍵。
- **VL3** crux 等向逐檔保形(scaleX==scaleY)+ squash 檔位變體非均勻隔離。
- **VL4** 兩軸峰遞增 + φ 逐檔≈0.7 不變(vol scale 不擾動 shear 簽章 → 沿用 TT2/TT3 結果)。
- **VL5** 每檔位 identity 介面(shear (0,0)、scale (1,1))+ 兩軸阻尼/反相簽章保形。
- **VL6** 端到端三通道逐檔 pivot 不動:`--twist-volume --tier-variants --shear-pivot` pivot 殘差 <0.5px
  (Super 0.004–0.016 → Legend 0.08–0.32,隨強度增大仍 sub-px)vs 負對照(繞件中心)8–74px;≥1 tier bone 帶 scale。

### 踩雷 / 誠實邊界(閘設計)

- 體積守恆是**關鍵幀級**性質。build_spine 的 pivot densify 把 scale/shear 各自線性重取樣到密網格 →
  **關鍵幀之間**線性內插的 s 與 shear 天然**不**滿足 det≡1(base vol 亦然,非本 feature 迴歸)。故 VL6
  **不**在密網格上重驗守恆(那是內插性質),守恆只在 gen 極值幀(VL2)量;VL6 只驗 pivot 三通道錨定。

## honest boundary(仍在)

- vol-tier 已補齊 → twist 系列幅度/段數/守恆三軸皆接檔位;vol 與 count 段數重生成正交(段數×幅度×守恆×φ 四效)。
- 幅度/φ/段數階梯皆 PROPOSAL(手感 A 類,留使用者);單一真值資產(防固化)。`spine-anim-forge` 仍 **HOLD**。
- 可續:cascade count-aware(J-3,跨件波第三檔位軸)、charge 蓄力段數(第四通道 count-aware)、
  `--rig`×pivot 語意去重(G-1)、主秀 beat 下 limb 繞關節 AC(G-2)。

## 一句話心法

**跨通道約束(det≡1)在 tier 放大後不會自動保持 —— 必須以放大後的 shear 重算補償(cos 的反推);
「線性拉長舊補償」是最誘人的錯法(g=1 時恰好對,愈高檔位破得愈狠)。**
