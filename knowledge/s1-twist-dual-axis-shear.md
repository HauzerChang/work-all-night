# S1 生成器產雙軸 shear(shearX+shearY 旋擰):塞滿一般仿射 M 的最後一條自由度(G-4'''''')

> 里程碑 2026-09-22(candidate G-4'''''')。補上 wobble/squash 系列一路留到現在的**最後一條 shear 通道
> honest boundary —— `shearY≡0`**。生成器 `beat_templates.gen_twist`(旋擰果凍晃)是**第一個同時產出
> shearX **且** shearY** 的節拍;`build_spine --shear-pivot` 端到端把此**真正的一般仿射**繞關節 pivot 補償。
> 工具:`tools/analyzer/beat_templates.py`(擴充)、`gen_animations.py`/`tier_variants.py`/`genre_priors.py`
> (路由)、`validate_twist_gen.py`(新閘,7AC)。

## 動機:為何 shearY 是「最後一條自由度」

真實 Spine 3.8 bone local(`transform_matrix_full`,TransformMode.Normal):
```
a = cos(θ+shearX)·sx    b = cos(θ+90+shearY)·sy      M = [[a,b],[c,d]]
c = sin(θ+shearX)·sx    d = sin(θ+90+shearY)·sy
```
- **shearX 只擾第一欄 (a,c) 的角**;**shearY 只擾第二欄 (b,d) 的角** —— 兩者**獨立**。
- 只產 shearX(wobble)時,第二欄恆為 `(cos(θ+90)·sy, sin(θ+90)·sy)`,與第一欄**近正交**(sx=sy 時嚴格
  正交)→ M 殘留相似/近相似結構;非均勻 scale(squash)雖破壞欄長相等,兩欄仍正交。
- **只有 shearX 與 shearY 同時非零**,兩欄的角才各自獨立、欄間不再正交 → M 是**真正的一般 2×2**
  (四自由度全填)。故 shearY 是 G-4 通用一般仿射公式一路以來、生成器側最後沒接上的那一維。

G-4(`validate_shear_pivot.py`)早已用**合成** shy 驗過管路(`transform_matrix_full`/`_sample_shear`/
`pivot_channels_affine` 全讀 shy),但此前**沒有任何生成器餵它**。本 candidate 把生成器接上。

## 運動基元:旋擰(rotary)阻尼 shear + 旋轉體積守恆 squash

`gen_twist(role, side_sign, radial, nturn=8)`:
- **旋擰 shear**:shear 向量 (shearX, shearY) 以四分之一週期為步在相位上前進。第 k 步
  (τ 於 [WOBBLE_LEAD,WOBBLE_TAIL] 均勻、阻尼 `decay=r^(k/2)`,r=WOBBLE_DAMP=0.5):
  ```
  shearX = Ax·decay·cos(k·90°)   shearY = Ay·decay·sin(k·90°)
  ```
  cos/sin 在 90° 倍數為精確 {1,0,−1,0}/{0,1,0,−1}(整數查表,免浮點塵埃)⇒ 偶步 shearX 為峰、shearY=0;
  奇步 shearY 為峰、shearX=0 → shear 向量方向**每步轉 90°(旋擰)**、**正交**(一軸峰時另一軸≈0)。
  nturn=8 → shearX 5 極值(k=0,2,4,6,8)、shearY 4 極值(k=1,3,5,7),兩軸繞 0 變號皆 ≥3、相繼極值 ×r 遞減。
- **旋轉 squash**(掛 scale,體積守恆):每步 `q=Q·decay`;偶步(shearX 主導)拉 X `(1+q, 1/(1+q))`、
  奇步(shearY 主導)拉 Y `(1/(1+q), 1+q)` ⇒ `scaleX·scaleY≡1`(面積守恆)、`scaleX≠scaleY`(非均勻)、
  **拉長軸在 X/Y 間交替(旋轉)** → 與固定軸 squash(恆拉 X)分離。
- **limb 另加伴隨阻尼 rotate**(對齊 shearX 偶步極值)→ 該 bone 同時帶 **rotate+scale+shear** 三通道
  (演示 M=R·shear·S 完整補償;其餘 role 無 rotate 亦已由**雙軸 shear + 非均勻 scale** 填滿 M 四自由度)。
- 首尾 identity(shearX=shearY=0、scaleX=scaleY=1)→ 可插 Loop 間(同其他主秀 beat)。

實測(robot,effect role Ax=16):shearX `[0,16,0,−8,0,4,0,−2,0,1,0]`、
shearY `[0,0,11.31,0,−5.66,0,2.83,0,−1.41,0,0]`(峰在 shearX 過零處)、scaleX·scaleY 殘差 <1e-4。

## 驗收 `validate_twist_gen.py`(先驗庫→真實 build_spine robot→build_animations,7AC 全 PASS)

| AC | 內容 | 實測 |
|---|---|---|
| TW1 | present + **雙軸 shear**(crux):≥1 bone 同時帶非零 shearX **且** shearY + scale | 峰 shearX 16°·shearY 11.3°·aniso 0.30 |
| TW2 | shearX **與** shearY **各自** 阻尼振盪(首尾0·變號≥3·極值遞減) | 兩軸皆 PASS(復用 G-4' 判準) |
| TW3 | **旋擰/正交**(crux):存在 shearY 主導幀(\|shy\|≥5 而\|shx\|<1)且 shearX 主導幀 | 5/5 bone 皆有兩類幀 |
| TW4 | **旋轉**體積守恆 squash:每極值積≈1+非均勻+拉長軸 X/Y 交替 | PASS(sign 序列含 +1 與 −1) |
| TW5 | identity 介面(首尾幀 + shear (0,0) + scale (1,1)) | PASS |
| TW6 | 端到端一般仿射 pivot 不動 + M 真一般仿射 | 殘差 ≤0.18px vs 負對照 37–52px;anisoM 0.18–0.22、shyPk 7–8.4° |
| TW7 | 負對照/隔離(shearY≡0→非雙軸非旋擰·對角 shear→旋擰FALSE·固定軸 squash→旋轉FALSE·隔離·加性) | 全 PASS |

**TW3 是本閘 crux**:對角(共線)shear `shearY=c·shearX` 兩軸**同時過零** → 沒有「一軸大、另一軸≈0」的錯位幀
→ 旋擰 FALSE。旋擰 shear 因兩軸正交(相位差 90°),必有 shearY 主導幀與 shearX 主導幀 → 證測的是**向量方向
確實旋轉**,不是「有兩個 shear 值」就算。

## 關鍵發現 / 踩雷

1. **shearY 是一般仿射的最後一維,不是「多一個 shear」**:shearX/shearY 各自只擾 M 的一欄;兩者同時非零才讓
   欄間不再正交 → M 真正一般。TW6 以 M 的 **anisotropy(奇異值差)>0 且 shy≠0** 鎖定「真一般仿射」,非只看有值。
2. **旋擰 = 相位正交**:用整數查表產 cos/sin(90° 倍數),shear 向量每步轉 90°,天然得到「一軸峰時另一軸=0」的
   正交簽章;這是與對角(共線)shear 的乾淨鑑別點。
3. **管路早備,只差生成器**(再現「公式/閘就緒 ≠ 生成器接上」):`transform_matrix_full`/`_sample_shear`/
   `apply_pivots(include_shear=True)` 一路讀 shy;接上生成器後 `--shear-pivot` 端到端無需改補償碼。
4. **回歸踩雷(耦合隔離的類別化)**:squash 的 SQ6(c) 曾斷言「squash 獨佔 shear+非均勻 scale」,twist 加入後
   成為第二個合法耦合產出者 → 誤判 leak。修法:SQ6(c) 改以 `COUPLED_SCALE_CATS` 集合排除(同 (G-4''''') K5c
   改以 `SHEAR_CATS` 排除 combo impact 誤判)。**類別專屬隔離指標,凡新增同類產出者就該用類別集合而非硬編碼單名。**
5. **一般仿射 M 六自由度首次由生成器全填**:rotate(limb)+ sx + sy(非均勻)+ shearX + shearY,translate 為
   pivot 補償產物 —— 至此 Spine bone local 的所有運動自由度都有生成器實際驅動並經端到端 pivot 閘。

## 回歸(全綠)

20 閘全綠:19 既有(squash_count/squash_tier/squash_gen/wobble_count/wobble_tier/tier_combo_count/
tier_variants/shear_gen/shear_pivot/scale_pivot/pivot_rotation/cascade/priors/priors_beats/
priors_combo_charge/priors_cascade/more_beats/beat_templates/deform_gen)+ 新 twist_gen;
round-trip `validate_build` 對 `--tier-variants --shear-pivot` build overall_pass(premult MAE 0.031、0 孤兒)。

## cap / skill

新增 cap `dual_axis_shear_generation` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。

## honest boundary(仍在)

- 雙軸 shear 幅度階梯與旋擰形狀皆為 PROPOSAL(結構簽章客觀、手感留使用者 A 類)。
- twist 未接 count-aware(旋擰步數隨檔位遞增;`gen_twist(nturn=)` 已備參數未接,比照 G-4'''/G-4'''''-c)。
- 單一真值資產(robot_parts);anim-forge 仍 HOLD;S5→L3 仍待多 rig 真值(C/資源類,使用者提供)。
