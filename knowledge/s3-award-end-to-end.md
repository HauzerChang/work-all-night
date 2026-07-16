# S3+S4 端到端驗收 — 真實貼圖區 → S3 mesh → 對照 Award 藝術家 mesh

- **結論**：把 S3 mesh 生成器接到**真實生產標的**(Award 機器人拆件的 3 個 mesh 件)做端到端驗收，
  三件**全部 overall_pass**：生成 mesh 的靜態輪廓保真 ≥ 藝術家同件基準(margin 0.02 內)、頂點更精簡、
  0 孤兒/0 退化、Spine 格式合規。同時**揭露一個關鍵落差**:這些生產件是 **weighted mesh**,
  S3 目前只產 unweighted → 要貼近生產「變形」需補權重(BBW,未建)。
- **信心**：高(對真實生產 spine 的藝術家 mesh 為 ground truth;靜態量化 + 視覺疊圖雙驗;負向診斷+修正+回歸)。
- **階段**：第 2 階段 / S3+S4 串接(里程碑:合成→main_draw→**真實生產件**)。

## 驗收結果(atlas 真實貼圖區 alpha → generate_mesh_v2 → 對照)

| 件 | 藝術家 nv/tris/hull | 藝術家 weighted? | 藝術家 fill-IoU | S3 nv/mode | S3 fill-IoU | overall |
|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | 78 / 76 / 78 | ✅ 是 | 0.9795 | 61 / delaunay-v1 | **0.9656** | ✅ PASS |
| 機器人拆件/身體 | 98 / 154 / 40 | ✅ 是 | 0.9760 | 64 / delaunay-v1 | **0.9709** | ✅ PASS |
| 機器人拆件/左手 | 80 / 116 / 42 | ✅ 是 | 0.9681 | 61 / delaunay-v1 | **0.9884** | ✅ PASS |

- IoU 用 attachment 的 `uvs`(永遠 nv×2,weighted 也適用)映射到 atlas 裁切件像素框比對填滿覆蓋率。
- S3 三件頂點數(48–64)**都比藝術家精簡**(78–98)且達到相近或更高覆蓋率。
- 3 件 aspect < 1.2 → v2 auto 全走 v1(Delaunay);strip 模式在此不適用(非高瘦條狀)。
- 視覺疊圖:`knowledge/figures/s3-award-mesh-compare.png`(左=藝術家紅、右=S3 綠)。

## ★ 關鍵發現:生產 mesh 是 **weighted**(與 main_draw 本質不同)

- Award 這 3 件 `len(vertices) ≠ nv×2` → **weighted mesh**(骨骼蒙皮權重變形),且**無 per-vertex deform timeline**。
- 對比:main_draw 的 4 個 mesh 全 **unweighted**(靠 `deform` timeline 逐頂點變形)。
- **意涵**:兩種變形機制並存於真實資產。S3 目前只產 **unweighted** mesh(座標+uv+三角)。
  要真正逼近像 Award 這種**權重蒙皮**件的變形,需補 **BBW 權重**(S3 路線圖第三塊,尚未實作)。
- 本次驗收因此明確分層:**① 靜態輪廓 + ② 拓樸有效性** 已對真實件過關;
  **③ 蒙皮權重** 是下一個被真值點名的落差。

## 拓樸耐變形探測(非主閘,誠實標註)

- 這些件無 per-vertex deform → 無法用「件自身真實位移場」測。改**轉移 main_draw curtain_left 的真實位移場**
  作**最壞情況探測**:結果生成拓樸在該場下有自交/翻面。
- ⚠️ **這不是 fail**:curtain 的場是為高瘦窗簾校準的單向大拉伸,套到近方形的機器人件是 apples-to-oranges;
  且生產中這些件**根本不做逐頂點 deform**(靠骨骼剛體+權重)。故僅記錄,不列入 pass/fail。
- 真正該測的變形是「權重蒙皮下的骨骼驅動」,待 BBW 權重能力建立後才有對的 harness。

## 工具改進(本次)

### 1. `validate_against_award.py`(新)
端到端閘:atlas 切真實貼圖區 → generate_mesh_v2 → ①輪廓 IoU vs 藝術家 ②有效性(evaluate_mesh)
③頂點預算 ④Spine 格式 ⑤變形探測(轉移 curtain 場,標註為非主閘)。**能處理 weighted 目標 mesh**
(藝術家 IoU 走 `uvs`,不碰 weighted 的 `vertices`),補上 `validate_against_real.py` 對 weighted 會崩的空缺。

### 2. `generate_mesh.py` v1 → auto-refine epsilon
- **問題**:固定 `epsilon_frac=0.008`(佔周長比例)**不隨件大小/複雜度縮放**。大且凹的光暈
  (496×480,solidity 0.79)邊界嚴重欠取樣 → hull 只 14 點、IoU 0.929、且三角過濾產生 **1 個孤兒頂點**。
- **修法**:改為在**頂點預算內選「最細、0 孤兒」的邊界** —— 由粗到細掃 epsilon(0.008→0.002),
  取 nv≤budget 且 0 孤兒中最細者(在預算下最大化輪廓保真)。schedule 以舊值 0.008 為最粗 → 小件行為不變。
- **效果**:光暈 IoU 0.929→**0.966**、孤兒 1→**0**、nv 61≤64。
- **回歸**:main_draw 4 mesh(走 strip,不受影響)重驗全過;Award 3 件全過。

## 可重現

```
for p in 機器人拆件/光暈 機器人拆件/身體 機器人拆件/左手; do
  python3 tools/mesh_gen/validate_against_award.py --slot "$p" --gen v2 ; done   # 全 exit 0
# 回歸(main_draw 4 mesh;注意 shadow2 的 slot 用共用 region image/shadow):
python3 tools/mesh_gen/validate_against_real.py --slot image/shadow2 --name image/shadow --gen v2
```

## 附帶發現

- `validate_against_real.py` 假設 attachment 名 == atlas region 名;`image/shadow2` slot 的
  attachment/region 實為共用的 `image/shadow`(`path=None`),故驗 shadow2 需 `--slot image/shadow2 --name image/shadow`。
  已在此記錄(非 bug,是命名慣例)。

## 下一步

- **S3 BBW 權重**(被真值點名的最大落差):對生成的 unweighted mesh,依骨架綁定算 bounded biharmonic weights,
  產 weighted Spine mesh → 才能對照 Award 這類蒙皮件的「變形」而非只有靜態輪廓。需要骨架(S5)或先用 Award 現成骨綁定當輸入。
- 「件→Spine attachment 組裝」(SkelToJson):把 `PSD名/圖層名` + size+2px padding + mesh 段固化成寫檔工具,端到端產 Spine JSON。
