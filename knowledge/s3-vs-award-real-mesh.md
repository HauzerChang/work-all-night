# S3 端到端驗收 — PSD 件 → 生成 mesh 對照 Award 真實生產 mesh

- **結論**:用 `robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手,在生產 spine `Award` 中皆為 mesh),
  跑 `generate_mesh_v2`(auto),與 Award **真實藝術家 mesh** 做同一張 alpha、同一 fill 的覆蓋對比:
  **生成 mesh 的覆蓋 IoU 與藝術家真值相當(差距 ≤0.016),且用 45%~77% 的頂點數**。
  端到端「PSD→件→mesh」對真實生產標的驗收 **PASS**。
- **信心**:高(對真實生產 mesh 交叉比對 + flip 校準明確 + 軟邊發現有量化佐證)。
- **階段**:第 2 階段 / S3×S4 串接(里程碑:合成/自我驗證 → 對真實藝術家 mesh 比對)。

## 量化結果(`tools/mesh_gen/compare_award_mesh.py`)

| 件 | W×H | 真值頂點 | 真值 IoU | 真值 recall | 生成 mode | 生成頂點 | 生成 IoU | 生成 recall | 判定 |
|---|---|---|---|---|---|---|---|---|---|
| 光暈 | 706×683 | 78 | 0.949 | 0.959 | delaunay-v1 | **35** | 0.933 | 0.951 | PASS |
| 身體 | 379×425 | 98 | 0.948 | 0.961 | delaunay-v1 | **60** | **0.966** | 0.974 | PASS |
| 左手 | 257×215 | 80 | 0.977 | 0.997 | delaunay-v1 | **59** | 0.964 | 0.977 | PASS |

- 判準:**生成 IoU ≥ 藝術家真值 IoU − 0.03**(見下「為何不用固定 0.95」)。三件全過。
- 身體:生成(60v)IoU **反超**藝術家(98v)。頂點數全面較省。

## 關鍵發現

### 1. auto 模式對「blob 狀件」選 Delaunay-v1,不是 strip
三件長寬比 aspect(H/W)分別 0.97 / 1.12 / 0.84,皆 < 1.2 → `generate_mesh_v2` auto 回退 v1 Delaunay。
**strip 是窗簾(高瘦、單向拉伸)專屬**;一般機器人拆件(近方/塊狀)走 Delaunay 才對。
這些件在 Award **無 deform timeline**(靠骨骼權重變形),故「靜態覆蓋保真 + 頂點經濟」是對的軸,
不是 deform 耐受度 —— v1 先前的 deform 自交問題在此不適用。

### 2. ★ 評估器校準:固定 0.95 靜態 IoU 對「軟邊發光件」不可達(真值也達不到)
`evaluate_mesh` 的 `AC1_iou` 門檻 0.95 讓 **光暈 FAIL(0.933)**。但**藝術家自己的 78 頂點真實 mesh 也只有 0.949**,
同樣搆不太到 0.95。查因:光暈是徑向發光,**soft_ratio=0.236(23.6% 像素為半透明 8<a<247)**,
多邊形 hull 無論頂點多寡都無法把模糊邊界圍到 0.95 IoU。對照身體/左手 soft_ratio 僅 0.019/0.027(硬邊)→
輕鬆過 0.95。
- **修正判準**:軟邊件不用固定 0.95,改以**藝術家真實 mesh IoU 為可達上限**(或用 recall)。
  `compare_award_mesh.py` 即以「≥ 真值 − margin」判定 → 光暈 PASS。
- **教訓(延續前 3 次 miscalibration)**:固定閾值要先問「真值達得到嗎」;拿真實藝術家產物當上限最誠實。

### 3. 貼圖 v 慣例:flip=False(影像 top-down,無需翻轉)
真實 mesh uvs 為 region 局部 0..1;px=u·W、py=v·H(不翻)時 IoU 最大,與 `generate_mesh_v2`
自身 uv 慣例(uvs=y/H,y 由上而下)一致。三件一致 flip=False → 無歧義。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot
python3 tools/mesh_gen/compare_award_mesh.py --slices /tmp/robot --award assets/Award.json   # overall PASS
```

## 下一步候選

- 把「件→Spine attachment」慣例(`PSD名/圖層名`、size+2px、mesh/region 分配、uv 佈局)固化成
  SkelToJson 組裝工具,端到端寫出 Spine JSON(串起 S4 切圖 → S3 mesh → JSON)。
- 或補 S2 補圖閘 / 骨架閘(純 CPU)。
- `evaluate_mesh` AC1 可加「軟邊自適應」:soft_ratio 高時放寬 IoU 或改判 recall(本次已在
  compare 工具用真值上限規避,尚未回寫進 evaluate_mesh 本體以免影響既有 4-mesh 結論)。
