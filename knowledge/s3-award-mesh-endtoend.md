# S3 端到端:PSD/atlas 件 → 生成 mesh → 對照 Award 真實藝術家 mesh(幾何驗收)

- **結論**:對 Award 生產 spine 的 3 個機器人 mesh 件(光暈/身體/左手)用真實 atlas 貼圖跑
  S3 `generate_mesh_v2`,在同一局部幀與**藝術家真實 mesh** 做覆蓋率(coverage IoU)並排比對:
  **3 件生成 mesh 覆蓋率全 ≥ 藝術家基準,且頂點數全少於藝術家**(更精簡)。端到端
  「真實件 → 生成 mesh 對真實生產標的」幾何層**驗收通過**(`overall_pass=true`)。
- **信心**:高(對真實生產 mesh ground truth 交叉比對 + mapping 自我檢查 + 單一參數泛化 + 無回歸)。
- **階段**:第 2 階段 / S3(里程碑:從 main_draw 自身驗證 → 對「另一份真實生產 spine」的藝術家 mesh 驗收)。

## 量化結果(工具:`tools/mesh_gen/compare_gen_vs_artist.py`)

| 件 | 藝術家 verts/tri/hull | 藝術家 cov IoU | 生成 verts/tri/hull | 生成 cov IoU | 判定 |
|---|---|---|---|---|---|
| 光暈 | 78 / 76 / 78 | 0.9795 | 73 / 106 / 38 | **0.9832** | ✅ 覆蓋更高、更少頂點 |
| 身體 | 98 / 154 / 40 | 0.9760 | 77 / 115 / 37 | **0.9926** | ✅ |
| 左手 | 80 / 116 / 42 | 0.9681 | 67 / 89 / 43 | **0.9913** | ✅ |

- 3 件 aspect 皆 < 1.2 → v2 auto **回退 Delaunay(v1)**(非 strip;strip 只適高瘦拉伸件如窗簾)。
- 視覺對照圖:`knowledge/figures/s3-award-mesh-compare.png`(紅=藝術家、綠=生成)。

## 兩個關鍵發現(可寫進契約)

### 1. Spine mesh `uvs` 是「來源圖局部 [0,1]」,不是 atlas page 座標
初版誤把 mesh `uvs` 當 atlas page-space(`px = u*pageW - x`),藝術家自身覆蓋率崩到 **0.0~0.54**
→ 被 `mapping_ok`(藝術家對自身 alpha 覆蓋率應 ≥0.8)這個**自我檢查抓到**。實測 uvs 值域為
全頁 [0,1](左手 u∈[0.008,1.0]),證實是**該件來源圖的局部正規化座標**;runtime 的
`AtlasAttachmentLoader.updateUVs` 才在載入時 remap 進 atlas region。
→ 正解:藝術家與生成 mesh **同用去旋轉 upright 件圖**(`atlas_crop.extract`,方向已用 PSD 真值校 CW),
兩者都 `(u*W, v*H)` 映射。coverage IoU 對旋轉不變,徹底避開 derotate 方向 bug 類別。
**教訓延續**:每個外部映射都配一個「已知該高的量」當自我檢查,錯了立刻崩、當場抓到。

### 2. blob 件需比 strip/curtain 更密的邊界(v1_epsilon 0.008 → 0.002)
v1 預設 `epsilon_frac=0.008` 對不規則 blob(光暈這種柔邊光暈)hull 僅 14 點 → 覆蓋率 0.929
(內接多邊形恆低估凸弧)。epsilon 掃描(3 件一致單調):**0.002 為單一泛化值** —— 3 件覆蓋率
全 ≥ 藝術家且頂點仍少於藝術家。已設為 `generate_mesh_v2` **回退 Delaunay 路徑的預設**
(`v1_epsilon=0.002`);`generate_mesh`(v1)自身預設維持 0.008,不動已記錄的 main_draw v1 數據。
- 泛化證據(同一 0.002 對 3 件都過,非逐件調參);無回歸(main_draw curtain_left/shadow v2 strip 重驗仍 overall_pass)。

## ⚠️ 限界 / 下一個明確缺口(誠實記錄)

- 這 3 件在 Award 是 **weighted mesh 且 9 支動畫全無 deform timeline**(靠骨骼權重變形,非逐頂點 deform)。
  故本次**真實 deform 閘 N/A**(無真實位移場;依 RULES 拒絕用未校準合成場冒充)。
- S3 生成器產出 **unweighted** mesh;真實生產 mesh 是 **weighted**。幾何層(covering+拓樸)已驗收,
  但「**權重生成(BBW)+ 骨綁**」是端到端補完的**下一個明確缺口** → 對應 PLAN 的 S3「+BBW權重」子項。
- 藝術家頂點布局帶語義(身體在關節/彎折處加密以利權重形變);生成器目前靠 Canny+格點布點。
  weight-aware 布點是 BBW 階段要一起處理的(頂點該放哪 ↔ 骨骼在哪)。

## 可重現

```
python3 tools/mesh_gen/compare_gen_vs_artist.py            # 3 件全 overall_pass
python3 tools/mesh_gen/compare_gen_vs_artist.py --slot 機器人拆件/光暈
```
