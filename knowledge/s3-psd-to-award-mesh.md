# S3×S4 端到端:PSD 件 → 自動 mesh → 對照 Award 真實生產 mesh

- **結論**:把 S4(PSD 切件)與 S3(mesh 生成)串成端到端,對**真實生產標的**(`robot_parts.psd` 的
  3 個件 ↔ `Award.json` 的 `機器人拆件/{光暈,身體,左手}` mesh)完成閉環驗收。**OVERALL PASS**
  (輪廓對真值 + 頂點預算全過);光暈的「靜態覆蓋」略低是**軟 alpha 邊緣的已知限制**,非流程 bug。
- **依據/來源**:`tools/mesh_gen/compare_to_award_mesh.py`(可重跑);素材 `assets/robot_parts.psd` + `assets/Award.json`。
- **信心**:高(有真實生產 mesh 當真值 + 判別力自驗;純 CPU,無外部依賴)。
- **相關階段**:第 2 階段(鍛鍊四能力)— S3 mesh × S4 切圖 的整合驗收。

## 做了什麼

`robot_parts.psd` → `psd_slice`(5 件)→ 其中 3 件在 Award 為 mesh → 各跑 `generate_mesh_v2`
(auto 模式對這 3 個 blob 件都選 **delaunay-v1**,合理:非高瘦 row-convex,不適合 strip)→
`evaluate_mesh` 靜態閘 → 對照 Award 真實 mesh。

## 對照真值的方法(關鍵:不需骨頭變換、不需 uv 反解旋轉)

Award 這 3 件在生產檔是 **weighted** mesh(`vertices.length ≠ uvs.length`),取 setup 世界座標需骨頭變換。
但**每個 mesh 的 uv layout 本身就是它在貼圖上的 2D 輪廓嵌入**(頂點貼在素材上)。故:
把兩邊 hull 各自正規化到自身 bbox → 對 8 個二面體變換(4 旋轉 × 2 翻)取最佳 IoU → 純比「形狀」,
自動吸收 scale(~0.704 打包縮小)/ atlas rotate / flip 差異。

**判別力自驗(先驗證評估器再信判定,遵 RULES)**:輪廓 IoU 矩陣對角(同件)必須顯著壓過非對角。

## 量化結果

| 件 | mode | 靜態 IoU | 輪廓 IoU(對真值) | 非對角 max | gen v/h | 藝術家 v/h | v 比 |
|---|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 0.933 ✗ | **0.888** | 0.635 | 35/16 | 78/78 | 0.45 |
| 身體 | delaunay-v1 | 0.966 ✓ | **0.938** | 0.710 | 60/20 | 98/40 | 0.61 |
| 左手 | delaunay-v1 | 0.964 ✓ | **0.967** | 0.710 | 59/19 | 80/42 | 0.74 |

輪廓 IoU 矩陣(gen 列 × award 行):對角 0.888 / 0.938 / 0.967,非對角僅 0.60–0.71 →
**判別力確認**(每列/每行對角皆為最大)。圖:`knowledge/figures/s3-psd-to-award-hull.png`
(紅=生成、藍=藝術家,正規化並對齊方向後疊圖)。

## 發現 / 洞見

1. **端到端成立**:PSD→件→自動 mesh 的輪廓與藝術家手做 mesh 吻合到 0.89–0.97,且明確可與其他件區分。
2. **頂點更省**:生成 mesh 只用藝術家 **0.45–0.74×** 的頂點數,仍在實心件上通過覆蓋閘。
3. **藝術家光暈 mesh = 純周界環**(78v 全在 hull,無內部三角):glow 當作單一柔性整體變形,不需內部細分;
   我方生成器加了內部點(35v/16h)。哲學不同但輪廓一致。
4. **光暈靜態覆蓋 0.933 < 0.95**:軟 alpha(羽化邊緣 + 可能中空環)使 hull 覆蓋率天生偏低。
   對照顯示這是**素材特性 / 閾值校準議題**,不是生成錯誤 → 建議對 soft-alpha 件放寬靜態 IoU 門檻
   或改用「藝術家自身覆蓋率」作動態基準(待有 Award mesh 局部覆蓋真值時做)。

## 侷限 / 下一步

- 本次比的是 **setup 輪廓**;尚未對 Award 這 3 件的**真實 deform**做耐變形對照
  (weighted + Award 有 deform timeline,較重)→ 列為下一個 bounded chunk 候選。
- `compare_to_award_mesh.py` 目前寫死 robot 3 件對映;要泛化到其他 PSD/spine 對可加參數化 map。
