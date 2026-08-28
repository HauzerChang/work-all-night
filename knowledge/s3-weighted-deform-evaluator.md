# S3 weighted-mesh 變形評估器 — 補上「靜態 IoU PASS ≠ 骨骼變形品質」的缺口

- **結論**:實作 Spine 3.8 骨骼 FK + weighted 蒙皮引擎(純 CPU),對 Award 3 個機器人
  weighted mesh(光暈/左手/身體)在其動畫下逐幀量測**變形幾何合法性 + 應變非均勻度**,
  建立可比對的**變形平滑度真值基準**。3 條可機讀 AC 全 PASS,並以硬綁負對照證明鑑別力。
- **信心**:高。引擎正確性以「剛體再現性」自證(浮點級 2.8e-13);評估器以負對照(硬綁破裂)自證。
- **階段**:第 2 階段 / S3。補上 `compare_robot_mesh` 誠實限制列的**唯一未驗維度**
  (weighted mesh 骨骼變形平滑度),見 `s3-robot-mesh-vs-award.md` §誠實限制。
- **工具**:`tools/mesh_gen/weighted_skin.py`(引擎)、`tools/mesh_gen/weighted_deform_eval.py`(評估器)。

## 標準指令

```
python3 tools/mesh_gen/weighted_deform_eval.py            # 全 AC → exit 0
python3 tools/mesh_gen/weighted_deform_eval.py --json     # 完整逐動畫報告
python3 tools/mesh_gen/weighted_deform_eval.py --selftest # 負對照鑑別力(硬綁光暈應破裂)
```

## 三條 AC(全 PASS)

| AC | 內容 | 結果 |
|---|---|---|
| AC1 仿射再現性 | 對 root 骨施加剛體 T → 所有蒙皮頂點必**恰**被 T 映射(∵ 權重和=1)。同時驗 FK 組合 + 權重正規化,**非循環**。 | max_err **2.8e-13 px** ✅ |
| AC2 權重單位分解 | 每頂點權重和 = 1 | dev **1e-5**(藝術家 3~5 位小數捨入)✅ |
| AC3 藝術家 mesh 乾淨 | 3 件在其掛載動畫**可見幀**逐幀 0 自交/0 翻面/0 退化 | 全 clean ✅ |

## 變形平滑度真值簽章(供 S3 weighted 生成器對照)

3 件 setup attachment 皆 null,只在 **Legend 檔位 In/Loop/Out** 三支動畫掛載顯示。

| 件 | 頂點 | 綁定骨(關節) | max_edge_strain_mean | **max_strain_dispersion** | area_ratio 範圍 |
|---|---|---|---|---|---|
| 光暈 | 78 | LEG3/4/5/6(4骨,達3骨/頂點) | 0.410 | **0.119** | 0.348–1.064 |
| 左手 | 80 | LEG5/9(2骨) | 0.410 | **0.085** | 0.348–1.064 |
| 身體 | 98 | LEG3/7/8(3骨) | 0.410 | **0.124** | 0.348–1.064 |

- **dispersion = p95(|strain|) − p50(|strain|)** = 邊長應變**非均勻度**。這是「內部取樣密度
  服務變形平滑度」的可比對信號:**均勻縮放**時每邊應變相同 → dispersion≈0(非平滑度問題);
  **局部撕扯 / 取樣過疏**才會讓少數邊應變爆高 → dispersion 大。
- 為何**不用 max 應變**:三件的 max_edge_strain_mean 都是 0.410,因最壞幀是近**均勻**縮到
  area 34.8%(每邊壓縮 ≈ 1−√0.348 = 0.41),被均勻縮放主導、無鑑別力 → 改用 dispersion。
- 為何**不用 CV**:平移主導變形下平均應變≈0,CV=std/|mean| 被小分母放大(光暈曾算出 171),不穩。

## 三個關鍵發現

### 1. ⚠️ 可見性 gating 是誠實關鍵(否則假陽性)
光暈在 `Award_Legend_In` 前段(t≤0.29)被骨骼壓到**自交 71 處**,乍看「藝術家 mesh 會壞」。
但查 slot color timeline:該段 **alpha=0**(淡入前完全透明,t=0→0.5 全 0,0.633 才到 1.0)。
→ 那些幀根本沒顯示。評估器加**可見性 gating**(attachment==name 且 slot alpha>0.02)後,
只評估真正看得到的幀 → 3 件全乾淨。對映 CLAUDE.md 雷點 #2/#3(attachment gating),
再擴充 alpha gating。**教訓:weighted mesh 變形品質必須在可見幀上評估,否則誤判被隱藏的極端幀。**

### 2. 這 3 件靠 **bone transform** 變形,不是 deform timeline
先前 `compare_robot_mesh` 記「無 deform timeline → 變形品質未驗」。正解:weighted mesh 靠所綁
**骨骼的 rotate/scale/translate 動畫**變形(LEG5 rotate 達 14°、LEG6 達 −26.8°、scale 1.667、
translate 數百 px)。故需完整 Spine FK 才能驅動 → 本次補上引擎。deform timeline 與 bone-driven
是兩條正交的變形路徑,unweighted 走前者(`deform_eval`)、weighted 走後者(本工具)。

### 3. 引擎範圍(對 Award 充分)
Award 77 骨**全 `normal` transform mode、無 shear** → 只需標準 `Bone.updateWorldTransform`
組合(cosDeg/sinDeg × scale,沿階層 root→leaf)。動畫內插支援緊湊 bezier
`{curve,c2,c3,c4}`(Newton 解)/ "stepped" / linear 三種。scale key 缺 x/y 預設 1(乘數),
translate/rotate 缺值預設 0(offset)。

## 負對照(鑑別力自證)
`--selftest`:對光暈(綁到會大旋轉的 LEG5/LEG6 關節)把混合權重改**硬綁**(每頂點只綁最高權重骨,
權重=1)。結果:藝術家平滑混合可見幀全乾淨,**硬綁在關節自交 4 處** → 幾何閘能區分好壞蒙皮,非恆真。
(註:身體/左手骨間相對關節運動小,硬綁差異不顯著;光暈是關節articulation最強的鑑別點。)

## 誠實限制 / 下一步
- 本評估器量**幾何合法性 + 應變非均勻度**;未涵蓋貼圖採樣品質、視覺羽化帶保真(需 PNG+PMA 實機)。
- dispersion 是**相對簽章**:對「同一件、同骨綁權重轉移」的生成 mesh 才可直接比大小
  (愈低 = 內部取樣愈能平滑吸收變形)。跨件絕對值受各件關節運動幅度影響,不宜互比。
- **下一步(接續)**:S3 weighted 生成器 —— 對這 3 件生成內部取樣夠密的拓樸 + BBW/heat 權重,
  用本評估器對照「同動畫下 dispersion ≤ 藝術家基準、0 自交」→ 完成 weighted mesh 生成閘。
  真值(藝術家權重/骨架)已在 `Award.json`,純 CPU 可自驅。
</content>
