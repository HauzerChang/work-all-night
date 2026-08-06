# S3 端到端:PSD 件 → 生成 mesh → 對照 Award 真實 artist mesh

- **結論**:把 S4(PSD 切件)接上 S3(生成 mesh),對「真實生產 spine(Award)」的 3 個機器人
  mesh 件做覆蓋率對照。**修正生成器預設 `epsilon_frac` 0.008→0.004 後,3 件生成 mesh 的
  靜態 IoU 全部 ≥ artist 自身覆蓋率 baseline,且頂點數皆 ≤ artist**(更精簡)。
- **依據**:`tools/mesh_gen/validate_psd_to_mesh.py`(本次新增),真值 = `assets/Award.json` 的
  artist mesh(uvs/triangles);件來自 `assets/robot_parts.psd` 經 `psd_slice` 切出。
- **信心**:高(靜態覆蓋率有真值對照 + 無回歸驗證)。
- **相關階段**:第 2 階段 S3(mesh 生成)× S4(PSD 切件)端到端。

## 對照結果(eps=0.004)

| 件 | artist nv/hull | artist IoU | 生成 nv/hull/mode | 生成 IoU | 判定 |
|---|---|---|---|---|---|
| 機器人拆件/光暈 | 78 / 78 | 0.9486 | 44 / 25 / delaunay-v1 | 0.9606 | ✅ PASS |
| 機器人拆件/左手 | 80 / 42 | 0.9768 | 70 / 30 / delaunay-v1 | 0.9796 | ✅ PASS |
| 機器人拆件/身體 | 98 / 40 | 0.9477 | 69 / 29 / delaunay-v1 | 0.9828 | ✅ PASS |

## 關鍵發現

1. **Award 的機器人 mesh 全是 weighted(骨綁)mesh,且無 deform timeline**
   (`len(vertices) != len(uvs)`;光暈→骨 `4_LEG`、左手→`4_LEG5`、身體→`4_LEG3`)。
   → 它們的變形來自**骨權重 + 骨姿勢**,不是 deform 逐頂點偏移。
   → 為 unweighted+deform(窗簾/陰影)打造的 **`transfer_deform_check` 變形閘對這些件 N/A**。
   端到端只驗到「**切件 + 拓樸/覆蓋率**」這半;**變形正確性驗收缺 BBW 權重生成器**(S3 未建元件)。

2. **預設 `epsilon_frac=0.008` 對大件(數百 px)邊界取樣過粗** → hull 只 16–20 點,IoU 差
   artist ~1.3–1.5%。**降到 0.004**:hull 升到 25–30、IoU 全過 baseline,頂點數仍 < artist。
   佐證舊結論「IoU 由邊界取樣密度決定」。掃描:0.002/0.001 IoU 更高(0.98–0.99)但頂點暴增,
   0.004 是「過 artist baseline 且比 artist 精簡」的甜蜜點。

3. **無回歸**:0.008→0.004 只影響 v1 delaunay 路徑(v2 strip 用掃描線格點,與 epsilon 無關)。
   - v1 curtain_left:IoU 0.98→0.99,deform 仍乾淨(si=0/flips=0)。
   - v2 4-mesh:curtain_left/right、shadow 三件 overall_pass 不變。
     (`--name image/shadow2` 因 shadow2 與 shadow **共用同一 region**,region 查表落空 —
      屬既有工具 quirk,與本次改動無關。)

## 下一個槓桿(承接)

- **S3 缺口 = weighted(BBW)mesh 生成 + weighted 變形閘**。要對 Award 機器人 mesh 做「變形正確性」
  對照,需:(a) 生成骨權重(BBW / heat / bone-distance),(b) 讀 Award 骨姿勢驅動 weighted 變形後
  比幾何。這是把 S3 從「靜態覆蓋率」推到「真實骨綁變形」的關鍵一步。
- 現有 `deform_eval` 只支援 unweighted 逐頂點 offset;需擴 weighted 路徑(`[骨數,骨idx,bx,by,w,...]`
  攤平格式,見 CLAUDE.md 雷點 #6)。
