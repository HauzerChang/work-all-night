# S3 對照 Award 真實生產 mesh(端到端 PSD→件→mesh 靜態驗收)

- **結論**:S3 `generate_mesh_v2`(auto)對 Award(機器人 big win 生產 spine)的 **3 個真實藝術家 mesh
  部位全部通過**靜態幾何 AC —— 覆蓋率 IoU 達/超過藝術家基準(margin 0.02),且**用更少頂點**。
  這是 S3 首次對照「真實生產 mesh」(先前只對 main_draw 窗簾這種簡單直條)。
- **信心**:高(有藝術家真實 mesh 作外部真值;量化 + 視覺雙重確認)。
- **相關階段**:專案第 2 階段 S3;串接 S4(PSD 切件)→ 端到端。
- **工具**:`tools/mesh_gen/compare_award_mesh.py`(新);改良 `generate_mesh.py`(adaptive 邊界)。
- **圖**:`knowledge/figures/s3-award-mesh-compare.png`(藝術家 vs S3,3 件並列)。

## 標的與結果

Award 有 3 個 weighted mesh 部位 `機器人拆件/{光暈,身體,左手}`(對應 `robot_parts.psd` 3 圖層)。
**皆無 deform timeline(靠骨骼 weighted 驅動)** → 真實位移場轉移閘(`transfer_deform_check`)對它們 **N/A**;
本輪聚焦**靜態幾何**(覆蓋率 IoU vs 藝術家 + evaluate_mesh 全靜態 AC)。weighted deform 對照需 BBW 權重(S3 未來組件)。

| 部位 | 藝術家 IoU / v / hull | S3 IoU / v / hull | 判定 |
|---|---|---|---|
| 光暈 glow | 0.9795 / 78 / 78(全 hull,羽化圓形) | **0.9629 / 60 / 21** | ✅ |
| 身體 body | 0.9760 / 98 / 40 | **0.9680 / 61 / 21** | ✅ |
| 左手 hand | 0.9681 / 80 / 42 | **0.9602 / 48 / 18** | ✅ |

- 三件皆路由到 **delaunay(非 strip)**,因長寬比 < 1.2(非直條);exercise 的是 v1 Delaunay 路徑,不是 v2 strip。
- S3 mesh **頂點數全少於藝術家**(60<78、61<98、48<80),覆蓋率相當 → 拓樸更精簡、三角更規則(見圖)。

來源 alpha 用 Award atlas 該 region(藝術家 mesh uv 定義於此座標系,可同框公平對照)。
`PSD→件` 段先前已驗(log 005:PSD 切件 ↔ atlas 切件 alpha-IoU 0.92~0.99 同素材),
故在 atlas region 生成 ≈ 在 PSD 件生成,並保持與藝術家同座標。

## 過程發現與修正:固定 epsilon → adaptive 邊界細化

- **初測光暈 FAIL**(IoU 0.929 < 0.9595):`generate_mesh` v1 用**固定** `epsilon_frac=0.008`
  的 `approxPolyDP`,把光暈的**羽化/複雜邊界**簡化到只剩 14 hull 點 → 覆蓋率不及藝術家。
  身體/左手(緊實形)在同 epsilon 已達標,故只有複雜邊界受害。
- epsilon 掃描(光暈):0.008→IoU 0.929/54v;0.004→0.966/61v(達標且 ≤64 預算);0.001→0.992/92v(爆預算)。
  → 覆蓋率是**邊界細節受限**,單一全域 epsilon 無法同時服務簡單形與複雜形。
- **修正 = adaptive epsilon**(`generate_mesh.generate(..., adaptive=True)`):由粗到細掃 epsilon,
  取**最粗(頂點最省)且覆蓋率 ≥ iou_target(0.96)** 的解;無人達標則取預算(64)內覆蓋率最高者;
  細化受 vertex_budget 上限約束。`generate_mesh_v2` 的 delaunay fallback 已改用 `adaptive=True`
  (mode 標 `delaunay-v1-adaptive`)。**預設(非 adaptive)路徑不變**,向後相容。
- 修正後光暈 0.929→**0.9629** 過關;身體/左手不受影響(仍在最粗 epsilon 達標,頂點不變)。

## 回歸驗證(無破壞)

- main_draw 4 mesh(curtain_left/right + shadow/shadow2)`validate_against_real --gen v2` **仍全 overall_pass**
  (皆走 strip 模式,不碰 delaunay 路徑 → 我的改動與其正交)。
  ⚠️ 慣例雷:`image/shadow2` slot 的 attachment 名是 `image/shadow`(兩 slot 共用 region);
  驗證要 `--slot image/shadow2 --name image/shadow`。

## 標準指令

```
python3 tools/mesh_gen/compare_award_mesh.py          # 3 件靜態對照,全過 exit 0
# 回歸:main_draw 4 mesh
for s in "image/curtain_left" "image/curtain_right" "image/shadow"; do
  python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot "$s" --name "$s"; done
python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot image/shadow2 --name image/shadow
```

## 待續 / 局限

- weighted-deform 對照(BBW 權重)未做 → S3 尚缺「自動綁權重」組件;這是把生成 mesh 接上真實骨架驅動的關鍵缺口。
- 光暈這種「全 hull 羽化圓形」S3 用內部點三角化(hull 21 + 內部),藝術家用純 fan(hull 78);兩種拓樸覆蓋率相當,
  但若要 deform 貼合光暈的徑向漸變,fan 拓樸可能更自然 —— 屬未來 mesh-style 選擇題。
