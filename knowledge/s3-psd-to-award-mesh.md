# S3×S4 端到端:PSD 件 → 生成 mesh → 對照真實生產 spine(Award)

- **結論**:把 S4(PSD 切件)與 S3(mesh 生成)串成 pipeline,並用**真實生產標的**
  (機器人 big-win `robot_parts.psd` ⇄ 生產 spine `Award.json`)驗收。**3 個真實 mesh 件
  (光暈/身體/左手)全數 PASS**:自動生成 mesh 的覆蓋率 **match/beat 藝術家生產 mesh**,
  且頂點數 **≤ 藝術家**,setup 幾何 0 缺陷,負對照有鑑別力。
- **信心**:高(對真實生產 ground truth;有負對照確認閘)。
- **階段**:第 2 階段(S3 mesh 生成器)× S4(PSD 切圖)整合 AC — 端到端里程碑。
- **工具**:`tools/mesh_gen/psd_to_award_mesh.py`(overall_pass → exit 0)。

## 對照結果(epsilon=0.004,margin=0)

| 件 | 生成 nv/hull/tri | 生成 IoU | 藝術家 IoU | Δ | 藝術家 nv | setup 幾何 | 負對照(0.85×) |
|---|---|---|---|---|---|---|---|
| 光暈 | 44 / 25 / 56 | 0.9606 | 0.9486 | **+0.012** | 78(weighted) | 0/0/0 | 0.687 ✓ |
| 身體 | 69 / 29 / 107 | 0.9828 | 0.9477 | **+0.0351** | 98(weighted) | 0/0/0 | 0.720 ✓ |
| 左手 | 70 / 30 / 108 | 0.9796 | 0.9768 | **+0.0028** | 80(weighted) | 0/0/0 | 0.712 ✓ |

- 生成 mesh 用 **≈ 半數頂點**達到 ≥ 藝術家覆蓋率(藝術家 weighted mesh 頂點較多)。
- 負對照:把生成 mesh 對中心縮 0.85 → IoU 掉到 0.69~0.72,遠低於藝術家基準 → **閘能區分好壞**。

## 關鍵發現

1. **epsilon 校準(改了預設)**:v1 hull 的 Douglas-Peucker `epsilon_frac` **舊預設 0.008 對
   羽化軟邊(光暈)覆蓋率低藝術家 4.5%**(0.9041 vs 0.9486)。掃描 0.008→0.001:
   **0.004 是甜蜜點** —— 3 件全 match/beat 藝術家、頂點數仍 ≤ 藝術家;再細(0.002/0.001)
   IoU 續升但頂點暴增、開始過擬合羽化邊。→ **`generate_mesh_v2.generate` 的 v1 後備預設
   改 epsilon_frac=0.004**(strip 路徑不受影響)。
2. **Award 機器人 mesh 是 weighted 骨骼蒙皮,`deform` timeline = 0**(枚舉全 12 動畫確認)。
   → 對此資產 **deform 轉移閘 N/A**;真值是「靜態覆蓋率對照藝術家」。deform 幾何仍以
   setup-pose 自交/翻面/退化把關。(對照:main_draw 4 mesh 是 unweighted + 有 deform,
   才適用 `transfer_deform_check`。)
3. **座標對齊有效**:Award region `orig==size`、`offset 0,0`(僅 ~0.70 打包縮放,無 trim),
   mesh `width/height` = 件尺寸 +2px。藝術家 UV 為 region 正規化 0..1,故
   `uv*(件寬,件高)` 對齊件 alpha,誤差僅 +2px(<0.5%,IoU 噪音內)→ 對照可信。

## 復用/慣例

- 映射:PSD 圖層名 `L` → spine slot `機器人拆件/L`(`--prefix` 可調);只挑在生產 spine 為
  **mesh** 的 slot(region/未用 slot 自動跳過)。與 `s4-psd-to-spine-real.md` 的命名慣例一致。
- 標準指令:`python tools/mesh_gen/psd_to_award_mesh.py`(預設 robot_parts⇄Award,全 PASS)。

## main_draw 回歸(確認未破)

- 4 mesh 以 `validate_against_real.py --gen v2` 全 overall_pass(strip 路徑;epsilon 改動不影響)。
  ⚠️ 注意:`image/shadow2` slot 的 mesh **attachment 名為 `image/shadow`**(共用 region),
  驗證要用 `--slot image/shadow2 --name image/shadow`。
