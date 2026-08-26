# S3 — weighted-mesh 骨骼變形評估器(候選 2 前置閘)

- **結論**:補齊了 S3 唯一未驗維度的**閘**——weighted mesh 在骨骼動畫下的變形品質。純 Python 重現
  Spine 3.8「骨骼世界變換 + 每頂點權重混合」,對 Award 機器人 3 件 weighted mesh × 真實 In/Loop/Out 動畫
  逐幀跑幾何品質檢查。**結構件(左手/身體)於三支動畫全乾淨**(0 自交/翻面/退化),證明重現正確;
  **負對照(打亂綁定)三件全被抓到** → 閘具鑑別力,可作為後續 BBW 權重生成的收斂依據。
- **依據/來源**:`tools/mesh_gen/weighted_deform_eval.py`;真值 `assets/Award.json`(77 骨/12 動畫)。
- **信心**:高(結構件正對照 + 負對照雙向驗證;transform-constraint 限制已界定)。
- **相關階段**:S3(mesh),補上 `s3-robot-mesh-vs-award.md` 標記的「weighted 骨骼變形平滑度未驗」。

## 為什麼需要它

`deform_eval.py` 只處理 **unweighted** mesh(靠 `deform` timeline 逐頂點加偏移;main_draw 的 4 個窗簾/陰影)。
但真實生產美術(Award 機器人)的 mesh 是 **weighted**:不存 setup 2D 頂點,變形完全來自
**骨骼世界變換 × bind 座標 × 權重**。要自主鍛鍊 BBW(骨綁權重)生成,必先有能對「骨骼拉扯下網格會不會壞」
pass/fail 的閘(RULES「每能力必配評估器」)。本檔即該閘。

## 重現的 Spine 3.8 數學(全 normal transform mode)

骨骼 local→world(父 pa,pb,pc,pd,pWX,pWY):
```
rotationY = rot + 90 + shearY
la=cosDeg(rot+shearX)*sx ; lb=cosDeg(rotationY)*sy
lc=sinDeg(rot+shearX)*sx ; ld=sinDeg(rotationY)*sy
a=pa*la+pb*lc ; b=pa*lb+pb*ld ; c=pc*la+pd*lc ; d=pc*lb+pd*ld
worldX=pa*x+pb*y+pWX ; worldY=pc*x+pd*y+pWY   (root:直接用 la..ld, x, y)
```
weighted 頂點:`worldPos = Σ_bone weight * (bone.a*bindX+bone.b*bindY+bone.worldX, bone.c*..+bone.d*..+bone.worldY)`。

動畫套用:每骨 local = setup + rotate(角度加)/translate(xy 加)/scale(xy **乘**)/shear(加);
keyframe 間以緊湊 bezier(`curve=cx1,c2=cy1,c3=cx2,c4=cy2`,stepped/linear 特例)內插。

## ⚠️ 踩到的雷(關鍵修正)

**Spine timeline 省略的 keyframe 值取該 timeline 的「中性值」,不是 0。**
- rotate/translate/shear 省略 → 0(偏移)。
- **scale 省略 → 1.0(倍率)**。一開始把 scale 缺鍵當 0 → 內插到 0 → 整個 mesh 面積比塌到 **0.0**
  (`Award_Legend_In` 全 mesh 假性退化)。修正 `_sample_timeline(..., default=1.0)` for scale 後,
  左手/身體 立即全乾淨。教訓:reproduce Spine timeline 一定要用 per-timeline 中性預設值。

## 驗收結果(`weighted_deform_eval.py`,~30fps 取樣)

| mesh | 綁定骨 | POSITIVE(美術真值) | 說明 |
|---|---|---|---|
| 機器人拆件/左手 | 4_LEG5,4_LEG9(2骨/頂點) | **In/Loop/Out 全乾淨** | 結構件 |
| 機器人拆件/身體 | 4_LEG3,7,8(≤3骨/頂點) | **In/Loop/Out 全乾淨** | 結構件 |
| 機器人拆件/光暈 | 4_LEG3,4,5,6(≤3骨/頂點) | In 折疊(si≤71,flip≤7) | **軟發光層,美術容忍** |

**光暈折疊是真值不是 bug**(資料驅動證據):
- setup pose 乾淨;折疊只在 `Award_Legend_In` 爆發期出現。
- flip 三角**空間叢聚於 4_LEG6**(該骨 In 期 `scale=1.667` + translate 231px,影響 49/78 頂點),
  與幾乎不動的鄰骨(4_LEG3)交界處折疊 —— 高倍率骨邊界的真實 mesh fold。
- **共用同骨鏈的鄰件(左手/身體)全乾淨** → 排除變換管線 bug(否則會一起壞)。
- 光暈是柔性發光貼圖,fold 在視覺上被軟漸層藏住 → 美術不介意。
- **設計啟示**:嚴格幾何 clean 閘適用於**結構件**;軟 FX/glow 件需放寬(或排除)。

## 負對照(鑑別力)

- **shuffle-bind**(每頂點骨索引在該 mesh 用到的骨集合內循環錯位):**三件全被抓到**
  (si 155~467)→ 可靠負對照。
- **hard-1-bone**(每頂點只留權重最大的骨):只抓到光暈(si 117);左手/身體在其較溫和的動作下
  硬綁單骨仍乾淨。**發現**:單骨硬綁只在「相鄰骨強烈分歧」時才撕裂 → hard-1 是較弱的負對照,
  正式閘用 shuffle。

**判定 `evaluator_discriminative = True`**:結構件正對照全乾淨 + shuffle 負對照每件都抓到。

## 限制 / 待續

- 未處理 **transform-constraint**(Award 的 `transform` 陣列有 `4_LEG7→4_LEG8`);本 3 件所綁 LEG 骨
  除身體用到 4_LEG8 外多不受直接約束,身體實測仍乾淨,但嚴謹起見日後擴到受約束骨需補 constraint 求解。
- 曲線內插用 Newton+二分解 bezier x→y;僅影響中間幀,keyframe 極值正確(自交主要出現在極值幀,已覆蓋)。
- **下一步(候選 2 主體)**:在我方生成的 mesh 拓樸上做「內部取樣密度控制 + BBW 權重」,
  用本閘量化生成 weighted mesh 的變形平滑度是否 ≥ 美術基準(結構件 clean;光暈可比 fold 幅度)。
