# S1 (J-10) cascade 波方向 diameter(最遠對)geo source — 只由兩極端件決定、移動內部件不改向

> candidate J-10 · 2026-10-08 run 002 · cap `cascade_dir_farthest_pair` L2(併入 `spine-anim-forge`,仍 HOLD)
> 閘:`tools/analyzer/validate_cascade_dir_farthest_pair.py`(5 AC 全 PASS)

## 承 (J-7/J-8/J-9):同一條 provenance 軸再多一個 geo source(直徑方向)

J-7/J-8/J-9 把 cascade 方向軸的取值來源分別下推成「質心→最遠件 / PCA 主軸 / PCA 次主軸」。J-10 新增
`"farthest_pair"` = 件中心點集的 **diameter(彼此距離最大的兩件,凸包直徑)**方向 —— 波橫越「兩件最遠
分離的肢體」的最長連線。

| source | 方向怎麼來 | 用到哪些件 | 幾何語意 | 符號(正負)怎麼定 |
|---|---|---|---|---|
| `centroid_farthest`(J-7) | 質心 → **單一最遠件** | 質心(全件)+ 1 件 | 單點極端 | 最遠件天然有向 |
| `pca`(J-8) | PCA **主軸**(λ1) | **所有件**(二階矩) | 長軸延掃 | 幾何規則確定性定號 |
| `pca_minor`(J-9) | PCA **次主軸**(λ2) | **所有件**(二階矩) | 短軸橫掃(⟂ 主軸) | 同 J-8 確定性定號 |
| **`farthest_pair`(J-10)** | **diameter**(最遠對) | **只 2 個極端件** | 最長跨度(直徑) | **字典序**:小端點→大端點 |

**honest distinction(勿誇大)**:J-10 **不是**新正交軸、**不改** J-6 投影排序機制 —— 導出向量後仍走
`("proj", vec)` 路徑。它只是那條「方向軸取值來源(provenance)」再多一個 source。跨件時序通道仍是三條
正交軸(結構 nrip × 幅度 span × 方向 dir)。

## crux 1(價值):幾何基礎與前三者不同 —— 只由兩極端件決定 → 移動內部件不改方向

這是 J-10 最乾淨、且 **asset-independent** 的鑑別子:diameter 只取決於**彼此最遠的兩個件**;只要這兩件
不變,**移動任何內部(非極端)件完全不影響方向**。而 `centroid_farthest`(質心會隨內部件移動)與
`pca`/`pca_minor`(二階矩用所有件,內部件移動會轉動主/次軸)**都會改變**。

- FP3 實測(固定 diameter 對 `(-6,0)-(6,0)`、把內部件 `(3,0.5)→(3,6)`,diameter 對不變):
  - **`farthest_pair`:逐位元不變(0°)**;
  - `pca`:轉 **15.07°**;
  - `centroid_farthest`:轉 **10.03°**。

> 這與 J-8/J-9 的價值軸又不同:J-8 比**資訊基礎**(全域二階矩 vs 單點)、J-9 比**幾何方向**(長軸 vs 短軸)、
> **J-10 比對內部擾動的敏感度**(極端對不變 vs 全件敏感)。四者各自誠實,不互相宣稱優劣。

## crux 2(正確性):diameter 正確 + 符號 + 件輸入順序無關

- **diameter 正確性**(FP2a / FP5a):`farthest_pair` == 閘**獨立** brute-force diameter(**逐位元**同向量,
  非只同線)—— robot / L / scatter / diag 多佈局皆逐位元相等。
- **符號(定向)**:方向由**座標字典序較小端點**指向**較大端點**(純幾何,非 index)→ 件序無關。
- **件輸入順序無關**(FP2b):非對稱 5 件(120 排列)+ **正方 4 件(24 排列,兩對角並列 diameter)**皆只
  **1 個 distinct 帶號向量**。並列最遠時以**端點對的字典序**取唯一代表(排序後 `(lo,hi)` 最小者)。
- **符號跟隨幾何**(FP2c):沿 x 軸鏡射(y→−y)→ 方向 **y 分量符號翻轉、x 分量不變**。

## 守衛:件數 < 2 / 件重合 → ValueError;**但無各向同性守衛**(與 PCA 的關鍵差異)

`farthest_pair` 非變異軸、不靠特徵值分離,故**不需各向同性守衛**。只要 diameter > 0(≥2 件且不全重合)
方向就良定義。附帶一條誠實對比(FP5b):**正方**佈局 `pca` 因 `λ1≈λ2` 會 `ValueError`,而 `farthest_pair`
仍**確定性回對角 diameter**(`(0.707, 0.707)`,所有排列單一結果)。守衛只擋:件數 < 2(無對)、所有件重合
(diameter≈0)、未知 source → `ValueError`(不捏造方向)。

## 實作(全 additive;`centroid_farthest`/`pca`/`pca_minor` 路徑皆逐位元不變)

- `gen_animations._farthest_pair_dir(centers, tol=1e-9)`:O(n²) 找最遠對(diameter),並列以端點對字典序
  取唯一代表,方向 = 字典序小端點→大端點(正規化)。守衛件數<2 / diameter≈0 → ValueError。
- `derive_cascade_dir(centers, source)`:加分支 `source=="farthest_pair" → _farthest_pair_dir(centers)`;
  `_CASCADE_GEO_SOURCES` 加 `"farthest_pair"`。
- `_normalize_cascade_dir` / `_cascade_phase_of` / `build_spine --cascade-dir`:**無須改碼** —— `("geo","farthest_pair")`
  走 J-7 既有 `("geo", source)` 解析;`geo:farthest_pair` 由 `_parse_cascade_dir` 的 `geo:SOURCE` 分支吃。
- 端到端 `build_spine --animate --cascade-dir geo:farthest_pair` 產可載入 Spine 素材(json+atlas+png;robot 6 bones / 5 slots / 11 animations)。

## 閘(`validate_cascade_dir_farthest_pair.py`,5 AC 全 PASS)

diameter **由閘以 brute-force 獨立重算**(不呼叫生成器私有 `_farthest_pair_dir`),PCA 軸亦以 numpy 獨立重算,保持獨立驗證。

- **FP1 present + backward-compat + 零回歸**:`("geo","farthest_pair")` 產每 cascade beat(finite/有 bone)・非
  cascade 逐位元同 base・`po`/`None` 逐位元同件序・**零回歸**(`geo` 預設 ==`("geo","centroid_farthest")`、
  `("geo","pca")`、`("geo","pca_minor")` 皆逐位元不變、`derive(.,"pca")`==numpy 主特徵向量、
  `derive(.,"centroid_farthest")`==閘獨立質心→最遠件)。
- **FP2 crux diameter 正確 + 件序無關 + 符號確定**:(a) ==閘獨立 brute diameter 逐位元;(b) 非對稱 & 正方(並列
  diameter)所有排列逐位元同一帶號向量;(c) 沿 x 鏡射 → y 分量符號翻轉。
- **FP3 crux fp vs pca/cf**:固定 diameter 對 + 移動內部件 → fp 逐位元不變、pca 轉 15.07°、cf 轉 10.03°。
- **FP4 端到端(robot)**:diameter 投影序嚴格遞增 + 最遠投影最後 pop + 仍跨件波(散佈≥0.30)+ 首尾 setup
  identity + 特效 slot alpha=1 + dir⟂nrip;**誠實回報** robot 上 fp 序 `[3,0,1,2,4]` ≠ major `[1,0,2,3,4]`(不作判準)。
- **FP5 metric + 守衛**:(a) ==brute diameter 多佈局逐位元;(b) **並列/各向同性** 正方 `pca`→ValueError 而
  `farthest_pair` 確定性回對角且件序無關;(c) 守衛 件重合/單件/空件/未知 source(直接 & 經 build)→ ValueError、
  `("geo","farthest_pair")` 經 build 可用。

## 關鍵發現

1. **「同一條 provenance 軸」可被多種正交的鑑別維度刻畫** —— J-7/J-8/J-9/J-10 四個 geo source 各在不同維度
   互別:用到幾件(全件 vs 2 件)、資訊階數(一階質心 vs 二階矩 vs 極值對)、對內部擾動的敏感度。J-10 的
   價值 crux(內部件不變性)**不需真實資產**即成立,比 J-9「robot 上 pop 序不同」更 asset-independent。
2. **極值型幾何量(diameter)無各向同性病態** —— 不像 PCA 在 λ1≈λ2 退化,diameter 對正方/圓對稱仍良定義
   (選對角),代價是對並列最遠需一條確定性 tie-break(端點對字典序);誠實標明這條與 PCA 的互補性。
3. **定向(無向→有向)的正確性一律靠「件輸入順序無關」釘死** —— 本 run 的字典序定號、J-8/J-9 的投影極端件
   定號、J-6 的 lr/rl 特例,都以「所有排列逐位元同一帶號向量」驗證(含對稱佈局正是天真 index tie-break 翻號處)。
4. **獨立重算是幾何量閘的底線** —— diameter/PCA 皆由閘以 brute-force/numpy 獨立重算,不呼叫被測私有函式,
   才能真正把關(呼應 repo 通則:閘要可信,別讓被測碼自證)。

## honest boundary(仍在)

- 用 `farthest_pair` / `pca` / `pca_minor` / `centroid_farthest`(或手感常數)仍屬**美術手感(A 類 PROPOSAL)**:
  本閘只新增一個**確定性**的幾何 source(直徑方向),不替使用者決定用哪個。
- `tol=1e-9`、FP3 `MIN_ROT=3.0°`、FP 各門檻皆為量級選擇。
- 單一真值資產(robot);無改任何 beat 生成 / 產線值(全 additive,前三 source 路徑逐位元不變)。
- cap `cascade_dir_farthest_pair` L2 併入 `spine-anim-forge`(仍 HOLD;生成能力整體待 S5 多 rig 真值等上游)。

## 下一步(候選,皆自主)

- **讓 genre 先驗庫建議「用 geo:farthest_pair / geo:pca / geo:pca_minor / geo:centroid_farthest / 手感常數」**
  (provenance 之上再加一層選擇規則;最終手感仍 A 類)。
- **其他確定性幾何 source**(如加權質心、最小包圍盒軸、凸包最長邊;各有不同的敏感度/語意)。
- 或回 crossfade 線(L-7 之續:genre 建議每接點 xf / crossfade×tier / 非對稱單接點 crossfade)、
  charge 蓄力深度隨檔位、S5 rig 真值(C/資源類,使用者提供)。
