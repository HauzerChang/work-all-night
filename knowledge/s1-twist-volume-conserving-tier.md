# S1 — volume-conserving twist 接檔位差異化(補償 scale 隨檔位重算維持 det≡1)

> 結論先行 / candidate **G-4''''''-vol-tier** / 里程碑 2026-09-28 / 信心:**高**(閘 6 AC + 負對照 + 23→24 閘回歸全綠)
> 相關階段:專案第 2 階段(S1 反推分析器 → 分鏡→動畫 keyframe 生成器);運動基元庫 `spine-anim-forge`(HOLD)。

## 結論

補上 (G-4''''''-vol) 明列的**最後一條 honest boundary**:「vol 僅作用 base twist,tier 變體仍 shear-only —— vol
隨檔位放大需重算補償 scale 維持 det≡1」。volume-conserving twist(G-4''''''-vol)的等向補償
`s = 1/√cos(shearX − shearY)`(scaleX==scaleY)使全域 local 行列式 `det ≡ 1`,但只掛在 base twist:tier 變體
放大 shear 後,舊的逐軸 `_amp_scale`(線性放大 identity 上方)會給 `1 + g·(s−1) ≠ 1/√cos(g·(shearX−shearY))`
(cos 非線性)→ **破壞體積守恆**。

本次:tier 放大 shear(兩軸同一 g → 扭角差 `g·(shearX − shearY)`)後,補償 scale 由 `tier_variants._twist_vol_scale`
從**放大後 shear** 逐幀重算

```
s' = 1/√cos(g·(shearX − shearY))     →   det = s'²·cos(g·(shearX − shearY)) ≡ 1   # 每檔位都守恆
```

而兩軸 shear 峰隨檔位嚴格遞增(shearX 16→33.6°、shearY 11.2→23.52°)、φ=shearY/shearX 比值不變(0.7)。至此
**帶跨通道守恆約束的檔位軸已在 squash(非均勻)與 twist(等向)雙機制成立**。

## 為什麼要「重算」而非「放大」補償 scale(crux)

補償 scale 不是獨立的運動幅度,而是 shear 造成面積變化的**反函數**。檔位把 shear 放大 g 倍後,面積縮放
`cos(g·(shearX−shearY))` 是 g 的**非線性**函數,故補償必須跟著非線性重算,不能沿用「線性放大 identity 上方」的
`_amp_scale`。這與 squash(G-4''''')的耦合 amplify 同一道理(跨通道約束放大時必須沿約束流形走),差別在:

| | squash(G-4''''') | volume-conserving twist(本次) |
|---|---|---|
| 檔位守恆 by | `_amp_scale_coupled`:放大拉長軸、壓縮軸設**倒數** → `scaleX·scaleY≡1` | `_twist_vol_scale`:從**放大後 shear** 重算 `s'=1/√cos(g·dφ)` → `s'²·cos(g·dφ)≡1` |
| 補償形狀 | **非均勻**(scaleX≠scaleY,scale 自己即擠壓) | **等向**(scaleX==scaleY,scale 純補償 shear) |
| 約束來源 | scale 兩軸互為倒數(建構保證) | scale 為 shear 面積縮放的反函數(從主通道重算保證) |

→ **同一守恆目標(det≡1)、不同源機制**;共通原則:**檔位放大時,守恆由『從放大後的主通道重算補償』保證**。

## 關鍵實作抉擇:從「放大後 shear」重算,不從「舊 scale 值」反推

兩種算 s' 的路子:
- **(棄)從舊 scale 值反推**:`dφ = arccos(1/s²)` → `s' = 1/√cos(g·dφ)`。自足(只吃 scale 值)但用的是**未放大** shear
  隱含的 dφ,與實際存下的 4-dec 放大後 shear 有獨立捨入 → det 殘差**隨 g 疊大**(實測 Legend 達 6e-4)。
- **(採)從放大後 shear 重算**:amplify 先把 shear 放大並存成 4-dec,再由**那些實際 shear 值**逐幀算
  `s'=1/√cos(shearX'−shearY')`。與 runtime 用的 shear **精確配對** → det 殘差**同 base 級**(≤1e-4 各檔位,不隨 g 疊大)。
  且 base twist 的 shear 幅度(16/8/4/2、φ×之)皆為 4-dec 精確值 → Super(g=1)重算後**逐位元同 base**。

實作:`amplify_bone_tl` 對 twist_vol 的 scale 通道在 **shear 放大之後**、逐 index 配對放大後 shear 重算
(shear 與 scale 關鍵幀由 `gen_twist` 共 env 生成 → 同長同索引同 τ)。

## 實作(全 additive、預設逐位元向後相容)

- `tier_variants._twist_vol_scale(shx, shy)`:單幀等向補償 `round(1/√cos(shx−shy), 4)`(與
  `beat_templates._twist_scale_env` 同公式,供 amplify 端由放大後 shear 重算)。
- `tier_variants.amplify_bone_tl(b, g, coupled=False, twist_vol=False)`:`twist_vol=True` 時,scale 於 shear 放大後
  逐幀重算(不走逐軸 `_amp_scale`);`amplify_anim(..., twist_vol=)` 透傳。`coupled`/`twist_vol` 互斥。
- `gen_animations.build_animations(..., twist_volume=False)`:tier 路由對 `cat=="twist" and twist_volume` 設
  `tvol=True` 傳給 `amplify_anim`;count-aware 重生成路徑亦帶 `twist_vol=twist_volume`(使段數變體亦掛補償 scale)。
- `build_spine.py`:`--tier-variants --twist-volume`(既有 CLI,已把 twist_volume 傳進 build_animations)端到端直出
  `twist__{tier}` 帶 shear+scale+rotate,配 `--shear-pivot` 三通道繞關節 pivot 補償。

## 閘 `validate_twist_volume_tier.py`(6 AC 全 PASS,真實 robot 骨架)

- **TVT1** present + backward-compat:base twist(vol)雙通道;每 `twist__{tier}` 產出/finite/有 bone/≥1 bone dual-channel
  且 scale **等向**/路由回 twist;base(含 In/Loop/Out)帶不帶 tier_gains 逐位元不變;**Super(g=1)逐位元 == base**。
- **TVT2** crux:每檔位每內部極值 `|det−1| ≤ 2e-4`(實測 ≤1e-4)**且** shearX 峰[16,21.6,27.2,33.6]°、shearY 峰
  [11.2,15.12,19.04,23.52]° 皆嚴格遞增(Super==base)。
- **TVT3** 雙軸反相阻尼簽章逐檔保形(繞 0 變號≥3+極值遞減+每內部極值反號)且 φ=峰Y/峰X≈0.7 逐檔不變。
- **TVT4** identity 介面:每檔位 sample(0)/(dur) identity、shear 首尾 (0,0)、scale 首尾 (1,1)。
- **TVT5** crux 負對照:對 base twist(vol)施**逐軸** amplify(`twist_vol=False`,Legend 增益)→ `|det−1|` 0.11–0.31
  (破守恆)vs `twist_vol=True` 同增益 ≤8.5e-5(>1000× 鑑別餘裕);附 `_twist_vol_scale` 單元(shear=0→s=1、
  shear≠0→s>1 且 `s²·cos≡1`)。
- **TVT6** 隔離/加性/三效正交/端到端:(a) 平增益守衛(全 1.0 → 峰不遞增且各檔位==base);(b) twist tier 變體 scale
  皆等向、非 twist 主秀 tier 變體不冒出 scale;(c) 移除 twist storyboard → 其餘 beat 逐位元不變;(d) tier_gains ×
  tier_twist_cycles × twist_volume 併用 → 段數 4→7 遞增且每檔位仍守恆(段數×幅度×體積守恆三效正交);(e) 端到端
  `build_spine --tier-variants --twist-volume --shear-pivot` 每檔位 tier 變體 pivot 殘差 < 0.33px vs 負對照 8–74px。

## honest boundary(仍在)

- 幅度增益階梯 / φ 為 PROPOSAL(手感 A 類,留使用者);單一真值資產(防固化)。`spine-anim-forge` 仍 **HOLD**。
- twist 系列(生成 shearY → tier 幅度 → count 段數 → vol → vol-tier)至此**四自由度 + 體積守恆 + 檔位(幅度/段數/守恆)
  三軸全接齊**;後續大方向轉向其他節拍的 count-aware(如 charge 蓄力段數、cascade 波速/件數隨檔位)或 (G-1)/(G-2)。

## 一句話心法

**檔位放大帶跨通道守恆約束的節拍時,守恆由『從放大後的主通道重算補償』保證(twist:從放大後 shear 重算等向 scale;
squash:從放大後拉長軸設倒數壓縮軸)—— 補償不是獨立幅度,是主通道效應的反函數,故隨檔位非線性重算而非線性放大。**
