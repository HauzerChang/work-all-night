# S3 端到端:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:S3 v2 生成器對 3 個真實生產 mesh 件(Award 機器人拆件 光暈/身體/左手)
  **靜態覆蓋率全部達到藝術家水準**(IoU 對齊藝術家 mesh 對自身 alpha 的基準,margin 0.02 內),
  且頂點數比藝術家更精簡、setup pose 0 自交 / 0 退化。這是「PSD→件→S3 mesh」對真實標的的
  端到端驗收(第一次有藝術家真值可直接對照)。
- **信心**:高(對照真實生產 spine 的藝術家 mesh 真值;純 CPU 可複現)。
- **相關階段**:第 2 階段 S3(mesh 生成)× S4(PSD 切圖)串接。
- **工具**:`tools/mesh_gen/compare_award_mesh.py`(標準指令,exit 0 = 全過)。
- **圖**:`knowledge/figures/award_robot_mesh_compare.png`(左=藝術家綠線 / 右=生成紅線+黃點)。

## 結果(2026-07-23)

| 件 | region | 藝術家 nv/tris/IoU | 生成 nv/tris/IoU | AC1 覆蓋 | AC2 預算 | AC3 拓樸 |
|---|---|---|---|---|---|---|
| 光暈 | 496×480 | 78 / 76 / 0.9795 | 61 / 97 / 0.9656 | ✅ | ✅ | ✅ |
| 身體 | 267×299 | 98 / 154 / 0.9760 | 61 / 98 / 0.9680 | ✅ | ✅ | ✅ |
| 左手 | 181×152 | 80 / 116 / 0.9681 | 48 / 76 / 0.9602 | ✅ | ✅ | ✅ |

三件全 `overall_pass`,生成頂點數皆 < 藝術家(自動化未浪費頂點)。

## 兩個關鍵發現

### 1. 兩種變形模型 → 兩種閘,不可混用

Award 機器人 3 件在生產 spine 都是 **weighted mesh**(`len(vertices) != 2·nv`),
而且 **沒有任何 deform timeline 引用它們** —— 它們純靠骨骼加權蒙皮(bone-driven skinning)變形。

- 因此 `deform_eval.transfer_deform_check`(真實 deform 位移場轉移)**對這些件不適用**:
  那是給「**deform-driven** mesh」(如 main_draw 窗簾,有逐頂點 deform timeline)的閘。
- bone-weighted 件的「耐變形」正確性屬 **S3 加權(BBW)** 課題:要先給生成的 unweighted mesh
  綁上權重、再用 Award 的骨骼姿勢驅動,才能量測。該能力尚未建 → 本輪只做**靜態輪廓/覆蓋率**對照
  (誠實範圍界定,不假裝跑了不適用的閘)。

**教訓**:選閘前先判斷 mesh 的變形來源(deform timeline vs 骨骼加權)。真實生產資產兩種都有。

### 2. 覆蓋率的主槓桿 = hull 解析度(epsilon);已做成自適應

diagnose 光暈時掃 epsilon 得(mi=40):

| epsilon_frac | hull 點 | nv | IoU |
|---|---|---|---|
| 0.008(舊預設) | 14 | 54 | 0.930 |
| 0.004 | 22 | 62 | 0.966 |
| 0.002 | 38 | 78 | 0.983 |
| 0.001 | 58 | 98 | 0.992 |

圓潤/軟邊件(發光暈)上,**固定 epsilon=0.008 覆蓋不足**;IoU 幾乎完全由 hull 解析度決定
(與 strip 的「IoU 由 rows 決定」同構)。

→ 給 `generate_mesh.generate` 加了 **`target_coverage` + `vertex_budget`** 自適應:
由粗到細掃 epsilon,取「達覆蓋目標且頂點在預算內」中最省頂點的解(達不到則回覆蓋率最高者)。
`generate_mesh_v2.generate` 轉呼叫時透傳。**預設 `target_coverage=None` → 舊行為完全不變**
(main_draw 4 mesh + slicing gate 重跑無回歸)。`compare_award_mesh` 以「藝術家基準−margin」為目標、
藝術家 nv×1.5 為預算,自主收斂。

## 素材等價性(為何直接用 atlas region 當來源)

log 006 已用 alpha-IoU 0.92~0.99 證明「PSD 切件 == atlas 生產貼圖」(同素材,約 0.70 縮放)。
故本工具直接取 Award atlas region alpha 當生成來源 —— 與藝術家 mesh 落在**同一 crop 座標系**,
IoU 可直接對照;等價於 PSD→件→(素材相同)→region alpha→mesh,免除跨檔重定位誤差。

## 下一步候選

1. **S3 加權(BBW)**:給生成 mesh 綁權重,用 Award 骨骼姿勢驅動 → 才能對 bone-weighted 件補上耐變形閘。
2. **件→Spine JSON 組裝(SkelToJson)**:把 `機器人拆件/<圖層名>` 命名 + size+2px padding + 生成 mesh
   固化成端到端寫出工具。
