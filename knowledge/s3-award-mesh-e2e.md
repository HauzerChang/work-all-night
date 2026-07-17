# S3 端到端驗收:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把「PSD 切件 → `generate_mesh_v2` → 靜態幾何」對真實生產標的(Award spine 的
  3 個機器人 mesh 件:光暈/身體/左手)閉環驗收。**經校準後 3/3 PASS**,生成 mesh 覆蓋率
  達/超過藝術家自身 silhouette 覆蓋率基準,頂點數與藝術家同級。
- **關鍵副產(已修)**:發現並修掉 v1 生成器的**尺度依賴 bug** —— epsilon 用「周長比例」
  使大件外輪廓被過度簡化,覆蓋率掉到 0.93。改為**尺度不變(絕對像素上限)**後 3 件全達標。
- **信心**:高(對真實生產 mesh 交叉比對 + 評估器先自我校驗才下判定 + 無回歸)。
- **階段**:第 2 階段 / S3(里程碑:S3+S4 端到端串通,對真實標的)。

## 做了什麼

1. `robot_parts.psd` → `psd_slice` 切出 5 件;取 Award 中為 **mesh** 的 3 件(光暈/身體/左手)。
2. 各件跑 `generate_mesh_v2(auto)` → 皆 aspect<1.2 → **回退 Delaunay v1**(strip 只適用高瘦窗簾)。
   → 這是 v1 Delaunay 路徑首次在「真實生產、多樣形狀」上被驗(先前僅 curtain_left)。
3. `evaluate_mesh` 靜態閘(IoU/format/孤兒/退化) + 與 Award 藝術家 mesh 拓樸/覆蓋率對照。
4. 工具:`tools/mesh_gen/compare_gen_vs_award.py`(可重跑)。

## ★ 評估器校準(又一次,務必記取)

**藝術家覆蓋率基準的重建一開始是錯的 → overall_pass 假性通過。**
- 初版誤把 Spine mesh `uvs` 當 **full-sheet** 正規化 → 重建藝術家多邊形 IoU 得 0.0/0.50/0.70
  (荒謬:藝術家 mesh 蓋自己的 silhouette 不可能才 0.0)。此時生成 IoU 0.93~0.97 輕鬆「贏」
  垃圾基準 → 假 PASS。**若不查證就會誤報成功。**
- **校驗過的事實**:Spine 3.8 mesh `uvs` 是 **region-local 正規化 [0,1]**(與既有
  `validate_against_real.py::artist_iou` 的 `uvs*(W,H)` 一致)。直接對 `atlas_crop`(derotate 後
  upright)切件 alpha 重建,對 v/1-v 取最佳 → 3 件皆 **v 不翻、IoU≈0.97** → 對映正確、基準可信。
- 教訓(延續 stress_field / composite 白底 / atlas CCW 三次):**評估器先自我校驗(高基準 sanity)
  才可下判定**;一個「太容易通過」的比對要先懷疑基準壞了。

## ★ 生成器 bug:epsilon 尺度依賴(已修)

- 症狀:校準後 **光暈 FAIL**(生成 IoU 0.933 << 藝術家 0.980),身體/左手 PASS。
- 根因:`generate_mesh.boundary_points` 用 `epsilon = epsilon_frac(0.008) * 周長`。
  大件周長大 → 絕對容差過粗(光暈 706px → **23px**!),Douglas-Peucker 把外輪廓抹平,
  hull 只剩 16 點 → 覆蓋率崩。小件(身體 12px、左手 8px)剛好還行 → 掩蓋了 bug。
- epsilon 掃描(光暈):0.008→IoU0.93(hull16);0.002→0.98(hull45);0.001→0.99(hull62)。
  **覆蓋率由外輪廓細緻度(hull 取樣密度)決定**(呼應 v2「IoU 由 rows 決定」)。
- **修法(尺度不變)**:`epsilon = min(epsilon_frac*peri, abs_tol_px=3.0)`。大件收斂到 ~3px 細緻度,
  小件維持比例(peri<375 時仍走比例,不過度細分噪邊)。

## 校準後結果(3/3 PASS,margin=0.03)

| 件 | 模式 | 生成 v/hull/IoU | 藝術家 v/hull/base_IoU | pass |
|---|---|---|---|---|
| 光暈 | delaunay-v1 | 80 / 61 / **0.9914** | 78 / 78 / 0.9795 | ✅ |
| 身體 | delaunay-v1 | 77 / 37 / **0.9908** | 98 / 40 / 0.9760 | ✅ |
| 左手 | delaunay-v1 | 74 / 34 / **0.9844** | 80 / 42 / 0.9689 | ✅ |

→ 生成覆蓋率**達/超**藝術家自身基準,頂點數同級(甚至更省,身體 77<98)。

## ⚠️ 誠實範圍註記

- 這 3 件在 Award **無 deform timeline**(weighted mesh,靠骨骼/權重變形,非逐頂點 deform)。
  故 `deform_eval` 的「真實位移場轉移」閘**不適用**於它們;本比對是**靜態幾何**(覆蓋率+拓樸)。
  真實 deform 耐受度已由 main_draw 4 mesh(有 deform timeline)驗過,結論分開成立。
- 覆蓋率是「三角化蓋 silhouette 的緊密度」,對兩邊各以其自身 alpha 量,scale/frame 無關 → 公平比對。

## 無回歸(改 v1 default epsilon 後重驗)

- `validate_against_real --gen v1 image/curtain_left`:PASS(IoU 0.9949,deform si=0/flips=0)。
- `validate_against_real --gen v2`:curtain_left/right + shadow 全 PASS(strip 模式,不受 v1 edit 影響)。
  (`image/shadow2` 與 shadow **共用同一 atlas region**,無獨立 region,經 shadow 驗。)

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_pieces
python3 tools/mesh_gen/compare_gen_vs_award.py --psd-dir /tmp/robot_pieces   # overall_pass: true
```

## 下一步

- **切圖→Spine JSON 組裝(SkelToJson)**:把已驗的慣例固化(`<PSD名>/<圖層名>` slot、+2px padding、
  mesh/region 分配、atlas 0.70 縮放),端到端從 PSD 件產出可載入的 Spine mesh attachment JSON。
- 生成 mesh 目前 **unweighted**;Award 真實件為 **weighted**(骨骼變形)。若要對 weighted 生產標的
  完整對齊,下一個能力缺口是 **BBW 權重生成**(S3 路線圖第三塊)。
