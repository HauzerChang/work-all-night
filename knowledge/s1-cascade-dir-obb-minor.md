# S1 (J-13) cascade 波方向 最小面積包圍矩形(OBB)次軸 geo source — 短邊橫掃 vs 長邊延掃

> 承 (J-7..J-12):`cascade_dir="geo"` 的方向**向量由件幾何導出**,前六個確定性 source =
> 質心→最遠件(`centroid_farthest`)/ PCA 主軸(`pca`)/ PCA 次主軸(`pca_minor`)/
> diameter 最遠對(`farthest_pair`)/ 凸包最長邊(`hull_longest_edge`)/ OBB 長軸(`obb_major`)。
> J-13 新增**第七個**確定性幾何 source `"obb_minor"`。比照 J-8→J-9(pca→pca_minor):
> 同一個 OBB 幾何物件的**正交次軸**。

## 一句話

波方向 = 件中心**最小面積包圍矩形(OBB)的次軸**(OBB 長軸轉 90°,**較短邊**方向,與長軸**正交**),
字典序確定性定號 → 波沿件群**最緊包圍盒的短邊**橫掃(vs `obb_major` 沿長邊延掃)。

## 機制(全 additive)

`tools/analyzer/gen_animations.py`,前六 source 路徑**皆逐位元不變**:
- `_obb_major_axis_dir(centers, aspect_tol=1e-6, tol=1e-9, minor=False)`:加 `minor` 參數。
  - `minor=False`(預設)**= J-12 原碼逐位元不變**:回長軸(較長邊方向)。
  - `minor=True`(J-13):選出最小面積矩形的折半平面長軸 `(ux,uy)` 後、過正方守衛,**轉 90°**
    `(ux,uy)=(-uy,ux)`(與長軸正交),再走**同一套**幾何符號規則定號(指向沿**該次軸**投影 |proj|
    最大的極端件,其 proj≥0,tie 以座標字典序 → 件序無關)。
  - 退化守衛(最小矩形近正方 → 長≈寬 → 軸不唯一)與長軸**共用**:正方時長軸/次軸皆退化 → ValueError。
- `derive_cascade_dir`:加分支 `source=="obb_minor" → _obb_major_axis_dir(centers, minor=True)`;
  `_CASCADE_GEO_SOURCES` 加 `"obb_minor"`。
- `_normalize_cascade_dir`/`_cascade_phase_of`/`build_spine --cascade-dir geo:obb_minor`:**無須改碼**
  (走 J-7 既有 `("geo", source)` 解析)。

## crux(各在最鋒利維度各別證)

- **vs obb_major(同一 OBB、正交次軸)—— OBM2a / OBM3**:次軸 ⟂ 長軸(|dot|≈0)→ 產生**不同的件 pop 序**
  (是一條真正不同的波,非 obb_major 改版)。斜四邊形/二維展開佈局下依 minor 投影排序 ≠ 依 major 投影排序,
  次軸方向的極端件在 minor 下最後 pop。
- **正確性 —— OBM2a / OBM5a**:`obb_minor` == 閘**獨立** scipy.spatial.ConvexHull + 自寫旋轉卡尺重算的
  OBB 次軸(套**同一套**折半平面→座標字典序 tie-break 選唯一 OBB → 長軸轉 90° → 幾何符號規則),**逐位元**同
  (robot/slant_quad/tall_slant/L_shape/penta)。不呼叫生成器私有函式。
- **件序無關 —— OBM2b**:唯一最小矩形(slant_quad)與面積並列(三角形每邊)佈局的**所有排列** → 1 個 distinct
  帶號向量(折半平面 + 座標字典序 tie-break 釘死,同 obb_major)。
- **退化守衛(與 obb_major 共用,fp/hle 無)—— OBM5b**:正方的最小矩形就是正方形(長≈寬)→ `obb_minor`
  **ValueError**;`farthest_pair`/`hull_longest_edge` **無**此守衛、確定性回值;`pca` 亦在正方 raise 但判據不同
  (λ1≈λ2 變異各向同性 vs OBB 矩形長≈寬)→ 誠實共標。

## 端到端(robot)—— OBM4

`build_animations(cascade_dir=("geo","obb_minor"))` 每 cascade beat 各件峰時刻依 OBB 次軸投影鍵
(robot vec=`(0.9433, 0.3319)`)嚴格遞增、最遠投影最後 pop、仍一道有序跨件波(散佈≥門檻)、首尾 setup
identity、特效 slot alpha=1、dir⟂nrip。**crux(asset-dependent)**:robot 上 obb_minor pop 序 `[1,3,0,2,4]`
**≠** obb_major pop 序 `[1,2,0,4,3]` → 端到端證兩者不同波。**這補足了 J-12 的憾**:J-12 的 obb_major 在此
robot 資產上恰與 hle/fp 同向(genuine-diff 只能交 asset-independent 佈局);J-13 的 obb_minor 與 obb_major
**正交**,故在 robot 上就直接產生不同 pop 序,端到端即有真實差異。

`build_spine --animate --cascade-dir geo:obb_minor` 產可載入 Spine 素材(6 bones / 5 slots / 11 anims + atlas + png)。

## 關鍵發現

1. **「同一幾何物件的正交次軸」是一條現成的確定性波** —— 比照 pca→pca_minor,OBB 長軸算好後轉 90° 即得次軸,
   零額外幾何搜尋、零額外 tie-break(次軸線由選定的 OBB 唯一決定),只需重跑符號規則。
2. **正交次軸在真實資產上天然不同波** —— obb_major 可能與其他 source 偶然同向(robot 上 == hle/fp),但其
   正交次軸 obb_minor 必與 obb_major 不同向 → 端到端 pop 序不同是 asset-dependent 但**不依賴特殊佈局**。
3. **退化守衛隨幾何物件走,不隨主/次軸走** —— 正方時長軸與次軸皆不唯一,故 minor 與 major **共用**正方守衛;
   這與 pca_minor/pca 共用各向同性守衛同理(λ1≈λ2 時主/次軸皆退化)。
4. **minor=False 必須逐位元等於原碼** —— 把 `if minor:` 的轉 90° 插在符號規則**之前**、守衛**之後**,
   `minor=False` 分支完全不經過該段 → J-12 obb_major 路徑零回歸(OBM1 驗 6 source 全逐位元不變)。
5. **幾何量閘底線 = 閘獨立重算** —— OBB 次軸由 scipy 凸包 + 自寫卡尺 + 同一 tie-break + 轉 90° 獨立算,
   被測碼不自證。

## honest boundary(仍在)

- 用 `obb_minor` / `obb_major` / `hull_longest_edge` / `farthest_pair` / `pca` / `pca_minor` /
  `centroid_farthest`(或手感常數)**用哪一個**仍屬美術手感(A 類 PROPOSAL)—— 本閘只新增一個**確定性**幾何
  source,不替使用者決定用哪個。
- `aspect_tol=1e-6`、OBM3 判準、tie `tol=1e-9` 為量級選擇;單一真值資產(robot);無改任何生成 / 產線值(全 additive)。
- cap `cascade_dir_obb_minor` L2 併入 `spine-anim-forge`(仍 HOLD;生成能力整體待 S5 多 rig 真值等上游)。

## 檔案

- 生成:`tools/analyzer/gen_animations.py`(`_obb_major_axis_dir` 加 `minor` 參數、`derive_cascade_dir` 加分支)。
- 閘:`tools/analyzer/validate_cascade_dir_obb_minor.py`(5 AC;OBB 次軸由閘以 scipy+卡尺獨立重算)。
- cap:`tools/check_readiness.py` → `cascade_dir_obb_minor` L2 @ `spine-anim-forge`。
