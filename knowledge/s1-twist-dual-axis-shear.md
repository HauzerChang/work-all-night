# S1 (G-4'''''') twist 生成器產出 shearY 通道 —— 雙軸 shearX+shearY 正交扭

- **結論**:產線第一個產出 **shearY** 通道的生成器 `gen_twist`(斜扭果凍)已就緒,補齊 wobble
  (G-4',純 shearX)/ squash(G-4'''',shearX+耦合非均勻 scale)一路留到現在的**最後一條 shear
  honest boundary**(`shearY≡0`)。運動基元 = **雙軸阻尼 shear 於正交相位(quadrature)**:shearX
  與 shearY 皆阻尼擺動,但相位錯開 90° —— shearX 到極值時 shearY 恰過 0、反之亦然。幾何上斜拉方向
  隨時間**旋轉**(平行四邊形傾斜方向繞圈,像果凍被「扭」而非單向斜拉)。至此**一般仿射 M 的所有
  shear 自由度都已被生成器塞滿**(shearX by wobble/squash、shearY by twist)。
- **依據/來源**:`tools/analyzer/beat_templates.py`(`gen_twist`/`_twist_env`/`_TWIST_SHEAR`/
  `TWIST_KEYWORDS`)、`gen_animations.py`(`_DISPATCH["twist"]` + `_CAT_KEYWORDS` 註冊)、
  `tier_variants.py`(`SHEAR_CATS` 加 twist)、`genre_priors.py`(slot_bigwin 加 twist beat,
  additive)、自我驗收閘 `tools/analyzer/validate_twist_gen.py`(**6 AC 全 PASS**)。從**先驗庫**
  (slot_bigwin)→ **真實 build_spine robot 骨架** → `build_animations` 端到端量;另經
  `build_spine --animate --shear-pivot` 直出 `twist` 段(shearY peak 12° at 光暈)且 `validate_build`
  round-trip overall_pass(premult MAE 0.031)。
- **信心程度**:高(客觀結構簽章:雙軸阻尼 + 正交相位 crux + 端到端不動點 + 負對照;扭的形狀為
  PROPOSAL 屬使用者 A 類手感)。
- **相關階段**:第 2 階段(用工具鍛鍊四能力)之 S1 生成器 / shear 通道自由度補齊。

## 為什麼「雙軸」需要新生成器而非放大既有

wobble/squash 的 shear 通道皆 `{"x": sx, "y": 0.0}` —— shearY 永遠 0。`amplify_bone_tl` 事後同比
放大 `f["y"]=g*f["y"]` 對 0 仍是 0,加不出 shearY。shearY 是關鍵幀**值**(不是幅度),必須在生成器
產出當下寫入。故新增 `gen_twist` 讓 shearY 通道實際被驅動。基礎設施早就緒:
`transform_matrix_full(θ,sx,sy,shx,shy)` 的 `b=cos(θ+90+shy)·sy`、`d=sin(θ+90+shy)·sy` 本就吃
shearY,`pivot_channels_affine` / `validate_shear_pivot._world` 也都讀 `shy` —— 又一個「公式/閘就緒
≠ 生成器接上」的實例(同 G-4'→wobble 產 shearX、G-4''''→squash 產非均勻 scale)。

## 正交相位(quadrature)如何精確達成 —— 交錯事件

`_twist_env(A, B, nosc)` 在 `[WOBBLE_LEAD, WOBBLE_TAIL]` 均勻布 **2·nosc 個交錯事件**:
- **偶事件** k=2i:shearX 放極值 `(−1)ⁱ·A·rⁱ`,shearY 於**同時刻**放**顯式 0**。
- **奇事件** k=2i+1:shearY 放極值 `(−1)ⁱ·B·rⁱ`,shearX 於同時刻放顯式 0。

兩軸包絡構於**同一組時間點**(每事件各補一幀,首尾亦同),直接 zip 成單一 `shear` timeline
`{time,x,y}`。⇒ shearX 全域峰時 shearY==0(反之亦然)= 精確正交;兩軸各自繞 0 變號 `nosc−1` 次
(nosc≥4→≥3)、相繼極值幅度嚴格遞減(阻尼)、首尾 identity。r=`WOBBLE_DAMP`=0.5 共用阻尼。
`_TWIST_SHEAR` 給 (A,B) 兩軸幅度皆非零且 A≠B(扭的兩軸幅度可不同;B≈0.7A 仍明顯 > MIN_SHEAR)。

## 閘設計(6 AC,負對照證鑑別力)

- **TW1 present + 雙軸 crux**:twist beat 直出、finite、有 bone,且峰 |shearX|≥MIN_SHEAR **且**
  峰 |shearY|≥MIN_SHEAR(實測 x=16°、y=12°)—— 這是產線第一次產 shearY。
- **TW2 兩軸阻尼振盪**:shearX **與** shearY 序列各自 首尾 0 + 繞 0 變號≥3 + 相繼極值嚴格遞減。
- **TW3 正交相位(crux)**:shearX 全域峰時刻 `|shearY|/峰shearY ≤ QUAD_TOL(0.25)`、shearY 峰時
  `|shearX|/峰shearX ≤ QUAD_TOL`(實測皆 0.0)。**同相退化雙通道**(shearY==shearX)此比 =1.0 → 負對照分離。
- **TW4 identity 介面**:sample(0)/sample(dur) 各 bone identity 且兩 shear 軸首尾 0(可插 Loop 間)。
- **TW5 端到端 pivot 不動(含 shearY)**:`build_spine --shear-pivot`(真實 robot)產 twist 帶補償,
  pivot 殘差 <0.04px vs 內建負對照(未補償繞件中心含雙軸 shear)~22px(>500×,shy_peak 至 8.87°)→
  證 `transform_matrix_full` 的 shearY 項第一次被生成器產的值端到端驅動並正確補償。
- **TW6 負對照/隔離**:(a)純 shearX(shearY≡0,同 wobble)→ 雙軸 crux FALSE(證閘測真 shearY 非
  「有 shear 即可」);(b)同相 shear(shearY==shearX)→ 正交 FALSE(證閘測相位錯開非「有第二通道
  即可」);(c)shear 隔離:非 `SHEAR_CATS` beat 皆 0 bone 帶 shear;(d)加性:移除 twist storyboard →
  其餘 beat 逐位元不變(零回歸)。

## 關鍵發現

- **一般仿射 M 的所有 shear 自由度已被生成器塞滿**:2×2 local basis 的兩個角度自由度
  (`θ+shearX`、`θ+90+shearY`)分別由 shearX(wobble/squash)與 shearY(twist)驅動。
- **正交相位是「真雙軸」的簽章**:單純加第二通道(同相)不是扭,是把 shear 峰放大 √2 倍的斜拉;
  「峰時另一軸過 0」才使斜拉方向隨時間旋轉。這與之前發現「真簽章常需兩獨立條件並立」一脈相承
  (squash 體積守恆+非均勻、cascade 散佈+遞增、charge 長 hold+squash-floor)。
- twist 刻意**只產 shear、不接檔位幅度/count-aware**(不在 MAIN_SHOW_CATS/COUNT_AWARE_CATS),
  regression surface 最小、專注補 shearY 邊界。

## honest boundary(仍在)

- twist 未接檔位幅度(tier amplitude)/ count-aware(shearY 通道差異化為後續;`amplify_bone_tl`
  已能放大 `f["y"]`,接 MAIN_SHOW_CATS 即可,但需另加 AC 驗兩軸皆隨檔位遞增且正交不壞)。
- **shear+scale+rotate 三通道同時**的單一運動基元(twist 純 shear;squash shear+scale;尚無同時
  三者)為後續。
- 斜扭形狀為 PROPOSAL(結構簽章客觀、手感留使用者 A 類);單一真值資產(robot);與 anim-forge 同 HOLD。

cap `twist_dual_axis_shear` L2 併入 `spine-anim-forge`(仍 HOLD:運動基元為手感先驗、單一真值資產,防固化)。
