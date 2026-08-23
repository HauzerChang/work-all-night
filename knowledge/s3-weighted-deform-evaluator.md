# S3 — weighted-mesh 骨骼變形評估器(補上唯一未驗維度)

- **結論**:新建 `tools/mesh_gen/weighted_deform_eval.py`,以 **forward-kinematics(FK)+ linear-blend-skinning(LBS)**
  在純 Python 重現 Spine 對 **weighted mesh** 的世界頂點計算,再套 `deform_eval` 的幾何閘
  (自交/翻面/退化/面積比)。**評估器自檢三閘全 PASS**,並對 Award 真實美術 weighted mesh
  跑出**藝術家變形品質基準**。這補上 `s3-robot-mesh-vs-award.md` 標記的唯一未驗維度:
  「weighted mesh 骨骼變形平滑度(靜態 IoU 不涵蓋)」。
- **信心**:高(對真實生產骨架+權重+動畫;評估器經 t0-identity / setup-clean / 負對照三閘自驗)。
- **階段**:第 2 階段 / S3(評估器樞紐 — 依 RULES「每能力必配評估器」,先把 weighted 變形閘做可信)。
- **工具**:`tools/mesh_gen/weighted_deform_eval.py`(可重現,`python3` 直跑做自檢+基準)。

## 標準指令

```
PYTHONPATH=tools/mesh_gen python3 tools/mesh_gen/weighted_deform_eval.py   # 自檢全 PASS → exit 0
```

## 方法(對照 CLAUDE.md 雷點 #4/#6)

1. **FK**:每骨 world = parent.world ∘ local(setup + 動畫 delta)。全骨依序(parent 先)。
   - local 矩陣 `_local_matrix(rot,sx,sy,shx,shy)`:`a=cos(r)·sx, c=sin(r)·sx, b=cos(r+90)·sy, d=sin(r+90)·sy`。
   - 動畫套用:`rotate`(angle 為 delta,加)/`translate`(x,y delta,加)/`scale`(乘)/`shear`(加)。
   - transform mode:Award 這些驅動骨**全為 `normal`**(已驗);遇其他 mode 直接拋 `NotImplementedError`(不默默算錯)。
2. **LBS**:`worldVertex = Σ_b weight_b · (bone_b.world 套用到 bind 座標)`。bind 為 setup 下相對該骨座標(#6)。
3. **幾何閘**:重用 `deform_eval.eval_pose`(self_intersections / triangle_flips / degenerate / area_ratio)。

**全域仿射不變性**:self-intersection 與「相對 setup 的 flip」對全域仿射(含鏡射)不變,故**不需**校 y-up/down
或 skeleton flip —— 只要 setup 與各 pose 用同一套 FK。t0-identity 閘會抓到任何不一致。

**curve**:於每個 keyframe 時刻取**精確值**(與 bezier 無關)+ 相鄰幀線性 substep(與 `deform_eval` 一致)。
極值落在 keyframe 上,故足以判定拓樸破壞;線性 substep 為近似(誠實界定)。

## 評估器自檢(三閘,全 PASS)

| 閘 | 內容 | 結果 |
|---|---|---|
| **AC1 中性** | 套「空動畫」(無 timeline)== setup pose,逐頂點差 | 3 件 max_diff = **0.0**(FK/LBS 正確) |
| **AC2 setup 乾淨** | 藝術家 setup 世界頂點 0 自交 / 0 退化 | 3 件全 **PASS** |
| **AC3 負對照** | 對驅動骨注入 +30/60/120° 假旋轉 → 應出現破壞 | 3 件皆抓到自交 23~81、翻面 1~3(**有鑑別力**) |

> ⚠️ **踩過的坑(修正記錄)**:初版 AC1 用「動畫 t=0 == setup」→ 光暈/左手**假性 FAIL**(diff 237~527)。
> 原因:`Award_Legend_In` 是**進場**動畫,t=0 本就偏離 setup(從遠處/縮放進場),不是 FK bug。
> 改為「空動畫 == setup」的中性測試才正確隔離 FK 正確性。

## 藝術家真實 weighted mesh 變形品質基準(visible frames)

> **只判定 slot alpha > 0.05 的可見幀**(見下方關鍵發現)。`Award_Legend_Out` 對這些骨無 timeline。

| 件 | 動畫 | 可見幀比 | 可見 max自交 | 可見 max翻面 | 可見面積比 | 乾淨 |
|---|---|---|---|---|---|---|
| 光暈 | Legend_In | 0.39 | **4** | 0 | 0.877–1.072 | ✗(軟邊容忍) |
| 光暈 | Legend_Loop | 1.0 | **0** | 0 | 0.997–1.002 | ✓ |
| 左手 | Legend_In | 0.98 | 0 | 0 | 0.779–1.014 | ✓ |
| 左手 | Legend_Loop | 1.0 | 0 | 0 | 0.975–1.000 | ✓ |
| 身體 | Legend_Loop | 1.0 | 0 | 0 | 1.000–1.001 | ✓ |

- 驅動骨:光暈=`4_LEG3/4/5/6`、左手=`4_LEG5/9`、身體=`4_LEG3/7/8`(1~3 骨/頂點,權重和=1)。
- 視覺證據:`knowledge/figures/robot_weighted_deform_loop.png`(灰=setup、橙=Loop 最大變形)。

## 三個關鍵發現

### 1. 變形品質判定**必須**做 slot-alpha 可見度閘
`Award_Legend_In` 進場時 slot color = `ffffff00`(**alpha=0,不可見**),且驅動骨 `4_LEG6` 有 **stepped 1.667× 縮放**。
未閘時光暈報 max_self_intersections=**71**、面積比 **1.98** —— 但那全發生在**不渲染**的進場窗。
加 `slot_alpha()` 閘(honor `stepped`)後降為 4 自交、面積 1.07。**教訓:不可見的進場擠壓不是破圖。**

### 2. 藝術家對「軟邊 blob」的變形容忍度不是 0
光暈在可見 fade-in 尾段仍有 **4 處自交**(羽化軟邊、半透明,肉眼無感)。
→ 對光暈這類件,**真實的變形品質標竿是 sustained `Loop`(0 自交、面積≈1.0)**,而非「所有可見幀 0 自交」。
生成器對硬邊件(左手/身體)可要求 Loop 全乾淨;對軟邊件放寬進出場即可。

### 3. 身體幾乎不變形、四肢才變形 —— 內部頂點密度的用途被量化
身體 Loop 面積比 1.000–1.001(近剛體,作錨點);左手 In 面積縮到 0.78(手臂收放)但拓樸恆合法。
→ 呼應 `s3-robot-mesh-vs-award.md`:美術身體 98v 的密集**內部**頂點主要服務**平滑權重過渡**,
   而非大幅變形;下一步生成器要對照的正是「同樣的骨/權重下,我方拓樸能否一樣乾淨」。

## 對下一步(生成器對照)的意義

- **閘已就緒**:有了可信的 weighted 變形閘 + 藝術家基準,下一 chunk 可做
  **S3 weighted 生成(內部取樣密度 + BBW 權重)**,並用同一支評估器做**同骨同動畫**的變形品質對照。
- 對照範式:對生成 mesh 綁上 Award 這 3 件的**同一組骨**、用 BBW 算權重 → 跑 `benchmark` →
  可見幀變形品質應**不劣於**上表藝術家基準(硬邊件 Loop 0 自交;軟邊件容忍同級)。

## 誠實界定 / 限制

- 只實作 transform=`normal`(本資產足夠);其他 inherit mode 未實作(會拋錯,不會默默算錯)。
- substep 為線性近似(keyframe 極值精確);IK / transform constraint 未套用(這些骨無 constraint 驅動)。
- 尚未生成我方 weighted mesh 對照 —— 本 chunk 專注把**評估器**做可信(RULES:能力前先有閘)。
