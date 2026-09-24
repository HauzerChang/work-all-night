# S1 · 體積守恆扭轉(volume-conserving twist,candidate G-4''''''-vol)

> 里程碑日期:2026-09-24(run 002)。分支 `claude/focused-dirac-st57q9`(主研究線,較 `claude/spine-main` 領先)。
> cap `twist_volume_conserving` L2 → `spine-anim-forge`(仍 HOLD)。閘 `tools/analyzer/validate_twist_vol.py` 6AC 全 PASS。

## 一句話

補齊 twist(G-4'''''')留下的最後一條 honest boundary:twist 產反相雙軸 shear 但**擰轉會變面積**;
本次讓生成器在每個 shear 極值施耦合 **uniform** scale `s=1/√cos(shearX−shearY)`,使真實 Spine local
**行列式 det(M)≡1(真面積守恆)**,且 `scaleX==scaleY`(uniform)—— 塞滿一般仿射四自由度(旋轉/非均勻
scale/雙軸 shear/等積約束)全被真實 beat 驅動。

## 幾何(為什麼 twist 會變面積、怎麼補)

真實 Spine 3.8 bone local 2×2(`pivot_rotation.transform_matrix_full`):

```
a=cos(rot+shearX)·sx  b=cos(rot+90+shearY)·sy=−sin(rot+shearY)·sy
c=sin(rot+shearX)·sx  d=sin(rot+90+shearY)·sy= cos(rot+shearY)·sy
det(M)=a·d−b·c = sx·sy·[cos(rot+shX)cos(rot+shY)+sin(rot+shY)sin(rot+shX)]
              = sx·sy·cos(shearX − shearY)          ← rot 不影響 det(相似不變量)
```

- twist(G-4''''''):`sx≡sy≡1`、反相 `shearY=−φ·shearX`(φ=`TWIST_PHI`=0.7)→ `shearX−shearY=(1+φ)shearX≠0`
  → **det=cos((1+φ)shearX) < 1**(擰愈狠面積縮愈多,一般仿射非等積)。這是 twist 一路留著的 honest boundary。
- twistvol(本次):每個 shear 極值施 **uniform** scale `s`,要 `s²·cos(shearX−shearY)=1`
  ⟺ **`s = 1/√cos(shearX−shearY)`** → **det≡1**(真面積守恆),且 `scaleX==scaleY`。s≥1(補償 shear 的縮面)。

## crux:與 squash 的「體積守恆」正交(兩種守恆、兩種 scale 結構)

| | shear 軸 | scale 結構 | 守的量 | shear 在時 det |
|---|---|---|---|---|
| **squash**(G-4'''') | 單軸 shearX | **非均勻** `sx=1+q, sy=1/(1+q)`(`sx·sy=1`) | **scale 積**(動畫 squash&stretch 原理) | `1·cos(shearX)≠1`(**非**真面積守恆)|
| **twistvol**(本次) | 反相雙軸 shearX/shearY | **uniform** `sx=sy=1/√cos(shearX−shearY)` | **真 det**(幾何面積) | `s²·cos(shearX−shearY)≡1`(真面積守恆)|

→ squash 的「體積守恆」其實是 **scale-積守恆**(shear 存在時真面積仍變);twistvol 守的是**真幾何面積**。
兩者用不同 scale 結構(非均勻 vs uniform),是**正交**的兩種守恆。這是 TV5 兩個內建負對照的核心洞見:
無 scale(`s≡1`)與 squash 式 `sx·sy=1` 都給 det=cos(shearX−shearY)≠1(max|det−1|≈0.11),證真面積守恆
**須** `s²=1/cos`、且 twistvol 用 uniform scale。

## 實作

- `beat_templates.gen_twist_vol(role, side_sign, radial, nosc=4)` + `_twist_vol_env`:shear 同 `gen_twist`
  (反相雙軸阻尼),scale 每 shear 極值 `scaleX=scaleY=1/√cos((1+φ)|shearX_i|)`,首尾 identity。
- `gen_animations`:`_DISPATCH["twistvol"]`;`_CAT_KEYWORDS` 置最前(單一 token `twistvol` 精確命中)。
- `tier_variants`:`twistvol` 併入 `SHEAR_CATS`(第四個 shear 產出者);新增
  **`DUAL_AXIS_CATS={twist,twistvol}`**(shearY 產出者集中認定,供 shearY-isolation 閘)。
- `genre_priors.slot_bigwin`:加 `twistvol` beat(additive;Award 真值僅 In/Loop/Out → prior_beats_unused,覆蓋率仍 1.0)。
- `build_spine --shear-pivot`(include_shear 隱含 include_scale)自動端到端補償(twistvol 產 shear+scale,走既有
  `pivot_channels_affine` 路徑,**無須改 build_spine**)。

## 閘 `validate_twist_vol.py`(6 AC,從先驗庫 → 真實 build_spine robot 骨架 → build_animations)

- **TV1** present + dual-axis + uniform 補償 scale(crux):twistvol 直出、finite;≥1 bone 同時帶 shear
  (shearX 峰 16°·shearY 峰 11.2°)與 scale(峰 1.06);**每幀 scaleX==scaleY(uniform)**。
- **TV2** 兩軸各自阻尼振盪(首尾 0、繞 0 變號≥3、相繼極值遞減)—— 復用 G-4'/twist 判準。
- **TV3** 反相雙軸耦合:每內部極值 shearX·shearY<0 且夾角偏離≥8° —— 復用 twist `_tw3_eval`。
- **TV4** identity 介面:shear 首尾(0,0)、scale 首尾(1,1)、sample(0/dur) identity。
- **TV5** 真面積守恆(crux):每 bone 每內部極值 |det(M)−1|≤2e-3(實測 ≤1e-4);內建負對照 無 scale/squash
  式 `sx·sy=1` 皆 max|det−1|≈0.11(≥門檻 0.02,>5× 餘裕)。
- **TV6** 端到端 + 隔離:`--shear-pivot` pivot 殘差 <0.016px vs 負對照(繞件中心)8–29px(>1000×);
  uniform vs squash 非均勻;shearY 隔離到 DUAL_AXIS_CATS;移除 twistvol 其餘 beat 逐位元不變(零回歸)。

## 回歸

23 閘全綠(22 既有 + 新 `twist_volume_conserving`)。唯一回歸踩雷:`validate_twist_gen` TW6c 的 shearY-isolation
原硬編碼「非 twist beat 皆 shearY≡0」,twistvol 亦合法產 shearY → 改以 `tier_variants.DUAL_AXIS_CATS` 認定
(集中一處,避免每加一個雙軸節拍就改硬編碼)。`check_readiness.py` 退出 0,0 RED,無 GREEN→RED。

## honest boundary(仍在)

- **twistvol 未接 tier 幅度 / count-aware**:tier 放大 shear(×g)後,`shearX−shearY` 變大 → 基於 base 幅度算的
  `s=1/√cos` 補償**不再守恆**,須隨幅度**重算耦合 scale**(比照 squash G-4''''→G-4''''' 的耦合 amplify)。為後續。
- **`s²=1/cos` 補償為幾何客觀**(非美感);扭轉手感(擰多快、φ 值)仍 PROPOSAL(A 類,留使用者)。
- 單一真值資產(robot_parts);與 `spine-anim-forge` 同 HOLD(運動基元為先驗手感,防固化)。

## 一般仿射四自由度總結(這條 G-4→G-4''''''-vol 線的收束)

真實 Spine local M 的 4 自由度全被**真實 beat** 驅動且可守恆:
旋轉(0i/G-4 pivot)· 非均勻 scale(squash)· shearX(wobble)· shearY(twist,反相雙軸)· **等積約束(twistvol,det≡1)**。
公式/閘(G-4)早通用,這條線逐一把「公式就緒 ≠ 生成器接上」的每條通道與約束接齊。
