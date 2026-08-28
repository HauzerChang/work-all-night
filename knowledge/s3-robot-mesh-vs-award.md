# S3 端到端驗收 — 生產貼圖件 → S3 mesh → 對照 Award 真實美術 mesh

- **結論**:S3 `generate_mesh_v2`(auto)對 Award「機器人拆件」的 **3 個 mesh 件**(光暈/左手/身體)
  生成 mesh,在**同一 region 影像框**裡與美術 mesh 做靜態覆蓋率 IoU 對照 —— **3 件全 overall_pass**
  (覆蓋率達美術基準 −0.03 margin 內、拓樸 0 退化/0 孤兒),且**頂點數更省**(37~48 vs 美術 78~98)。
- **信心**:高(對真實生產 spine 的美術 mesh 逐件量化;UV 對映經 4 組合實測校準)。
- **階段**:第 2 階段 / S3(里程碑:S3 首次對「真實生產美術 mesh」端到端驗收,非合成/非自產真值)。
- **工具**:`tools/mesh_gen/compare_robot_mesh.py`(可重現)。

## 標準指令

```
python3 tools/mesh_gen/compare_robot_mesh.py     # 3 件全 PASS → exit 0
```

## 量化結果(region 框內,IoU vs 該件 alpha 真值)

| 件 | gen 模式 | gen IoU | 美術基準 | gen 頂點 | 美術頂點 | 判定 |
|---|---|---|---|---|---|---|
| 光暈 | boundary-dense-v1 | 0.983 | 0.980 | 38 | 78 | PASS |
| 左手 | delaunay-v1 | 0.960 | 0.968 | 48 | 80 | PASS |
| 身體 | boundary-dense-v1 | 0.993 | 0.976 | 37 | 98 | PASS |

視覺證據:`knowledge/figures/robot_mesh_gen_vs_artist.png`(綠=美術 / 橙=生成,疊在各件剪影上)。

## 三個關鍵發現(本 session)

### 1. Spine JSON mesh 的 `uvs` 是 **region-local [0,1]**,不是 atlas-page 分數
先前 STATE 假設「Award mesh uvs 為 atlas UV,需先轉 region 局部」→ **錯**。實測 4 種組合
(v-flip × derotate 手性)後:直接 `uvs×(regionW,regionH)`、**vflip=False** 對 3 件皆 IoU 0.97~0.98,
其餘組合 <0.61。即 Spine editor 匯出時 mesh uvs 已是 attachment region 內的正規化座標
(載入時才由 atlas region 重映到貼圖)。**對照美術 mesh 覆蓋率不需要 atlas 幾何轉換**。

### 2. 軟邊 blob(光暈)需「密邊界描邊」— 新增 `boundary-dense-v1` 自適應模式
光暈羽化帶佔前景 **38%**(部分透明像素)。預設 `epsilon_frac=0.008` 的 Douglas-Peucker 只給
hull=14 → 覆蓋率 0.923(< 美術 0.980)。美術對這類件用**純邊界密多邊形**(hull=78=全頂點、
76 三角扇、無內部點)描平滑外緣。
→ `generate_mesh_v2` auto 下新增偵測:`soft_band_frac(path) >= 0.20` → 改
`epsilon=0.002 + max_interior=0`(密邊界、不放內部點),模式標 `boundary-dense-v1`。
光暈由此 0.923 → **0.983**,且頂點更省。**只影響 delaunay 分支,strip(窗簾/陰影)不受影響。**

### 3. `filter_triangles` 會造孤兒頂點 → 新增通用 `prune_orphans`(正確性修正)
內部 Canny/格點被「重心在 mask 內」過濾三角時,可能所有相鄰三角都被濾掉 → 該點成孤兒
(評估器 AC2c 正確抓到,光暈初版 orphan=1)。`generate_mesh.py` 現在 `filter_triangles` 後
`prune_orphans`(移除未引用頂點 + 重編索引,保住 hull-first 順序、重算 hull 數)。**通用修正**,
對所有 delaunay 分支件生效。

## ✅ 更新(2026-08-28):此限制已由 weighted 變形評估器補上

> 下方「變形品質未驗」的限制**已解決**。`tools/mesh_gen/weighted_deform_eval.py`(+ `weighted_skin.py`
> Spine FK+蒙皮引擎)驅動這 3 件在其動畫下逐幀量測變形幾何合法性 + 應變非均勻度,建立真值簽章。
> **關鍵更正**:這 3 件**不是**靠 deform timeline,而是靠所綁**骨骼的 rotate/scale/translate 動畫**變形
> (下段「無 deform timeline」正確,但不代表不變形)。評估器 3 AC 全 PASS,見 `s3-weighted-deform-evaluator.md`。

## ⚠️ 誠實限制(原記錄,已補齊):靜態覆蓋率 PASS ≠ 變形品質對等(weighted mesh)

- 這 3 件在 Award 是 **weighted mesh 且無 deform timeline**(靠骨骼+權重變形,非逐頂點 deform)。
  故**真實逐頂點 deform 轉移閘不適用**;本次驗收 = 靜態覆蓋率 + 拓樸合法性 + 頂點經濟度。
- 圖中可見:美術 **身體 98v** 有密集**內部**頂點,這是為 **骨骼權重變形的平滑度**服務的
  (內部取樣密度 = 變形品質槓桿),而我的 boundary-dense 幾乎只有邊界點。
  → **靜態 IoU 高、頂點更省,不代表 bone-driven 變形一樣平滑**。要量化這點需該件的
  權重 + 骨骼 pose 序列(目前資產未含這 3 件的變形動畫)→ 屬 S3 後續(weighted mesh 生成 + BBW 權重)。
- 收斂判定僅就「覆蓋率 + 拓樸」下 PASS;變形平滑度留待 weighted/BBW 能力補齊後再驗。

## 下一步候選

- **S3 weighted 生成 + BBW 權重**:對身體這類 bone-變形件,加內部取樣密度控制 + 骨綁權重,
  才能對 weighted mesh 做變形品質對照(補上本次的限制)。
- **件→Spine JSON 組裝(SkelToJson)**:把 `<PSD名>/<圖層名>`、mesh/region 分配、+2px padding、
  atlas 0.70 縮放固化成工具,端到端產出可載入 spine。
