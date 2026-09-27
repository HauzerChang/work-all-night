# S1 — volume-conserving twist 接檔位差異化(補償 scale 由放大後 shear 重算)

> 結論先行 / candidate **G-4''''''-vol-tier** / 里程碑 2026-09-27(run 002)/ 信心:**高**(閘 6 AC + 負對照 + 23→24 閘回歸全綠)
> 相關階段:專案第 2 階段(S1 反推分析器 → 分鏡→動畫 keyframe);運動基元庫 `spine-anim-forge`(HOLD)。

## 結論

補上 (G-4''''''-vol) 留下的 honest boundary:「vol 僅作用 **base twist**,tier 變體仍 shear-only」。
把 volume-conserving twist 的等向補償 scale 接上**檔位放大**,使**每個檔位**都維持 `det ≡ 1`(擰而不變面積)。

**crux(檔位放大為何不能沿用逐軸/耦合 scale 增益)**:tier 放大讓兩軸 shear **同比** ×g
(`shearX'=g·shearX`、`shearY'=g·shearY` → φ 比值不變),故補償 scale 必須是

```
s' = 1/√cos(g·(shearX − shearY))          # 對 g 非線性(cos 之反推)
```

而逐軸 `_amp_scale(s,g)=1+g·(s−1)` 是對 s 的**線性**放大,`≠ s'` → det 隨檔位漂移
(實測 base/Super g=1 |det−1|≈9e-5,但 Mega 0.063、Omg 0.159、**Legend g=2.1 高達 0.311**)。
所以 twist(vol)檔位變體的 scale 必須**由(放大後的)shear 重算**,不可沿用逐軸或 squash 耦合增益。

## 機制(全 additive、預設逐位元向後相容)

- `tier_variants._twist_comp_scale(shx_deg, shy_deg)`:等向補償 `s=1/√cos(shearX−shearY)`,捨入管路
  (`round(_,6)` 後 `round(_,4)`)與 `beat_templates._twist_scale_env`+`gen_twist` **一致** →
  g=1.0(Super)時與 base twist(vol)beat **逐位元一致**。
- `tier_variants.amplify_bone_tl(b, g, coupled=False, twist_vol=False)`:新增第三種 scale 模式。
  **shear 先放大**(v'=g·v,兩軸同一 g → φ 不變);`twist_vol=True` 時 scale **由放大後的 shear 重算**
  (同 τ 對應 shear 幀 → `_twist_comp_scale`,等向 scaleX==scaleY)。三種模式互斥:
  `twist_vol`(等向重算)/ `coupled`(squash 非均勻倒數)/ 逐軸(其餘主秀 overshoot)。
- `gen_animations.build_animations(tier_gains, twist_volume=True)`:對 twist 檔位變體
  `tvol=(cat=="twist" and twist_volume)` → `_amplify_anim(..., twist_vol=tvol)`;段數變體
  (`tier_twist_cycles`)重生成時**帶 vol_conserve**(`_build_beat(..., twist_vol=twist_volume)`),逐段重算補償。

## 與 squash 耦合 amplify(G-4''''')的對比

| | squash(G-4''''') | volume-conserving twist tier(本次) |
|---|---|---|
| 守恆量 | `scaleX·scaleY≡1` | 全域 `det = s²·cos(shearX−shearY) ≡ 1` |
| 檔位放大 scale | `_amp_scale_coupled`:拉長軸脹、壓縮軸=倒數(由建構守恆) | `_twist_comp_scale`:由放大後 shear 反推 s(cos 之反推) |
| 各向異性 | scale **非均勻**(scale 本身即擠壓) | scale **等向**(各向異性全由 shear 提供,scale 純補償) |
| 對 g 的關係 | scale 對 g 線性(overshoot ×g) | 補償 s 對 g **非線性**(`1/√cos(g·Δ)`) |

→ **同一守恆目標、不同源**:squash 由建構保證(倒數),twist 由 shear 反推(cos)。這也是為何逐軸/squash
耦合增益都套不到 twist —— twist 的 scale 是 shear 的函數,放大 shear 就得重算 scale。

## 閘 `validate_twist_volume_tier.py`(6 AC 全 PASS,真實 robot 骨架)

- **TVT1** present + 等向雙通道:每檔位 `twist__{tier}` 帶雙軸 shear + 等向 scale,**Super==base twist(vol)逐位元一致**。
- **TVT2 crux 每檔位體積守恆**:每檔位每 twist bone 每內部極值 `|det−1| ≤ 9.6e-5`(TOL 2e-4);
  **負對照**(逐軸線性放大)`|det−1|` 9e-5→0.063→0.159→**0.311** 單調漂移 → >500× 分離,證守恆來自
  「由 shear 重算」非「有 scale 通道即可」。
- **TVT3** 幅度遞增 + φ + 補償遞增:shearX [16→21.6→27.2→33.6]°、shearY [11.2→15.12→19.04→23.52]° 皆遞增;
  補償 scale 峰 [1.0603→1.1169→1.2024→1.3572] 亦遞增(擰愈狠 → 補愈多);φ 逐檔恆 0.7。
- **TVT4** identity 介面:每檔位 shear 首尾 (0,0)、scale 首尾 (1,1)。
- **TVT5** 反相 + 阻尼簽章逐檔保形(兩軸繞 0 變號≥3 + 相繼極值遞減 + 每內部極值反號)。
- **TVT6** 負對照/正交/向後相容:(a) 平增益守衛 全 g=1.0 → 各檔位==base 逐位元;(b) **count×tier×vol 正交**
  段數 [4,5,6,7] 遞增 **且**每檔位每極值仍 det≡1;(c) `twist_volume=False`+tier_gains → 檔位變體**無 scale**
  且非-scale 通道與 shear-only 逐鍵一致(vol-tier 純加性)。

## honest boundary(仍在)

- 幅度/φ 為 PROPOSAL(手感 A 類,留使用者);單一真值資產(防固化)。`spine-anim-forge` 仍 **HOLD**。
- twist 系列(生成 → tier 幅度 → count 段數 → vol → **vol-tier**)四軸差異化已全數守恆閉合;
  後續候選轉向 cascade count-aware(J-3)/ charge 段數 / rig×pivot 語意去重(G-1)。

## 一句話心法

**沿檔位軸維持跨通道約束時,「由建構保證的量」直接放大即可(squash 的倒數),但「由別的通道反推的量」
必須跟著那個通道重算(twist 的補償 scale = 放大後 shear 的 cos 反推)—— scale 的來源決定它能否被獨立放大。**
