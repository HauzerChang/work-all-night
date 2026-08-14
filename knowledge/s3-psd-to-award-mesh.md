# S3 端到端驗收 — PSD 件 → 生成 mesh → 對照 Award 真實 artist mesh

- **結論**:把 `robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手)跑 S3 生成器,與**真實生產
  spine `Award`** 裡對應的**藝術家手做 mesh**(ground truth)做**靜態 IoU 對照**。在公平共同遮罩下,
  S3 生成 mesh 的覆蓋率**達到甚至略勝藝術家**(eps=0.004 時 3/3 落在 artist ±1.4%,且頂點數更少),
  首次把「PSD→件→mesh」pipeline 對**人類藝術家標的**驗收通過。
- **信心**:高(真實生產 mesh 當真值 + UV→local 映射自檢 IoU 0.97 + PSD↔atlas 同素材佐證 + 視覺疊圖)。
- **階段**:第 2 階段 / S3×S4 串接(里程碑:S3 首度對 artist mesh 驗收)。
- **工具**:`tools/mesh_gen/compare_award_mesh.py`(可重現)。

## 對照結果(共同遮罩 = 真實 atlas region alpha)

| 件 | region 尺寸 | artist IoU (v) | 生成 IoU @default (v) | 生成 IoU @eps0.004 (v) | Δ@0.004 |
|---|---|---|---|---|---|
| 光暈 | 496×480 | 0.9795 (78) | 0.929 (54) | **0.9656 (61)** | −0.014 |
| 身體 | 267×299 | 0.976 (98) | 0.968 (61) | **0.9858 (69)** | +0.010 |
| 左手 | 181×152 | 0.9681 (80) | 0.960 (48) | **0.9816 (57)** | +0.014 |

- artist 全為 **weighted mesh**(骨骼/權重變形,**無 deform timeline**)→ 本驗收為**靜態覆蓋率**,
  不含逐頂點 deform 閘(deform 穩健性已於 main_draw 4 mesh 真實位移場轉移驗過)。
- 生成 mesh 頂點數(48–69)**低於**藝術家(78–98)卻覆蓋率相當/更高 → S3 拓樸效率不輸手做。

## ★ 兩個必記的方法論校正(evaluator/實驗設計)

### 1. Award JSON mesh `uvs` 是 **region 局部正規化 [0,1]**,不是 atlas page 正規化
- 一開始誤把 uvs 當 page 正規化(`u*pageW`)→ 落在整張 2040² 上,artist IoU 0.0–0.54(全錯)。
- 實測:uvs 範圍剛好 0..1 且 4 種翻轉中 **`(u*W, v*H)`**(v 原點在上、**與 atlas rotate 無關**)
  對 3 件 IoU 0.968–0.979,其餘翻轉 <0.77 → 確認。**Spine runtime 的 SkeletonJson 載入時才把
  局部 uv 乘進 atlas region 的 UV rect**;JSON 存的是局部值。weighted mesh 的 `vertices` 是權重格式
  (`[骨數,骨idx,bindX,bindY,w,...]`,變長),**不能當座標**,setup 形狀只能從 uvs 還原。
- 這也給了一個**免費的映射正確性自檢**:還原 mask 對真實 region alpha 的 IoU 應 ≥0.80(藝術家就建在這張上)。

### 2. 生成與評分必須用**同一張遮罩**(否則注入 ~5% 假性 gap)
- 初版在「PSD 切件(0.70 縮放前)」上生成 mesh,卻拿去對「atlas region alpha」評分。
  兩者羽化不同(PSD↔atlas alpha-IoU 0.92–0.99,差 ~5–8%)→ 生成 mesh 完美貼合 PSD 件,
  對 region 評分卻天花板 ~0.95,被誤讀為「生成器覆蓋不足」。
- **修正**:生成也改在**真實 region alpha** 上跑(藝術家用的同一張)。修正後 gap 從 −0.05 收到 −0.008
  (身體/左手)→ 證實先前 gap 是**實驗設計 confound,非生成器弱點**。PSD→件 連結另以 psd↔region
  IoU(0.946–0.980)獨立佐證同素材,不當評分基準。
- **教訓(累計第 N 次)**:先確認「比的是不是同一個東西」,再下生成器好壞的結論。

## 生成器特性發現(可執行的下一步改進)

- 預設 `epsilon_frac=0.008` 對**大面積、平滑、近圓**件(光暈 496×480)**過度簡化**成 14-gon
  → IoU 0.929。降到 0.004(22 hull)→ 0.966;0.002(38 hull)→ 0.983。身體/左手 預設即達標。
- epsilon_frac 雖對周長正規化,但平滑曲線「角點少」會被 approxPolyDP 收得太狠 → **大平滑件需較細取樣**。
- **建議下一 chunk**:給 v1 加**曲率/面積自適應 epsilon**(或依 hull 目標點數反解 epsilon),
  讓預設對「小strip件」與「大平滑件」都穩。**改預設前須對 main_draw 4 mesh + slicing 跑回歸**
  (本次未改任何共用檔,只新增 compare 工具,故無回歸風險)。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
python3 tools/mesh_gen/compare_award_mesh.py                     # 生成器 auto 預設(2/3 過)
python3 tools/mesh_gen/compare_award_mesh.py --eps 0.004 --fig knowledge/figures  # 3/3 過 + 疊圖
```

疊圖 `knowledge/figures/cmp_{光暈,身體,左手}.png`:綠=真實 region alpha、藍=artist mesh、
紅=生成 mesh;三者疊成紫色 = 高度吻合,僅邊緣細絲差異。
