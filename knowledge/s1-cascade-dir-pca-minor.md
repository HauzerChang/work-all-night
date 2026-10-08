# S1 (J-9) cascade 波方向 PCA 次主軸 geo source — 沿短軸橫掃的另一條確定性幾何波

> candidate J-9 · 2026-10-08 run 001 · cap `cascade_dir_pca_minor` L2(併入 `spine-anim-forge`,仍 HOLD)
> 閘:`tools/analyzer/validate_cascade_dir_pca_minor.py`(5 AC 全 PASS)

## 承 (J-8):同一條 provenance 軸再多一個 geo source(次主軸)

J-8 新增 geo source `"pca"` = PCA **主軸**(最大變異方向,沿件群**長軸延掃**)。J-9 新增
`"pca_minor"` = PCA **次主軸**(**最小變異方向**,`θ+90°`,與主軸**正交**)—— 波沿件群的**短軸橫掃**。

| source | 方向怎麼來 | 幾何語意 | 符號(正負)怎麼定 |
|---|---|---|---|
| `centroid_farthest`(J-7) | 質心 → **單一最遠件** | 單點極端 | 最遠件天然有向 |
| `pca`(J-8) | PCA **主軸**(λ1) | **長軸延掃**(整體散佈最大方向) | 幾何規則確定性定號 |
| **`pca_minor`(J-9)** | PCA **次主軸**(λ2) | **短軸橫掃**(與主軸正交) | **同 J-8 確定性定號**(本文 crux) |

**honest distinction(勿誇大)**:J-9 **不是**新正交軸、**不改** J-6 投影排序機制 —— 導出向量後仍走
`("proj", vec)` 路徑。它只是 J-7/J-8 那條「方向軸取值來源(provenance)」再多一個 source(短軸方向)。
跨件時序通道仍是三條正交軸(結構 nrip × 幅度 span × 方向 dir)。

## crux 1(價值):次主軸是一條**真正不同的波**,非 pca 主軸的改版

次主軸與主軸**正交**,所以沿它排序件 → 得到**不同的 pop 序**。這是 J-9 的價值:同一套 PCA 機制,
換取一條幾何上正交、語意上互補(橫掃 vs 延掃)的確定性方向。

- 真實 robot 骨架(端到端驗證,PM4):major 導出 vec≈`(0.998, 0.063)`(≈水平)、pop 序 `[1,0,2,3,4]`;
  **minor 導出 vec≈`(0.063, −0.998)`(≈垂直)、pop 序 `[2,1,4,0,3]`** —— 兩序**不同**(閘以實測峰時刻比對)。
- 合成二維佈局(PM3):minor⟂major、依 minor 投影排序的件序 ≠ 依 major 投影排序的件序、次軸方向的極端件
  在 minor 下**最後 pop**。

> 這與 J-8「pca vs centroid_farthest」的價值軸不同:J-8 比的是**資訊基礎**(全域二階矩 vs 單點),
> J-9 比的是**幾何方向**(長軸 vs 正交的短軸)。兩者都誠實:J-9 不宣稱 minor「更好」,只是**另一個確定性選項**。

## crux 2(正確性):符號確定性(與 J-8 同一套,沿用不另造)

次主軸同樣只給一條**線**(±v 皆合法),符號歧義與主軸相同。J-9 **沿用 J-8 的定號規則**,不另造機制:
閉式 2×2 PCA 主軸角 `θ=½·atan2(2sxy, sxx−syy)`,次主軸 = `θ+90°`;再以「指向沿**該軸**投影 |proj| 最大的
極端件(令其 proj≥0)」定號,tie 以**座標字典序**(純幾何 → **件輸入順序無關**;非 index tie-break)。

- PM2(a):minor⟂major(|dot|≈0)且 minor == 閘獨立 numpy **次**特徵向量(同一條線,|dot|≈1)。
- PM2(b):非對稱 120 排列 + 對稱 24 排列**皆只 1 個 distinct 帶號向量**(對稱佈局正是 index tie-break 會翻號處)。
- PM2(c):沿 y 鏡射(翻次軸方向的極端件)→ 次軸符號確定性翻轉。

## 守衛:近似各向同性 → ValueError(主 / 次軸共用)

PCA 的主軸與次軸只在有明確各向異性(λ1≠λ2)時良定義;λ1≈λ2 時兩軸**皆**不唯一(正方 / 正多邊形),
`minor` 無從區分主/次。故守衛**與主軸共用**:件重合(λ1≈0)或 `λ1−λ2 ≤ aniso_tol·(λ1+λ2)` → `ValueError`。
PM5(b) 證門檻有鑑別力:正方 / 正五邊形 → raise;微量各向異性(`var_x≫var_y` 些微)→ 放行且次軸⟂主軸。

## 實作(全 additive;`centroid_farthest` 與 `pca` 路徑皆逐位元不變)

- `gen_animations._pca_principal_axis_dir(centers, aniso_tol=1e-6, minor=False)`:加 `minor` 參數。
  `minor=True` 時在算出 `θ` 後 `θ += π/2`(次主軸),再走**同一套**確定性定號。
  **`minor=False`(預設)= J-8 原碼逐位元不變** → `pca` 路徑零回歸。
- `derive_cascade_dir(centers, source)`:加分支 `source=="pca_minor" → _pca_principal_axis_dir(centers, minor=True)`;
  `_CASCADE_GEO_SOURCES` 加 `"pca_minor"`。
- `_normalize_cascade_dir` / `_cascade_phase_of` / `build_spine --cascade-dir`:**無須改碼** —— `("geo","pca_minor")`
  走 J-7 既有 `("geo", source)` 解析;`geo:pca_minor` 由 `_parse_cascade_dir` 的 `geo:SOURCE` 分支吃。

## 閘(`validate_cascade_dir_pca_minor.py`,5 AC 全 PASS)

主 / 次軸 / 投影序**由閘以 numpy 獨立重算**(不呼叫生成器私有 `_pca_principal_axis_dir`)以保持獨立驗證。

- **PM1 present + backward-compat + 零回歸**:`("geo","pca_minor")` 產每 cascade beat(finite/有 bone)・非
  cascade 逐位元同 base・`po`/`None` 逐位元同件序・**零回歸**(`geo` 預設逐位元 ==`("geo","centroid_farthest")`、
  `("geo","pca")` 加 minor 參數後逐位元不變、`derive(.,"pca")` 仍 == numpy **主**特徵向量 → 主軸路徑未動)。
- **PM2 crux 正交 + 符號確定性**:(a) minor⟂major + minor==numpy 次特徵向量;(b) 件序無關(所有排列逐位元同一);
  (c) 沿 y 鏡射 → 符號確定性翻轉。
- **PM3 crux minor vs major**:二維佈局 minor⟂major + minor 序 ≠ major 序 + 次軸極端件最後 pop。
- **PM4 端到端(robot)**:minor 投影序嚴格遞增 + 最遠投影最後 pop + **crux robot 上 minor pop 序 ≠ major pop 序**
  + 仍跨件波(散佈≥0.30)+ 首尾 setup identity + 特效 slot alpha=1 + dir⟂nrip。
- **PM5 metric + 守衛**:(a) minor == numpy 共變異最小特徵向量且⟂主軸(3 佈局);(b) 各向異性門檻有鑑別力
  (正方/正五邊形 → ValueError、微量各向異性放行且次軸⟂主軸);(c) 守衛 件重合/單件/空件/未知 source
  (直接 & 經 build)→ ValueError、`("geo","pca_minor")` 經 build 可用。

## 關鍵發現

1. **同一套 PCA 符號定號機制可直接延伸到次主軸** —— 主軸確定性定號(J-8)一旦釘住,次主軸只是 `θ+90°` 後
   套同一套規則,**不必另造機制**;正確性同樣靠「件輸入順序無關」釘死(呼應本 repo 通則:一般化/新表示的
   正確性靠不變量驗證,J-8 鏡射翻號、L-7 scalar==等值向量逐位元)。
2. **正交方向 = 一條真正不同的波** —— minor 與 major 幾何正交 → pop 序不同(robot 上實測 `[2,1,4,0,3]` vs
   `[1,0,2,3,4]`);價值 crux 要**端到端在真實資產上**證「不同波」,不能只證向量正交(向量正交不保證在特定
   件佈局下排序一定不同,故 PM3/PM4 都實測件序差異)。
3. **各向同性守衛主 / 次軸共用** —— λ1≈λ2 時主軸不唯一⇒次軸也不唯一,同一個守衛同時擋掉兩者;不需為 minor
   另設門檻。
4. **「換一個幾何特徵」與「換資訊基礎」是兩條不同的 provenance 價值軸** —— J-8 是後者(散佈 vs 單點)、
   J-9 是前者(長軸 vs 短軸);誠實地各自標明價值,不互相宣稱優劣。

## honest boundary(仍在)

- 用 `pca` / `pca_minor` / `centroid_farthest`(或手感常數)仍屬**美術手感(A 類 PROPOSAL)**:本閘只新增一個
  **確定性**的幾何 source(短軸方向),不替使用者決定用哪個。
- `aniso_tol=1e-6`、PM3/PM5 門檻(perp≤1e-6、align≤1e-6、barely |dot|≥0.999)皆為量級選擇。
- 單一真值資產(robot);無改任何 beat 生成 / 產線值(全 additive,`centroid_farthest`/`pca` 路徑逐位元不變)。
- cap `cascade_dir_pca_minor` L2 併入 `spine-anim-forge`(仍 HOLD;生成能力整體待 S5 多 rig 真值等上游)。

## 下一步(候選,皆自主)

- **讓 genre 先驗庫建議「用 geo:pca / geo:pca_minor / geo:centroid_farthest / 手感常數」**(provenance 之上再加
  一層選擇規則;最終手感仍 A 類)。
- **其他確定性幾何 source**(如加權質心、徑向以外的對稱軸)。
- 或回 crossfade 線(L-7 之續:genre 建議每接點 xf / crossfade×tier / 非對稱單接點 crossfade)、
  charge 蓄力深度隨檔位、S5 rig 真值(C/資源類,使用者提供)。
