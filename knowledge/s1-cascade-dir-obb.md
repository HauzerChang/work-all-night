# S1 (J-12) cascade 波方向 最小面積包圍矩形(OBB)長軸 geo source — 面積極小 vs 方差極小

> 承 (J-7..J-11):`cascade_dir="geo"` 的方向**向量由件幾何導出**,前五個確定性 source =
> 質心→最遠件(`centroid_farthest`)/ PCA 主軸(`pca`)/ PCA 次主軸(`pca_minor`)/
> diameter 最遠對(`farthest_pair`)/ 凸包最長邊(`hull_longest_edge`)。
> J-12 新增**第六個**確定性幾何 source `"obb_major"`。

## 一句話

波方向 = 件中心**最小面積包圍矩形(OBB,oriented bounding box)的長軸** —— 以**旋轉卡尺**
(rotating calipers)求「面積最小」的外接矩形,取其**較長邊**方向,字典序確定性定號 →
波沿件群**最緊包圍盒的長邊**橫掃。

## 機制(全 additive)

`tools/analyzer/gen_animations.py`,前五 source 路徑**皆逐位元不變**:
- `_obb_major_axis_dir(centers, aspect_tol=1e-6, tol=1e-9)`:
  ① 去重排序 → **Andrew's monotone chain** 凸包(件序無關)。
  ② **旋轉卡尺**:掃凸包每條邊,把頂點投影到「該邊方向 × 其法向」兩軸取範圍相乘 = 該朝向的
     外接矩形面積;取**最小面積**者(經典定理:凸多邊形的最小面積外接矩形**必有一邊與凸包某邊共線**)。
  ③ 方向軸 = 最小矩形的**較長邊**方向(`we>=wn` 取邊向、否則取法向)。
  ④ **並列最小面積**(如三角形**每條邊**外接矩形面積皆 == 2×三角面積;正多邊形多解)→ 把候選長軸
     **折到上半平面**(`uy>0`,或 `uy==0 且 ux>0`)再取**座標字典序最小**者定出唯一**軸線**。
  ⑤ **符號**:指向沿該軸投影 `|proj|` 最大的極端件(其 proj≥0;tie 以座標字典序 → 件序無關;
     同 `_pca_principal_axis_dir` 的定號規則)。
  ⑥ **守衛**:相異件<2 → ValueError;最小矩形為(近)**正方形**(長−寬 ≤ `aspect_tol`·(長+寬),
     長軸不唯一)→ ValueError。
- `derive_cascade_dir`:加分支 `source=="obb_major" → _obb_major_axis_dir(centers)`;
  `_CASCADE_GEO_SOURCES` 加 `"obb_major"`。
- `_normalize_cascade_dir`/`_cascade_phase_of`/`build_spine --cascade-dir geo:obb_major`:**無須改碼**
  (走 J-7 既有 `("geo", source)` 解析)。

## crux(各在最鋒利維度各別證;asset-independent 優先)

- **vs pca(最相近,皆「用整個外廓的軸」)—— OBB3a**:OBB 最小化矩形**面積**(只看極值/範圍),
  pca 最小化**方差**(質量二階矩)。對**質量偏一側**的佈局兩者方向不同,**不需真實資產**即成立:
  L 形 `(0,0),(6,0),(6,1),(1,1),(1,4),(0,4)` obb=`(1,0)` vs pca=`(0.921,-0.389)` 差 **22.89°**;
  flag `(0,0),(10,0),(10,1),(3,1),(3,6),(0,6)` 差 **21.42°**。
- **vs hull_longest_edge / farthest_pair —— OBB3b**:最小面積矩形**必與某凸包邊共線**(旋轉卡尺定理),
  但那條邊**未必最長邊**,且長軸是矩形的**較長邊**(可能垂直於共線邊)。斜四邊形
  `(0,0),(6,0),(6,2),(0,5)` obb=`(1,0)`(軸對齊最緊盒 6×5)vs hle=`(0.894,-0.447)` 差 **26.57°**、
  vs fp=`(0.768,-0.640)` 差 **39.81°**;閘**獨立確認** OBB 選到的最小矩形**共線邊 ≠ 凸包最長邊**。
- **守衛 crux(與 fp/hle 不同)—— OBB5b**:正方 `(0,0),(2,0),(2,2),(0,2)` 的最小矩形**就是正方形**
  (長≈寬)→ 長軸不唯一 → `obb_major` **ValueError**;而 `farthest_pair`/`hull_longest_edge`
  **無**此守衛、確定性回對角/邊。pca 亦在正方 raise,但**判據不同**(pca 看 λ1≈λ2 變異各向同性,
  OBB 看矩形長≈寬)→ 誠實共標。
- **正確性 crux —— OBB2a/OBB5a**:`obb_major` == 閘**獨立**以 `scipy.spatial.ConvexHull` + **自寫旋轉
  卡尺**重算的 OBB 長軸(套**同一套**「折半平面 → 座標字典序」tie-break + 幾何符號規則),多佈局**逐位元**同;
  不呼叫生成器私有 `_obb_major_axis_dir`。

## 閘 `validate_cascade_dir_obb.py`(5 AC 全 PASS)

- **OBB1 present + backward-compat + 零回歸**:`("geo","obb_major")` 產每 cascade beat(finite/有 bone)・
  非 cascade 逐位元同 base・`po`/`None` 逐位元同件序・**零回歸**(`geo` 預設==`("geo","centroid_farthest")`、
  `("geo","pca")`/`("geo","pca_minor")`/`("geo","farthest_pair")`/`("geo","hull_longest_edge")` 皆逐位元不變、
  `derive(.,pca)`==numpy 主特徵向量、`derive(.,farthest_pair)`==閘獨立 brute diameter、
  `derive(.,hull_longest_edge)`==閘獨立 scipy 最長邊、`derive(.,centroid_farthest)`==閘獨立質心→最遠件)。
- **OBB2 crux 正確性 + 件序無關 + 符號確定**:(a) obb_major == 閘獨立 scipy+卡尺 OBB 長軸逐位元
  (robot/L_shape/slant_quad/flag);(b) **唯一最小盒**(slant_quad)& **面積並列**(三角形每邊並列,tie-break 驗)
  所有排列 → **1 個 distinct 帶號向量**;(c) 沿 x 鏡射(y→−y)→ 方向 y 分量符號翻轉、x 分量不變。
- **OBB3 crux obb 價值**:(a) **min-area ≠ min-variance**:L 形 22.89°/flag 21.42°(asset-independent);
  (b) **OBB 共線邊 ≠ 最長邊**:斜四邊形 obb≠hle(26.57°)≠fp(39.81°)+閘獨立確認 flush_edge≠longest_edge。
- **OBB4 端到端(robot)**:`build_animations(cascade_dir=("geo","obb_major"))` 峰時刻依 OBB 長軸投影鍵
  (vec=`(0.332,-0.943)`)嚴格遞增・最遠投影最後 pop・仍跨件波(散佈≥0.30)・首尾 identity・特效 slot
  alpha=1・dir⟂nrip;**obb≠pca 於 robot 成立**(obb 序 `[1,2,0,4,3]` ≠ pca 序 `[1,0,2,3,4]`,
  `differs_from_pca=True`)。**誠實回報**:此 robot 資產**最小面積恰有 2 個相異朝向 exact tie**(兩邊外接
  矩形面積皆 == `47243.000000000`,差 2e-11)→ **tie-break 路徑**,字典序確定性選 `(0.332,-0.943)`,
  閘獨立 scipy 重算逐位元同 → 故 robot 端到端走的是 tie-break 分支,genuine-diff crux 在 asset-independent
  的 OBB3(非此)。
- **OBB5 metric + 守衛**:(a) == scipy+卡尺 OBB 長軸多佈局逐位元;(b) **正方守衛** obb 與 pca 皆 raise
  (判據不同)而 fp/hle 確定性回值;(c) 守衛 件重合/單件/空件/未知 source(直接 & 經 build)→ValueError、
  `("geo","obb_major")` 經 build 可用。

端到端 `build_spine assets/robot_parts.psd --animate --cascade-dir geo:obb_major` → 產可載入 Spine 素材
(6 bones / 5 slots / 11 animations + atlas + png)。回歸 **0 RED / 65 GREEN**(新增 cap `cascade_dir_obb`
L2 併入 `spine-anim-forge`,仍 HOLD)。

## 關鍵發現

1. **「最小面積軸」與「最小方差軸」是兩個不同的最優化準則** —— OBB 只看**外廓極值/範圍**(面積),pca 看
   **質量二階矩**(方差)。質量偏一側(L 形 / flag)兩者方向差 20°+,**不需真實資產**即成立;是 J-12
   相對最相近 source(pca)最鋒利且 asset-independent 的鑑別子。
2. **旋轉卡尺定理把連續的旋轉搜尋降成「掃凸包每條邊」** —— 最小面積外接矩形必與某凸包邊共線,故只需 O(h)
   個離散朝向。但**共線邊未必最長邊**、長軸也未必沿共線邊(取矩形較長邊)→ 與 hull_longest_edge 可方向不同。
3. **OBB 有退化守衛(正方)、極值型 fp/hle 沒有** —— 最小矩形為正方時長軸不唯一(與 pca 的各向同性守衛
   **語意相近但判據不同**:pca 看 λ1≈λ2、OBB 看矩形長≈寬)。故「哪些 source 在正方 raise」把
   {obb, pca} 與 {fp, hle} 分成兩族。
4. **面積並列(三角形每邊、正多邊形)靠 tie-break 釘死** —— 三角形**每條邊**外接矩形面積皆 == 2×三角面積
   → OBB 朝向天然並列;折半平面 → 座標字典序取唯一軸線 + 幾何符號規則 → 件序無關、確定性。
5. **真實資產可能恰落在 exact tie 的 tie-break 路徑上** —— robot 件中心(半整數座標)使兩邊外接矩形面積
   **精確相等**(47243.000000000,差 2e-11),端到端走 tie-break 分支;這**非**瑕疵(確定性且閘獨立重算
   逐位元同),但意味 robot OBB 朝向對幾何微擾敏感(落在 tie 邊界上)——故 genuine-value 的刻畫交給
   asset-independent 的 L 形/flag/slant_quad,robot 端到端只驗「仍是一道有序跨件波 + obb≠pca」。
6. **幾何量閘底線 = 閘獨立重算** —— OBB 由 scipy 凸包 + 自寫卡尺獨立算 + 套同一 tie-break 逐位元,
   被測碼不自證(呼應 J-8..J-11)。

## honest boundary(仍在)

- 用 `obb_major` / `hull_longest_edge` / `farthest_pair` / `pca` / `pca_minor` / `centroid_farthest`
  (或手感常數)仍屬**美術手感(A 類 PROPOSAL)**:本閘只新增一個**確定性**幾何 source,不替使用者決定用哪個。
- `aspect_tol=1e-6`、OBB3 `MIN_ROT=3.0°`、tie `tol=1e-9` 為量級選擇;單一真值資產(robot);
  無改任何生成/產線值(全 additive,前五 source 逐位元不變)。
- cap `cascade_dir_obb` L2 併入 `spine-anim-forge`(仍 HOLD;生成能力整體待 S5 多 rig 真值等上游)。

## 下一步(候選,皆自主)

- **更多確定性幾何 source**:加權質心、凸包**最短**邊、周長加權方向、OBB **次軸**(短邊方向,與 obb_major
  正交,比照 pca→pca_minor)、最小**周長**外接矩形(vs 最小面積)。
- **讓 genre 先驗庫建議「用哪個 geo source」**(provenance 之上再加一層選擇規則;最終手感仍 A 類)。
- 或回 crossfade 線(L-7 之續)、charge 蓄力深度隨檔位、S5 rig 真值(C/資源類,使用者提供)。
