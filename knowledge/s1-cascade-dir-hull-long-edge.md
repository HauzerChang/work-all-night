# S1 (J-11) cascade 波方向 凸包最長邊(hull_long_edge)geo source — 邊界決定,但取最長邊 ≠ 最長弦

> candidate J-11 · 2026-10-08 run 003 · cap `cascade_dir_hull_long_edge` L2(併入 `spine-anim-forge`,仍 HOLD)
> 閘:`tools/analyzer/validate_cascade_dir_hull_long_edge.py`(5 AC 全 PASS)

## 承 (J-7..J-10):同一條 provenance 軸再多一個 geo source(凸包最長邊方向)

J-7..J-10 把 cascade 方向軸的取值來源分別下推成「質心→最遠件 / PCA 主軸 / PCA 次主軸 / diameter(最遠對)」。
J-11 新增 `"hull_long_edge"` = 件中心**凸包最長邊**(相鄰頂點間最長的邊界邊)方向 —— 波沿件群輪廓的最長
一段邊界掃。

| source | 方向怎麼來 | 用到哪些件 | 幾何語意 | 符號(正負)怎麼定 |
|---|---|---|---|---|
| `centroid_farthest`(J-7) | 質心 → **單一最遠件** | 質心(全件)+ 1 件 | 單點極端 | 最遠件天然有向 |
| `pca`(J-8) | PCA **主軸**(λ1) | **所有件**(二階矩) | 長軸延掃 | 幾何規則確定性定號 |
| `pca_minor`(J-9) | PCA **次主軸**(λ2) | **所有件**(二階矩) | 短軸橫掃(⟂ 主軸) | 同 J-8 確定性定號 |
| `farthest_pair`(J-10) | **diameter**(最遠**弦**) | **只 2 個極端件**(hull) | 最長跨度(直徑) | **字典序**:小端點→大端點 |
| **`hull_long_edge`(J-11)** | 凸包**最長邊** | **只 2 個相鄰 hull 頂點** | 最長一段邊界 | **字典序**:小端點→大端點 |

**honest distinction(勿誇大)**:J-11 **不是**新正交軸、**不改** J-6 投影排序機制 —— 導出向量後仍走
`("proj", vec)` 路徑。它只是那條「方向軸取值來源(provenance)」再多一個 source。跨件時序通道仍是三條
正交軸(結構 nrip × 幅度 span × 方向 dir)。

## crux 1(價值):與 farthest_pair 的對比 —— 同屬凸包邊界量,但取不同邊界特徵(最長邊 ≠ 最長弦)

J-11 的價值 crux 不在「vs pca/cf」(那是全體點 vs 邊界點的老區分),而在**與 J-10 farthest_pair 的精細對比**:
兩者**都只看凸包邊界頂點**(都是「邊界決定量」),但**取不同的邊界特徵**:

- `farthest_pair`:凸包上**彼此距離最大的兩頂點**(最長**弦**,diameter)——兩端點**一般不相鄰**(跨對角)。
- `hull_long_edge`:凸包上**相鄰**兩頂點間最長的**邊**(最長**邊界邊**)。

最長弦 ≠ 最長邊(除退化情形)→ **一般給出不同方向**。

- **HE3(a) 同佈局方向相異**(值 crux,合成佈局 `[(10,3),(2,9),(4,-3),(-6,-4),(-7,6)]`):
  - he-vs-fp = **72.1°**(頭條:最長邊 ≠ 最長弦)
  - he-vs-pca = **87.4°**、he-vs-cf = **89.2°**(近正交)→ he 是一條真正不同的方向。
- **正方佈局**(HE5b):diameter = **對角**(`farthest_pair`→(0.707,0.707))、最長邊 = **一條邊**
  (`hull_long_edge` 回確定性邊,≠ 對角)→ 兩量在同一佈局明確不同。

**HE3(b) 邊界決定性**(he 與 fp 同一側):固定凸包四角、移動一個**嚴格內部(非 hull 頂點)件**
`(-5,3)→(6,5)`:
- **`hull_long_edge`:逐位元不變**(內部件非 hull 頂點 → 不影響任何邊);
- **`farthest_pair`:逐位元不變**(同屬邊界量);
- **`centroid_farthest`:轉 41.0°**(質心移動)→ 證 he 屬邊界決定量,與 cf 的全體點統計不同。

> 四條 provenance 價值軸至此:J-8 比**資訊基礎**(全域二階矩 vs 單點)、J-9 比**幾何方向**(長軸 vs 短軸)、
> J-10 比**對內部擾動的敏感度**(極端對不變 vs 全件敏感)、**J-11 比同屬邊界量的不同邊界特徵**(最長邊 vs
> 最長弦)。五者各自誠實,不互相宣稱優劣。

## crux 2(正確性):最長邊正確 + 符號 + 件輸入順序無關

- **最長邊正確性**(HE2a / HE5a):`hull_long_edge` == 閘**獨立** `scipy.spatial.ConvexHull` 最長邊(**逐位元**
  同向量,非只同線)—— robot / value / pent / hex 多佈局皆逐位元相等。生成端用**純 Python Andrew monotone
  chain**(不依賴 scipy),閘端用 scipy 獨立重算 → 兩路相互把關。
- **符號(定向)**:方向由**座標字典序較小端點**指向**較大端點**(純幾何,非 index)→ 件序無關。
- **件輸入順序無關**(HE2b):非對稱 5 件(120 排列)+ **正方 4 件(24 排列,四邊並列最長)**皆只
  **1 個 distinct 帶號向量**。並列最長時以**端點對的字典序**取唯一代表(排序後 `(lo,hi)` 最小者)。
- **符號跟隨幾何**(HE2c):沿 x 軸鏡射(y→−y)→ 方向 **y 分量符號翻轉、x 分量不變**。

## 守衛:凸包頂點 < 2 / 件重合 → ValueError;**無各向同性守衛**;全共線退化成 diameter

`hull_long_edge` 非變異軸、不靠特徵值分離,故**不需各向同性守衛**(與 `farthest_pair` 同、與 PCA 相反)。
守衛只擋:所有件重合(凸包 1 點,無邊)、件數不足、未知 source → `ValueError`(不捏造方向)。
**誠實邊界**:**全共線**時凸包退化成**線段**(Andrew monotone chain 的 `cross<=0` 判準丟棄共線中點,只留
2 端點),其唯一「邊」= diameter → 此退化情形 `hull_long_edge` 與 `farthest_pair` **重合**(HE5b 實測
`[(0,0),(1,1),(2,2),(3,3)]` 兩者皆 (0.707,0.707))。非退化(嚴格凸)佈局才一般相異。

## 實作(全 additive;前四 source 路徑皆逐位元不變)

- `gen_animations._convex_hull(points)`:Andrew monotone chain(先去重 + 座標字典序排序 → 件序無關;叉積
  `<=0` 丟棄共線中點,等同 scipy ConvexHull 頂點集)。純 Python、O(n log n)。
- `gen_animations._hull_long_edge_dir(centers, tol=1e-9)`:取凸包、找相鄰頂點間最長邊,並列以端點對字典序
  取唯一代表,方向 = 字典序小端點→大端點(正規化)。守衛頂點<2 / 邊長≈0 → ValueError。
- `derive_cascade_dir(centers, source)`:加分支 `source=="hull_long_edge" → _hull_long_edge_dir(centers)`;
  `_CASCADE_GEO_SOURCES` 加 `"hull_long_edge"`。
- `_normalize_cascade_dir` / `_cascade_phase_of` / `build_spine --cascade-dir`:**無須改碼** ——
  `("geo","hull_long_edge")` 走 J-7 既有 `("geo", source)` 解析;`geo:hull_long_edge` 由 `_parse_cascade_dir`
  的 `geo:SOURCE` 分支吃。
- 端到端 `build_spine --animate --cascade-dir geo:hull_long_edge` 產可載入 Spine 素材(json+atlas+png)。

## 閘(`validate_cascade_dir_hull_long_edge.py`,5 AC 全 PASS)

最長邊 **由閘以 scipy ConvexHull 獨立重算**(不呼叫生成器私有 `_hull_long_edge_dir`),diameter 以 brute-force、
PCA 以 numpy 獨立重算,保持獨立驗證。

- **HE1 present + backward-compat + 零回歸**:`("geo","hull_long_edge")` 產每 cascade beat(finite/有 bone)・
  非 cascade 逐位元同 base・`po`/`None` 逐位元同件序・**零回歸**(`geo` 預設、`("geo","pca")`、
  `("geo","pca_minor")`、`("geo","farthest_pair")` 皆逐位元不變、`derive(.,"pca")`==numpy 主特徵向量、
  `derive(.,"farthest_pair")`==閘獨立 brute diameter、`derive(.,"centroid_farthest")`==閘獨立質心→最遠件)。
- **HE2 crux 最長邊正確 + 件序無關 + 符號確定**:(a) ==閘獨立 scipy ConvexHull 最長邊逐位元;(b) 非對稱 & 正方
  (並列最長邊)所有排列逐位元同一帶號向量;(c) 沿 x 鏡射 → y 分量符號翻轉。
- **HE3 crux he vs fp/pca/cf**:(a) 同佈局 he-vs-fp 72.1°・he-vs-pca 87.4°・he-vs-cf 89.2°(皆 ≥20°,頭條
  he≠fp);(b) 移動嚴格內部件 → he & fp 逐位元不變、cf 轉 41.0°(pca 僅回報 0.51° **不作判準**:邊界點主導
  方差使 pca 對單一內部件移動弱敏感)。
- **HE4 端到端(robot)**:最長邊投影序嚴格遞增 + 最遠投影最後 pop + 仍跨件波(散佈≥0.30)+ 首尾 setup
  identity + 特效 slot alpha=1 + dir⟂nrip;**誠實回報** robot 上 he 序 `[3,0,1,2,4]` 與 major `[1,0,2,3,4]` 相異
  (不作判準)。
- **HE5 metric + 守衛**:(a) ==scipy 最長邊 多佈局逐位元;(b) **並列/退化** 正方 `pca`→ValueError 而
  `hull_long_edge` 確定性回一條邊(≠對角)、**全共線 he==farthest_pair**(退化成 diameter,誠實邊界);
  (c) 守衛 件重合/單件/空件/未知 source(直接 & 經 build)→ ValueError、`("geo","hull_long_edge")` 經 build 可用。

## 關鍵發現

1. **同屬「邊界決定量」仍可取不同邊界特徵** —— `farthest_pair`(最長弦)與 `hull_long_edge`(最長邊)都只看
   凸包頂點(都對內部件移動不變),但一個取**跨對角的弦**、一個取**相鄰的邊**,一般給不同方向。J-11 的價值
   crux 因此必須**和 J-10 直接對打**(同佈局不同方向 72°、正方對角 vs 邊),而非再比「全體 vs 邊界」。
2. **robot 資產上最長邊恰 == diameter**(he 序 `[3,0,1,2,4]` == fp)—— 這 5 件佈局的最長弦正好也是最長邊;
   故 genuine-difference crux **走合成佈局(asset-independent)**,呼應 J-10「內部件不變性不需真實資產」。
   誠實標明:在真實 robot 上 he 與 fp 同向,是這個特定佈局的巧合,不是普遍恆等。
3. **生成端 / 閘端用不同實作互證** —— 生成端純 Python Andrew monotone chain(不加 scipy 依賴到產線),閘端
   scipy ConvexHull 獨立重算;兩套不同演算法逐位元吻合 = 既不讓被測碼自證,也不讓產線被重量級依賴綁住。
4. **全共線是 hull_long_edge 與 farthest_pair 的交會點** —— 凸包退化成線段時兩量重合;把退化情形誠實標成
   「交會」而非 bug,和 J-10「正方 pca 退化、fp 不退化」一樣是幾何量的互補邊界刻畫。

## honest boundary(仍在)

- 用 `hull_long_edge` / `farthest_pair` / `pca` / `pca_minor` / `centroid_farthest`(或手感常數)仍屬**美術手感
  (A 類 PROPOSAL)**:本閘只新增一個**確定性**的幾何 source(最長邊方向),不替使用者決定用哪個。
- `tol=1e-9`、HE3 `MIN_ANGLE=20°` / `MIN_ROT=3.0°`、HE 各門檻皆為量級選擇。
- robot 上最長邊與 diameter 同向(佈局巧合);genuine-difference 靠合成佈局證。
- 單一真值資產(robot);無改任何 beat 生成 / 產線值(全 additive,前四 source 路徑逐位元不變)。
- cap `cascade_dir_hull_long_edge` L2 併入 `spine-anim-forge`(仍 HOLD;生成能力整體待 S5 多 rig 真值等上游)。

## 下一步(候選,皆自主)

- **其他確定性幾何 source**(如加權質心、最小包圍盒 OBB 軸、凸包最長對角);各有不同的敏感度 / 語意。
- **讓 genre 先驗庫建議「用哪個 geo source」**(provenance 之上再加一層選擇規則;最終手感仍 A 類)。
- 或回 crossfade 線(L-7 之續:genre 建議每接點 xf / crossfade×tier / 非對稱單接點 crossfade)、
  charge 蓄力深度隨檔位、S5 rig 真值(C/資源類,使用者提供)。
