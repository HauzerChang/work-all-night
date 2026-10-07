# S1 (J-8) cascade 波方向 PCA 主軸 geo source — 符號確定性地解掉 J-7 迴避的 PCA ±歧義

> candidate J-8 · 2026-10-07 run 002 · cap `cascade_dir_pca` L2(併入 `spine-anim-forge`,仍 HOLD)
> 閘:`tools/analyzer/validate_cascade_dir_pca.py`(5 AC 全 PASS)

## 承 (J-7):同一條「方向軸取值來源(provenance)」多一個 geo source

J-7 讓 `cascade_dir="geo"` 時方向向量由件幾何導出,但**只實作了一個 source**:`centroid_farthest`
(質心 → 距質心最遠件)。J-7 當時**刻意避開 PCA**,原因寫在其 docstring:

> 「PCA 主軸只給一條**線**、方向正負須另定;最遠件天然定出一個明確指向。」

也就是 PCA 的主軸 `±v` 皆是合法特徵向量(numpy `eigh` 回哪個符號**不保證**、隨數值/輸入擺動),
若不定號就把「人手指定」又以另一種形式加回來。J-8 **正面解掉這個 ±歧義**,新增 geo source `"pca"`:
用 PCA 主軸(**最大變異方向**,反映件群的**整體散佈**)並以**幾何規則確定性定號**。

| source | 方向怎麼來 | 反映什麼 | 符號(正負)怎麼定 |
|---|---|---|---|
| `centroid_farthest`(J-7) | 質心 → **單一最遠件** | 單一極端件(單點) | 最遠件天然有向 |
| **`pca`(J-8)** | 件中心的 **PCA 主軸** | **整體散佈**(全域二階矩) | **幾何規則確定性定號**(本文 crux) |

**honest distinction(勿誇大)**:J-8 **不是**新正交軸,**不改** J-6 的投影排序機制 —— 導出向量後仍走
`("proj", vec)` 路徑。它只是 J-7 那條 provenance 軸多一個 source;其 crux 是**把 PCA 的符號歧義釘死**。
跨件時序通道仍是三條正交軸(結構 nrip × 幅度 span × 方向 dir)。

## crux 1:符號確定性(解掉 PCA ±歧義)

閉式 2×2 PCA(避開外部 `eig` 的特徵向量 ±不確定):共變異 `[[sxx,sxy],[sxy,syy]]` 的主軸角
`θ = ½·atan2(2·sxy, sxx−syy)` → 主軸 `(cosθ, sinθ)`(對應較大特徵值 λ1,即資料橢圓長軸)。

**定號規則(純幾何、件序無關、保 J-7 語意)**:主軸指向**沿主軸投影 |proj| 最大的極端件**(令其 proj ≥ 0)。
這保留 J-7「波朝最外延掃」的語意(最外延件投影最大 → 最後 pop)。tie(投影量並列,如左右對稱佈局)時
以**座標字典序最大件**定號 —— 純幾何 tie-break → **與件輸入順序完全無關**。

> **為何不能用 index tie-break**:天真規則「tie 時取 index 最小件」會因**件排列順序不同**而選到不同物理件 →
> 符號翻轉。對稱佈局(如 `[(−10,0),(10,0),(0,3),(0,−3)]`)正是反例:index tie-break 下 `[A,B,…]` 與
> `[B,A,…]` 兩種輸入會得相反方向。幾何 tie-break(座標字典序)對任意排列回同一件 → 逐位元同一向量。
> (PA2(b):非對稱 120 排列 + 對稱 24 排列**皆只有 1 個 distinct 輸出**。)

## crux 2:pca 看整體散佈 vs centroid_farthest 看單一最遠件(價值)

兩 source 的**資訊基礎不同**,這是 J-8 相對 J-7 的價值,也是**誠實的**差異(非「PCA 更穩健」的過度宣稱):

- **(a) 最遠件離主散佈軸時兩者不同線**:佈局 = 沿 x 的 6 件 + 一個離軸最遠件 `(0,22)`。
  `pca` 貼**整體延展**(與 x 軸夾角 **0°**);`centroid_farthest` **朝單一最遠件**甩(夾角 **90°**);|dot|=0 → 不同線。
- **(b) cf 只依單一最遠件,pca 整合所有件**:移動一個**非最遠**內部件(`(−5,0)→(−5,8)`,最遠件 `(0,22)` 不變)
  → `cf` 方向**嚴格不變**(line shift **0.0°**:它只看質心→最遠件,質心 x 對稱不動)、`pca` 主軸**隨之改變**
  (line shift **7.96°**)。證 cf 是**單點統計量**、pca 是**全域二階矩**。

> ⚠️ **誠實邊界 — PCA 對遠離群件並非穩健**:方差是平方和,**單一夠遠的離群件會主導方差** → PCA 主軸也會被它拉轉
> (探針:離軸件 y 由 22 推到 34,pca 線由 0° 翻到 90°,這是**正確行為** —— 該件此時真的成了主散佈方向)。
> 故本閘**不宣稱** PCA「抗離群」;只宣稱其資訊基礎是**整體散佈**而非單一極端件(crux 2 兩條皆嚴格為真)。

## 守衛:近似各向同性 → ValueError(不捏造方向)

PCA 主軸只在有明確各向異性時良定義。守衛:件重合(λ1≈0,無散佈)或 **λ1−λ2 ≤ `aniso_tol`·(λ1+λ2)**
(近似各向同性,主軸不唯一,如**正方 / 正多邊形**對稱佈局)→ `ValueError`。
PA5(b) 證門檻有鑑別力:正方 / 正五邊形 → raise;僅微量各向異性(`var_x≫var_y` 些微)→ 放行且軸正確(0°)。

## 實作(全 additive;`centroid_farthest` 路徑逐位元不變)

- `gen_animations._pca_principal_axis_dir(centers, aniso_tol=1e-6)`:閉式 2×2 PCA + 確定性定號 + 各向異性/重合守衛。
- `derive_cascade_dir(centers, source)`:`source=="pca"` 於 `n==0` 守衛後**提前分流**到上函式;
  `centroid_farthest` 落在其後的**原碼**(逐位元不變)。`_CASCADE_GEO_SOURCES` 加 `"pca"`。
- `_normalize_cascade_dir` / `_cascade_phase_of` / `build_spine --cascade-dir`:**無須改碼** —— `("geo", "pca")`
  走 J-7 既有的 `("geo", source)` 解析;`geo:pca` 由 J-7 既有的 `_parse_cascade_dir` 的 `geo:SOURCE` 分支吃。
- **J-7 閘微調**:`validate_cascade_dir_geo.py` 原有一條負對照斷言 `derive_cascade_dir(.,"pca")` 應 raise
  (當時 pca 未實作);J-8 起 pca 已合法 → 改用仍未知的 `"nonexistent_src_zzz"`,**守衛語意不變**。

## 閘(`validate_cascade_dir_pca.py`,5 AC 全 PASS)

PCA 主軸 / 投影序**由閘以 numpy 獨立重算**(不呼叫生成器私有 `_pca_principal_axis_dir`)以保持獨立驗證。

- **PA1 present + backward-compat**:`("geo","pca")` 產每 cascade beat(finite/有 bone)・非 cascade 主秀 beat
  逐位元同 base・`None`/`po` 逐位元同件序・**零回歸** `"geo"` 預設逐位元 == `("geo","centroid_farthest")`、
  `derive_cascade_dir(.,"centroid_farthest")` == 閘獨立質心→最遠件。
- **PA2 crux 符號確定性**:(a) 拉長件群主軸 == 閘獨立 numpy 主特徵向量(同一條線,|dot|≈1);
  (b) **件序無關**(非對稱 + 對稱佈局所有排列 → 逐位元同一帶號向量);(c) 沿主軸鏡射 → 符號確定性翻轉。
- **PA3 crux pca vs cf**:(a) 最遠件離主軸 → pca 貼主軸 0° / cf 甩向離群件 90° / 不同線;
  (b) 移非最遠內部件 → cf 方向嚴格不變(0°)/ pca 隨之改變(7.96°)。
- **PA4 端到端排序(robot)**:`build_animations(cascade_dir=("geo","pca"))` 每 cascade beat 各件峰時刻依閘獨立
  pca 投影鍵嚴格遞增(robot 導出 vec≈`(0.998,0.063)`、波序 `[1,0,2,3,4]`、最遠投影最後 pop)+ 仍跨件波
  (散佈≥0.30)+ 首尾 setup identity + 特效 slot alpha=1 + dir⟂nrip。
- **PA5 metric + 守衛**:(a) pca 主軸 == numpy 共變異主特徵向量(3 佈局 |dot|≈1);(b) 各向異性門檻有鑑別力
  (正方 / 正五邊形 → ValueError、微量各向異性放行);(c) 守衛 件重合 / 單件 / 空件 / 未知 source(直接 &
  經 build_animations `("geo","zzz")`)→ ValueError,`("geo","pca")` 經 build 可用。

## 關鍵發現

1. **J-7 迴避的「PCA ±符號歧義」可用純幾何規則確定性解掉** —— 不必回退到「人手定號」:閉式 2×2 主軸
   (`θ=½atan2`)避開外部 eig 的符號不確定,再以「指向投影 |proj| 最大極端件」定號(保 J-7 語意),
   **tie-break 必須用幾何(座標字典序)非 index**,否則件排列會翻號(對稱佈局是反例)。
2. **「一條無向線 → 有向向量」的定號,正確性靠「件輸入順序無關」釘住** —— 對所有排列證逐位元同一輸出,
   正是 J-7 刻意避 PCA 所擔心的歧義被消除的鐵證(呼應本 repo 通則「一般化/新表示的正確性靠不變量釘死」:
   J-6 的 lr/rl==0°/180° 特例、L-7 的 scalar==等值向量逐位元)。
3. **同一「值由資料導出」的 provenance 軸可有多個統計量來源,各反映不同層次** —— `centroid_farthest`=單點極端、
   `pca`=全域二階矩散佈;要誠實標明差異(移非最遠件 cf 不動 / pca 動)**而非誇大為「更穩健」**
   (PCA 對遠離群件有高槓桿、會被拉轉,這是正確行為)。選哪個 source 仍屬美術手感(A 類)。
4. **各向異性是 PCA 方向良定義的前提** —— 近似各向同性(正方/正多邊形)主軸不唯一,應 raise 不捏造方向;
   門檻要有鑑別力(恰各向同性 raise、微量各向異性放行且軸正確)。

## honest boundary(仍在)

- 用 `pca` 還是 `centroid_farthest`(或手感常數)仍屬**美術手感(A 類 PROPOSAL)**:本閘只新增一個**確定性**的
  幾何 source,不替使用者決定用哪個。
- `aniso_tol=1e-6`、PA3 門檻(align≤15° / swing≥40°)、PA3(b) 的 pca_shift≥5° 皆為量級選擇。
- 單一真值資產(robot);無改任何 beat 生成 / 產線值(全 additive,`centroid_farthest` 路徑逐位元不變)。
- cap `cascade_dir_pca` L2 併入 `spine-anim-forge`(仍 HOLD;生成能力整體待 S5 多 rig 真值等上游)。

## 下一步(候選,皆自主)

- **讓 genre 先驗庫建議「用 geo:pca 還是 geo:centroid_farthest 還是手感常數」**(provenance 之上再加一層
  選擇規則;但最終手感仍 A 類)。
- **其他確定性幾何 source**(如加權質心、沿主軸的**第二主軸**做垂直掃波)。
- 或回 crossfade 線(L-7 之續:genre 建議每接點 xf / crossfade×tier)、S5 rig 真值(C/資源類,使用者提供)。
