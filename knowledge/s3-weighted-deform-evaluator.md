# S3 — weighted(骨綁)mesh 變形評估器

- **結論**:補上 `deform_eval.py` 的唯一缺口——它只驗 unweighted mesh(deform timeline 逐頂點加偏移);
  真實生產角色多為 **weighted mesh**(頂點綁在骨上、靠 bone 動畫變形)。新工具
  `tools/mesh_gen/weighted_deform_eval.py` 在 Python 內重現 Spine 3.8 的 bone world transform + weighted
  skinning + timeline 取樣,對任一 weighted mesh 逐動畫逐幀量化自交/翻面/塌陷。
  `validate_weighted_deform.py` **對 Award 3 個機器人 weighted mesh 三道校驗全 PASS**,證明這支閘可信。
  → 這是 STATE 候選 2(weighted mesh + 內部取樣 + BBW 權重)的**前置品質閘**;沒它無法量化「BBW 產出的
  weighted mesh 骨骼變形平滑度」是否對等藝術家。
- **依據/來源**:`assets/Award.json`(77 bones/47 slots/12 anims)機器人 3 件 weighted mesh 真值
  + Award 真實 bone 動畫(Legend_In/Loop/Out 驅動 4_LEG3~9)。
- **信心**:高(數學經藝術家真值自一致性 + 負對照雙向確認;過程揪出並修掉 1 個 bug,見下)。
- **相關階段**:第 2 階段 S3(mesh);方法論延續 unweighted `deform_eval` 的 `_checker_validated`。

## Spine 3.8 weighted 變形數學(本工具重現)

1. **weighted vertices 格式**:`[boneCount, (boneIdx, bindX, bindY, weight)*bc, ...]`;bind 為該骨**局部**座標。
2. **bone world transform(transform="normal")**:
   - local 2×2 仿射 `a=cos(rot+shx)·sx, b=cos(rot+90+shy)·sy, c=sin(rot+shx)·sx, d=sin(rot+90+shy)·sy` + 平移 (x,y)。
   - `world = parent ∘ local`(沿 bones 陣列順序算,parent 必在 child 前;root 的 parent 為單位)。
3. **skinning**:`worldPos(v) = Σ_i weight_i · boneWorld_i.transformPoint(bindX_i, bindY_i)`。
4. **timeline 套用**:translate/rotate 是**加**在 setup 局部值(delta)、scale 是**乘**;沿 parent 鏈重算 world。
5. Award 全部骨皆 `transform="normal"`;遇非 normal 模式工具會 `raise`(不靜默出錯)。

## ⚠️ 踩過的雷(修正紀錄)

- **scale timeline 缺 channel 預設值**:Spine 匯出會省略 == 預設值的 channel。translate/rotate 預設 0,
  **但 scale 預設是 1**。一開始 `sample_timeline` 對缺的 channel 一律回 0.0 → scale 被當 0 → 整片 mesh
  在 y(或 x)塌陷成一線,造成**假性自交/翻面**(光暈 In si=115、左手 Loop si=3)。改成 per-channel default
  (scale 傳 1.0)後,左手/身體全動畫乾淨。**教訓**:忠實重現 Spine 必須尊重「省略即預設」且 scale 預設非 0。
- **big-win『scale 從 0 彈入』≠ 拓樸缺陷**:In/Out reveal 首幀整體 scale→0,全 mesh 均勻收合,
  絕對面積閾值會把 154 個三角全判 degenerate。改用 `eval_pose_wm`:degeneracy 用**相對面積**
  (< 1e-4×同姿勢平均;整體收合時 mean≈0 → 判 0)。self-intersection/flip 本就 scale-invariant,沿用。

## 評估器可信度(validate_weighted_deform.py 三道校驗,全 PASS)

1. **自一致性(setup 重建)**:3 件由 weighted 綁定重建 setup pose → 全 0 自交/0 塌陷
   (證 bone transform + skinning 數學正確,能重現藝術家靜態形狀)。
2. **藝術家真值(真實動畫)**:**不透明結構件**身體(98v)、左手(80v)在其驅動動畫**全幀乾淨**
   (si=0/flip=0/degen=0)→ 證閘不誤報好 mesh。
3. **鑑別力(負對照)**:
   - 直接:左手打亂權重 → si=21/flip=3(動作夠大即現形)。
   - 放大分離:身體真實動畫近剛體(area 1.0),打亂權重在 amp=1 不現形;**amp=4 時藝術家 si=0、
     打亂 si=54** → 證閘能隨動作幅度分離「好綁定 vs 壞綁定」,鑑別力不依賴資產動作大小。

## 誠實界定 / 重要發現

- **軟性加成件(光暈)容許自我重疊**:光暈(78v,綁 4 骨)在 Legend_In reveal 期真實自交 si=71
  (且發生在 **t=0 精確 keyframe**,非內插假象)。這是藝術家真實變形——additive halo 折疊重疊在混合下
  視覺無害。故 **pass/fail 門檻必須依 attachment 語意分類**:不透明結構件要 si=0;軟性加成件只記錄重疊幅度。
- 只有 Legend 三支動畫驅動機器人骨(Mega/Omg/Super 不碰);機器人 mesh 專用於 Legend tier。
- 目前只驗 `transform="normal"`;若未來資產有 IK/約束或其他 transform 模式需擴充。

## 圖

`figures/s3_weighted_deform_eval.png`:身體 setup / amp4 藝術家(乾淨) / amp4 打亂(纏繞);
左手真實 Loop(乾淨) / 光暈 reveal(軟重疊) / 左手打亂(破)。視覺與量化一致。

## 標準指令

```
PYTHONPATH=tools/mesh_gen python3 tools/mesh_gen/validate_weighted_deform.py   # → OVERALL: PASS ✅
PYTHONPATH=tools/mesh_gen python3 tools/mesh_gen/weighted_deform_eval.py assets/Award.json "機器人拆件/身體"
```

## 下一步(承 STATE 候選 2)

有了這支閘,即可做 **BBW(Bounded Biharmonic Weights)權重生成 + 內部取樣密度控制**:
對機器人件(已有真值骨架/區域)自動產 weighted mesh,用本閘量測其在真實 Legend 動畫下是否
達「不透明件 si=0、且變形平滑度(area_ratio 波動 / 邊長變異)≈ 藝術家」。真值(權重/骨架)在 `Award.json`,純 CPU 可自驅。
