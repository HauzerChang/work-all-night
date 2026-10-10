# S1 cascade 波方向 — 凸包最短邊 geo source(candidate J-14)

> 承 J-7→J-13 的「方向軸取值來源(provenance)」精煉。本篇新增**第八個確定性幾何 source**
> `"hull_shortest_edge"` = 件中心**凸包最短邊**(相鄰兩頂點中連線**最短**者)方向。
> 比照 `pca`→`pca_minor`(J-9)、`obb_major`→`obb_minor`(J-13):同一個凸包、同一套 tie-break,
> 只把 `hull_longest_edge`(J-11)的 max 換成 min(「換幾何特徵」:長↔短)。

## 一句話

`hull_shortest_edge` 讓 cascade 波沿件群外廓**最短的那條直邊**橫掃(vs `hull_longest_edge` 沿最長邊)——
在非正方矩形外廓下**⟂最長邊**(短側⟂長側);且揭示 **extremal-MIN(取最短)選擇子對擾動敏感、
extremal-MAX(取最長)穩健**的固有不對稱。

## 機制(全 additive,`tools/analyzer/gen_animations.py`)

- `_hull_longest_edge_dir(centers, tol=1e-9, shortest=False)`:新增 `shortest` 參數。
  - `shortest=False`(預設)= **J-11 原路徑逐位元不變**(Andrew's monotone chain 凸包 → 相鄰邊取**最長** →
    字典序定號)。重構為先算 `edge_lens` 再 `max/min`,`max` 分支與 J-11 同值 → 逐位元不變。
  - `shortest=True`:**同一個**凸包、同一套端點對字典序 tie-break,只把 `best_d = max(edge_lens)` 換成
    `min(edge_lens)`、tie 條件由 `d >= best_d - tol` 換成 `d <= best_d + tol`,其餘(符號/定向)完全相同。
- `derive_cascade_dir`:加分支 `source=="hull_shortest_edge" → _hull_longest_edge_dir(centers, shortest=True)`;
  `_CASCADE_GEO_SOURCES` 加 `"hull_shortest_edge"`。
- `_normalize_cascade_dir` / `_cascade_phase_of` / `build_spine --cascade-dir geo:hull_shortest_edge`:**無須改碼**
  (走 J-7 既有 `("geo", source)` 解析 → 落 J-6 `("proj", vec)` 投影機制)。

## 自驗閘 `validate_cascade_dir_hull_shortest_edge.py`(J-14,5 AC 全 PASS)

最短 / 最長邊 **由閘以 `scipy.spatial.ConvexHull` 獨立重算**(套同一字典序 tie-break),diameter / PCA
亦獨立重算,不呼叫被測私有函式 `_hull_longest_edge_dir`。

- **SE1 present + backward-compat + 零回歸**:`("geo","hull_shortest_edge")` 每 cascade beat finite/有 bone・
  非 cascade 逐位元同 base・`po`/`None` 逐位元同件序・**零回歸**(`geo` 預設==`("geo","centroid_farthest")`、
  `pca`/`pca_minor`/`farthest_pair`/`hull_longest_edge`/`obb_major`/`obb_minor` 六 source 皆逐位元不變、
  **`derive(.,"hull_longest_edge")` == 閘獨立 scipy 最長邊**(證 `shortest=False` 路徑逐位元不變)、
  各 derive == 閘獨立重算)。
- **SE2 crux 最短邊正確 + 件序無關 + 符號確定**:(a) `hull_shortest_edge` == 閘獨立 scipy ConvexHull 最短邊
  逐位元(robot/quad/rect/scalene_tri/scatter 五佈局);(b) 非對稱 + 正方(四邊並列)所有排列 → 1 個 distinct
  帶號向量;(c) 沿 x 鏡射(y→−y)→ 方向 y 分量符號翻轉、x 分量不變。
- **SE3 crux 價值**:
  - (a) **⟂ longest on (非正方)rectangle**:矩形 `(0,0),(14,0),(14,4),(0,4)` short=`(0,1)` ⟂ long=`(1,0)`,
    `|dot|=0`(**asset-independent**:矩形外廓邊交替長短,最短邊=短側、最長邊=長側,恆正交);閘獨立 scipy
    雙確認短 / 長邊。
  - (b) **hull-only(內部件不變性)**:固定矩形凸包 + 移一個**嚴格內部**件 `(2,2)→(12,2)` → `hull_shortest_edge`
    **逐位元不變**、`centroid_farthest` 轉 **28.07°**(只由凸包頂點決定,與 longest/fp 共有此性質)。
  - (c) **extremal-MIN 擾動敏感(honest)**:矩形 + 2 個近角擾動件 `(14.1,3.9),(13.9,4.1)` 造一條極短凸包邊
    → **最短邊方向擺動 45°**(`(0,1)→(0.707,−0.707)`)而**最長邊穩健 0°**(仍 `(1,0)`);閘獨立 scipy 雙確認。
    **這是 extremal-MIN 相對 extremal-MAX 選擇子的固有性質**(取最小的量對「幾近共線頂點產生的極短邊」敏感;
    取最大的量不受小邊影響)—— 誠實標明,非 bug。
- **SE4 端到端(robot)**:`build_animations(cascade_dir=("geo","hull_shortest_edge"))` 峰時刻依最短邊投影鍵
  (vec=`(0.9787,0.2054)`)嚴格遞增・最遠投影最後 pop・仍跨件波≥0.30・首尾 identity・特效 slot alpha=1・
  dir⟂nrip(帶 ripples 各件 pop 次數==nrip)。**crux:robot 上 short pop 序 `[1,0,3,2,4]` ≠ long pop 序
  `[3,0,1,2,4]`(differs_long=True)→ 真正不同的波**(robot 外廓非矩形,short/long 夾 36°)。
- **SE5 metric + 守衛**:(a) == scipy 最短邊多佈局(robot/quad/scalene_tri/penta)逐位元;(b) **各向同性**:
  正方 `pca`→ValueError 而 `hull_shortest_edge` 確定性回 `(0,1)` 且件序無關(極值型、**無各向同性守衛**);
  (c) 守衛 件重合 / 單件 / 空件 / 未知 source(直接 & 經 build;`("geo","hull_shortest_edge")` 經 build 可用、
  `("geo","zzz")` 報錯)→ ValueError。

端到端 `build_spine --animate --cascade-dir geo:hull_shortest_edge` 產可載入 Spine 素材。

## 關鍵發現

1. **「換幾何特徵(長↔短)」在凸包邊族成立**:繼 `pca`→`pca_minor`(散佈長↔短軸)、`obb_major`→`obb_minor`
   (最緊盒長↔短邊)之後,`hull_longest_edge`→`hull_shortest_edge`(外廓最長↔最短邊)是第三對「同一幾何
   物件、換取較大/較小特徵」的確定性波。
2. **extremal-MIN ≠ extremal-MAX 的穩健性**:取**最大**線段(longest edge / diameter)對「幾近共線的凸包頂點」
   穩健;取**最小**線段(shortest edge)對同一擾動敏感(極短邊主導方向)。這是本 run 最有價值的新洞見——
   **選最小 vs 選最大不是對稱操作**(SE3c 以矩形 + 近角擾動 asset-independent 地量化)。誠實後果:
   `hull_shortest_edge` 在近共線佈局方向不穩,實用上不如 `hull_longest_edge` 魯棒(屬手感取捨,A 類)。
3. **矩形外廓下短邊⟂長邊是 asset-independent crux**:矩形凸包邊長短交替 → 最短邊必⟂最長邊(|dot|=0),
   不靠特定資產;一般凸包(robot 36°)兩者方向只是不同,不保證正交。
4. **hull-only 不變性是外廓族共有**(shortest/longest/farthest_pair 皆只由凸包頂點決定)→ 內部件 crux 分
   外廓族與 cf/pca,不分外廓族內部各 source(那要靠「相鄰 vs 對角」「最長 vs 最短」「面積 vs 方差」各別證)。
5. **幾何量閘底線=閘獨立重算**(scipy 凸包 + 同一 tie-break;shortest=False 路徑以 `derive==scipy 最長邊`
   逐位元釘住零回歸)。

## honest boundary

- 用 `hull_shortest_edge` 還是其他 source(或手感常數)決定 cascade 波方向,仍屬**美術手感(A 類 PROPOSAL)**;
  本閘只新增一個**確定性**幾何 source,不決定「該用哪個」。
- `hull_shortest_edge` 的擾動敏感(SE3c)使它在近共線佈局不穩 → 多數情況 `hull_longest_edge` / `obb_*` 更實用;
  本 source 的價值在**揭示 min/max 選擇子的不對稱**,而非作為預設推薦方向。
- `MIN_ROT=3.0` / `STABLE_MAX=1e-6` / `ALIGN_MAX=1e-6` 為量級選擇;無改任何生成 / 產線值(全 additive,
  `shortest=False` 逐位元不變);單一真值資產。
- cap `cascade_dir_hull_shortest_edge` L2 併入 `spine-anim-forge`(仍 HOLD:生成器為單一真值資產、方向選擇
  屬 A 類,防半成品固化)。
