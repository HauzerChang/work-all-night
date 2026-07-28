# S3 對真實生產 mesh(Award 機器人 weighted)靜態驗收 + deform 閘缺口

- **結論**:S3 生成器可在真實生產標的上把 mesh **拓樸/輪廓覆蓋**做到 ≥ 藝術家水準;
  但這 3 個真實 mesh 是 **weighted、bone-driven、無 deform timeline**,現有 deform 閘
  (`transfer_deform_check`,吃 per-vertex 位移場)**不適用** → 揭露 S3 尚缺兩塊:
  (a) BBW 權重綁定、(b) bone-affine-blend 變形閘。
- **依據**:`tools/mesh_gen/validate_robot_award.py` 對 `assets/Award.json` 的
  `機器人拆件/{左手,光暈,身體}`(從 `Award.atlas`+`Award.png`/`Award2.png` extract 的 region alpha)
  跑,對照藝術家 weighted mesh 的 uvs+triangles 覆蓋 IoU。可重跑、EXIT=0。
- **信心**:高(靜態部分,外部真值 = 生產藝術家 mesh)。deform 部分為**尚未驗**(明確缺口)。
- **相關**:專案第 2 階段,S3(mesh)× S4(PSD→件)端到端;S2(評估器)新缺口。

---

## 為什麼這是「第一次真實生產標的」

- main_draw 的 4 mesh 全 **unweighted** 且靠 **deform timeline** 變形 → 之前的整合 AC
  (`validate_against_real.py`)與 deform 閘都建在這個前提上。
- Award(機器人 big win 的生產 spine)的 3 個 mesh 全 **weighted**(`vertices.length != uvs.length`,
  格式 `[boneCount, boneIdx,bindX,bindY,weight, ...]`),且 **9→實為 12 anim 中 0 條 deform timeline**
  → 純靠 bone 變換驅動。這是完全不同的變形機制。

## 靜態輪廓覆蓋對照(region 像素空間,與藝術家 uvs 同座標)

指令:`python3 tools/mesh_gen/validate_robot_award.py --gen v1 --epsilon 0.002`

| 件 | region | 藝術家 weighted nv / IoU | S3 v1(eps=0.002)nv / IoU | 達標 |
|---|---|---|---|---|
| 左手 | 181×152 | 80 / 0.9681 | 103 / **0.9913** | ✅ |
| 光暈 | 496×480 | 78 / 0.9795 | 98 / **0.9832** | ✅ |
| 身體 | 267×299 | 98 / 0.9760 | 97 / **0.9926** | ✅ |

圖:`knowledge/figures/robot_award_mesh_compare.png`(上=藝術家 weighted,下=S3 v1)。

## 關鍵發現

1. **strip(v2 預設)在這些件上有結構天花板**:這 3 件都**非 row-convex**(手有指縫、光暈有芒刺、
   身體有肢/凹口)。strip 假設每列 min-x→max-x 填滿 → 凹處過覆蓋,IoU 封頂約 0.95~0.96,
   即使 rows 拉到 30(90 頂點)仍**過不了**藝術家基準。**cols 完全不影響 IoU**(印證舊發現:
   IoU 由 rows 決定)。
2. **auto 模式的路由是對的**:`generate_mesh_v2(mode='auto')` 對這些非 row-convex 件
   自動回退 **v1 Delaunay**(`is_row_convex`=False)。v1 的輪廓跟隨(findContours+approxPolyDP)
   天生適合凹形。
3. **v1 的 `epsilon_frac` 是輪廓保真旋鈕**:0.008(預設)覆蓋不足(0.927~0.969);
   0.004 過 2/3;**0.002 三件全過**,頂點數與藝術家同級(97~103 vs 78~98)。
   ⚠️ 但 eps 越小靜態 IoU 越高**不代表**變形越好 —— 這正是舊教訓「靜態≠變形穩健」。
   eps 的正確取值取決於變形機制:
   - **deform-timeline 件(如 main_draw 窗簾)**:別為衝靜態 IoU 而狂降 eps;strip / 較粗
     拓樸反而耐變形(舊結論)。
   - **bone-driven weighted 件(如 Award 機器人)**:變形是各 bone 仿射的加權混合,對頂點密度
     較不敏感;可用較密 v1 追求輪廓保真 —— **但這需要先有權重綁定與變形閘才算真的驗過**(見下)。

## 缺口 / 下一步(明確的新子目標)

- ❗**S3 尚未產出 weights**:要真的把生成 mesh 放進 Award 這種 rig,需 BBW(Bounded Biharmonic
  Weights)或等效權重綁定,把頂點綁到既有骨。目前只驗到「拓樸/覆蓋」層級,**未到 rigging 層級**。
- ❗**缺 bone-driven 變形閘**:weighted mesh 在 bone 動畫下的拓樸穩健(自交/翻面)要另寫閘 ——
  用「各 bone 的世界仿射 × 頂點權重 = 變形後座標」重建(對照 CLAUDE.md 雷點 #4/#6),
  而非 deform-timeline 轉移。這是 S2 評估器套件的新缺口。
- 端到端「PSD→件→**可 rig 的 mesh**」的最後兩哩 = 上述兩塊。本次已把**第一哩(件→合格拓樸)**
  對真實生產標的釘死。
