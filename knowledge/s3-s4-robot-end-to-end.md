# S3+S4 端到端:PSD 件 → S3 mesh 對真實生產 mesh 驗收(里程碑)

- **結論**:`robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手)經 `generate_mesh_v2(auto)`
  自動生成的 mesh,**IoU 全部達到並超過 Award 生產 spine 藝術家 mesh 的覆蓋率基準**,
  且 rest-pose 0 自交/0 翻面/索引合法。**「PSD→件→mesh」端到端對真實標的驗收通過。**
- **依據**:`tools/mesh_gen/compare_robot_mesh.py`(可重跑);圖 `figures/robot_mesh_compare.png`。
- **信心**:高(對照真實生產 spine 的藝術家 mesh 做外部真值 IoU;非自洽測試)。
- **階段**:S3(mesh 生成)× S4(PSD 切件)整合。

## 量化結果(atlas region alpha,已 CW derotate)

| 件 | 藝術家 mesh | 藝術家 IoU 基準 | 生成 mode | 生成頂點(hull) | 生成 IoU | 判定 |
|---|---|---|---|---|---|---|
| 光暈 | 78v 扇形(hull=78) | 0.9795 | delaunay-v1 | 82(hull 48) | **0.9882** | PASS |
| 身體 | 98v weighted | 0.9760 | delaunay-v1 | 70(hull 30) | **0.9868** | PASS |
| 左手 | 80v weighted | 0.9681 | delaunay-v1 | 61(hull 36) | **0.9884** | PASS |

- 3 件在 Award 皆 **無 deform**(靠骨骼權重/剛體移動),故本輪不做 deform 轉移閘(無藝術家真值可轉);
  改以 IoU 覆蓋率 + rest-pose 幾何(自交/翻面/索引)為 AC。deform 耐受已在 4 curtain/shadow mesh 驗過。
- 交叉:對 PSD 全解析度件也生成一次(來源不同),覆蓋率同量級(光暈 0.933→修正前、身體/左手 ~0.88~0.96),
  確認自動路由與覆蓋率不因來源崩;主判定以「與藝術家 mesh 同一 atlas region alpha」對齊為準。

## 關鍵發現:v1 邊界密度自適應(auto-epsilon)

- **首測光暈 FAIL**:固定 `epsilon_frac=0.008` 只給 **14 hull 點** → IoU 0.929 < 藝術家 0.98。
  身體/左手因輪廓較小/較折,固定 eps 剛好夠(0.968/0.960 過)。
- **根因**:IoU 受 **hull 取樣密度** 限制。這是 v2「IoU 由 rows 決定、cols 不影響」在 v1
  **邊界**上的對應 —— 大而平滑的輪廓(光暈)需要更多 hull 點才貼合。
- **eps 掃描**(光暈):eps 0.008→0.002→0.001 對應 hull 14→38→58、IoU 0.929→0.983→0.992。
- **修法(非特例化)**:新增 `auto_epsilon_frac()` —— 由「hull 多邊形填滿 vs mask 的 IoU」驅動,
  逐步縮小 eps 直到 hull 覆蓋率達 target(0.985)或 hull 達 max_hull(80)。
  `generate()` 預設 `epsilon_frac="auto"`。密度隨輪廓曲率自適應,不再是武斷常數。
- 自適應後 hull:光暈 48 / 身體 30 / 左手 36;curtain/shadow(走 v2 strip,不經此路徑)不受影響。

## 真實命名/結構慣例(承 s4-psd-to-spine-real)

- slot/attachment = `機器人拆件/<圖層名>`;3 mesh(光暈/身體/左手)+ 2 region(右手/頭)。
- atlas 貼圖縮小 ~0.70 打包;mesh uvs 為 **region 局部 0..1**(可直接 ×region W,H 對齊,
  無需 atlas-page 轉換 —— 修正 session 006 log 中「uvs 為 atlas UV」的臆測)。
- 光暈 mesh 為 **純扇形(hull=頂點數)**,無內部點 → 生成器的內部點對這類件冗餘(可後續按 hull/頂點比抑制)。

## 未竟 / 下一步

- 生成 mesh 為 **unweighted**;藝術家為 **weighted**(綁骨)。端到端到「可綁骨的 weighted mesh」
  仍缺 **自動權重(BBW)** 與 **骨架**(S5)。本輪只驗「拓樸/覆蓋率」層。
- 把 `機器人拆件/<圖層名>` + size+2px padding + mesh/region 分配 固化成「件→Spine JSON」組裝工具(SkelToJson)。
- 扇形/實心件可加「hull 佔比高 → 抑制內部點」啟發式,省頂點預算(光暈藝術家 0 內部點)。
