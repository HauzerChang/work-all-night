# S3 端到端驗收:生成 mesh vs Award 真實生產 mesh(有真值)

> 結論:**S3 生成器對真實生產 mesh 達到藝術家覆蓋率同級**(3/3 通過);過程校正一個 UV 誤解、
> 找到並修掉 v1 一個覆蓋率缺陷。信心:高(對照藝術家手做真值 + 自身覆蓋率為基準,非武斷門檻)。
> 相關階段:第 2 階段 S3 mesh。日期 2026-07-13。

## 做了什麼

把「PSD 件 → `generate_mesh_v2` → 對照 Award 真實 mesh」串成端到端閘,對照生產真值:
Award(big win spine)裡機器人有 3 件是**藝術家手做 weighted mesh**——`機器人拆件/{光暈,左手,身體}`。
用 `atlas_crop.extract` 取這 3 件去旋轉後的真實貼圖(atlas ~0.70 縮小),
把「生成 mesh 覆蓋率」與「藝術家 mesh 覆蓋率」放**同一張真實 alpha** 上比 IoU。

工具:`tools/mesh_gen/compare_generated_vs_award.py`(內建 sanity gate,見下)。

## 三個關鍵結論

### 1) 端到端通過(對真值)— 生成 mesh ≈ 藝術家,且更精簡
`epsilon=0.004` 下 3 件全過(pass = 生成 IoU ≥ 藝術家 IoU − 0.03):

| 件 | 生成 IoU | 藝術家 IoU | gap | 生成頂點 | 藝術家頂點 | 形狀 IoU(生成⇄藝術家) |
|---|---|---|---|---|---|---|
| 光暈 | 0.966 | 0.980 | −0.014 | 61 | 78 | 0.954 |
| 左手 | 0.982 | 0.968 | +0.014 | 57 | 80 | 0.964 |
| 身體 | 0.986 | 0.976 | +0.010 | 69 | 98 | 0.968 |

生成 mesh 用**比藝術家更少的頂點**達到同級或更高覆蓋率。3 件長寬比 <1.2 → v2 auto 回退 **v1(Delaunay)**。
視覺對照圖:`figures/s3-vs-award-robot-mesh.png`(綠=藝術家、橘=生成)。

### 2) 【校正 log 006】Award mesh uvs 是 **region 局部 0..1(y 向下)**,不是 atlas UV
log 006 記「Award mesh uvs 為 atlas UV,需先轉 region 局部」——**實測為誤**。
量測:uvs 的 u,v 幾乎鋪滿 [0,1] 且**不落在該 region 的 atlas box 內**(例:光暈 atlas box u≈0.32–0.59,
但 uvs u≈0.01–0.99)。直接 `px=u*W, py=v*H`、**不翻 y** 時,藝術家 mesh 對自身貼圖 IoU=0.97–0.98(翻 y 只有 0.44–0.61)。
→ Spine .json 的 mesh uvs 是相對「原始邏輯圖(未旋轉、未縮放)」的局部座標;旋轉/縮放/atlas 打包由 runtime 載入時處理。
**教訓**:先前那條假設從未被驗證(當時沒真的畫出來比),差點讓本次比較用錯基準(初版腳本就因此得到藝術家 IoU 0.0/0.49 的假低基準)。

### 3) 覆蓋率由 **hull 邊界密度(epsilon)** 決定,內部點無關 → 修 v1 預設 0.008→0.004
光暈初版 IoU 只有 0.929(< 藝術家 0.980)。掃描發現:

| epsilon | 光暈 hull | 光暈 IoU |
|---|---|---|
| 0.008(舊預設) | 14 | 0.930 |
| 0.004(新預設) | 22 | 0.966 |
| 0.002 | 38 | 0.983 |

`max_interior`(內部點)40→80 對 IoU **零影響**。這與 v2 strip「rows 決定 IoU、cols 不影響」完全同構:
**覆蓋率是邊界取樣密度的函數**。`epsilon_frac` 是周長的比例,大而圓滑的件(光暈周長大)× 0.008 = 絕對容差過大 → 切角 → 少覆蓋。
改 `generate_mesh.py` 預設 `epsilon_frac 0.008→0.004`:3 件全過,頂點仍 < 藝術家。
**回歸驗證**:main_draw 4 mesh 走 v2 strip(mode=strip 確認),不受此改動影響,重驗全 PASS。

## 評估器可信度(避免第四次 miscalibration)
`compare_generated_vs_award.py` 內建 **sanity gate**:若「藝術家 mesh 對自身貼圖 IoU < 0.90」直接拒絕出報告——
因為那代表 UV 解讀錯、基準不可信(初版就是這樣被擋下才發現 log 006 的誤解)。這是本專案第 N 次驗證「評估器本身要先自證可信」。

## 檔案
- `tools/mesh_gen/compare_generated_vs_award.py`(新;端到端閘 + sanity gate)
- `tools/mesh_gen/generate_mesh.py`(改預設 epsilon 0.008→0.004)
- `knowledge/figures/s3-vs-award-robot-mesh.png`(藝術家 vs 生成 線框對照)

## 待續
- 這 3 件是 **weighted** mesh(骨骼變形),本次只比**靜態覆蓋率**;deform 對照需重建 Award 骨骼權重變形場
  (現有 `deform_eval` 是 unweighted+deform timeline,不直接適用)→ 下一個候選課題。
- 把「件→Spine attachment(命名慣例 + size + 2px pad + 生成 mesh)」固化成 SkelToJson 寫出工具(S3+S4 串成端到端產檔)。
