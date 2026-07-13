# S3+S4 端到端:PSD 件 → 生成 mesh → 對照 Award 真實藝術家 mesh

- **結論**:把 `robot_parts.psd` 的三件（光暈/身體/左手，在生產 spine `Award` 中為 mesh）以 PSD 切件
  全解析度 alpha 當來源跑 `generate_mesh_v2`，與 Award 藝術家 mesh 做**靜態輪廓 IoU + 拓樸**對照：
  **座標系一致、輪廓覆蓋率貼近藝術家（差 ≤1.55%）、拓樸全乾淨，且頂點數比藝術家少 30–55%。**
  這是「PSD→件→mesh」對真實生產標的的第一次端到端驗收。
- **信心**:中高（對真實 ground truth 交叉比對 + 座標系經驗校準 + 拓樸量化）。**唯一保留**：
  這些件在 Award **無 deform timeline**，逐頂點 deform 穩健**無法**用此標的驗（見下）。
- **階段**:第 2 階段 / S3×S4 串接。

## 結果（`tools/mesh_gen/validate_psd_to_award.py`，exit 0）

| 件 | 藝術家 verts/IoU | 生成 mode/verts/IoU | 達藝術家基準 | AC1(0.9) | 拓樸 |
|---|---|---|---|---|---|
| 光暈 | 78 / 0.9486 | v1 / 35 / 0.9331 | ✗(−1.55%) | ✅ | 乾淨 |
| 身體 | 98 / 0.9477 | v1 / 60 / 0.9660 | ✅ | ✅ | 乾淨 |
| 左手 | 80 / 0.9768 | v1 / 59 / 0.9642 | ✗(−1.26%) | ✅ | 乾淨 |

拓樸 = AC2a 重心在內 100% + AC2b 0 退化 + AC2c 0 孤兒（三件全過）。

## 關鍵發現

1. **座標系一致（geometry 角度的閉環）**:藝術家 mesh uvs 對三件全部以 `identity` 朝向（非翻轉）
   吻合 PSD 切件 alpha（校準時 4 朝向變體取最佳）→ **Award 藝術家 mesh uvs = 件本地 0..1 座標，
   與 PSD 切件同框**。這從**幾何**面再次確認 s4 的 texture-IoU 閉環（PSD↔spine↔atlas 同素材），
   且證明 atlas 的 `rotate:true` / 0.70 縮放只影響貼圖打包，**不改** JSON mesh uvs 的邏輯座標。

2. **v2 auto 對這三件全部回退 v1 Delaunay**（非 strip）:三件都是**團塊狀**（非細長 row-convex），
   `aspect>=1.2 且 row-convex` 條件不成立 → 走散點 Delaunay。
   → **strip 拓樸是給細長、承載逐頂點 deform 的件（窗簾/陰影）**；角色部件（團塊）走 v1。
   兩條路各有適用域，v2 的 auto 分流對真實件做出正確選擇。

3. **輪廓覆蓋率貼近藝術家、頂點更省**:生成件 IoU 在藝術家 ±1.5% 內，卻用 35–60 頂點
   （藝術家 78–98），全數過固定 0.9 門檻。身體甚至超越藝術家基準。

## 誠實的範圍限制（重要）

- Award 這 5 件（含 3 mesh）**無 deform timeline**：mesh 靠**骨骼綁定 + 權重**變形，
  不是逐頂點 `deform`。因此 main_draw 用的**真實位移場轉移閘**（硬約束）在此**沒有 ground truth 可跑**。
- 故本輪只對這三件宣稱**靜態輪廓 + 拓樸**達標，**不**宣稱逐頂點 deform 穩健。
- 合成 stress 場已知未校準（前有 miscalibration 教訓），**不**拿來當這些件的 pass/fail。
- **逐頂點 deform 穩健仍只在 main_draw 4 mesh（curtain/shadow）被真值驗過**（v2 strip 通用）。

## 可重現

```
python3 tools/mesh_gen/validate_psd_to_award.py        # exit 0；印三件對照表
```
（來源:`assets/robot_parts.psd` + `assets/Award.json`，皆已在 repo。）

## 下一步候選

- 若要驗 weighted/bone-driven 變形穩健,需能重現 Award 的骨骼綁定 + 權重（S5 骨架 + weighted mesh 讀取）,
  或改以有 deform timeline 的真實 mesh 當標的 → 目前唯 main_draw 4 mesh 具備。
- 把「件→Spine attachment」命名/尺寸慣例（`PSD名/圖層名` + size+2px + mesh/region 分配 + atlas 0.70）
  固化成 SkelToJson 組裝工具，端到端產出 Spine JSON（PLAN 的 S3 SkelToJson 一環）。
