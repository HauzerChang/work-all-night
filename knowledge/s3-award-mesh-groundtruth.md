# S3 端到端驗收 — Award 真實 weighted mesh 對照 + v1 hull 自校準

- **里程碑**:第一次把 S3 mesh 生成器對「真實生產 spine 的 mesh」做 ground-truth 對照
  (先前 4-mesh 驗收用的是 main_draw 藝術家 mesh;此處換成另一支生產檔 `Award` 的機器人件)。
- **結論**:v1 Delaunay 的固定 `epsilon_frac=0.008` 對「大而柔邊」的件 hull 過疏 → 覆蓋率低於
  藝術家基準;改為**以自身覆蓋率為閘的自校準 hull 密度**後,3 件全數達標,且頂點數與藝術家相當
  (未過度細分)。main_draw 4 mesh 走 v2 strip,不受影響(全 overall_pass)。
- **信心**:高(對真實生產 mesh 交叉比對 + 藝術家自一致性先驗證評估器可信)。

## 對照標的(Award 機器人拆件,3 件 mesh)

`Award.json` 中 `機器人拆件/{光暈,身體,左手}` 為 **weighted mesh**(靠骨骼權重變形,
**無 deform timeline**);`右手`、`頭` 為 region。alpha 來源:Award atlas region
(多頁 Award2.png/Award.png,rotate=true → `atlas_crop` CW derotate)。

## 評估器可信度先驗(必要步驟)

比對前先重建**藝術家 mesh 自身**在同一 region frame 的覆蓋率(uvs×[W,H] 填三角 vs alpha):

| 件 | 藝術家 self-IoU | 藝術家 nv / hull |
|---|---|---|
| 光暈 | 0.9795 | 78 / 78 |
| 身體 | 0.9760 | 98 / 40 |
| 左手 | 0.9681 | 80 / 42 |

三者一致落在 0.97–0.98(非 1.0:hull 為多邊形近似 + 邊緣羽化殘差)→ **frame 對齊
(derotate 方向 + region-local uvs)正確、評估器可信**,才據此判定生成 mesh。

## 發現:固定 epsilon 對柔邊件 hull 過疏(epsilon 掃描,對 alpha 覆蓋率)

| eps | 光暈 IoU | 身體 IoU | 左手 IoU |
|---|---|---|---|
| 0.008(舊預設) | 0.927 ✗ | 0.969 ✗ | 0.960 ✗ |
| 0.004 | 0.962 ✗ | 0.986 ✓ | 0.982 ✓ |
| **0.002** | **0.983 ✓** | **0.993 ✓** | **0.991 ✓** |
| 0.001 | 0.992 | 0.995 | 0.996 |
| 0.0005 | 0.996(nv 175) | 1.000(nv 311) | 1.000(nv 292) |

- **覆蓋率由 hull 密度(epsilon)決定**;eps 越小 hull 越密、IoU 越高,但 nv 爆增(過細分)。
- eps=0.002 是**與藝術家等值的甜蜜點**:3 件全過基準,nv(97–103)≈ 藝術家(78–98),不過度細分。
- 光暈(大柔邊 radial glow)最吃 hull 密度:0.008 時 hull 僅 14、藝術家用 78。

## 修正:v1 自校準 hull 密度(`generate_mesh.generate`)

從粗 epsilon(0.008)起,每輪以 `mesh_self_iou`(重建覆蓋率 vs 自身 alpha,**無需外部真值**)
為閘,未達 `target_iou`(預設 0.985)且 nv < `vertex_cap`(預設 140)就把 epsilon 減半,
最多 6 輪。`target_iou=None` 還原單發舊行為(向後相容)。

自校準結果(auto,預設 min_dist=14/max_interior=40):

| 件 | 生成 IoU | 生成 nv / hull | 藝術家 IoU / nv | PASS |
|---|---|---|---|---|
| 光暈 | 0.9924 | 92 / 58 | 0.9795 / 78 | ✓ |
| 身體 | 0.9858 | 69 / 29 | 0.9760 / 98 | ✓ |
| 左手 | 0.9913 | 67 / 43 | 0.9681 / 80 | ✓ |

自校準各件停在不同 epsilon(hull 58/29/43)—— 光暈需最密 hull,身體/左手較疏,正是想要的
**依件柔硬度自適應**行為。

## 誠實限制

- 這 3 件在 Award **無 deform timeline**(weighted、骨骼驅動),故**無法跑真實 deform 轉移閘**;
  本次為**靜態拓樸/覆蓋率**對照。deform 耐受度結論仍以 main_draw 4-mesh(有 deform)為準。
- 覆蓋率閘不保證內部三角分佈對變形最佳;weighted 綁定(骨權)本工具尚未生成(生成的是 unweighted)。

## 可重現

```
# 依賴 assets/Award.{json,atlas,png,2png};robot 件對照見本檔腳本邏輯
# 主要改動:tools/mesh_gen/generate_mesh.py generate() 加 target_iou/vertex_cap 自校準
python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot image/curtain_left --name image/curtain_left  # 回歸:仍 overall_pass
```

## 下一步

- 把「PSD名/圖層名 + size+2px padding + mesh/region 分配」慣例固化成 **SkelToJson 組裝工具**
  (端到端 PSD→件→mesh→Spine JSON attachment),用 Award 命名慣例當範本。
- weighted mesh 生成(骨權綁定,BBW)仍未做 —— 目前只生成 unweighted;真實生產件多為 weighted。
