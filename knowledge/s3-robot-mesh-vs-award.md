# S3 端到端驗收：PSD件 → 生成 mesh → 對照真實生產 mesh（機器人拆件 / Award）

- **結論**：把 S3 mesh 生成器對「真實生產標的」驗收 —— 用機器人 3 件 mesh（光暈/身體/左手）
  的真實貼圖跑生成器，與 Award spine 內**藝術家手做的真實 mesh** 比對三角覆蓋 IoU。
  **自適應 hull 密度後 3 件全 PASS，且生成頂點數皆 ≤ 藝術家、覆蓋率追平或超越藝術家。**
- **信心**：高（真值 = 生產 spine 的實際 mesh；同一張真實貼圖上比對；含參數掃描根因診斷 + 主線無回歸）。
- **階段**：第 2 階段 / S3 收斂到真實標的（里程碑：從 main_draw 自家 mesh → 跨資產真實生產 mesh）。

## 與 main_draw 的關鍵差異

| | main_draw 4 mesh | Award 機器人 3 mesh |
|---|---|---|
| 權重 | **unweighted** | **weighted（骨骼驅動）** |
| 變形來源 | deform timeline（逐頂點） | 骨骼 + 權重（**無 deform timeline**） |
| 形狀 | 窗簾/陰影（長條/薄） | 光暈/身體/左手（blobby，aspect<1.2） |
| 驗收閘 | 靜態 IoU + **真實位移場轉移**（deform 穩健） | **靜態覆蓋 IoU**（無 deform timeline 可轉移） |
| v2 dispatch | strip（aspect≥1.2） | 全落 **delaunay-v1**（blobby） |

→ 逐頂點 deform 閘對 weighted/無 deform 的件**不適用**；改做「同一真實貼圖上的覆蓋率對照」。
工具：`tools/mesh_gen/validate_robot_mesh.py`（真值取自 `assets/Award.json`）。

## 主要發現

1. **覆蓋率由 hull 密度決定，interior 點幾乎無關**（再次印證 S3 定律「IoU 由 rows 決定、cols 不影響」）。
   對光暈掃描：`max_interior` 40 vs 60 → IoU 幾乎不變；`epsilon_frac`（Douglas-Peucker）才是主宰：

   | epsilon_frac | hull | verts | IoU |
   |---|---|---|---|
   | 0.008（舊預設） | 14 | 54 | 0.929 ✗ |
   | 0.005 | 21 | 60 | 0.963 |
   | 0.003 | 32 | 68 | 0.978（追平藝術家 0.980） |
   | 0.002 | 38 | 73 | 0.983（超越） |

2. **固定 `epsilon_frac=0.008` 對 soft/round 件取點太少 → 欠覆蓋**。該預設是在窗簾/陰影上調的
   （而那些其實走 v2 strip），對 blobby delaunay-v1 件過粗。藝術家對光暈**本人也用了 78 頂點**
   （超過既有 64 budget）→ 說明 **soft glow 的頂點預算 64 偏緊；預算應隨形狀複雜度**。

3. **修法（opt-in，不動主線）**：`generate_mesh.generate_adaptive(path, vertex_cap, iou_target)`
   從粗到細掃 epsilon，回傳「達 iou_target 的**最粗** hull」（頂點越少越好），但不超過 vertex_cap。
   只掃 hull（interior 對覆蓋無影響）。`generate_mesh.generate` 預設**完全不變** → main_draw v1/v2 無回歸。

## 驗收結果（`validate_robot_mesh.py --adaptive`，per-shape 預算 = 藝術家頂點數 +4）

| 件 | 生成 v / 藝術家 v | 生成 IoU / 藝術家 baseline | chosen ε | 判定 |
|---|---|---|---|---|
| 光暈 | 68 / 78 | 0.978 / 0.980 | 0.003 | PASS |
| 身體 | 68 / 98 | **0.983 / 0.976** | 0.005 | PASS |
| 左手 | 53 / 80 | **0.976 / 0.968** | 0.005 | PASS |

→ 自適應生成器用**比藝術家更少的頂點**達到相同或更好的覆蓋（身體 −30%、左手 −34% 頂點）。
非自適應（固定 ε=0.008）時光暈 fail（0.929）、身體/左手 pass —— 故自適應是收斂關鍵。

## 可重現

```bash
python3 tools/mesh_gen/validate_robot_mesh.py --adaptive   # 3 件全 PASS，exit 0
python3 tools/mesh_gen/validate_robot_mesh.py              # 固定 ε：光暈 fail（診斷用）
# 主線無回歸：
python3 tools/mesh_gen/validate_against_real.py --gen v1 --slot image/curtain_left --name image/curtain_left
python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot image/curtain_left --name image/curtain_left
```

## 未解 / 下一步

- **變形穩健未驗**：Award 這 3 件靠骨骼權重變形，repo 無其權重反解，逐頂點 deform 閘不適用。
  若要驗 weighted 件的變形穩健，需 BBW 權重生成器（S3 後段）+ 骨骼姿勢；屬另一 bounded chunk。
- 可把 `generate_adaptive` 接進 `generate_mesh_v2` 的 delaunay 分支作為 blobby 件預設（先確認不回歸 main_draw）。
- 端到端「PSD→件→mesh→Spine JSON 組裝（SkelToJson）」仍待固化（STATE 候選 2）。
