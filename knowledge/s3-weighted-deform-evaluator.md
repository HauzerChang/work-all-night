# S3 — weighted-mesh deform 評估器(補上「骨骼變形平滑度」未驗維度)

- **結論**:完成 `tools/mesh_gen/weighted_deform.py` —— 純 CPU 重現 Spine 3.8 的
  骨骼 world-transform + 動畫 bone timeline apply + weighted `computeWorldVertices`,
  對 Award「機器人拆件」3 個 weighted mesh 件(光暈/左手/身體)在**會 pose 到其綁定骨的
  真實動畫**下逐幀量化變形。評估器可信度以 **frame-invariant 多骨一致性**(不需外部真值)
  + **負對照鑑別力**雙重自證。這補上 `s3-robot-mesh-vs-award.md` 標記的唯一未驗維度
  (靜態 IoU PASS ≠ 骨骼變形品質對等)。
- **信心**:高。骨骼變換數學經多骨 bind 一致性驗證到 0.014~0.037px;動畫 apply 經
  「t=末幀精確回到 setup(disp=0.0)」+「逐幀連續無跳變」自證;3 件對真值行為分明。
- **階段**:第 2 階段 / S3(里程碑:weighted mesh 變形能被量化,為權重生成器(2b)備妥閘)。
- **工具**:`python3 tools/mesh_gen/weighted_deform.py --negative`(AC1+AC3+AC4 全過 → exit 0)。

## 重現的 Spine 3.8 機制(transform=normal;Award 77 骨全 normal)

- 骨骼 world transform:`la=cos((rot+shx)°)sx, lc=sin((rot+shx)°)sx, lb=cos((rot+90+shy)°)sy,
  ld=sin((rot+90+shy)°)sy`;child = parent 矩陣 ∘ local。父先於子拓樸序遞迴。
- 動畫 bone apply:rotate/translate **加成** setup、scale **乘成** setup;緊湊 bezier
  `{"curve":cx1,"c2":cy1,"c3":cx2,"c4":cy2}`(cy1 預設 0、cx2/cy2 預設 1)、`"stepped"`、
  無 curve=linear。以二分解 Bx(s)=p 求 y 分數。
- weighted computeWorldVertices:`worldVec = Σ_i weight_i · worldBone_i·(bindX_i,bindY_i)`。

## 評估器可信度(RULES「每能力必配評估器」— 先於權重生成器)

- **AC1 多骨一致性閘(frame-invariant,核心自證)**:setup pose 下,同一頂點受多骨影響時,
  各骨各自 `worldBone·(bind)` 必須吻合(bind 定義如此)。**對 root/全域座標框不變** →
  即使根骨/skeleton 座標慣例有歧義也不影響此相對驗證。實測 3 件最大不一致
  **0.037 / 0.014 / 0.014 px**(< 0.5px)→ 骨骼變換數學正確。
- **AC2 動畫 apply 自證**:t=0 delta=0;**Legend_In 末幀 disp 精確回到 0.0**(In 動畫從偏移態
  收斂到 setup);逐幀 disp 連續無跳變(排除 bezier/區間 bug)。
- **AC4 負對照(鑑別力)**:打亂每頂點『骨↔bind 座標』配對 → 多骨一致性由 0.01~0.04px
  爆到 **287~654px** 且幾何全壞 → 評估器能區分好壞權重(權重生成器閘的前提)。

## 關鍵發現:自交是「每件校準」閘,非通用硬閘

`--negative` 全過,但**藝術家自己的光暈**在 `Award_Legend_In` 入場時 **si=71 / flip=7 /
area 0.89~1.98 / maxdisp 676px**(源於 `4_LEG6` 起手 scale=1.667× 再收回)。這**不是 bug**
(AC1 精確、末幀回 setup、逐幀連續),而是**軟光暈 additive/半透明,自疊視覺無害**,藝術家
刻意用大幅重疊變形 —— 正呼應 S3 生成階段光暈需 `boundary-dense soft-band` 特例。

反之**不透明結構件(左手/身體)藝術家 mesh 全乾淨**(si=0/flip=0,area 0.74~1.01)。

→ **設計結論(同 `compare_robot_mesh` 的『不劣於藝術家』IoU baseline 哲學)**:
  以**藝術家自身 mesh 在自身動畫下的變形包絡**當每件 baseline,而非硬性「全乾淨」通用閘。
  - 硬閘只保 **AC1(變換正確)** + **AC4(鑑別力)** + **不透明件乾淨**(正對照)。
  - 光暈的有效判據是「回 setup + area 連續 + AC1」,不是自交數。
  - 這些藝術家包絡數字(每件每動畫的 si/flip/area range)即**下一步權重生成器**的比較真值。

## 藝術家變形包絡(baseline,供 2b 權重生成器對照)

| 件 | 綁定骨 | 動畫 | si | flip | area range | maxdisp |
|---|---|---|---|---|---|---|
| 光暈(soft glow) | 4_LEG3/4/5/6 | Legend_In | 71 | 7 | 0.89–1.98 | 676px |
| 光暈 | 同上 | Legend_Loop | 0 | 0 | 1.00–1.00 | — |
| 左手(opaque) | 4_LEG5/9 | Legend_In | 0 | 0 | 0.74–1.01 | 241px |
| 左手 | 同上 | Legend_Loop | 0 | 0 | 0.98–1.00 | — |
| 身體(opaque) | 4_LEG3/7/8 | Legend_Loop | 0 | 0 | 1.00–1.00 | 12px |

(件僅在「有 pose 到其綁定骨」的動畫上評估;身體綁 3/7/8,Legend_In 只 pose 4/5/6 → 不評。)

## 下一步

- **2b 權重生成器(heat/BBW)**:對這 3 件用相同 setup 頂點+相同綁定骨自動算權重,以本評估器
  對照藝術家包絡(不透明件:si/flip=0 且 area 在藝術家 range;光暈:回 setup+area 連續)。
  真值(藝術家權重/骨架)已在 `Award.json`,純 CPU 可自驅。
- 可選:把 pose_at/world_transforms 抽成共用模組供 spine_inspector 離線驗證用。
