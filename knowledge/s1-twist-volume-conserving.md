# S1 — 體積守恆反相雙軸 shear:完整矩陣 det≡1(candidate G-4''''''-vol,`twist_volume_conserving` L2)

> 2026-09-26。續 twist 系列(G-4''''''／-tier／-count):補上這一路一直明列的 honest boundary ——
> 「反相雙軸未接體積守恆耦合 scale(`det=cos(shearY−shearX)≠1` → 擰轉變面積,volume-conserving twist 為後續)」。
> `gen_twist_vol` 讓扭轉「擰而不變面積」(像擰乾毛巾):第一個守**完整 Spine local 矩陣行列式** det(M)≡1 的生成器。

## 缺口(honest boundary 的接續)

- **twist(G-4'''''')** 首度驅動 shearY(反相雙軸 shear),但誠實標記:反相雙軸 shear 會**改變面積**。
- **(-tier)/(-count)** 把 twist 的幅度／段數接上檔位差異化,但兩者都仍**不守面積** —— honest boundary 一直是
  「volume-conserving twist 為後續」。本次正好照那條邊界接上。

## 關鍵幾何:完整矩陣行列式 det(M) = sx·sy·cos(shearY − shearX)

真實 Spine 3.8 bone local 2×2(`pivot_rotation.transform_matrix_full`):

```
a = cos(rot + shearX)·sx    b = cos(rot + 90 + shearY)·sy
c = sin(rot + shearX)·sx    d = sin(rot + 90 + shearY)·sy
```

行列式(推導,與 rot 無關):

```
det(M) = a·d − b·c
       = sx·sy·[cos(rot+shx)·sin(rot+90+shy) − cos(rot+90+shy)·sin(rot+shx)]
       = sx·sy·sin((rot+90+shy) − (rot+shx))
       = sx·sy·sin(90 + shy − shx)
       = sx·sy·cos(shearY − shearX)
```

- **純 twist**(sx=sy=1、shearY=−φ·shearX,φ=`TWIST_PHI`=0.7)⇒
  `det = cos((1+φ)·shearX) < 1` → **擰轉時件面積縮小**(峰處 head 0.044、body 0.085、特效 0.111)。
- **twist_vol**:加耦合**均勻** scale `s`,令 `det = s²·cos(shearY − shearX) ≡ 1`
  ⟺ **`s = 1/√(cos(shearY − shearX))`**。首尾 shear=0 → cos(0)=1 → s=1(identity 介面保持)。

於是 rotate/scale/shearX/shearY **四通道**同時被生成器驅動、且面積在每個關鍵幀嚴格守恆 ——
**塞滿一般仿射四自由度且體積守恆**(擰而不變面積)。

## crux:守 scale 子塊 vs 守完整矩陣(與 squash 正交對立)

| 節拍 | scale | scaleX·scaleY | 完整 det(M) | 守的是 |
|---|---|---|---|---|
| squash(G-4'''') | 非均勻(1+q, 1/(1+q)) | **≡1** | cos(shearX) **≠1** | scale **子塊**面積 |
| twist_vol(本次) | **均勻**(s, s),s>1 | **s²>1** | **≡1** | **完整** Spine local 矩陣 |

- squash 的「體積守恆」只是 scale 兩軸乘積 ≡1;但它的 shearX≠0 使完整矩陣 det=cos(shearX)<1 ——
  **squash 不守完整矩陣**(它守的是 scale 子塊,shear 的面積效應沒補)。
- twist_vol 反過來:scaleX·scaleY=s²>1(**故意**脹一點),恰好補掉雙軸 shear 造成的 cos<1 面積損失,
  使**完整 det≡1**。
- 這是 twist_vol 與 squash 乾淨分離的鑑別點:同樣一組 twist shear,
  - 用 squash-式 scale(sx·sy≡1,非均勻)→ 完整 det=cos(shy−shx)≠1(守子塊 ≠ 守完整矩陣);
  - 用 twist_vol scale(sx=sy=1/√cos)→ 完整 det≡1。
  → 負對照 (c) 直接對照這兩者(見下)。

## 均勻 scale 是設計選擇

要 det≡1 只需 `sx·sy = 1/cos(shearY−shearX)`;把它平均分給兩軸(sx=sy=s=1/√cos)是**各向同性「呼吸」
修正**,不在雙軸 shear 之上再疊額外非均勻扭曲(擰的形狀由 shear 決定,scale 只還原面積)。亦可選非均勻
(只要 sx·sy=1/cos),屬 honest boundary(手感 A 類)。

## 實作

- `beat_templates.gen_twist_vol` + `_twist_vol_env`:shear 同 `gen_twist`(反相雙軸阻尼,首尾 0);
  scale 每個 shear 極值 τ(與 shear 同點)施 `s=1/√cos(shy−shx)`,首尾 s=1。
- `gen_animations`:`_DISPATCH["twist_vol"]` + `_CAT_KEYWORDS`(twist_vol **置於 twist 前**;exact
  `"twist_vol"` 精確路由,keyword 皆明確前綴不含裸 `"twist"` → `"twist"` 仍精確路由回 twist)。
- `genre_priors.slot_bigwin`:加 twist_vol beat(additive、coverage 仍 1.0;Award 真值僅 In/Loop/Out →
  列 prior_beats_unused,誠實 PROPOSAL)。
- `tier_variants.SHEAR_CATS += {twist_vol}`(shear-isolation 閘認定合法 shear 產出者);
  **刻意不在** `MAIN_SHOW_CATS`(見 honest boundary)。
- `validate_twist_gen.py` TW6c:shearY 隔離由「只 twist」改認 `{twist, twist_vol}`。
- `build_spine --shear-pivot`:apply_pivots(include_shear=True)把 twist_vol 的 scale+雙軸 shear 一起
  繞關節 pivot 補償(bone 無 rotate 通道,pivot_channels_affine 以 ang=0 處理)。

## 自我驗收:`validate_twist_vol.py` 6 AC 全 PASS

從**先驗庫**經 `analyze_target` → **真實 build_spine robot 骨架** → `build_animations` 端到端量。

- **VT1** present + dual-axis + scale(crux setup):twist_vol 直出、finite、有 bone,≥1 bone 同時帶
  shear(shearX 峰 16°、shearY 峰 11.2°)**與** scale(峰 |s−1|=0.060)—— 與純 twist(無 scale 通道)分離。
- **VT2** 兩軸各自阻尼振盪(繞 0 變號 ≥3 + 相繼極值遞減)。
- **VT3** crux 反相雙軸耦合:每內部極值 shearX·shearY<0、夾角偏離 ≥8°(復用 twist `_tw3_eval`)。
- **VT4** crux **完整矩陣體積守恆**:每個內部 shear 極值幀
  (a)`|det − 1| ≤ 8.8e-5`(≤TOL_DET 2e-3);(b)scale **均勻**(sx=sy,gap=0);
  (c)scale 確實修正:scaleX·scaleY 峰 **1.045–1.124 > 1**(與 squash 的 ≡1 分離)、
  純-twist det 在峰處縮小 **0.044–0.111 ≥ SHRINK_MIN(0.02)**(證 scale 在做真實功)。
- **VT5** identity 介面(shear 首尾 (0,0)、scale 首尾 (1,1))+ 端到端 `--shear-pivot` pivot 殘差
  **0.004–0.016px**(在 scale+雙軸 shear 同時驅動下)vs 未補償(繞件中心)**8.5–29.5px**(>1000×)。
- **VT6** 負對照/隔離:
  (a)純-twist(scale≡1)→ 守恆 FALSE(det_min 0.915);
  (b)定值 scale(常數 1.05,非 1/√cos)→ FALSE(det_max_err 0.101);
  (c)**squash-式**(sx·sy≡1 非均勻)→ 完整 det FALSE(det_min 0.915)且非均勻、prod≈1
     —— 證「守 scale 子塊 ≠ 守完整矩陣」;
  (d)正控 s=1/√cos → 守恆 TRUE 且均勻、prod>1;
  (e)shearY 隔離到 {twist, twist_vol}(其餘 beat shearY≡0);
  (f)加性:移除 twist_vol storyboard → 其餘 beat 逐位元不變(零回歸)。

端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 `twist_vol` 單支(**無** `twist_vol__tier`
變體,honest boundary),`twist` 及其 `__{tier}` 變體逐位元不變(向後相容)。
**回歸 23 閘全綠**(22 既有 + 新 twist_vol;`check_readiness.py` 退出 0,無 GREEN→RED)。
新增 cap `twist_volume_conserving` L2 併入 `spine-anim-forge`(**仍 HOLD**)。

## 關鍵發現

- **面積守恆有「守誰」之分**:scale 子塊(squash,sx·sy≡1)vs 完整 Spine local 矩陣(twist_vol,
  det=sx·sy·cos(shy−shx)≡1)。shear 有面積效應(cos<1),要守完整矩陣就必須把它算進去 ——
  這是產線第一次把 shear 的面積損失也納入守恆。
- **至此 Spine local 一般仿射四自由度全被真實 beat 驅動、且面積可依需求守恆**:
  rotate(0i/G-4)、非均勻 scale(squash)、均勻 scale(twist_vol)、shearX(wobble)、shearY(twist);
  面積:squash 守子塊、twist_vol 守完整矩陣。
- 守恆由**建構保證**(s=1/√cos 直接令 det≡1),與 squash 的「壓縮軸=倒數」同精神(沿守恆流形生成)。

## honest boundary(仍在)

- **twist_vol 未接 tier / count-aware**:tier 幅度增益放大 shear 會改 shearX/shearY 峰,使守恆所需
  `s=1/√cos(shearY−shearX)` 需**重算**(現有 amplify 對 shear/scale 各自 `v'=g*v` 會破 det≡1)——
  檔位差異化須走 count-aware 式**重生成**而非 amplify(後續)。
- **均勻 scale 分配為設計選擇**(亦可非均勻,只要 sx·sy=1/cos;手感 A 類)。
- **守恆僅在關鍵幀嚴格、幀間線性**(同 squash;shear 與 scale 各自線性內插,幀間 det 近似 1)。
- 幅度/φ 為 PROPOSAL(結構簽章客觀、手感留使用者 A 類);單一真值資產(robot_parts)。

見 `tools/analyzer/beat_templates.py`(`gen_twist_vol`)、`tools/analyzer/validate_twist_vol.py`。
