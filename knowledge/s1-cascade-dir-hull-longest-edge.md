# S1 — cascade 波方向 凸包最長邊 geo source（candidate J-11）

> 承 J-7→J-8→J-9→J-10 的「方向軸取值來源（provenance）」精煉線。J-11 新增第五個**確定性幾何
> source** `"hull_longest_edge"`，**不是**新正交軸、**不改** J-6 投影排序機制，只是 `derive_cascade_dir`
> 多一個 source 選項。全 additive，前四 source（`centroid_farthest`/`pca`/`pca_minor`/`farthest_pair`）
> 路徑**皆逐位元不變**。

## 一句話

cascade 跨件波的方向，取自件中心**凸包最長邊**（凸包上**相鄰**兩頂點中連線最長者）的方向，
字典序確定性定號 → 波沿件群外廓**最長的直邊**橫掃。

## 與既有四 source 的幾何基礎對照

| source | 錨 / 用件 | 幾何量 | 移動內部件 |
|---|---|---|---|
| `centroid_farthest` | 質心 → 單一最遠件 | 一階質心 + 單點極端 | **方向改變**（質心移動）|
| `pca` | 全部件 | 二階矩主軸（最大變異）| 改變（外廓極值主導，槓桿小）|
| `pca_minor` | 全部件 | 二階矩次主軸（⟂主軸）| 改變 |
| `farthest_pair` | 兩極端件 | diameter（全域最遠對，常是凸包**對角線**）| **不變**（hull-only）|
| `hull_longest_edge`（J-11）| 凸包相鄰頂點 | 最長**邊**（相鄰頂點的最長外廓線段）| **不變**（hull-only）|

## 三個 crux

- **最鋒利 crux（vs 最相近的 `farthest_pair`）— longest edge ≠ diameter**：同一點集下，diameter 是
  **全域最遠對**（端點常是凸包**不相鄰**頂點＝對角線），longest edge 是**相鄰**頂點的最長外廓線段。
  凸四邊形 `(0,0),(6,0),(6,2),(0,5)`：`hull_longest_edge` = 邊 `(0,5)-(6,2)` 方向 ≈ `(0.894,−0.447)`
  （−26.57°），`farthest_pair` = 對角 `(6,0)-(0,5)` 方向 ≈ `(0.768,−0.640)`（−39.81°），**差 13.24°**；
  閘以獨立 scipy 凸包確認 hle 端點對**相鄰**、diameter 端點對**不相鄰**。此 crux **asset-independent**
  （不需真實資產即成立）。
- **vs `centroid_farthest` crux — hull-only（內部件不變性）**：固定凸包（矩形 `(0,0),(14,0),(14,4),(0,4)`）、
  移動一個**嚴格內部**件 `(2,2)→(12,2)`：`hull_longest_edge` **逐位元不變**（0°）、`farthest_pair` 亦不變
  （**同屬 hull-only → 誠實共標**），而 `centroid_farthest` 轉 **28.07°**（質心移動）。
  ⚠️ **誠實回報（非判準）**：此佈局下 `pca` 轉動 **0°**——外廓極值主導其二階矩，內部件槓桿小，故
  **hle 與 pca 皆對內部件穩健**；不把「hle≠pca」硬塞進內部件 crux，而由下一條承擔。
- **vs `pca` crux — 無各向同性病態**：對**正方 / 正多邊形**，`pca` 因 λ1≈λ2 會 ValueError（主軸不唯一），
  而 `hull_longest_edge` **仍確定性回最長邊**（正方四邊並列 → 端點對字典序 tie-break 回 `(0,1)` 即 90°，
  件序無關）。極值型幾何量**無各向同性守衛**（同 `farthest_pair`）。

## 正確性 crux（定向 = 無向線→有向向量）

方向 = **座標字典序較小端點 → 較大端點**（純幾何、件輸入順序無關）；多條邊並列最長（如正方）時以
**端點對的字典序**取唯一代表（沿用 `_farthest_pair_dir` 的 tie-break）。閘對所有排列驗**逐位元同一帶號
向量**（含對稱佈局 = 天真 index tie-break 的翻號處）。

## 實作（全 additive）

`tools/analyzer/gen_animations.py`：
- `_hull_longest_edge_dir(centers, tol=1e-9)`：去重排序 → **Andrew's monotone chain** 凸包（`<=0` 剔除共線
  中間點 → 共線退化成兩端點，唯一邊 == diameter）→ 掃相鄰頂點邊取最長 → 字典序定號。守衛相異件數<2 /
  件重合（最長邊≈0）→ ValueError。**無各向同性守衛**。
- `derive_cascade_dir` 加分支 `source=="hull_longest_edge"`；`_CASCADE_GEO_SOURCES` 加 `"hull_longest_edge"`。
- `_normalize_cascade_dir` / `_cascade_phase_of` / `build_spine --cascade-dir geo:hull_longest_edge` **無須改碼**
  （走 J-7 既有 `("geo", source)` 解析）。

## 閘 `validate_cascade_dir_hull_longest_edge.py`（5 AC 全 PASS）

最長邊 **由閘以 `scipy.spatial.ConvexHull` 獨立重算**（套同一套字典序 tie-break，不呼叫被測私有
`_hull_longest_edge_dir`）；diameter / PCA 亦獨立重算。

- **HLE1** present + backward-compat + **零回歸**：hle 產每 cascade beat（finite/有 bone）・非 cascade 逐位元
  同 base・`po`==`None`・`geo` 預設==`geo:centroid_farthest`・`("geo","pca")`/`("geo","pca_minor")`/
  `("geo","farthest_pair")` 皆逐位元不變・`derive(.,"pca")`==numpy 主特徵向量・`derive(.,"farthest_pair")`==閘
  獨立 brute diameter・`derive(.,"centroid_farthest")`==閘獨立質心→最遠件。
- **HLE2** crux 最長邊正確+件序無關+符號確定：(a) `hull_longest_edge`==閘獨立 scipy 最長邊逐位元（robot/
  quad/rect/scatter）；(b) 非對稱 & 正方（並列邊）所有排列皆 1 個 distinct 帶號向量；(c) 沿 x 鏡射→y 分量
  符號翻轉、x 分量不變。
- **HLE3** crux longest-edge 價值：(a) 凸四邊形 hle≠fp 方向（差 13.24°）+ 閘獨立確認 hle 端點**相鄰** /
  diameter 端點**不相鄰**；(b) 固定凸包 + 移動嚴格內部件 → hle/fp 逐位元不變・cf 轉 28.07°（pca 轉動僅回報）。
- **HLE4** 端到端（robot）：`build_animations(cascade_dir=("geo","hull_longest_edge"))` 峰時刻依最長邊投影鍵
  （vec≈`(0.671,0.741)`）嚴格遞增・最遠投影最後 pop・仍跨件波（散佈≥0.30）・首尾 identity・特效 slot alpha=1・
  dir⟂nrip。**誠實回報**：此 robot 資產**最長邊恰與直徑同向** → hle pop 序 `[3,0,1,2,4]`==fp 序，genuine-diff
  crux 在 asset-independent 的 HLE3a（非此端到端）。
- **HLE5** metric + 守衛：(a) ==scipy 最長邊多佈局逐位元；(b) 正方 `pca`→ValueError 而 `hull_longest_edge`
  確定性回最長邊且件序無關；(c) 守衛 件重合/單件/空件/未知 source（直接 & 經 build）→ValueError、
  `("geo","hull_longest_edge")` 經 build 可用。

端到端 `build_spine --animate --cascade-dir geo:hull_longest_edge` → 可載入 Spine 素材（6 bones / 5 slots /
11 animations + atlas + png）。回歸 **check_readiness 0 RED / 64 GREEN**（新增 cap
`cascade_dir_hull_longest_edge` L2 併入 `spine-anim-forge`，仍 HOLD）。

## 關鍵發現

1. **「相鄰最長邊」與「全域最遠對」是兩個不同的凸包幾何物件** —— 同一點集，longest edge（相鄰頂點）與
   diameter（常是對角線、不相鄰頂點）方向可不同（凸四邊形差 13.24°）；這是 J-11 相對最相近 source
   （farthest_pair）最鋒利、且 **asset-independent** 的鑑別子。
2. **hull-only 性質（內部件不變性）是 hle 與 fp 共有，不是 hle 獨有** —— 誠實共標；內部件 crux 只能把
   hle/fp 與 **cf** 分開（cf 質心敏感），**不能**把 hle 與 fp 分開（要靠 crux 1），也**不能**把 hle 與 pca 分
   開（elongated 外廓下 pca 亦對內部件穩健 → pca 轉動 0°，誠實回報不作判準）。
3. **區別一個 source 要在它最鋒利的維度上證，而非硬塞到單一 crux** —— hle vs fp 用「相鄰 vs 對角」、
   hle vs cf 用「內部件不變性」、hle vs pca 用「各向同性病態（正方 pca ValueError / hle 確定性）」：**三個
   distinction 各在最鋒利處**，不強求同一佈局同時分開全部。
4. **幾何量閘底線＝閘獨立重算** —— 凸包最長邊由 scipy 獨立算、套同一字典序 tie-break 比逐位元；diameter/
   PCA 以 brute/numpy 獨立算。被測碼不自證。
5. **共線退化的一致性** —— 共線件凸包退化成線段，其唯一邊 == diameter → `hull_longest_edge` 與
   `farthest_pair` 在共線佈局自然一致（monotone chain `<=0` 剔除共線中間點保證）。

## honest boundary（仍在）

- 用 `hull_longest_edge` / `farthest_pair` / `pca` / `pca_minor` / `centroid_farthest`（或手感常數）**仍屬美術
  手感（A 類 PROPOSAL）**：本閘只新增一個**確定性**幾何 source，不替使用者決定用哪個。
- `tol=1e-9`、`MIN_ROT=3.0°` 及各門檻為量級選擇；單一真值資產（robot）；無改任何生成/產線值（全 additive）。
- cap `cascade_dir_hull_longest_edge` L2 併入 `spine-anim-forge`（仍 HOLD；生成能力整體待 S5 多 rig 真值等上游）。

## 下一步（候選，皆自主）

- **其他確定性幾何 source**：加權質心（area-weighted centroid→farthest）、最小面積包圍盒（min-area OBB）主軸
  （旋轉卡尺；對正方需各向同性守衛，與 pca 同）、凸包**最短邊** / 周長加權方向。
- **讓 genre 先驗庫建議「用 geo:hull_longest_edge / farthest_pair / pca / pca_minor / centroid_farthest / 手感
  常數」**（provenance 之上再加一層選擇規則；最終手感仍 A 類）。
- 或回 crossfade 線（L-7 之續）、charge 蓄力深度隨檔位、S5 rig 真值（C/資源類，使用者提供）。
