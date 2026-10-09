# S1 (J-13) cascade 波方向 最小面積包圍矩形(OBB)短軸 geo source — ⟂ 長軸的另一條確定性波

> 承 (J-7..J-12):`cascade_dir="geo"` 的方向**向量由件幾何導出**,前六個確定性 source =
> 質心→最遠件(`centroid_farthest`)/ PCA 主軸(`pca`)/ PCA 次主軸(`pca_minor`)/
> diameter 最遠對(`farthest_pair`)/ 凸包最長邊(`hull_longest_edge`)/ OBB 長軸(`obb_major`)。
> J-13 新增**第七個**確定性幾何 source `"obb_minor"`。

## 一句話

波方向 = 件中心**最小面積包圍矩形(OBB)的短軸** —— 與 `obb_major` **同一個**最小矩形的
**較短邊**方向(與長軸**嚴格正交**),字典序確定性定號 → 波沿件群最緊包圍盒的**短邊**橫掃
(vs `obb_major` 沿長邊延掃)。關係同 `pca_minor` 之於 `pca`(J-9 之於 J-8)。

## 機制(全 additive;`obb_major` 及前五 source 路徑皆逐位元不變)

`tools/analyzer/gen_animations.py`:把 J-12 的 `_obb_major_axis_dir` **參數化** `minor=False`:
- `minor=False`(預設)= **J-12 原碼逐位元不變**(旋轉卡尺求最小面積外接矩形、取較長邊)。
- `minor=True`(J-13):**先以同一套**旋轉卡尺 + 折半平面→字典序 tie-break 選出**同一個**最小面積
  矩形(得其 canon 長軸 `(ux,uy)`),再**轉 90°** `(ux,uy)=(-uy,ux)` 成短軸,然後走**同一套**幾何符號
  規則定號(指向沿該軸投影 `|proj|` 最大的極端件,proj≥0,tie 以座標字典序 → 件序無關)。
- **正交由建構保證**:短軸取自**與長軸同一個**矩形(不另解一次最小化),故 `obb_minor ⟂ obb_major`
  嚴格成立(`|dot|≈0`,非數值巧合)—— 恰如 `pca_minor` 以 `θ+90°` 取自同一 PCA。
- **守衛與 `obb_major` 共用**:近正方(長−寬 ≤ `aspect_tol`·(長+寬) → 長/短軸皆不唯一)→ ValueError;
  相異件<2 → ValueError。短軸**不會**在長軸退化(正方)時硬捏一個方向(比照 pca/pca_minor 各向同性
  守衛共用同理)。
- `derive_cascade_dir`:加分支 `source=="obb_minor" → _obb_major_axis_dir(centers, minor=True)`;
  `_CASCADE_GEO_SOURCES` 加 `"obb_minor"`。
- `_normalize_cascade_dir`/`_cascade_phase_of`/`build_spine --cascade-dir geo:obb_minor`:**無須改碼**
  (走 J-7 既有 `("geo", source)` 解析,導出向量後仍落 J-6 `("proj", vec)` 投影排序機制)。

## honest distinction(勿誇大)

J-13 **不是**新正交軸族,也**不改** J-6 投影排序機制;只是 provenance 再多一個 source(`obb_minor`)。
與 `obb_major` 同屬「OBB 的軸」,差別只在取**較短邊**而非較長邊 → **與長軸正交**、產生**不同件 pop 序**。

## 自我驗收閘 `tools/analyzer/validate_cascade_dir_obb_minor.py`(5 AC 全 PASS)

OBB 短軸 **由閘以 `scipy.spatial.ConvexHull` + 自寫旋轉卡尺獨立重算**(選同一最小矩形、取較短邊、
套**同一套** tie-break + 符號規則),其餘 source 亦獨立重算;不呼叫生成器私有函式。

- **OBM1 present + backward-compat + 零回歸**:`("geo","obb_minor")` 產每 cascade beat(finite/有 bone)・
  非 cascade 逐位元同 base・`po`/`None` 逐位元同件序・**零回歸**(**本次改碼的 `obb_major` 路徑逐位元
  不變** ← 關鍵:改的是它的函式、`pca`/`pca_minor`/`farthest_pair`/`hull_longest_edge` 逐位元不變、
  `geo` 預設==`centroid_farthest`、各 derive==閘獨立重算)。
- **OBM2 crux 正確性 + 正交 + 件序無關 + 符號確定**:(a) `obb_minor` == 閘獨立 scipy+卡尺 OBB 短軸
  **逐位元**(robot/L_shape/slant_quad/flag)**且 `⟂ obb_major`**(|dot|==0.0);(b) 唯一最小盒
  (slant_quad)& 面積並列(三角每邊)所有排列 → **1 個 distinct 帶號向量**;(c) 沿 x 鏡射(y→−y)→
  方向 y 分量符號翻轉、x 分量不變。
- **OBM3 crux minor 價值**:(a) **多佈局正交**(robot/L_shape/slant_quad/flag 皆 |dot|≈0);
  (b) **不同的波**:依 `obb_minor` 投影排序件序 ≠ 依 `obb_major`(slant_quad `[0,1,2,3]`≠`[0,3,1,2]`、
  flag `[0,1,2,3,4,5]`≠`[0,5,3,4,1,2]`、robot `[1,3,0,2,4]`≠`[1,2,0,4,3]`,asset-independent + 真實
  robot 皆成立)。
- **OBM4 端到端(robot)**:`build_animations(cascade_dir=("geo","obb_minor"))` 峰時刻依 OBB 短軸投影鍵
  (vec=`(0.9433, 0.3319)`)嚴格遞增・最遠投影最後 pop・仍跨件波(散佈≥0.30)・首尾 setup identity・
  特效 slot alpha=1・dir⟂nrip;**crux** robot 上 obb_minor pop 序 `[1,3,0,2,4]` ≠ obb_major 序
  `[1,2,0,4,3]`(短軸是真正不同的波)。
- **OBM5 metric + 守衛**:(a) == scipy+卡尺 OBB 短軸多佈局逐位元;(b) **正方守衛共用** 正方
  `obb_minor` **raise** 且 `obb_major` 亦 raise(同一最小矩形退化,長/短軸皆不唯一)而
  `farthest_pair`/`hull_longest_edge` 確定性回值;(c) 守衛 件重合/單件/空件/未知 source(直接 & 經
  build)→ValueError、`("geo","obb_minor")` 經 build 可用。

端到端:`build_spine.py assets/robot_parts.psd --animate --cascade-dir geo:obb_minor` 產可載入 Spine 素材
(6 bones / 5 slots / 11 animations + atlas + png)。

## 關鍵發現

1. **長軸/短軸由同一矩形取 → 正交由建構保證**,不是對另一個最小化問題求解再碰巧正交;恰如
   `pca_minor` 以 `θ+90°` 取自同一 PCA。**最小改碼面(一個 minor 參數 + 轉 90°)** 即得第二條軸,
   且避免「兩次最小化在 tie 路徑選到不同矩形」的不一致。
2. **正交軸 ⇒ 不同的件 pop 序**:投影到互相垂直的兩軸,排序一般不同(robot/slant/flag 皆驗),
   故 `obb_minor` 是**真正不同的波**而非 `obb_major` 的改版。
3. **退化守衛必須長/短軸共用**:正方時長軸不唯一,短軸同樣不唯一;若只對長軸 raise 而短軸硬給方向
   會製造「長軸未定但短軸有值」的矛盾 → 與 pca/pca_minor 各向同性守衛共用是同一原則。
4. **幾何量閘底線 = 閘獨立重算**:OBB 短軸由 scipy 凸包 + 自寫卡尺獨立算 + 套同一 tie-break 逐位元,
   被測碼不自證。

## honest boundary(仍在)

- 用 `obb_minor`/`obb_major`/`hull_longest_edge`/`farthest_pair`/`pca`/`pca_minor`/`centroid_farthest`
  (或手感常數)仍屬**美術手感(A 類 PROPOSAL)**:本閘只新增一個**確定性**幾何 source,不替使用者
  決定用哪個。
- `aspect_tol=1e-6`、tie `tol=1e-9` 為量級選擇;單一真值資產(robot);無改任何生成/產線值(全 additive)。
- cap `cascade_dir_obb_minor` L2 併入 `spine-anim-forge`(仍 HOLD;生成能力整體待 S5 多 rig 真值等上游)。
