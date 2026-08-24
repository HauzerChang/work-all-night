# S3 — weighted mesh 骨骼驅動變形:FK 評估器 + 生成器對照(補上唯一未驗維度)

- **結論**:補上 `s3-robot-mesh-vs-award.md` 標記的唯一未驗維度 ——「weighted mesh 骨骼變形平滑度」。
  新建 **Spine 3.8 骨架 FK + weighted 蒙皮 + 可見性 gating 的變形評估器**,以美術真值校準可信,
  再對**我方生成的 weighted mesh**(拓樸 + 內部密度控制 + BBW 代理權重)在**真實動畫骨骼 pose**
  下量化 → 機器人 3 件(左手/身體/光暈)**變形拓樸全乾淨(AC-W1 全 PASS)**。
- **信心**:高(評估器經生產美術 mesh 校準 `_checker_validated=True` + 負對照抓到 3702 自交,有鑑別力)。
- **階段**:第 2 階段 / S3(里程碑:weighted mesh 變形品質首次可機讀驗收)。
- **工具**:`spine_skeleton.py`(FK+蒙皮)、`weighted_deform_eval.py`(評估器)、
  `generate_weighted_mesh.py`(生成器)、`validate_weighted_gen.py`(整合 AC 閘)。

## 標準指令

```
python3 tools/mesh_gen/weighted_deform_eval.py artist   # 美術校準:_checker_validated=True
python3 tools/mesh_gen/weighted_deform_eval.py neg      # 負對照:detected_breakage=True
python3 tools/mesh_gen/validate_weighted_gen.py         # 生成件對照:_all_pass=True → exit 0
```

## 量化結果

美術校準(可見幀,Award_Legend_In + _Loop):3 件全 `all_clean`,`_worst_across_all` 全 0 → **checker_validated**。
負對照(身體 1/3 頂點權重換遠端骨 4_LEG9):self_intersections **3702** → 有鑑別力。

生成件對照(`validate_weighted_gen`,`_all_pass=True`):

| 件 | 美術 nv | 生成 nv | 驅動骨(真值) | AC-W1 乾淨 | 生成 CV | 美術 CV |
|---|---|---|---|---|---|---|
| 左手 | 80 | 106 | 4_LEG5,9 | ✅ 0/0/0 | 0.48 | 0.87 |
| 身體 | 98 | 194 | 4_LEG3,7,8 | ✅ 0/0/0 | 0.34 | 0.92 |
| 光暈 | 78 | 252 | 4_LEG3,4,5,6 | ✅ 0/0/0 | 0.51 | 1.78 |

內部密度槓桿(身體,spacing↓ ⇒ nv↑ ⇒ 三角面積更均勻,全程乾淨):
`spacing 40→32→26 ⇒ nv 107→137→175 ⇒ CV 0.557→0.486→0.368`。

## 三個關鍵發現

### 1.【校正 STATE 舊假設】這 3 件**有**骨骼變形動畫
`s3-robot-mesh-vs-award.md` 曾記「目前資產未含這 3 件的變形動畫」→ **不正確**。
驅動骨 `4_LEG3..9` 在 **`Award_Legend_In` 與 `Award_Legend_Loop`** 都有 rotate/translate/scale keyframe
(其餘 10 支動畫不驅動它們)。故有真實 bone-driven 變形場可對照,不必只靠靜態 IoU。

### 2.【雷點 #2/#3 在真實資料上實證】變形評估必須 **visibility gating**
光暈在 `Award_Legend_In` 前半段 slot `color` alpha=`ffffff00`(全透明,t=0→0.5 held),
t=0.6333 才 fade 到 `ffffffff`。若不 gating,評估器在**不可見**的爆開幀報 71 自交/7 翻面 →
**假性失敗**(生產美術 mesh 被誤判)。加入 `slot_visible()`(attachment timeline gating +
color alpha 內插 gating)後,只在**實際被渲染**的幀判定 → 光暈可見 7/25 幀全乾淨,checker 通過。
教訓:weighted/deform 變形閘一律先過 attachment+alpha gating(對照 unweighted deform_eval 也宜補)。

### 3. FK 正確性由「生產美術 mesh 保持乾淨」交叉驗證
5/6(件×動畫)組合一開始就 0 自交/0 翻面;唯一例外(光暈/In)經 gating 後也乾淨。
身體(98v 全綁 4_LEG3)與光暈共用 4_LEG3/5 卻乾淨 → 證明 FK 核心(緊湊 bezier 內插、
normal 繼承世界矩陣、weighted 蒙皮)正確,非全域錯。

## 誠實限制

- **AC-W2 smoothness_cv 是弱代理**:量的是「某 pose 下三角面積的變異係數」,均勻格點天生偏低,
  並非嚴格的「變形平滑度」。**嚴格的變形品質閘是 AC-W1(真實骨 pose 下 0 自交/0 翻面/0 退化)**,
  其鑑別力由負對照(3702 自交)證實。生成件 CV 低只代表三角尺寸均勻,不等於「比美術好」。
- **骨「集合」沿用美術真值**(該件用哪些骨)。本閘驗的是**權重 + 拓樸生成**,非骨骼選擇(屬 S1/S5)。
- **權重為 inverse-distance^2 BBW 代理**,非解離散拉普拉斯的真 harmonic/BBW 權重。已足以在此 3 件
  真實動畫幅度下產生乾淨變形;更大幅度或多骨交界的平滑度,待真 BBW 補強再驗。
- 只驗這 3 件 + Legend 系列動畫(唯一驅動它們的動畫)。

## 下一步候選
- 真 BBW(離散拉普拉斯 / 有界雙調和)取代 inverse-distance 代理,量化交界平滑度差異。
- 把 weighted mesh 生成接回 `build_spine.py`,對 bone-變形件輸出 weighted attachment(目前 build_spine 只輸出 region/unweighted）。
- 更嚴格的變形平滑度指標(相鄰頂點 Jacobian 變異),取代 AC-W2 弱代理。
