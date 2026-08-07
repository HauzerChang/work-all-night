# S3 生成 mesh vs Award 真實生產 mesh(端到端 PSD→件→mesh 對真值驗收)

- **結論**:對機器人拆件 3 個在 Award 為 **mesh** 的件(光暈/左手/身體),用 atlas 切出的真實 alpha
  跑 `generate_mesh`(v1 Delaunay),與 Award **藝術家手做 mesh** 做靜態 IoU 對照。**在對齊藝術家頂點預算下,
  生成 mesh 的靜態覆蓋率 3 件全 ≥ 藝術家**。這是 S3 第一次對「真實生產 mesh」有真值的端到端驗收。
- **信心**:高(真實生產 spine ground truth + 評估器先以藝術家自身 IoU 為基準,非武斷 0.95)。
- **階段**:第 2 階段 / S3 × S4 串接(端到端 PSD→件→mesh)。

## 對照結果(atlas 切件 alpha 為來源;`--gen v1 --epsilon 0.0015`)

| 件 | 藝術家 IoU | 藝術家頂點 | 生成 IoU | 生成頂點 | overall_pass |
|---|---|---|---|---|---|
| 機器人拆件/光暈 | 0.9795 | 78 | **0.9882** | 82 | ✅ |
| 機器人拆件/左手 | 0.9681 | 80 | **0.9929** | 73 | ✅ |
| 機器人拆件/身體 | 0.9760 | 98 | **0.9930** | 81 | ✅ |

指令(可重現):
```
for pc in 光暈 左手 身體; do
  python3 tools/mesh_gen/validate_against_real.py \
    --skeleton assets/Award.json --atlas assets/Award.atlas --png assets/Award.png \
    --slot "機器人拆件/$pc" --name "機器人拆件/$pc" --gen v1 --epsilon 0.0015
done
```

## 關鍵發現

### 1. 覆蓋率由「邊界取樣密度」決定,預設 epsilon 對大而軟邊的件太粗
光暈是大片羽化圓形 blob。預設 `epsilon_frac=0.008`(Douglas-Peucker)只得 14-gon hull → IoU 僅 0.929
(< 藝術家 0.980)。epsilon 掃描(光暈):

| eps | 0.008 | 0.004 | 0.002 | 0.0015 | 0.001 |
|---|---|---|---|---|---|
| hull | 14 | 22 | 38 | 48 | 58 |
| IoU | 0.930 | 0.966 | 0.983 | 0.988 | 0.992 |

- `eps=0.002` → 78 頂點(**恰好等於藝術家 78v**)、IoU 0.983 已超越藝術家 0.980 → 等預算下覆蓋率打平/超越。
- **`max_interior` 對 IoU 無影響**(40→80 同 IoU),再次確認先前結論:**覆蓋率由 hull/邊界取樣決定,內部點只影響變形品質不影響覆蓋**。
- 建議:對大而軟邊的件把 v1 epsilon 降到 0.0015~0.002;已把 `--epsilon` 開成 `validate_against_real.py` 參數。

### 2. 這 3 件是 weighted mesh 且**無 deform timeline** → 變形靠骨骼權重,不能用逐頂點 deform 閘
`Award.json` 中光暈/左手/身體皆 `weighted=True`,且 9... 12 支動畫**無任何 deform timeline**
(變形來自 bone transform × 權重,非 `DeformTimeline`)。
- 陷阱:`de.real_deform_field` 對「無 deform frame」回傳**零位移場**,套用後幾何必然「乾淨」→ **假性通過**。
- 修正:`validate_against_real.py` 偵測 `frame is None` → 把 deform 閘標為 `applicable: false`
  (reason: no deform timeline / bone-weighted),`overall_pass` **只採信靜態 IoU**,不讓零場假性通過。

## 限制 / 待辦(誠實記錄)

- 本次只驗**靜態覆蓋率**。靜態 IoU 可靠加邊界點無限逼近 → 真正的品質差異在**變形下的平滑度與權重綁定**,
  這 3 件的變形是 **bone-weighted**,本專案尚未重現「骨骼姿勢 × 權重」蒙皮,故變形品質**尚未對這類件驗**。
  → 下一候選:實作 weighted-mesh 骨骼蒙皮重現(讀 bones 階層 + 動畫 bone timeline → 世界變換 → 權重混合),
    對這 3 件做真實 bone-driven 變形的自交/翻面閘,才算完整對齊藝術家取捨(藝術家用較少頂點換蒙皮平滑)。
- 來源用 atlas 切件(S4 已證 atlas 切件 ⇄ PSD 切件 alpha-IoU 0.92~0.99 為同素材),故等同「PSD→件→mesh」;
  未直接用 PSD 切件避免跨解析度 / 0.70 縮放對齊噪音。
