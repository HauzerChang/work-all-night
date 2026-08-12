# S3 端到端:PSD件 → 生成 mesh vs Award 藝術家真實 mesh

- **結論**:把 `robot_parts.psd` 切件後跑 `generate_mesh_v2`,與生產 spine `Award.json` 裡對應的
  **藝術家手做 mesh** 做同一件、同一張 alpha 的**輪廓覆蓋(IoU)對照**——S3 在**實心件上以更少頂點
  達到或超越藝術家水準**,在**軟邊/中空件(光暈)上略遜**。這是 candidate #1「PSD→件→mesh 對真實生產標的
  端到端驗收」的落地結果。
- **依據**:`tools/mesh_gen/compare_to_artist.py`(可重跑),見下方指令與數字。
- **信心**:高(對照真實生產 mesh;藝術家 mesh 輪廓由其 uv 還原,8 朝向皆判定 (0,0) 無旋轉 → 對映正確)。
- **相關階段**:第 2 階段 S3(mesh),銜接 S4(切圖)—— S3+S4 首次串成端到端對真實標的。

## 標準指令

```
python tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o scratch/robot_parts
for f in 00_光暈 03_身體 04_左手; do
  python tools/mesh_gen/generate_mesh_v2.py scratch/robot_parts/$f.png -o scratch/robot_parts/${f}_mesh.json
done
python tools/mesh_gen/compare_to_artist.py --map 光暈=00_光暈 身體=03_身體 左手=04_左手
```

## 結果(2026-08-12)

| 件 | S3 verts | S3 IoU | 藝術家 verts(hull) | 藝術家 IoU | Δ(S3−藝術家) | S3/藝術家頂點比 |
|---|---|---|---|---|---|---|
| 身體 | 60 | **0.966** | 98 (40) | 0.9477 | **+0.018** | 0.61 |
| 左手 | 59 | 0.9642 | 80 (42) | 0.9743 | −0.010(打平) | 0.74 |
| 光暈 | 35 | 0.9331 | 78 (78) | 0.9478 | −0.015 | 0.45 |

- **身體:S3 覆蓋率勝過藝術家**,且只用 61% 頂點。**左手:與藝術家打平**(差 0.01 內)。
- **S3 平均只用藝術家 60% 的頂點**——生成 mesh 更精簡,實心件輪廓不吃虧。
- **光暈(軟邊光暈)是唯一明顯落後處**:藝術家用 `hull=78`(**全部頂點都在外周 = 環狀/中空拓樸**),
  S3 v1 delaunay 填成實心塊 → 對羽化外緣覆蓋較差。**下一步改進點:軟邊/中空件需環狀拓樸**(見待續)。

## 兩個關鍵發現

1. **評估器校準:0.95 固定 IoU 閘對軟邊件過嚴**。光暈連**藝術家自己的 mesh 也只有 0.9478**、
   身體藝術家 0.9477——皆 < 0.95。證明 `evaluate_mesh` 的 `iou_thresh=0.95` 是「魔術數字」,對羽化邊
   本就達不到。**正解:以藝術家 mesh 為相對基準(±0.01 判打平),而非固定絕對門檻**。
   延續本專案一貫教訓(gate 要對真值校準,別信未校準常數)。
2. **Award 無 deform timeline → 機器人 mesh 是 weighted 骨骼蒙皮,不是 deform 驅動**。
   `animations[*].deform` 全空;變形靠骨骼帶動 weighted 頂點。故本標的**不做 deform 閘**
   (RULES:不要用未校準 stress_field 假造)。deform 韌性仍由 main_draw 的 4 個 deform-driven mesh 負責。
   → **兩種 mesh 變形範式**:main_draw = deform-timeline(unweighted);Award = 骨骼蒙皮(weighted)。
   S3 目前產 unweighted,要對上 Award 範式需 S5 綁權重(超出本塊)。

## 方法備註(compare_to_artist.py)

- 藝術家 mesh 為 weighted,JSON 不存 setup 世界座標;用 `uv*(width,height)` 還原輪廓多邊形
  (mesh 宣告的 `width/height` = 原圖尺寸,實測 ≈ PSD 件 bbox,如 身體 381×427 vs 件 379×425)。
  uv→幾何在 setup pose 同形,故可比輪廓。取 8 朝向(rot90×flip)最佳,結果皆 (0,0) 佐證對映無旋轉。
- S3 為 unweighted,直接用本地像素座標填三角(同 evaluate_mesh AC1)。兩者對**同一張件 alpha**比 IoU,公平。

## 待續(下一個 bounded chunk 候選)

- **軟邊/中空件的環狀拓樸**:對 `hull==nv`(藝術家全周拓樸)或低填充比的件,S3 改用 ring/annulus
  生成(沿外/內輪廓各取一圈),預期把光暈拉到藝術家水準。可先加「是否中空」偵測(alpha 內部有洞)。
- **SkelToJson 組裝**:把 S3 mesh + S4 件命名慣例(`機器人拆件/<圖層名>` +2px padding)寫成 Spine JSON。
