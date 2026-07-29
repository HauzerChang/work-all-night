# S3 端到端驗收 — 件 alpha → 生成 mesh → 對照 Award 真實生產 mesh(有真值)

- **結論**:把 S4(切件)＋ S3(生成 mesh)串成端到端,並用**真實生產 spine(Award)的 mesh 當 ground
  truth**,對機器人拆件 3 個 mesh 件(光暈 / 身體 / 左手)驗收 **全 PASS**:生成 mesh 的 alpha 覆蓋 IoU
  **超越藝術家真實 mesh**,且**用更少頂點**、同一 synthetic stress 下自交/翻面不劣於藝術家。
- **信心**:高(對真實生產標的、有藝術家 mesh 真值交叉比對;主結論由參數掃描重現)。
- **階段**:第 2 階段 / S3+S4 端到端(里程碑:從「對 main_draw 自產 mesh 驗收」→「對真實生產 mesh 對標」)。

## 驗收數據(`validate_psd_to_mesh.py`,epsilon=0.002)

| 件 | 生成 nv/hull/tris | 藝術家 nv/hull/tris | IoU 生成 | IoU 藝術家 | 頂點 | stress 自交(gen/art) |
|---|---|---|---|---|---|---|
| 光暈 | 73 / 38 / 106 | 78 / **78** / 76 | **0.9832** | 0.9795 | 少 5 | 0 / 0 |
| 身體 | 77 / 37 / 115 | 98 / 40 / 154 | **0.9926** | 0.9760 | 少 21 | 0 / 0 |
| 左手 | 67 / 43 / 89 | 80 / 42 / 116 | **0.9913** | 0.9681 | 少 13 | 0 / 0 |

- 3 件皆非 strip(近正方,aspect<1.2)→ v2 auto **正確回退 Delaunay(v1)**;結果證明 v1 路徑對真實
  剛性件(靠骨骼權重變形)已足夠。
- 藝術家 **光暈 mesh 為純邊界 fan(78 hull of 78v,0 內部點)**;身體/左手為 hull+內部混合。生成器用
  「hull + 內部格點」拓樸即以更少頂點達更高覆蓋。

## ★ 關鍵發現:Delaunay 覆蓋率由 hull 邊界密度(epsilon)決定,內部點(max_interior)不影響

參數掃描(光暈,mask 平滑羽化邊):

| epsilon | hull 點 | IoU | max_interior 40/60/80 對 IoU |
|---|---|---|---|
| 0.008(舊預設) | 14 | 0.930 | 三者皆 ~0.93(**不變**) |
| 0.004 | 22 | 0.966 | 不變 |
| 0.002 | 38 | 0.983 | 不變 |
| 0.001 | 58 | 0.992 | 不變 |

→ **與 strip 模式「IoU 由 rows 決定、cols 不影響」完全同源**(見 s3-four-mesh-generalization.md):
**覆蓋率是「邊界取樣密度」的函數,內部頂點只影響變形自由度,不影響覆蓋**。這是跨兩種拓樸生成路徑
(strip / Delaunay)一致的普適規律。

**成因**:舊預設 `epsilon_frac=0.008` 是對 main_draw 窗簾(直邊、走 strip 模式、epsilon 未用)調的;
對**平滑曲邊生產件**,固定比例 × 周長 給的 hull 點太疏 → Douglas-Peucker 把曲線切成粗折線,覆蓋掉角。
`epsilon=0.002` 對 3 件 hull 密度 ≈ 藝術家,覆蓋即達標。

## 工具變更

- `generate_mesh_v2.generate(...)` 新增 `epsilon` / `max_interior` 參數並**透傳到 Delaunay 回退**
  (先前回退寫死預設、無法調 hull 密度)。預設仍 0.008(保 main_draw 行為不變,已重驗 4 mesh 無回歸);
  平滑生產件建議傳 **0.002**。CLI 新增 `--epsilon` / `--max-interior`。
- 新工具 `validate_psd_to_mesh.py`:件→生成 mesh→對照真實 spine mesh 的端到端閘。量化 4 條:
  `AC_coverage`(IoU ≥ 藝術家 − margin)、`AC_topology_setup`(0 自交/翻面/退化/孤兒)、
  `AC_budget`(頂點 ≤ 藝術家 ×1.5)、`REL_robust`(同一 stress 下 gen 自交/翻面 ≤ 藝術家)。
  - 針對 Award 的 **weighted + 無 deform timeline** mesh:真實逐頂點位移場不存在(靠骨骼權重變形),
    故變形項改用**相對**耐變形(對 gen 與 artist 施同一 `stress_field`,只作相對比較,非絕對閘,
    延續「stress_field 不可當硬閘」教訓)。
  - 真值座標系:Spine mesh uvs 為 **region 局部正規化**(0..1),artist 像素 = uvs×[W,H];已由
    main_draw(uvX/uvY∈[0,1])確認,先前「Award uvs 需轉 region 局部」的疑慮排除。

## 可重現

```
python3 tools/mesh_gen/validate_psd_to_mesh.py            # 3 件全 overall_pass, exit 0
python3 tools/mesh_gen/generate_mesh_v2.py <件.png> --epsilon 0.002   # 平滑件建議值
```

## 下一步候選

- **自適應 epsilon**:依邊界曲率/周長自動選 epsilon(而非固定比例),讓生成器對直邊/曲邊件都免調參。
- 把對應慣例(`PSD名/圖層名`、mesh/region 分配、+2px、atlas 0.70 縮放)＋本閘固化進「件→Spine JSON
  組裝」工具(SkelToJson),真正端到端產出可回填 Award 的 attachment。
