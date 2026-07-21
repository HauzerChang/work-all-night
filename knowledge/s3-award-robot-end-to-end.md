# S3 端到端:PSD 切件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把「PSD→件→S3 mesh」串到底,對真實生產標的(`Award` 機器人拆件的 3 個 mesh:
  光暈/身體/左手)做驗收。**靜態公平閘(覆蓋率 IoU + 頂點預算 + 拓樸)三件全過藝術家基準**;
  過程揭示兩個重要真相(下)。
- **信心**:高(對真實生產 spine ground truth 逐件對照 + 評估器公平性自檢 + main_draw 無回歸)。
- **階段**:第 2 階段 / S3 × S4 串接(里程碑:S3 首次對「非窗簾類」真實生產 mesh 驗收)。

## 做法(可重現)

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts     # 切件
python3 tools/mesh_gen/compare_to_real_mesh.py --skeleton assets/Award.json \
        --piece /tmp/robot_parts/00_光暈.png --slot 機器人拆件/光暈 --gen v2       # 對照真值
# 身體 03_身體.png / 左手 04_左手.png 同法
```

`compare_to_real_mesh.py`(本次新增):件 PNG → `generate_mesh_v2` → 對照 spine 真實 mesh 的
**靜態覆蓋率 IoU**(以 uvs×W,H 填三角,unweighted/weighted 皆可算)+ **頂點預算**(≤ 真實頂點數)
+ 拓樸格式。並自動判定真實 mesh 是否 weighted、有無 deform timeline,標示 deform 閘是否適用。

## ★ 真相一:Award 機器人 mesh 是 **weighted / 骨骼驅動**,與 main_draw 窗簾**不同類**

| | main_draw 窗簾/陰影 | Award 機器人拆件(光暈/身體/左手) |
|---|---|---|
| mesh 型態 | **unweighted**(vertices = 2×頂點) | **weighted**(vertices 變長格式:570/738/556 vals) |
| 變形驅動 | 逐頂點 **deform** timeline(9 動畫全有) | **0 deform timeline** → 靠**骨骼+權重** warp |
| 適用的 deform 閘 | ✅ 真實位移場轉移(`validate_against_real`) | ❌ 不適用(見真相二) |

→ S3 目前只生成 **unweighted 幾何**;要完全對上這類生產件,還缺 **BBW 權重生成**(S3 路線圖既有項)。
本次驗收=**幾何 ✓、skinning ✗**;權重生成是下一個 S3 缺口。

## ★ 真相二:curtain 位移場轉移對「骨骼驅動件」是**跨域不適用**(第 4 次評估器校準教訓)

初版把 main_draw `curtain_left` 的真實位移場轉移到機器人件當 deform 閘 → 左手 si=10/flips=3「失敗」。
**但這不公平**:(1) 機器人件是 weighted,連藝術家真值 mesh 都**無法**套 `transfer_deform_check`
(vertices 是變長 weighted 格式,`s=column_stack(v[0::2],v[1::2])` 直接壞掉);
(2) 把窗簾的**垂直大拉伸**場套到手部,根本不代表其生產變形(它在 Award 無 deform、只被骨骼帶)。
→ **對無 deform timeline 的 weighted 件,deform 閘不成立**;公平閘只有靜態覆蓋率+預算+拓樸。
`compare_to_real_mesh` 已把 `deform_gate_applies` 自動設 False,避免重犯
(前三次:合成 stress_field、composite 白底、atlas derotate 方向)。

## 靜態公平閘結果(對藝術家真值)

| 件 | 生成(v2) | IoU | 藝術家基準 IoU | 真實頂點 | 預算 | 判定 |
|---|---|---|---|---|---|---|
| 光暈 | 44v (delaunay-v1-fine) | **0.9606** | 0.9486 | 78 | ≤78 | ✅ |
| 身體 | 69v (delaunay-v1-fine) | **0.9828** | 0.9477 | 98 | ≤98 | ✅ |
| 左手 | 70v (delaunay-v1-fine) | **0.9796** | 0.9768 | 80 | ≤80 | ✅ |

## 修正:v2 的 Delaunay 回退 epsilon 自適應(本次 code 變更)

- 機器人件是 blobby(長寬比低、非 row-convex)→ v2 `auto` 正確**不選 strip**,回退 Delaunay。
- 但回退用的預設 `epsilon_frac=0.008`(為窗簾調)對**大型 compact 件邊界取樣過疏**:
  光暈 0.9331 / 左手 0.9642 都略低於藝術家基準。
- sweep 確認:`epsilon_frac=0.004` → 3 件全過基準且仍在頂點預算內(光暈 44v/左手 70v)。
- 已改 `generate_mesh_v2` 回退路徑用 `epsilon_frac=0.004`(mode 標 `delaunay-v1-fine`)。
  **不動 v1 預設**,故 `--gen v1` 與既有 curtain(走 strip)零回歸:main_draw 4 mesh 重驗全 `overall_pass`。

## 拓樸權衡(此次量化,對 blobby 件)

- **v1 散點 Delaunay**:靜態 IoU 高(邊界貼合輪廓);但大單向拉伸下易自交(不適合 deform-driven)。
- **strip 規則格點**:任意大變形下乾淨(si=0);但對 blobby 件靜態 IoU 只 0.85–0.94(頂/底平帽、
  逐列線性邊界漏曲率)→ 不該用於 compact 件。
- 對「無 deform、骨骼驅動」的 compact 件:**選 Delaunay-fine 追求靜態貼合**是對的
  (變形安全由骨骼權重負責,不靠拓樸)。v2 `auto` 的選路邏輯與此一致。

## 下一步(見 STATE)

1. **S3 權重生成(BBW)**:對這類 weighted 生產件補上 skinning,才算幾何+skinning 全端到端。
2. 把「件→Spine attachment」命名/尺寸慣例(`PSD名/圖層名`、+2px、mesh vs region 分配)固化成
   SkelToJson 寫出工具(候選 #2)。
