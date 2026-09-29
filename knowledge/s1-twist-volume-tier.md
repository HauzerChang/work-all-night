# S1 — volume-conserving twist 接檔位差異化(補償 scale 依放大後 shear **非線性重算**)

> 結論先行 / candidate **G-4''''''-vol-tier** / 里程碑 2026-09-29 / 信心:**高**(閘 6 AC + 負對照 + 23→24 閘回歸全綠)
> 相關階段:專案第 2 階段(S1 反推分析器 → 分鏡→動畫 keyframe 生成器);運動基元庫 `spine-anim-forge`(HOLD)。

## 結論

補上 (G-4''''''-vol) 明列的**最後一條 honest boundary**:「vol 僅作用 **base twist**;tier 變體仍 shear-only ——
vol 隨檔位放大需**重算補償 scale** 以維持 det≡1」。本次把體積守恆補到 twist 的**每個檔位變體**:

- tier 放大把兩軸 shear 同比拉大(`shearX'=g·shearX`、`shearY'=g·shearY` → 兩基底夾角偏離 `Δ'=(shearX−shearY)·g`);
- 於是真正的守恆補償變成 `s' = 1/√cos(g·Δ)` —— 對 g **非線性**(cos);
- `amplify_bone_tl(twist_vol=True)`:**先放大 shear**、再**依放大後的 shear 重算**每個 scale 極值的等向 s
  (`_recompute_twist_scale_iso`)→ 全域 local `det ≡ 1` 於**任一檔位**保持,補償量隨檔位**非線性遞增**。

至此**一般仿射四自由度(rotate / 非均勻 scale / shearX / shearY)+ 體積守恆已在生成端 base 與 tier 全檔位成立**。

## 為什麼不能沿用線性 / squash 耦合(crux)

補償 scale 是 shear 的**非線性**函數 `s=1/√cos(Δ)`。tier 放大讓 `Δ→g·Δ`,補償該走 `1/√cos(g·Δ)` 這條曲線:

| 放大方式 | 作法 | Legend(g=2.1)實測 |
|---|---|---|
| 逐軸線性 `_amp_scale(s,g)` | `1+g·(s−1)`(線性內插) | |det−1| **0.11–0.31**(追不上 cos → 破守恆) |
| squash 耦合 `_amp_scale_coupled` | `sy'=1/sx'`(倒數、與 shear 無關) | 對 twist 無意義(其補償等向、值來自 shear) |
| **依放大後 shear 重算**(本次) | `s'=1/√cos(shearX'−shearY')` | |det−1| **≤8.5e-5**(守恆) |

→ 逐軸線性追不上非線性曲線(VTT3 負對照,>1000× 分離);squash 的倒數耦合是另一種機制(scale 本身即擠壓,
不涉 shear)。twist 補償是**依放大後 shear 重算的等向 s**(cos 反推、值來自 shear),兩者**同為建構保證跨通道約束
但不同源**。

## 與 squash tier 耦合 amplify 的機制對比

| | squash tier(G-4''''') | volume-conserving twist tier(本次) |
|---|---|---|
| 跨通道約束 | `scaleX·scaleY≡1`(面積) | `s²·cos(shearX−shearY)≡1`(全域 det) |
| 放大時如何保約束 | 拉長軸自由、壓縮軸=**倒數**(與 shear 無關) | 補償 s **依放大後 shear 重算**(cos 反推) |
| scale 性質 | **非均勻**(scaleX≠scaleY,本身即擠壓) | **等向**(scaleX==scaleY,純補償) |
| 對 g | scale overshoot 線性、倒數耦合 | s 對 g **非線性**(cos) |

→ 同為「跨通道約束由建構保證於任一檔位」,但一個是倒數耦合、一個是 cos 反推重算 —— **不同源**。

## 實作(全 additive、預設逐位元向後相容)

- `tier_variants.VOL_TWIST_CATS = {"twist"}`:需依放大後 shear 重算等向補償 scale 的類別。
- `tier_variants._recompute_twist_scale_iso(sh_frames, sc_frames)`:對每個 scale 幀,依**同 time** 的(已放大)
  shear 值算 `s=1/√cos(shx−shy)`,等向寫回 (s,s)。捨入比照 `gen_twist`(round(s,6)→round(,4))→ g=1.0 逐位元同 base。
- `tier_variants.amplify_bone_tl(..., twist_vol=False)`:shear 迴圈移到 scale **之前**(twist_vol 要讀放大後 shear);
  三路互斥:`twist_vol`→重算等向補償、`coupled`→squash 倒數耦合、否則→逐軸 overshoot。`amplify_anim` 透傳。
- `gen_animations.build_animations`:twist 檔位變體以 `tv = twist_volume and cat∈VOL_TWIST_CATS` 路由 `twist_vol=tv`
  給 `amplify_anim`;段數變體(`tier_twist_cycles`)重生成時亦帶 `twist_vol=twist_volume` → 段數×幅度×守恆三效正交。
- 端到端:`build_spine --animate --tier-variants --twist-volume --shear-pivot`(twist_volume 早已透傳,無需改 build_spine)。

## 閘 `validate_twist_volume_tier.py`(6 AC 全 PASS,真實 robot 骨架)

- **VTT1** present + backward-compat:每檔位 `twist__{tier}` dual-channel(shear+**等向** scale);base 逐位元不變;
  **Super(g=1)逐位元 == base twist vol**(重算於 g=1 退化回 base)。
- **VTT2** crux 守恆 + 遞增:每檔位每內部極值 |det−1| ≤ 9.7e-5(TOL 2e-4);峰補償 scale **[1.0603, 1.1169,
  1.2024, 1.3572]**、峰 shearX [16, 21.6, 27.2, 33.6]° 皆嚴格遞增,Super==base。
- **VTT3** crux 負對照:逐軸線性 amplify(Legend)|det−1| **0.11–0.31** vs 重算 ≤8.5e-5(>1000× 鑑別)+ 重算單元測。
- **VTT4** 雙軸反相阻尼簽章 + φ 比值≈0.7 逐檔不變 + identity 介面(shear (0,0)、scale (1,1))每檔位保形。
- **VTT5** 端到端三通道 pivot 不動:`--tier-variants --twist-volume --shear-pivot` 每檔位 `twist__{tier}` pivot
  殘差 **<0.33px**(Legend 最強)vs 負對照(繞件中心)8–74px。
- **VTT6** 隔離/加性/平增益守衛:(a)平增益(隔離幅度軸)→ 補償不遞增且==base vol;(b)非 twist 主秀變體
  (wobble shear-only)不生 scale 通道;(c)移除 twist storyboard → 其餘 beat 逐位元不變。

回歸 **24 閘全綠**(23 既有 + 新 twist_volume_tier;`check_readiness.py` 退出 0,0 RED,無 GREEN→RED)。

## honest boundary(仍在)

- 幅度階梯為 PROPOSAL(手感 A 類,留使用者);單一真值資產(防固化)。`spine-anim-forge` 仍 **HOLD**。
- twist 系列的生成端能力(生成 shearY → tier 幅度 → count 段數 → 體積守恆 base → 體積守恆 tier)**至此全數接齊**。

## 一句話心法

**跨通道約束隨檔位放大要保住,關鍵在「補償是不是放大量的線性函數」:是(squash 倒數耦合)可線性耦合,
否(twist 的 cos 補償)就必須依放大後的驅動量重算 —— 補償的函數形狀決定它能否線性疊加。**
