# S1 生成器產出 shearY 通道(斜扭果凍 twist beat,G-4'''''')

> 里程碑 2026-09-23(candidate G-4'''''')。補 wobble/squash 系列一路留到現在的**最後一條 shear
> 通道 honest boundary**:`shearY≡0`。G-4'(wobble)只擺 shearX、G-4''''(squash)擺 shearX + 耦合
> 非均勻 scale,兩者的 **shearY 皆恆 0** —— 件的 **y 軸基向量方向**從未被獨立驅動過。本次的
> `gen_twist`(斜扭果凍)是**第一個產出 shearY 的生成器**,真正塞滿一般仿射 M 的所有自由度。
> 工具:`beat_templates.gen_twist`、`build_spine --shear-pivot`、`validate_twist_gen.py`。

## 動機(接 wobble/squash 系列的最後一塊 shear 自由度)

G-4(`s1-shear-pivot-affine.md`)證明補償公式 `Δ=(M−I)(O−P)`(M=真實 Spine local 含 shearX **與**
shearY)讓件繞關節 pivot 做**一般仿射**變換而 pivot 精確不動 —— 公式**早就支援 shearY**;
`pivot_channels_affine` 也早已取樣 shear 的 x **與 y** 兩軸。但一路以來**沒有任何生成器產出 shearY**:
wobble/squash 的 shear timeline 皆 `"y": 0.0`。本 candidate 把那最後一段接上,是本專案反覆出現的
**「公式/管路就緒 ≠ 生成器接上」** 模式的又一實例(同 (E)/(H)/(I)/(J)/G-4'/G-4'''')。

## 關鍵幾何:為何 shearY 才真正補滿一般仿射 M(crux 的數學根據)

Spine 3.8 bone local 2×2 的兩個基向量:

```
col1(x 軸)方向 = rot + shearX,  長度 sx
col2(y 軸)方向 = rot + 90 + shearY,長度 sy
```

一個 2×2 矩陣恰 **4 自由度**(兩長 + 兩方向),而 `(rot, shearX, shearY)` 三參數有**一個冗餘**:
把 shearX、shearY **同加**一量,兩基向量方向一起轉 → 等同 `rotate`。故:

- **shearX == shearY(等相)⇒ M == R(rot+shearX)**:**純旋轉**,件的兩軸夾角
  `(90 + shearY − shearX)` 恆 = 90°,件不變形(退化,**非真剪切**)。
- **shearX ≠ shearY ⇒ 件角偏離 90°** ⇒ 矩形歪成平行四邊形 = **真兩軸剪切**。

⇒ wobble(只動 shearX)、squash(shearX + 兩軸長)從未動過 **col2 的方向**;唯有讓
**shearX ≠ shearY** 才獨立操控 y 軸基向量方向、真正塞滿 M 最後一個自由度。這正是本里程碑的核心洞見:
**shearY 只有在與 shearX 不同時才是真正的新自由度**。

## 運動基元:斜扭果凍 twist(反相阻尼雙軸剪切)

`gen_twist(role, side_sign, radial, nosc=4)`(`beat_templates.py`)—— shearX 同 wobble 阻尼擺動,
shearY = **−shearX**(反相)→ 件角 `90 + shearY − shearX = 90 − 2·shearX` 來回開合(菱形晃)。

```
shearX 極值(τ, r=WOBBLE_DAMP=0.5): 0 → +A(0.128)→ −rA(0.299)→ +r²A(0.469)→ −r³A(0.64)→ 0(0.8s)
shearY 極值               : 上列各值的**相反數**(反相)
role 峰 A(度):特效 14 / body 12 / limb 10 / head 8   ;side_sign 決定首推方向(左右反相)
```

- **結構簽章**(客觀、可量化,與等相 shear / shearY≡0 負對照乾淨分離):
  1. **首尾 identity**(shearX == shearY == 0)→ 可插 Loop 循環間(同其他主秀 beat)。
  2. **shearX 與 shearY 兩通道各自阻尼振盪**:各繞 0 變號 ≥3 + 相繼極值幅度嚴格遞減。
  3. **件角剪切(crux)**:每個非零極值幀 `shearX·shearY < 0`(反相)且峰件角偏差
     `|shearY − shearX|` 顯著(峰達 `2A`)→ 件角真的偏離 90°(**真兩軸剪切,非等相純旋轉**)。

Spine shear timeline 一條同時帶 x、y:`{"time", "x"(shearX), "y"(shearY)}`。

## 接進產線(additive,直出)

- `beat_templates.py`:加 `gen_twist` + `_twist_env` + `_TWIST_SHEAR` + `TWIST_KEYWORDS` + `DUR["twist"]=0.8`。
- `gen_animations.py`:註冊 `_DISPATCH["twist"]=gen_twist`、`_CAT_KEYWORDS` 置前(exact 命中優先於 pulse)。
- `genre_priors.py`:`slot_bigwin` 加 `twist` beat(PROPOSAL);Award 真值僅 In/Loop/Out →
  `validate_priors` 列 `prior_beats_unused`(誠實,覆蓋率仍 1.0)。
- `tier_variants.py`:`twist` 併入 `SHEAR_CATS`(**第三個 shear 產出者**),使 shear-isolation 閘
  (shear_gen W5b / wobble_tier T4)認它為合法 shear 產出者、不誤報外洩。**未併入 `MAIN_SHOW_CATS`**
  (honest boundary:tier 幅度/count-aware 為後續)。
- `build_spine.py`:`--shear-pivot`(既有)已 `apply_pivots(include_shear=True)`,`pivot_channels_affine`
  早已取樣 shear x/y → twist 的 shearY **自動被端到端補償**,無需改 build。

`build_spine --animate --shear-pivot`(非 rig)即**直出**:twist beat 產 shearX+shearY,件繞關節 pivot
做含 shearY 的一般仿射。

## 驗收 `validate_twist_gen.py`(先驗庫→真實 build_spine robot 骨架→build_animations,6 AC 全 PASS)

| AC | 內容 | 實測 |
|---|---|---|
| T1 | **present + shearY 產出(crux)** twist 直出/finite/有 bone,≥1 bone 峰 \|shearX\| **與** \|shearY\| 皆 ≥5° | 峰 shx=shy=**14°**(產線第一次產 shearY) |
| T2 | **件角剪切(crux)** 每非零極值反相(shearX·shearY<0)+ 峰件角偏差 ≥5° + 峰幀 M anisotropy ≥0.10(真非相似) | 峰件角偏差 28°、峰 aniso 0.42 |
| T3 | **雙軸阻尼振盪** shearX **與** shearY 各自:首尾 0、變號 ≥3、相繼極值遞減 | 兩通道皆變號 4、極值遞減 |
| T4 | **identity 介面** sample(0)/sample(dur) 各 bone identity + shear 首尾 x==y==0 | PASS(可插 Loop 間) |
| T5 | **端到端 pivot 不動** `--shear-pivot` 有關節 bone pivot 殘差 < 0.5px | 右手 0.015 / 頭 0.003 / 左手 0.011px(arm 50–164px;負對照 6.5–25px,>20×) |
| T6 | **負對照/隔離(crux)** (a)等相 shear=純旋轉 aniso 0.0(M==R)vs 反相 0.42→件角簽章 FALSE;(b)shearY 隔離 僅 twist 帶 shearY≠0;(c)加性 移除 twist 其餘逐位元不變 | 全 PASS |

**T6(a) 是本里程碑的鑑別核心**:等相 shear(shearX==shearY=φ)的 Spine local M **逐位元 == R(φ)**
(數學上 col1=(cos φ,sin φ)、col2=(−sin φ,cos φ))→ anisotropy 精確 0(純旋轉,件角不變);
反相(twist)aniso 0.42 → 鑑別餘裕 ∞(等相 aniso=0)。這證明閘測的是**獨立 y 軸歪斜 / 件角改變**,
**而非「shearY 有非零值即可」**—— 否則等相 shear(shearY≠0 卻只是旋轉)會假陽性通過。

**T5 端到端**:含 shearY 的一般仿射**第一次由生成器**驅動 `Δ=(M−I)(O−P)` 補償路徑(先前 G-4 AC7
只用合成 shear、wobble/squash 的 shearY 恆 0)。殘差 <0.02px vs 負對照 6.5–25px,arm 達 164px。

## 關鍵發現 / 踩雷

1. **shearY 的「真正新自由度」條件**:矩陣僅透過兩基向量方向 `rot+shearX` / `rot+90+shearY` 依賴
   shear;把兩者同加 = rotate(冗餘)。故單看「shearY 是否非零」會被等相 shear(=純旋轉)騙過 —— 閘必須
   驗**件角改變 / anisotropy**(shearX≠shearY)才抓得住真剪切。這是「真簽章需比對兩參數的**差**、非各自值」
   的又一例(同 squash 的「體積守恆 且 非均勻」兩條件並立)。
2. **阻尼小尾極值的門檻拿捏**:T2 初版要求**每個**極值件角偏差 ≥5° → 阻尼末極值(±1.5°→偏差 3°)假陰性。
   修正:**反相符號**在每個非零極值都查(符號對阻尼不變),件角**幅度**只要求**峰極值**達門檻(遞減簽章
   由 T3 各通道保障)。判準要分清「對阻尼不變的性質(符號)」與「隨阻尼遞減的量(幅度)」。
3. **公式/管路早支援 ≠ 已兌現**:`transform_matrix_full`/`pivot_channels_affine`/`amplify_bone_tl` 早已
   處理 shear 的 x **和 y**;缺的只是生成器產 shearY。接上後 build/pivot/amplify **零改動**即端到端運作。
4. **加性 opt-in**:twist 加進先驗庫不擾其他 beat(build_animations 逐 beat 獨立);wobble/squash/既有
   pivot 路徑逐位元不變(T6c)。

## honest boundary(仍在)

- twist 形狀(阻尼比 0.5、反相、role 峰值)是 **PROPOSAL**(件角剪切結構簽章客觀,手感留使用者 A 類)。
- twist **未接 tier 幅度 / count-aware**(未併 `MAIN_SHOW_CATS`);`amplify_bone_tl` 對 shear x/y 已
  `v'=g*v`,故併入即可用(shearY 峰隨檔位遞增),為後續(比照 G-4''/G-4''')。
- **shear + scale + rotate 三通道同時**、以及 **shearY 下的體積守恆擠壓**(twist 目前 det=cos 2·shearX
  <1,非守恆)為後續(真正「塞滿 M 全部自由度 + 跨通道約束」)。
- 單一真值資產(robot);`spine-anim-forge` 仍 **HOLD**(運動基元先驗、未達 L3 端到端真值,防固化)。

## 回歸(全綠)

`shear_gen`(W5b SHEAR_CATS 含 twist)、`wobble_tier`(T4)、`squash_gen`/`squash_tier`/`squash_count`、
`wobble_count`、`tier_combo_count`、`tier_variants`、`priors`(cov 1.0)、`priors_beats`/`priors_combo_charge`/
`priors_cascade`、`cascade`、`more_beats`、`beat_templates`、`deform_gen`、`pivot_rotation`/`scale_pivot`/
`shear_pivot` + 新 `twist_gen` **共 20 閘全綠**;round-trip `validate_build` 對 `--animate --tier-variants
--shear-pivot`(含 twist)build overall_pass。
(註:`validate_analyzer_award` 的 `4_storyboard_structure` 因主秀 beat ≠ Award 的 In/Loop/Out 而
`beats_match=false` —— 此為**加主秀 beat 以來的既有狀態**,非本次回歸,已於 clean baseline 確認。)

## cap / skill

新增 cap `twist_sheary_generation` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
