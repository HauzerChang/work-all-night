# S3 端到端驗收：機器人件 → S3 mesh → 對照 Award 真實生產 mesh

- **結論**：把 Award(big win spine)3 個 mesh 件（機器人拆件 `光暈/身體/左手`）的真實 alpha
  餵給 S3 `generate_mesh_v2(mode=auto)`,對照 **藝術家真實 mesh** 做靜態覆蓋率/拓樸/精簡度,
  **3 件全 overall_pass**(里程碑:S3 首次對「跨資產、真實生產標的」端到端驗收成功)。
- **信心**:高(對真實生產 spine 的藝術家 mesh 交叉比對 + evaluate_mesh 全條 + 正常化 uv 對齊經 4 向翻轉負對照確認)。
- **階段**:第 2 階段 / S3 × S4 串接(PSD/atlas 切件 → S3 mesh → 真值對照)。
- **工具**:`tools/mesh_gen/validate_award_mesh.py`(新增)。指令 `python3 tools/mesh_gen/validate_award_mesh.py` → overall_pass。

## 對照結果(eps=0.003 預設 + orphan prune 後)

| 件 | crop(atlas,0.70縮) | 生成 nv/hull | 生成 IoU | 藝術家 nv/hull | 藝術家自身 IoU | cover/topo/budget |
|---|---|---|---|---|---|---|
| 光暈 | 496×480 | 68 / 32 | **0.9779** | 78 / 78(純邊界) | 0.9795 | ✅ ✅ ✅ |
| 身體 | 267×299 | 71 / 31 | **0.9876** | 98 / 40 | 0.9760 | ✅ ✅ ✅ |
| 左手 | 181×152 | 61 / 36 | **0.9884** | 80 / 42 | 0.9681 | ✅ ✅ ✅ |

覆蓋率 AC:生成 IoU ≥ 藝術家自身覆蓋率 − 0.03。生成頂點數 61~71,與藝術家 78~98 同量級(更精簡)。

## 兩個關鍵發現 / 修正(本次)

1. **v1 預設 epsilon 0.008 對「大件/軟邊件」邊界取樣太粗 → 覆蓋不足**(光暈只 0.929)。
   epsilon 掃描顯示覆蓋率**由邊界密度線性主導**:eps 0.008→0.004→0.002 時光暈 IoU 0.929→0.966→0.983。
   **改預設 0.008 → 0.003**:3 件 IoU 0.978~0.988、nv 61~71(近藝術家、仍精簡)。
   舊 0.008 只在 v2-strip 路徑(小窗簾)驗過,沒對大件驗過 → 這是「參數對小件過擬合」的盲點。
2. **v1 三角過濾後留下孤兒頂點(bug)**:`filter_triangles` 濾掉重心在 mask 外的三角後,
   其內部頂點變成未被引用的孤兒(光暈原有孤兒)。加 `prune_orphans()`:丟索引 ≥ n_hull 的未用頂點
   並重編三角索引(hull 前綴一律保留以維持 Spine『hull 排最前且連續』不變量)。

## ⚠️ deform 閘為何 N/A(誠實標記,非跳過)

這 3 件在 Award 是 **weighted mesh**(`len(vertices)!=len(uvs)`:光暈 570≠156、身體 738≠196、左手 556≠160)
**且 12 支動畫全部無 deform timeline 觸及這 3 slot**(已程式確認)。→ 它們靠**骨骼權重**變形,
非逐頂點 deform。S3 目前只產 unweighted 幾何、**BBW 權重尚未實作**,也沒有真實位移場可轉移
(RULES:別套未校準 stress_field)→ 本 chunk 只驗**靜態幾何/覆蓋率/精簡度**。
變形穩健性驗收仍由 main_draw 的 4 個 unweighted+有 deform mesh 負責(`validate_against_real.py --gen v2`)。

## uv 對齊(避免 atlas 旋轉/縮放踩雷)

Award mesh 的 `uvs` 是**件內 region-local 0..1**,與 `atlas_crop.extract`(CW derotate + 0.70 縮放後)
的 crop 方向一致 → 直接 `uv*[W,H]` 即可疊到件 alpha(4 向翻轉負對照:`none` IoU 0.97~0.98,
其餘翻轉 0.4~0.76 → 方向確認無誤)。

## 未竟 / 下一步

- **BBW 權重生成(S3 缺口)**:要讓生成 mesh 真的能替代 Award 這種 weighted mesh,需補骨骼綁定 + BBW 權重
  (SkelToJson 讀骨架 → 綁權重)。這是把「靜態幾何對齊」升級成「可動對齊」的關鍵,屬較大工作塊。
- **件→Spine JSON 組裝(SkelToJson 寫出)**:把 `<PSD名>/<圖層名>` 命名 + size+2px + mesh/region 分配
  固化成工具,端到端產 Spine attachment(見 s4-psd-to-spine-real.md 的真實慣例)。
