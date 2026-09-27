# S1 — volume-conserving twist 接檔位差異化(補償 scale 隨檔位重算)

> 結論先行 / candidate **G-4''''''-vol-tier** / 里程碑 2026-09-27(run 002)/ 信心:**高**(閘 6 AC + 負對照 + 23→24 閘回歸全綠)
> 相關階段:專案第 2 階段(S1 反推分析器 → 分鏡→動畫 keyframe 生成器);運動基元庫 `spine-anim-forge`(HOLD)。

## 結論

補上 `twist_volume_conserving`(G-4''''''-vol)明列的最後一條 honest boundary:「vol 僅作用 base twist,
tier 變體 vol 隨檔位放大需**重算補償 scale** 維持 det≡1」。檔位放大兩軸 shear 後(單一 g → φ 保形):

```
shearX' = g·shearX,  shearY' = g·shearY          # 兩軸同比 → shearY'/shearX' ≡ −φ 逐檔不變
s'      = 1/√cos(shearX' − shearY')              # 由**放大後的 shear** 重算等向補償
det     = s'² · cos(shearX' − shearY') ≡ 1       # 每個檔位仍守恆
```

至此**一般仿射四自由度 + 體積守恆在 base 與 tier(幅度軸 tier_gains、段數軸 tier_twist_cycles)全數成立**;
三通道(shear+scale+rotate)× 三效(幅度 / 段數 / 守恆)**正交可疊**。

## crux —— 為何必須「重算」而非「線性放大」(本閘鑑別力來源)

補償 `s = 1/√cos(shearX − shearY)` 對 shear 是 **cos 的反推**(非線性)。若沿用其他主秀 scale 的逐軸
`_amp_scale`(線性 `1 + g·(s−1)`,只放大 identity 上方),線性放大**追不上** cos 隨角度變化的曲率 →
det 隨檔位偏離 1 愈來愈遠(破守恆)。必須從**放大後的 shear 逐幀重算** s。

負對照(線性放大)實測 max-gain(Legend g=2.1)`|det−1|`:

| bone | 光暈 | 身體 | 右手/左手 | 頭 |
|---|---|---|---|---|
| neg-plain `|det−1|` | 0.311 | 0.229 | 0.162 | 0.109 |
| 重算 `|det−1|`(每檔位每關鍵幀) | ≤2e-4(實測 ~1e-6) | | | |

→ >500× 分離(重算 vs 線性放大),證閘測「補償隨檔位正確重算」非「有 scale 即可」。

## 與 squash 耦合 amplify 的對比(同保守恆、機制不同源)

| | squash(G-4''''')耦合 amplify | volume-conserving twist(本次)重算 |
|---|---|---|
| scale 的角色 | 本身**即擠壓**(各向異性來源) | 純**補償** shear 的面積變化(等向) |
| 檔位放大 scale | 放大**拉長軸** overshoot、壓縮軸取**倒數**(`_amp_scale_coupled`) | 由**放大後的 shear 重算** `s'=1/√cos(shearX'−shearY')` |
| det≡1 由 | `(1+gq)·1/(1+gq)≡1` 建構保證 | `s'²·cos(Δ')≡1`,s' 由 cos 反推 |
| 走哪條路 | `COUPLED_SCALE_CATS`(coupled=True) | `twist_vol=True`(新增,與 coupled 互斥) |

## 實作(全 additive、預設逐位元向後相容)

- `tier_variants._twist_vol_scale(shx, shy)` = `1/√cos(shearX−shearY)`(與 `beat_templates._twist_scale_env`
  同一公式,那裡對 env 逐點算、此處供 amplify 後逐幀重算)。
- `tier_variants._recompute_twist_vol_scale(shear_frames, scale_frames)`:以 time 對位、對每幀由**放大後**
  shear 重算等向 s,就地覆寫 scale;捨入 `round(round(s,6),4)` 與 `gen_twist` 產 scale 完全一致 →
  **g=1 逐位元同 base-vol twist**。
- `tier_variants.amplify_bone_tl(..., twist_vol=False)` / `amplify_anim(..., twist_vol=False)`:
  shear **先**放大(v'=g·v,對 0 對稱 → 首尾 0、φ 與阻尼簽章保形),`twist_vol=True` 時 scale **改走重算**
  (不走 `_amp_scale`);與 `coupled` 互斥。新增 `VOLUME_TWIST_CATS={"twist"}`(文件用)。
- `gen_animations.build_animations(..., twist_volume=True)` + `tier_gains`:對 twist 檔位變體 `tv=twist_volume
  and cat=="twist"`;count 路徑重生成 `_build_beat(..., twist_vol=tv)`、amplify 路徑 `_amplify_anim(..., twist_vol=tv)`。
- `build_spine --twist-volume --tier-variants --shear-pivot`:三通道端到端(build_spine 早已同時傳
  `twist_volume` 與 `tier_twist_cycles`,無需改動)。

## 閘 `validate_twist_vol_tier.py`(6 AC 全 PASS,真實 robot 骨架)

- **VT1** present + 每檔位 dual-channel + 等向 + 向後相容:每 `twist__{tier}` 帶 shear 與 scale、scale 等向
  (每幀 scaleX==scaleY)、名經 `beat_category` 仍路由回 twist;**Super(g=1)逐位元 == base-vol twist**;
  base(含 In/Loop/Out + base-vol twist)帶/不帶 tier_gains 逐位元不變。
- **VT2** crux 每檔位守恆 + 負對照:每 `twist__{tier}` bone 每內部**極值幀** `|det−1| ≤ 2e-4`;**負對照**
  對 base-vol scale 施線性 `_amp_scale` + 放大後 shear → max-gain `|det−1|` 0.11–0.31(破守恆)。
- **VT3** crux 雙軸峰遞增 + φ 不變:峰 |shearX| [16,21.6,27.2,33.6]°、|shearY| [11.2,15.12,19.04,23.52]°
  皆 Super<Mega<Omg<Legend 嚴格遞增(Super==base);每 bone 每檔位 shearY峰/shearX峰 ≈ 0.7(φ 不變)。
- **VT4** 雙軸阻尼反相簽章逐檔保形:每檔位每 bone 兩軸各自(首尾 0、繞 0 變號≥3、相繼極值遞減)+ 每內部
  極值反號;scale 首尾 (1,1)。
- **VT5** 端到端三通道 pivot 不動:`--twist-volume --tier-variants --shear-pivot` pivot 殘差 <0.16px
  (TOL 0.5)vs 負對照(繞件中心)8–55px;n_with_scale ≥ 1。
- **VT6** 負對照/隔離/向後相容:(a) 平增益全 1.0 → 各 `twist__{tier}` 逐位元 == base-vol twist;(b) 等向 vs
  非均勻隔離(twist__{tier} scale 等向;squash__{tier} scale 非均勻且 scaleX·scaleY≡1 耦合);(c)
  `twist_volume=False` + tier_gains → `twist__{tier}` **無 scale 通道**(vol 對 shear-only tier 為純加性)。

## honest boundary(仍在)

- **端到端 `--shear-pivot` 密取樣後 shear/scale 各自線性內插**,而補償對 shear 非線性 → 內插**中間幀** det
  略偏(關鍵幀仍 ≡1)。這是「線性內插近似非線性約束」的**固有性質**(base vol 亦然,故
  `validate_twist_volume` TV5 也只驗 pivot 不驗端到端守恆),非 tier 機制缺陷。VT5 記錄 max 內插偏離為資訊,
  不列入 gate;守恆為**關鍵幀**性質由 VT2 把關。未來可加 bezier 曲線鍵 / 加密關鍵幀使內插收斂。
- 幅度/φ 為 PROPOSAL(手感 A 類,留使用者);單一真值資產(防固化)。`spine-anim-forge` 仍 **HOLD**。

## 一句話心法

**跨通道約束(det≡1)在每個檔位由**建構**保證,但「怎麼建構」取決於 scale 的語意角色:squash 的 scale 是
擠壓(隨檔位走耦合 amplify),twist 的 scale 是補償(隨檔位由放大後的 shear **重算**)—— 線性放大只在小角度
近似,非線性約束的檔位放大必須沿約束流形重算。**
