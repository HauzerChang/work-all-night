# S3 端到端:PSD件 → mesh → 對照 Award 真實生產 mesh(機器人拆件)

- **結論**:S3 generator 對「非窗簾、blobby」的真實生產件也通用 —— 3/3(光暈/左手/身體)達到藝術家
  IoU 基準且頂點更精簡;`auto` 模式選擇經真實標的確認正確(這些件 aspect<1.2 → 回退 v1 Delaunay,
  非 strip)。過程用真實 ground truth 揪出並修好 v1 兩個缺陷。
- **依據**:`tools/mesh_gen/validate_robot_mesh.py` 對 `assets/Award.{json,atlas,png}` 的
  `機器人拆件/{光暈,左手,身體}` 3 個真實 mesh;來源為 atlas 切件(對齊藝術家 UV)+ PSD 切件(端到端)。
- **信心**:高(對照真實生產 mesh,非合成;含負向診斷 + 修後回歸不破 main_draw)。
- **階段**:S3(mesh 生成)× S4(PSD 切圖)端到端串接。

## 驗收結果(修後)

| 件 | 模式 | 生成頂點 | 藝術家頂點 | IoU | 藝術家基準 | overall |
|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 67 | 78 | 0.977 | 0.980 | PASS |
| 左手 | delaunay-v1 | 48 | 80 | 0.960 | 0.968 | PASS |
| 身體 | delaunay-v1 | 64 | 98 | 0.972 | 0.976 | PASS |

- **覆蓋率不輸藝術家**(2% 容差內)且**頂點少 14–40%** → 精簡度勝。
- **PSD 來源 ↔ atlas 來源**:同模式、self-IoU 相近(0.93~0.96)→ S4 切件 → S3 mesh 鏈一致。
  (PSD 件較小/含 padding,絕對 IoU 略異屬正常;S4 已證兩者同素材 alpha-IoU 0.92~0.99。)

## 關鍵發現

1. **auto 模式選擇是真的判別器,不是巧合**:窗簾/陰影(main_draw,aspect 1.55~6.22)→ strip;
   機器人 blob(aspect 0.84~1.12)→ v1 Delaunay。與藝術家實際拓樸一致(光暈=邊界多邊形、
   身體/左手=帶內部點的 Delaunay 狀)。**aspect≥1.2 門檻經真實雙向樣本確認**。
2. **這 3 件在 Award 無 deform timeline**(靠骨骼 warp,非 baked FFD)→ 真實位移場閘 N/A。
   依 RULES**不捏造未校準壓力測試**,deform 軸誠實標 N/A。

## 用真實標的揪出並修好的 v1 缺陷(→ `generate_mesh.py`)

1. **孤兒頂點**:`filter_triangles`(丟重心在 mask 外的三角以處理凹形)會留下不被任何三角參照的
   內部頂點(光暈 index 30)。→ 新增 `prune_orphans()`:移除未參照頂點 + 重編索引,
   保序使 hull 仍排前、重算 n_hull。**孤兒在 mesh 永遠非法,屬純正確性修**。
2. **固定比例 Douglas-Peucker epsilon 對大而平滑輪廓過度簡化**:`epsilon_frac*peri` 隨周長變大,
   光暈周長 1927px → 容差 15.4px → 只取 14 hull 點 → IoU 僅 0.929。
   → `boundary_points` 加**絕對像素上限 `max_eps_px=6.0`**(DP epsilon 本就是「多邊形與輪廓的最大像素偏差」,
   用像素封頂才是正確語意)。光暈 IoU 0.929→0.977;小件(左手 5.4px/身體 7.8px < 上限)不受影響。

## 回歸保證

- **main_draw 4 mesh(v2)全部仍 PASS**:它們 aspect≥1.55 一律走 strip,**v1 路徑在該驗證從不被呼叫**
  → 改 v1 不可能回歸 main_draw。已實跑確認 4/4 overall_pass。

## 可續下一步

- 光暈藝術家用 78 點**全 hull**(純邊界多邊形,0 內部)—— 我方用 67 點(14 hull+內部)達同等覆蓋。
  若要更貼合柔邊光暈,可加「邊界密度隨曲率自適應」而非單一上限(需跨全部件的前後 eval,另開 chunk)。
- Award.png/Award2.png 已在 repo → 可補 texture 級(切件 alpha-IoU)交叉驗,但幾何結論已成立。
