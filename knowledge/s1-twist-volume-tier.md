# S1 — volume-conserving twist 接檔位差異化(補償 scale 隨檔位重算維持 det≡1)

> 結論先行 / candidate **G-4''''''-vol-tier** / 里程碑 2026-09-28 / 信心:**高**(閘 6 AC + 兩條 crux 負對照 + 23→24 閘回歸全綠)
> 相關階段:專案第 2 階段(S1 反推分析器 → 分鏡→動畫 keyframe);運動基元庫 `spine-anim-forge`(HOLD)。

## 結論

補上 (G-4''''''-vol) 明列的**最後一條 honest boundary**:「vol 僅作用 base twist;tier 變體仍 shear-only,
vol 隨檔位放大需**重算**補償 scale 以維持 det≡1」。twist 現已併入 `TWIST_VOLUME_CATS`:當
`twist_volume=True` 且給 `tier_gains` 時,`twist__{tier}` 變體的兩軸 shear 照常**單一-g** 放大
(`v'=g*v`,φ 逐檔不變、反相不變),而**等向補償 scale** 則由 `amplify_anim(twist_vol=True)` 以**放大後**
的雙軸 shear **重算**:

```
shearX' = g·shearX,  shearY' = g·shearY
s'      = 1/√cos(shearX' − shearY')          # cos 隨 g 非線性變小 → s' 非線性變大
det'    = s'²·cos(shearX' − shearY') ≡ 1     # 逐檔體積守恆(擰而不變面積)
```

## crux:補償**不可逐軸線性放大**,必須從放大後 shear **重算**

檔位放大讓兩基底夾角偏離 `(shearX−shearY)` 隨 g 變大 → `cos` **非線性**變小 → 需要的補償 s 非線性變大。
若沿用逐軸線性增益 `_amp_scale(s,g)=1+g(s−1)`(「放大既有 s」),放大量與 cos 的變化**不匹配** →
`s²·cos ≠ 1`(破守恆)。實測(role 特效,Legend g=2.1):

| | shearX 峰 | 補償 scale 峰 | 內部極值 |det−1| |
|---|---|---|---|
| **重算**(twist_vol=True) | 33.6° | 1.3572 | **≤9.6e-5**(TOL 2e-4) |
| **逐軸線性放大**(負對照) | 33.6° | 1.1267 | **0.11–0.31**(破守恆) |

→ >1000× 分離(VL3 crux)。證「補償須從放大後 shear 重算」非「有 scale 即可 / 放大既有 s 即可」。

## 與 squash tier(G-4''''')耦合 amplify 的**機制對比**(關鍵鑑別點)

| | squash tier(G-4''''') | volume-conserving twist tier(本次) |
|---|---|---|
| 守恆量 | `scaleX·scaleY ≡ 1` | `det = s²·cos(shearX−shearY) ≡ 1` |
| scale 形態 | **非均勻**(拉長軸自由、壓縮軸=倒數) | **等向**(scaleX==scaleY=s) |
| tier 放大做法 | 耦合 amplify(拉長軸走 `_amp_scale`、壓縮軸=其倒數) | 兩軸 shear 單一-g 放大 + s 由 **cos 反推重算** |
| 守恆由 | 建構(倒數)保證 | cos 反推(重算)保證 |

→ **同是體積守恆、但不同源**:squash 的 scale 本身即擠壓(各向異性來源),twist 的 scale 純補償且等向。
兩種守恆機制在檔位放大下皆可差異化,各走各的保證路徑。閘 VL6(b) 以「twist tier scale 等向 vs squash tier
scale 非均勻」互證隔離。

## 實作(全 additive、預設逐位元向後相容)

- `tier_variants.TWIST_VOLUME_CATS = {"twist"}`:需等向補償 scale 重算的類別。
- `tier_variants._twist_vol_scale(shx, shy)`:`s=round(round(1/√cos(shx−shy),6),4)`(雙重捨入對齊
  `gen_twist` 產 base scale 的路徑 → g=1 逐位元 == base);shear=0 → cos≥1 → s=1(identity 介面保持)。
- `tier_variants.amplify_bone_tl(b, g, coupled=False, twist_vol=False)`:`twist_vol=True` 且 bone
  **同時帶 shear 與 scale**(且等長)時,先照常放大兩軸 shear(v'=g*v),再**逐索引**以放大後 shear 重算
  scale(scaleX==scaleY=s')。逐索引對齊(非時間字典)避免端點與末內部極值 τ 相同時相互覆蓋。
- `tier_variants.amplify_anim(..., twist_vol=False)`:透傳。
- `gen_animations.build_animations`:amplify 時 `tw_vol = twist_volume and cat in TWIST_VOLUME_CATS`
  → 透傳給 `amplify_anim`;count 重生成亦帶 `twist_vol=twist_volume`(count×vol 正交)。

## 閘 `validate_twist_vol_tier.py`(6 AC 全 PASS,真實 robot 骨架)

- **VL1** present + backward-compat:每檔位 `twist__{tier}` 產出/finite/有 bone/≥1 bone 雙通道
  (shear + **等向** scale)/路由回 twist;**Super(g=1)逐位元 == base vol twist**;base(In/Loop/Out +
  base vol twist)帶/不帶 tier_gains 逐位元不變;**twist_volume=False + tier_gains → tier 變體 shear-only**
  (無 scale,即 G-4''''''-tier 輸出)。
- **VL2 crux**:**每檔位**每 twist bone 每內部極值 `|det−1| ≤ 9.6e-5`(TOL 2e-4)+ scale 等向。
- **VL3 crux**:逐軸線性放大(不重算)Legend |det−1| 0.11–0.31 vs 重算 <1e-4 → >1000× 分離。
- **VL4**:兩軸峰皆嚴格遞增(shearX [16,21.6,27.2,33.6]°、shearY [11.2,15.12,19.04,23.52]°)+ φ 逐檔≈0.7
  不變 + **補償 scale 峰**亦嚴格遞增([1.0603,1.1169,1.2024,1.3572])(愈高檔位擰愈狠 → 補償愈大)。
- **VL5**:每檔位兩軸各自阻尼(首尾 0、繞 0 變號≥3、相繼極值遞減)+ 每內部極值反相。
- **VL6**:(a) identity 介面(shear (0,0)、scale (1,1))每檔位;(b) 等向 vs squash 非均勻隔離;
  (c) **count×vol 正交**:tier_twist_cycles + twist_volume → 段數 [4,5,6,7] 嚴格遞增 **且**逐極值仍守恆
  (段數×幅度×體積守恆三效正交可疊)。

**回歸**:全 twist/squash/wobble/priors/tier/beat/pivot 系列全綠;`check_readiness.py` 退出 0、0 RED、
無 GREEN→RED。新增 cap `twist_volume_tier` L2 併入 `spine-anim-forge`(**仍 HOLD**)。

## honest boundary(仍在)

- vol-tier 幅度階梯沿用 (J) 增益 [1.0,1.35,1.70,2.10] 為 PROPOSAL(手感 A 類,留使用者);單一真值資產。
- `spine-anim-forge` 仍 **HOLD**(運動基元先驗、防固化)。

## 一句話心法

**跨通道約束(det≡1)在檔位放大下由重算(cos 反推)保證,一如 squash 由建構(倒數)保證;同一守恆目標,
squash 走非均勻耦合、twist 走等向重算 —— 兩種不同源守恆機制皆能檔位差異化,各走各的保證路徑。**
