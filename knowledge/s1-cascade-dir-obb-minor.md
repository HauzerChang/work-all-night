# S1 cascade 波方向 — OBB 次軸 geo source(candidate J-13)

> 承 J-7→J-12 的「方向軸取值來源(provenance)」精煉。本篇新增**第七個確定性幾何 source**
> `"obb_minor"` = 件中心**最小面積包圍矩形(OBB)次軸**(短邊方向,與 `obb_major` 正交)。
> 比照 `pca`→`pca_minor`(J-9):同一個最小面積矩形、同一套 tie-break,只把導出軸由較長邊換成較短邊。

## 一句話

`obb_minor` 讓 cascade 波沿件群**最緊包圍盒的短邊**橫掃(vs `obb_major` 沿長邊延掃)——
是 OBB 這個幾何物件的**另一條確定性軸**,與長軸正交 → 產生不同的件 pop 序。

## 機制(全 additive,`tools/analyzer/gen_animations.py`)

- `_obb_major_axis_dir(centers, aspect_tol=1e-6, tol=1e-9, minor=False)`:新增 `minor` 參數。
  - `minor=False`(預設)= **J-12 原路徑逐位元不變**(選最小面積盒、取較長邊、符號規則)。
  - `minor=True`:**同一個**最小面積矩形(同凸包 + 同旋轉卡尺 + 同折半平面→字典序 tie-break 選唯一盒),
    把導出軸由較長邊換成**較短邊**(= 長軸轉 +90°,再折到上半平面),再套**同一套**符號規則
    (指向沿該軸投影 |proj| 最大的極端件、tie 以座標字典序 → 件序無關)。
- `derive_cascade_dir`:加分支 `source=="obb_minor" → _obb_major_axis_dir(centers, minor=True)`;
  `_CASCADE_GEO_SOURCES` 加 `"obb_minor"`。
- `_normalize_cascade_dir` / `_cascade_phase_of` / `build_spine --cascade-dir geo:obb_minor`:**無須改碼**
  (走 J-7 既有 `("geo", source)` 解析 → 落 J-6 `("proj", vec)` 投影機制)。

## 自驗閘 `validate_cascade_dir_obb_minor.py`(J-13,5 AC 全 PASS)

OBB 長/次軸 **由閘以 `scipy.spatial.ConvexHull` + 自寫旋轉卡尺獨立重算**(套同一 tie-break),pca_minor
亦以 numpy 獨立重算,不呼叫被測私有函式。

- **OM1 present + backward-compat + 零回歸**:`("geo","obb_minor")` 每 cascade beat finite/有 bone・非
  cascade 逐位元同 base・`po`/`None` 逐位元同件序・**零回歸**(`geo` 預設==`("geo","centroid_farthest")`、
  `pca`/`pca_minor`/`farthest_pair`/`hull_longest_edge`/`obb_major` 皆逐位元不變、各 derive==閘獨立重算)。
- **OM2 crux 正確性 + 件序無關 + 符號確定**:(a) `obb_minor` == 閘獨立 scipy+卡尺 OBB 次軸逐位元
  **且 ⟂ obb_major**(|dot|≤1e-6);(b) 唯一最小盒(slant_quad)& 面積並列(三角每邊)所有排列 → 1 個
  distinct 帶號向量;(c) 沿 x 鏡射(y→−y)→ 方向 y 分量符號翻轉、x 分量不變。
- **OM3 crux obb_minor 價值**:(a) **obb_minor ⟂ obb_major 是真正不同的波**:spread2d
  `[(0,0),(8,1),(2,6),(9,7),(4,3)]` minor 序 `[0,1,4,2,3]` ≠ major 序 `[3,1,4,2,0]`、L 形亦不同
  (asset-independent);(b) **min-area ≠ min-variance(vs pca_minor)**:L 形 obb_minor `(0,1)` vs pca_minor
  `(-0.389,-0.921)` **22.89°**、flag **21.42°**(質量偏一側 → OBB 次軸看外廓短邊、pca_minor 看方差次軸)。
- **OM4 端到端(robot)**:`build_animations(cascade_dir=("geo","obb_minor"))` 峰時刻依 OBB 次軸投影鍵
  (vec=`(0.9433,0.3319)`)嚴格遞增・最遠投影最後 pop・仍跨件波≥0.30・首尾 identity・特效 slot alpha=1・
  dir⟂nrip;**crux**:robot 上 obb_minor pop 序 `[1,3,0,2,4]` ≠ obb_major 序 `[1,2,0,4,3]`(端到端證不同波)。
- **OM5 metric + 守衛**:(a) == scipy+卡尺 OBB 次軸多佈局逐位元且 ⟂ 長軸;(b) **正方守衛** obb_minor 與
  pca_minor 皆 raise(判據不同:OBB 矩形長≈寬 vs λ1≈λ2)而 `farthest_pair`/`hull_longest_edge` 確定性回值;
  (c) 守衛 件重合/單件/空件/未知 source(直接 & 經 build)→ValueError、`("geo","obb_minor")` 經 build 可用。

端到端 `build_spine.py assets/robot_parts.psd --animate --cascade-dir geo:obb_minor` → 產可載入 Spine 素材。

## 關鍵發現

1. **OBB 的長/次軸構成一對正交的確定性波** —— 與 PCA 的主/次軸完全平行(J-8/J-9);長軸確定性定號一旦
   釘住,次軸只是轉 90° 後套同一符號規則,不必另造機制(呼應 `_pca_principal_axis_dir(minor=True)`)。
2. **「換幾何特徵」(J-9 pca 長↔短、J-13 obb 長↔短)與「換資訊基礎」(J-8 散佈 / J-12 面積)是兩條正交的
   provenance 價值軸** —— obb_minor 同時佔「obb 家族」且是「次軸」,其 crux 要**分別**對 obb_major
   (⟂,不同波)與 pca_minor(面積≠方差)各別證,不硬塞單一佈局同時分開全部(呼應 J-11 的通則)。
3. **正交不保證特定件佈局下 pop 序一定不同** → 「不同波」的 crux 要**端到端在真實/合成 2D 佈局上**證件 pop
   序不同(OM3a/OM4),不只證向量正交(呼應 J-9 PM3/PM4)。
4. **退化守衛沿著整個 OBB 家族共用** —— 最小矩形近正方時長/短軸皆不唯一,obb_major 與 obb_minor 由同一
   `aspect_tol` 守衛同時擋掉;極值型 fp/hle 無此守衛 → {obb_major, obb_minor, pca, pca_minor} 與
   {fp, hle} 由「正方是否 raise」分兩族。

## honest boundary(仍在)

- 用 `obb_minor` / `obb_major` / `hull_longest_edge` / `farthest_pair` / `pca` / `pca_minor` /
  `centroid_farthest`(或手感常數)仍屬**美術手感(A 類 PROPOSAL)**:本閘只新增一個**確定性**幾何 source。
- `aspect_tol=1e-6`、OM3 `MIN_ROT=3.0°`、tie `tol=1e-9`、`PERP_MAX=1e-6` 為量級選擇;單一真值資產(robot);
  無改任何生成/產線值(全 additive,minor=False 逐位元不變)。
- cap `cascade_dir_obb_minor` L2 併入 `spine-anim-forge`(仍 HOLD;生成能力整體待 S5 多 rig 真值等上游)。

## 下一步(候選,皆自主)

- **更多確定性幾何 source**:最小**周長**外接矩形軸(vs 最小面積)、加權質心方向、凸包**最短**邊、周長加權
  方向;或讓 genre 先驗庫建議「用哪個 geo source」(provenance 之上再加一層選擇規則;最終手感仍 A 類)。
- 或回 crossfade 線(L-7 之續)、charge 蓄力深度隨檔位、S5 rig 真值(C/資源類,使用者提供)。
