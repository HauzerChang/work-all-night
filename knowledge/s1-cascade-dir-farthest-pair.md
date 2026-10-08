# S1 (J-10) cascade 波方向 farthest_pair geo source — 件群直徑軸(只依 2 極端件)

> candidate J-10 · 2026-10-08 run 002 · cap `cascade_dir_farthest_pair` L2(併入 `spine-anim-forge`,仍 HOLD)
> 閘:`tools/analyzer/validate_cascade_dir_farthest_pair.py`(5 AC 全 PASS)

## 承 (J-7/J-8/J-9):同一條 provenance 軸再多一個 geo source(直徑軸)

J-7 立了 `cascade_dir="geo"`(方向由件幾何導出),之後逐一補確定性 geo source。J-10 新增
`"farthest_pair"` = 件中心的**直徑軸**(互距最遠的兩件連線方向)。

| source | 方向怎麼來 | 資訊基礎 | 符號(正負)怎麼定 |
|---|---|---|---|
| `centroid_farthest`(J-7) | 質心 → **單一最遠件** | **質心**(全件均值)+ 單一最遠件 | 最遠件天然有向 |
| `pca`(J-8) | PCA **主軸**(λ1) | **全域二階矩**(所有件散佈) | 幾何規則確定性定號 |
| `pca_minor`(J-9) | PCA **次主軸**(λ2) | **全域二階矩**(與主軸正交) | 同 J-8 確定性定號 |
| **`farthest_pair`(J-10)** | 互距**最遠兩件**連線 | **只依 2 極端件**(與質心、內部件、二階矩皆無關) | **同一套 `_orient_axis` 定號**(本文 crux 2) |

**honest distinction(勿誇大)**:J-10 **不是**新正交軸、**不改** J-6 投影排序機制 —— 導出向量後仍走
`("proj", vec)` 路徑。它只是 J-7~J-9 那條「方向軸取值來源(provenance)」再多一個 source(最長跨距方向)。
跨件時序通道仍是三條正交軸(結構 nrip × 幅度 span × 方向 dir)。

## crux 1(價值):farthest_pair 的**資訊基礎**與既有三者皆不同 —— 只依 2 極端件

J-8 vs J-9 比的是「換幾何特徵」(長軸 vs 短軸),兩者**資訊基礎相同**(都用全域二階矩)。
J-10 換的是**資訊基礎本身**:直徑只由**兩個互距最遠的極端件**決定 —— 不依質心(≠ cf)、不依內部件 /
全域散佈(≠ pca/pca_minor)。這帶出一個乾淨、可量化的**不變量**:

> **移動一個非極端的內部件 → farthest_pair 方向逐位元不變;但 centroid_farthest(質心移動)與 pca
> (二階矩改變)兩者皆隨之改變。**

閘 FP3 以**單一佈局**同時釘住兩件事(呼應 J-8 的 PA3「移非最遠件 cf 不變/pca 變」,J-10 更進一步:
fp 對內部件**全不變**,而 cf 與 pca **兩者都變**):

- 佈局 `[(-10,0),(11,0),(0,16),(1,1),(-2,-1.5)]`:直徑 = `(-10,0)-(11,0)`(水平)→ `fp0=(1,0)`;
  遠離質心的 `(0,16)` → `cf0=(0,1)`(**fp ⟂ cf,|dot|=0**,不同線)。
- 移動兩個內部件(idx 3,4)→ **`fp` 逐位元不變**(`(1,0)`),而 `cf` 改變(|dot|<1)、`pca` 改變(|dot|<1)。

> ⚠️ **誠實的細微處**:farthest_pair 的**軸「線」**完全由 2 極端件決定(內部件全不影響);但其**符號**用的是
> 與 pca 共用的 `_orient_axis`(以**件質心**為基準投影找極端件),故原則上符號參考可能隨內部件移動而變。
> 本閘 FP3 的佈局中水平極端件(±10/11)的 |proj| 恆最大 → 符號不翻,**連帶號向量都逐位元不變**(更強的
> 展示)。一般情形至少保證「軸線」不變;符號採**與既有 source 一致**的規則(見 crux 2),而非另造。

## crux 2(正確性):件對無序的 ± 歧義,用**同一套**規則定號 + 件序無關

直徑的兩端點無序 → 只給一條線(±v 皆合法,與 PCA 同病)。J-10 **不另造**定號機制:

1. **選直徑件對**:O(n²) brute-force 找最大互距;**並列最遠**件對(如正方兩條對角線等長)取**端點座標
   字典序最小**的 canonical 件對(端點先排序後比較)→ 純幾何、**與件輸入順序無關**。
2. **定號**:抽出 J-8 建立的符號規則成共用 helper `_orient_axis(centers, ux, uy)` —— 指向沿該軸(相對
   件質心)投影 |proj| 最大的極端件、tie 以座標字典序。沿用後 `_pca_principal_axis_dir` 的符號語意與
   farthest_pair **完全一致**(所有 geo source 共用同一「波朝最外延掃」符號約定)。

閘 FP2 驗:(a) fp == 閘**獨立 brute-force** 直徑(|dot|≈1);(b) 非對稱 & **正方**(兩對角線並列最遠,
正是 tie-break 的考驗)佈局的**所有排列**產出**逐位元同一**帶號向量;(c) 傾斜直徑沿 y 鏡射 → y 分量符號
確定性翻轉。

## crux 3(行為差異):farthest_pair **無各向同性退化**,正方上 fp 成功 / pca 報錯

pca/pca_minor 在近似各向同性(λ1≈λ2,如正方 / 正多邊形)時**主軸不唯一 → ValueError**(J-8/J-9 守衛)。
farthest_pair **沒有這個退化**:直徑恆良定義(除非件**全重合**);正方等對稱佈局只是讓「哪條直徑」有並列,
由 canonical tie-break 確定性選一條對角線 → **不報錯**。閘 FP5(b) 以同一組佈局(正方 / 正五邊形)證兩
source **行為不同**:`farthest_pair` 成功、`pca` ValueError。這是一個誠實的**行為對照**,非優劣宣稱 ——
farthest_pair 對對稱佈局給出確定答案,但那條對角線的選擇是 tie-break 約定(honest boundary)。

## 端到端(robot,FP4)

真實 robot 骨架 `build_animations(cascade_dir=("geo","farthest_pair"))`:導出 vec≈`(0.671, 0.741)`(對角),
每 cascade beat 各件峰時刻依直徑投影鍵**嚴格遞增**、最遠投影最後 pop、仍一道跨件波(散佈≥門檻)、首尾
setup identity、特效 slot alpha=1、dir⟂nrip(帶 ripples 時各件 pop 次數==nrip)。**crux**:robot 上
farthest_pair pop 序 `[3,0,1,2,4]` **≠** pca 主軸 pop 序 `[1,0,2,3,4]` → 端到端證兩者不同波。

## 實作(全 additive,centroid_farthest/pca/pca_minor 路徑逐位元不變)

- `_orient_axis(centers, ux, uy)`(**新,抽出 J-8 共用符號規則**;`_pca_principal_axis_dir` 內聯碼**未動** →
  pca/pca_minor 路徑逐位元不變,僅新增供 farthest_pair 共用)。
- `_farthest_pair_axis_dir(centers)`(**新**;brute-force 直徑 + canonical tie-break + `_orient_axis` 定號;
  守衛 n<2 / 全件重合 → ValueError)。
- `derive_cascade_dir` 加分支 `source=="farthest_pair"`;`_CASCADE_GEO_SOURCES` 加 `"farthest_pair"`。
- `_normalize_cascade_dir`/`_cascade_phase_of`/`build_spine --cascade-dir geo:farthest_pair` **無須改碼**
  (走 J-7 既有 `("geo", source)` 解析)。

`validate_cascade_dir_farthest_pair.py`(直徑件對**由閘以 O(n²) brute-force 獨立重算**,不呼叫生成器私有
函式)**5 AC 全 PASS**。回歸:既有 cascade dir 閘(`validate_cascade_dir`/`_vector`/`_geo`/`_pca`/`_pca_minor`)
逐一 **PASS** → centroid_farthest/pca/pca_minor 路徑逐位元不變;check_readiness **0 RED**(新增 cap
`cascade_dir_farthest_pair` L2 併入 `spine-anim-forge`,仍 HOLD)。

## 關鍵發現

1. **provenance 的價值軸有三層,不互相宣稱優劣**:J-8 vs J-9 是「換幾何特徵」(長軸 vs 短軸,**同**資訊基礎);
   J-10 是「**換資訊基礎**」(2 極端件 vs 全域二階矩 vs 質心單點)。三者是**正交的 provenance 選擇**,各自誠實標明。
2. **「只依少數極端點」給出乾淨的不變量**:farthest_pair 對內部件的**全不變性**是比 cf(PA3 只對「非最遠件」不變)
   更強的性質,而且用**單一佈局**就能同時證 fp 不變 + cf 與 pca 皆變(資訊基礎三方對照)。
3. **符號定號可抽成跨 source 共用 helper**(`_orient_axis`):一旦把「無向線 → 有向向量」的規則釘死(投影極端件
   + 座標字典序 tie-break + 件序無關),任何「只給一條線」的幾何 source 都能直接共用,不必各自重造(呼應 J-9
   「同一套 PCA 符號定號可延伸到次主軸」)。
4. **退化行為是 source 的固有屬性,要誠實對照**:pca 各向同性退化、farthest_pair 件全重合退化 —— 兩者退化
   條件不同(FP5(b) 正方上行為相反),閘以**行為對照**呈現而非宣稱誰更穩健。

## honest boundary

- 用 `farthest_pair` / `pca` / `pca_minor` / `centroid_farthest`(或手感常數)仍屬**美術手感**(A 類 PROPOSAL,
  本閘只新增一個**確定性**幾何 source)。
- 並列最遠件對的 canonical tie-break(座標字典序)是**確定性約定**,非幾何唯一解(對稱佈局本就無唯一直徑)。
- farthest_pair 的**符號**用件質心基準的 `_orient_axis`(與既有 source 一致),故軸「線」對內部件完全不變,
  符號在一般情形可能隨質心微動(FP3 佈局中不翻 → 連帶號向量逐位元不變)。
- `rtol=1e-9` 並列判定、FP3/FP5 門檻為量級選擇;無改任何生成 / 產線值(全 additive,既有 geo source 逐位元
  不變);單一真值資產(防固化)。
