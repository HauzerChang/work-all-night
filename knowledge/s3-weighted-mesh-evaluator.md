# S3 weighted-mesh 變形評估器 — 純 CPU 重現 Spine 骨骼變形 + LBS,對 Award 真值驗收

- **結論**:補上 `compare_robot_mesh.py` 唯一未驗的維度 —— **bone-driven weighted mesh 的變形品質**。
  新工具 `tools/mesh_gen/weighted_mesh.py` 用純 Python 重現 **Spine 3.8 骨骼世界變換
  (TransformMode.Normal)+ Linear Blend Skinning(LBS)**,不需 Spine runtime(CDN 被擋不影響)。
  對 Award 三個真實 weighted mesh 件(機器人拆件 身體/左手/光暈)**三軸驗收全 PASS**。
- **信心**:高。核心引擎(骨世界變換+LBS)由**藝術家真值自身**做非平凡交叉驗證(見 AC1),
  非自產真值;負對照與剛體校準皆通過。
- **階段**:第 2 階段 / S3(里程碑:S3 首次能量化 weighted mesh 骨骼變形,而非只有靜態覆蓋率)。
- **工具**:`tools/mesh_gen/weighted_mesh.py`(可重現)。

## 標準指令

```
python3 tools/mesh_gen/weighted_mesh.py     # AC1+AC2+負對照全過 → exit 0
```

## 三軸驗收(Award 真值)

| 件 | n | hull | internal | AC1 bind-consistency | AC2 baseline bend | bend-tolerance | strain-smoothness mean |
|---|---|---|---|---|---|---|---|
| 身體 | 98 | 40 | **58** | max 0.0075px ✅ | clean ✅ | 26° | 0.251 |
| 左手 | 80 | 42 | 38 | max 0.0071px ✅ | clean ✅ | ≥70° | 0.165 |
| 光暈 | 78 | 78 | **0** | max 0.0193px ✅ | clean ✅ | **18°** | 0.103 |

- **負對照**(打斷 parent 階層):bind-spread 168px(應 >>1px)✅ → 檢查有鑑別力。
- **剛體校準**:旋轉 root 40°(全骨剛體同動)→ strain-smoothness = **0.00000** ✅
  → 平滑度量測的是**微分變形**,不受整體平移/旋轉污染。

## 為何這個引擎可信(AC1 bind-consistency,關鍵)

weighted 頂點的每個 influence 存的是「該頂點在 setup pose 下**相對那根骨**的座標」。
所以對一個受多骨影響的頂點,把每個 influence 的 bind 座標用**各自骨的 setup 世界變換**還原,
必須落在**同一個世界點**。三件的多骨頂點還原離散度 max **0.007~0.019px**(次像素)
→ 同時驗證了(a)flattened weighted 格式解析、(b)Spine normal-mode 骨世界變換合成。
這是用外部真值(而非自產真值)驗證引擎的非平凡檢查。

Spine normal-mode 骨世界變換(本 repo 全 77 骨皆 normal):
```
la=cos(r)·sx  lb=-sin(r)·sy  lc=sin(r)·sx  ld=cos(r)·sy   (r=局部旋轉, x,y=局部平移)
world = parentWorld ∘ local   (root 的 parentWorld = 單位)
點套用:  x' = a·px + b·py + wx ;  y' = c·px + d·py + wy
LBS:     worldVert = Σ_influence  w · (boneWorld_b 套用 bind_b)
```

## 量化指標定義

- **AC1 bind-consistency**(硬閘,驗引擎):多骨頂點 per-influence 世界點離散度 < 1px。
- **AC2 baseline bend clean**:在**容差內**的溫和 pose 下 0 自交 / 0 翻面 / 0 退化。
- **bend-tolerance**:對抗式(driver 交替正負號)單步旋轉,能保持乾淨的最大角度。
- **strain-smoothness**:相鄰三角的**變形梯度 F**(setup→deformed 的 2×2 map)Frobenius 差的平均。
  剛體 → 0;值越低代表彎折越平滑。**這就是「內部取樣密度服務變形平滑度」要量化的指標**。

## 關鍵發現

1. **光暈(0 internal)bend-tolerance 只有 18°,最脆**:純邊界多骨 mesh 對「差分骨旋轉」容忍度低
   —— 只轉 4_LEG6(影響 49 頂點)而其他 3 根影響同一邊界的骨不動,邊界就在支配權交界處摺疊自交。
   對照身體有 58 個內部點,能吃 setup 幀 area_ratio≈1.0 的彎折 → **量化佐證「內部密度→變形穩健度」論點**
   (注:tolerance 亦受 pose 對抗性影響,非單一「越多內部點越大」;身體 26° 是 ±18° 反向對抗式彎折的結果)。
2. **bend-tolerance 是 pose 相依的特徵值**,不是絕對品質分;正確用法是**同 driver 同角度**下比較
   「生成 mesh vs 藝術家 mesh」(下一步),而非比絕對數字。
3. **strain-smoothness 已校準**(剛體=0),可作為下一步生成器 weighted mesh 的平滑度閘。

## 誠實界定 / 限制

- 只驗 `TransformMode.Normal`(本資產全 normal);若日後遇 `noRotationOrReflection` 等模式需擴充。
- 這三件在 Award **無 deform timeline**(純骨骼+權重變形),故用**合成骨 pose** 掃描,
  非真實動畫幀(Award 的 12 支動畫是否驅動這些骨、以多大角度,尚未逐幀比對 → 可作後續)。
- 本工具是 candidate 2 的**評估器半邊**(RULES:每能力必配評估器,且需先於生成器)。
  **尚缺:weighted mesh 生成器**(內部取樣密度控制 + BBW/熱擴散權重),用本評估器對照藝術家
  身體/左手件的 strain-smoothness 收斂 → 下一個 bounded chunk。

## 下一步候選

- **S3 weighted 生成器**:給一件 alpha + 骨骼結構(bones + 影響半徑),自動放內部取樣點
  (密度可控)+ Delaunay 三角化 + BBW/熱擴散骨權重 → 輸出 flattened weighted vertices。
  用 `weighted_mesh.py` 對照藝術家件:同 pose 下 strain-smoothness ≤ 藝術家 baseline(+margin)、
  bend-tolerance ≥ 藝術家、頂點經濟。
- 逐幀比對 Award 動畫實際驅動這些骨的角度,把合成 pose 換成真實動畫 pose。
