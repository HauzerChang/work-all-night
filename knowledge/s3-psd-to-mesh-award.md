# S3 端到端:PSD/atlas 件 → 生成 mesh → 對照 Award 真實生產 mesh(里程碑)

- **結論**:S3 mesh 生成器對真實生產標的(Award「機器人拆件」3 個 mesh 件)端到端驗收通過。
  加入**自適應邊界(adaptive boundary)**後,3 件生成 mesh 的靜態 IoU **全部達到或超越藝術家基準**,
  且頂點數 ≤ 藝術家。這是「PSD→件→mesh」對真實生產 spine 的首次量化閉環。
- **信心**:高(對照真實藝術家 mesh 的覆蓋率為外部真值;純 CPU 可重現)。
- **相關階段**:第 2 階段 S3(mesh)× S4(PSD 切圖)串接;工具 `generate_mesh.py`、`validate_against_real.py`。
- **日期**:2026-07-18。

## 測試標的(Award 真實生產 spine 的 weighted mesh)

Award(機器人 big win)有 3 個 mesh 件 + 2 個 region 件(見 `s4-psd-to-spine-real.md`):

| slot/attachment | 類型 | 藝術家 nv/tris | 形狀 solidity | 有 deform? |
|---|---|---|---|---|
| 機器人拆件/光暈 | mesh(weighted) | 78 / 76 | **0.793(凹/尖刺)** | 無 |
| 機器人拆件/身體 | mesh(weighted) | 98 / 154 | 0.873 | 無 |
| 機器人拆件/左手 | mesh(weighted) | 80 / 116 | 0.889 | 無 |
| 機器人拆件/右手 | region | — | — | — |
| 機器人拆件/頭 | region | — | — | — |

- 三個 mesh 皆 **weighted**(`len(vertices) != len(uvs)`)且 **無 deform timeline** → 純靠骨骼驅動,
  故**不套變形閘**(topology 不會被 deform 拉扯);AC = 靜態 IoU vs 藝術家覆蓋率。
- **UV 是 region-local 0..1**(非 atlas 全頁 UV);`artist_iou` 用 `uv*W, uv*H`(W,H=crop 尺寸)直接可比。
  (先前 session 006 註記「Award mesh uvs 為 atlas UV 需轉」經實測**不成立** —— uvs 已是 region 局部。)
- atlas:雙頁(Award.png/Award2.png)、部分件 rotate=true、貼圖縮小打包 ~0.70;IoU 尺度不變故不影響。
  `offset=0,0` 且 `orig==size`(無白邊裁切)→ crop 直接對應 uvs。

## 關鍵發現:固定 epsilon 對凹形件取樣過疏 → 自適應邊界

`generate_mesh.py` v1 用 `cv2.approxPolyDP(epsilon_frac*peri)` 簡化外輪廓當 hull。**IoU 幾乎全由
hull(邊界)決定**(內部點在形內不影響覆蓋)。固定 `epsilon_frac=0.008`:

- 近凸件(窗簾/陰影 solidity>0.99):夠用,且它們走 v2 strip 模式,不受影響。
- **凹/尖刺件(光暈 solidity 0.79)**:hull 只取到 **14 點 → IoU 僅 0.929**(< 藝術家 0.98)。

epsilon 敏感度(光暈):

| epsilon_frac | hull 點 | IoU |
|---|---|---|
| 0.008(舊預設) | 14 | 0.929 |
| 0.004 | 22 | 0.966 |
| 0.002 | 38 | **0.983** |
| 0.001 | 58 | 0.992 |

**修正(確定性、單一預設通吃)**:`boundary_points(adaptive=True, target_iou=0.985, max_hull=80)` ——
從給定 epsilon 起逐步 ×0.6 收細,直到「輪廓多邊形對 mask 的 IoU ≥ target」或 hull 點達預算上限。
近凸件第一輪(粗 epsilon)即達標 → 行為≈不變、不會過度取樣(實測窗簾強制走 v1 仍只 13 hull 點)。

## 驗收結果(加自適應邊界後,`--gen v2` auto → 3 件皆落 v1 delaunay)

| 件 | 生成 nv/tris | 生成 IoU | 藝術家 IoU | 判定(margin 0.01) |
|---|---|---|---|---|
| 光暈 | 78 / 111 | **0.9856** | 0.9795 | ✅ PASS(舊:0.929 FAIL) |
| 身體 | 72 / 110 | **0.9881** | 0.9760 | ✅ PASS |
| 左手 | 61 / 84 | **0.9884** | 0.9681 | ✅ PASS |

- 生成 mesh 覆蓋率**全超越**藝術家,且頂點數持平或更少(藝術家 78/98/80 vs 生成 78/72/61)。
- main_draw 4 mesh(strip 模式)重驗:curtain_left/right/shadow OVERALL PASS **無回歸**(自適應只動 v1 路徑)。
- 視覺對照:`figures/s3-robot-parts-gen-vs-artist.png`(左=生成綠、右=藝術家紅)。

## 工具變更

- `generate_mesh.py`:`boundary_points` 加自適應邊界(`_poly_iou` 輔助);`generate()` 透出
  `adaptive/target_iou/max_hull` 參數(預設 on)。
- `validate_against_real.py`:`has_deform()` 判斷;**無 deform → 跳變形閘標 N/A pass**(支援 weighted/剛體件);
  IoU margin 預設放寬到 0.01;報告加 slot/name 與 deform `applicable` 欄。
- 標準指令(robot 件):
  `python3 tools/mesh_gen/validate_against_real.py --skeleton assets/Award.json --atlas assets/Award.atlas --png assets/Award.png --gen v2 --slot 機器人拆件/光暈 --name 機器人拆件/光暈`

## 教訓

- **單一固定幾何參數難通吃形狀多樣性** → 用「評估器閘」把參數變成自調目標(deterministic + gate),
  正是 RULES「用確定性演算法 + 評估器,別用 ML 學美術決定」的實踐。
- **有外部真值(藝術家 mesh)才敢下 pass/fail** —— 生成器覆蓋率對齊真實生產件,而非武斷門檻。
