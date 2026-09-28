# S1 — volume-conserving twist 接檔位差異化(補償等向 scale 由放大後 shear 重算)

> 結論先行 / candidate **G-4''''''-vol-tier** / 里程碑 2026-09-28 / 信心:**高**(閘 6 AC + 雙負對照 + 23→24 閘回歸全綠)
> 相關階段:專案第 2 階段(S1 反推分析器 → 分鏡→動畫 keyframe 生成器);運動基元庫 `spine-anim-forge`(HOLD)。

## 結論

補上 volume-conserving twist(G-4''''''-vol)明白列出的最後一條 honest boundary:**vol 僅作用 base twist;
tier 變體仍 shear-only**。本次讓 twist 的檔位(tier)幅度變體**也體積守恆**。

關鍵是一個**跨通道耦合陷阱**:
- G-4''''''-vol 在 base 幅度掛等向補償 `s = 1/√cos(shearX − shearY)` → 全域 local 行列式 `det ≡ 1`。
- G-4''''''-tier 以同一 g 同比放大兩軸 shear(`v' = g·v`)→ `shearX' = g·shearX`、`shearY' = g·shearY`。
- 於是 `cos(shearX' − shearY') = cos(g·(shearX − shearY))` **隨 g 改變**(擰得愈狠、面積縮愈多)。

⇒ **base 幅度算出的補償 scale 已不足以維持 det≡1**。若沿用 base scale(或對 base scale 線性放大),高檔位
面積守恆破裂(實測 Legend `|det−1|` 達 **0.39**)。

解法:tier 變體的補償等向 scale 必須由**放大後**的 shear **重算**

```
s' = 1/√cos(shearX' − shearY') = 1/√cos(g·(shearX − shearY))      # det = s'²·cos(shearX'−shearY') ≡ 1
```

## 與 squash 耦合 amplify(G-4''''')的**機制對比**(關鍵鑑別點)

| | squash tier(G-4''''') | volume-conserving twist tier(本次) |
|---|---|---|
| 守恆約束 | `scaleX·scaleY ≡ 1` | `s²·cos(shearX−shearY) ≡ 1` |
| 約束是否耦合 shear | **否**(與 shear 無關) | **是**(耦合到放大後的 shear 值) |
| 重算方式 | 由 scaleX 反推 scaleY(`_amp_scale_coupled`) | **讀放大後 shear** 才能算 s(`_twist_vol_scale_from_shear`) |
| 補償各向性 | 非均勻(scaleX≠scaleY) | 等向(scaleX==scaleY) |

→ twist vol-tier 的獨有鑑別點:**補償量取決於放大後 shear**,不能只看 scale 通道自身。squash 沿守恆流形放大
不必回看 shear;twist 必須。

## 實作(全 additive、預設逐位元向後相容)

- `tier_variants._twist_vol_scale_from_shear(shear_frames)`:由(已放大的)雙軸 shear frames 算等向補償 scale,
  首尾 (1,1);rounding 對齊 `beat_templates._twist_scale_env`(round 6 再 4)→ Super(g=1)逐位元同 base。
- `tier_variants.amplify_bone_tl(b, g, coupled=False, twist_vol=False)`:新增 `twist_vol` 分支——**先**放大兩軸
  shear(`v'=g·v`),**再**由放大後 shear 重算等向 scale(不走逐軸 `_amp_scale`,那無法維持隨 shear 非線性變化的 det≡1)。
  三種 scale 模式互斥:`twist_vol`(重算等向)/ `coupled`(squash 耦合非均勻)/ 皆 False(逐軸 overshoot)。
- `amplify_anim(..., twist_vol=)` 透傳。
- `gen_animations.build_animations(..., tier_gains, twist_volume=True)`:對 twist 檔位變體 `tvol = (cat=="twist" and
  twist_volume)` → amplify 走 `twist_vol=True`;檔位變體重生成(count-aware 段數)時亦帶 `twist_vol=twist_volume`
  → **段數 × 幅度 × 體積守恆三效正交可疊**(重算補償讀多少段 shear 就算多少段 scale)。
- `build_spine --tier-variants --twist-volume --shear-pivot`:端到端三通道(shear+scale+rotate)繞關節 pivot 補償。

## 閘 `validate_twist_volume_tier.py`(6 AC 全 PASS,真實 robot 骨架)

- **VTT1** present + dual-channel + backward-compat:每檔位 `twist__{tier}` finite、雙軸 shear + 等向 scale;
  base 逐位元不變;`twist_volume=False` → tier 變體 **shear-only 無 scale**(向後相容)。
- **VTT2 crux** 每檔位體積守恆:每檔位每內部極值 `|det−1| ≤ 2e-4`(max 9.6e-5,**不只 base**);
  **負對照(a)無補償** scale≡1 → `|det−1|` [0.11, 0.20, 0.31, 0.46] 隨檔位遞增(縮愈多);
  **負對照(b)base scale 未重算** → 對高檔位放大後 shear 施 Super base scale → `|det−1|` [~0, 0.099, 0.222, 0.390]
  Mega/Omg/Legend 破裂且遞增 → 證「補償 scale 必須由放大後 shear 重算」非「沿用 base 即可」。
- **VTT3** 每檔位 scale 等向;兩軸峰 shearX [16,21.6,27.2,33.6]°/shearY [11.2,15.12,19.04,23.52]° 遞增;
  補償幅度 `|s−1|` [0.060, 0.117, 0.202, 0.357] 隨檔位**嚴格遞增**(擰愈狠→補愈多)。
- **VTT4** 每檔位雙軸阻尼簽章(首尾 0、變號≥3、極值遞減)+ 反相耦合 + φ 比值≈0.7 保形。
- **VTT5** 每檔位 identity 介面(shear (0,0)、scale (1,1))。
- **VTT6** 端到端 `build_spine --tier-variants --twist-volume --shear-pivot` 每檔位 twist__tier pivot 殘差 < 0.5px
  (Legend 最強一般仿射 0.32px)vs 負對照 ≥18px(>150×);此路徑同時帶 `tier_twist_cycles`(段數 4→7)→
  **段數 × 幅度 × 體積守恆**三效端到端同時驗證。

## honest boundary(仍在)

- 幅度增益階梯 / φ 為 PROPOSAL(手感 A 類,留使用者);單一真值資產(防固化)。`spine-anim-forge` 仍 **HOLD**。
- twist 系列(生成 → tier 幅度 → count 段數 → vol → **vol-tier**)的自主結構軸至此收斂;後續運動基元(如
  cascade count-aware、charge 蓄力段數)為別的通道。

## 一句話心法

**兩個各自守恆/保形的機制相乘,未必自動守恆 —— 當守恆約束耦合到被放大的通道(twist:det 依賴放大後 shear),
補償必須沿放大後的狀態重算,不能沿用 base。squash 的守恆與 shear 無關故不必回看;twist 的必須。**
