# S1 — volume-conserving twist 接檔位差異化（tier 放大重算等向補償維持 det≡1）

> 結論先行 / candidate **G-4''''''-vol-tier** / 里程碑 2026-09-28 / 信心:**高**（閘 6 AC + 負對照 + 23→24 閘回歸全綠）
> 相關階段:專案第 2 階段（S1 反推分析器 → 分鏡→動畫 keyframe 生成器）;運動基元庫 `spine-anim-forge`（HOLD）。

## 結論

補上 G-4''''''-vol 明白列出的最後一條 honest boundary:「**vol 僅作用 base twist**（tier 變體仍 shear-only:
vol 隨檔位放大需**重算補償 scale** 以維持 det≡1，比照 squash 耦合 amplify，為後續）」。本次讓
volume-conserving twist 的**檔位變體**（`twist__{tier}`）也維持體積守恆 —— 至此**一般仿射四自由度
（rotate / 非均勻 scale / shearX / shearY）＋ 體積守恆的檔位差異化全數在生成端成立**。

## crux 1 — 為何不能沿用既有 amplify（補償 scale 是 shear 的非線性函式）

base twist-vol 的等向補償 `s = 1/√cos(shearX − shearY)`。檔位放大時 shear 以單一 g 同比放大
（shearX' = g·shearX、shearY' = g·shearY，兩軸同比 → φ 不變，見 G-4''''''-tier），於是兩基底夾角偏離
隨 g 放大：

```
cos(shearX' − shearY') = cos(g·(shearX − shearY))     # 隨 g 非線性縮小
正確補償           s' = 1/√cos(g·(shearX − shearY))    # 非線性,不是 1+g·(s−1)
```

- 逐軸 `_amp_scale`（線性放大 identity 上方 overshoot）→ 算出 `1 + g·(s−1)` ≠ s' → **破守恆**。
- 甚至 squash 的耦合倒數 `_amp_scale_coupled`（scaleY = 1/scaleX）也算不出 s'（它從輸入 scale 推，
  不讀 shear）。

**實測負對照**（對 base vol scale 施逐軸線性放大，`shear_compensated=False`）:

| tier | g | 逐軸線性放大 max\|det−1\| | 重算補償 max\|det−1\| |
|---|---|---|---|
| Super | 1.0 | 9.0e-5 | 8.8e-5 |
| Mega | 1.35 | **0.0626** | 9.2e-5 |
| Omg | 1.70 | **0.1593** | 9.6e-5 |
| Legend | 2.10 | **0.3110** | 8.5e-5 |

> 分離 >600×（Mega）至 >3600×（Legend）→ 閘測「真體積守恆（重算補償）」非「有 scale 通道即可」。

## 解法 — shear-compensated amplify（先放大 shear，再從放大後 shear 重算補償）

`tier_variants.amplify_bone_tl(..., shear_compensated=True)`:

1. 先放大 shear 通道（`v' = g·v`，對 0 對稱 → 首尾 0 保持、φ 比值 = shearY/shearX ≡ −0.7 不變、
   阻尼反相簽章保形）。
2. 再依 time 對齊，把 scale 通道**從放大後的 shear 重算** `s = 1/√cos(shearX' − shearY')`，
   等向寫入（scaleX == scaleY）。

→ 全域 `det = s²·cos(shearX' − shearY') ≡ 1` 於**每個檔位由建構保證**。

路由:新增 `tier_variants.SHEAR_COMPENSATED_SCALE_CATS = {"twist"}`；`build_animations` 依
`cat ∈ 該集合 ∧ twist_volume` 決定走 shear-compensated 重算；count 變體重生成時帶 `twist_vol`
（段數 × 幅度 × 體積守恆三效正交）。`beat_templates.twist_vol_scale(shx, shy)` 抽為**單一真相來源**，
base（`_twist_scale_env`）與 tier 重算共用同式（tier_variants 延遲 import 避模組載入期循環）。

## crux 2 — 與 squash 耦合 amplify 的機制差異（同守恆目標，不同源）

| | squash（G-4'''''） | twist-vol（本次） |
|---|---|---|
| scale 語意角色 | **自己是擠壓**（非均勻，scaleX≠scaleY） | **補償別人**（等向，scaleX==scaleY，補 shear 造成的面積變化） |
| 守恆機制 | scale **內部**倒數 scaleY = 1/scaleX（**永不讀 shear**） | **跨通道**:scale 從放大後 shear 重算 |
| 放大 | `_amp_scale_coupled`（拉長軸放大、壓縮軸取倒數） | shear-compensated（放大 shear → 重算等向 s） |

> **scale 的「語意角色」（自己是擠壓 vs 補償別人）決定放大機制**。兩者皆維持 det≡1 但由**不同建構**保證。

## 驗收（`validate_twist_vol_tier.py`，6 AC 全 PASS）

- **VVT1 present + backward-compat**:每檔位雙軸 shear + 等向 scale；**Super(g=1) 逐位元 == base twist(vol)**；
  base 帶/不帶 tier_gains 逐位元不變；`twist_volume=False` 檔位變體逐位元 == shear-only（無 scale）。
- **VVT2 crux 體積守恆 per tier**:每檔位 |det−1| ≤ 9.6e-5（TOL 2e-4）vs 負對照逐軸線性放大 0.063/0.159/0.311。
- **VVT3 兩軸峰遞增 + φ + 等向 + 補償遞增**:shearX [16,21.6,27.2,33.6]°、shearY [11.2,15.12,19.04,23.52]°
  嚴格遞增（Super==base）；φ 逐檔≈0.7；scale 等向；**補償 scale 峰 [1.060,1.117,1.202,1.357] 隨檔位遞增**
  （擰愈狠補償愈大 = scale 通道的檔位簽章）。
- **VVT4 阻尼反相簽章保形 per tier**:兩軸各自繞 0 變號≥3 + 相繼極值遞減 + 每內部極值反相。
- **VVT5 端到端三通道 pivot 不動**:`build_spine --tier-variants --twist-volume --shear-pivot`，12 bone×tier
  帶 shear+scale+rotate 補償，pivot 殘差 < 0.33px（TOL 0.5；Legend 極強一般仿射殘差最大）vs 負對照大位移。
- **VVT6 負對照/隔離/正交**:(a) 平增益 → 兩軸遞增 FALSE 且各檔位==base；(b) 機制隔離 twist 等向 vs
  squash 非均勻 vs wobble 無 scale；(c) 段數×幅度×體積守恆三效正交（段數 [4,5,6,7] 遞增且每檔位仍守恆）。

## honest boundary（仍在）

- 幅度增益階梯（1.0/1.35/1.70/2.10）與段數階梯（4–7）為 **PROPOSAL**（結構簽章客觀、手感 A 類留使用者）。
- 單一真值資產（robot_parts）。
- `spine-anim-forge` 仍 **HOLD**（運動基元先驗、單一真值資產，防固化）。

## 關鍵發現

**跨通道守恆約束的檔位放大有兩種源**:當一個通道（scale）受另一通道（shear）約束時，放大另一通道後,
被約束通道必須沿約束**重算**（twist-vol:從 shear 重算等向補償）或沿約束流形**耦合放大**（squash:
scale 內部倒數）—— 取決於被約束通道的語意角色。單一 g 同比放大「主動」通道（shear）保住了跨軸關係（φ）,
而「被動/補償」通道則由建構（重算）保住守恆。**這是「約束由建構保證則放大天然不破」在跨通道情形的推廣**
（對照 squash count「沿守恆流形放大」、twist count「沿約束流形生成」）。
