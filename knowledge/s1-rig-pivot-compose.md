# S1×S5 (G-1) rig × keyframe-pivot 組合正確性 — 整合閘

> 結論:`build_spine` 對「件繞關節 pivot」有**兩條不同機制**(S5 `--rig` 結構搬骨 / S1 keyframe-pivot
> `--pivot-rotate`/`--scale-pivot` 逐幀補償),兩者達成**同一幾何目標**(limb 繞關節動),故**不可疊加**
> (疊加=雙重補償)。`build_spine` 以 `(pivot_rotate or scale_pivot or shear_pivot) and not rig` 全域守衛
> **擇一**,本閘證此組合正確且把它釘成回歸防線。
> 依據:`tools/analyzer/validate_rig_pivot_compose.py`(純 CPU,對真實 robot 三版 build)。4 AC 全 PASS。
> 信心:高(結構事實 + 補償殘差 0.39px + 疊加注入假 translate 161px 強分離)。階段:S1(keyframe)× S5(rig)整合。

## 兩條「繞關節」機制(本就並存,從未被一起驗過正確組合)

| 機制 | 階段 | bone 原點 | 如何繞關節 | translate 通道 |
|---|---|---|---|---|
| **`--rig`** | S5 | **搬到接觸縫(關節)** | bone 自身 rotate/scale 本就繞 bone 原點 → 原點在關節 ⇒ **結構性繞關節**;父子樹(limb 掛 body)帶動 | **無**(不需補償) |
| **`--pivot-rotate`/`--scale-pivot`** | S1 | 留在**件中心** O | 逐幀補償 `Δ=(M−I)(O−P)`(P=關節)把不動點從件中心移到關節 ⇒ **keyframe 繞關節** | **有**(補償 Δ) |

兩者**冗餘**(同目標、不同機制),故 `build_spine.py` 用全域守衛 `... and not rig` **擇一**:rig 時跳過
keyframe 補償。本閘補的缺口 = **從未有 AC 驗過這個組合是對的**(呼應 (G-2)「整合點最該放回歸閘」、
RULES「每能力必配評估器」)。

## 誠實解答 STATE (G-1) 原議題:「per-bone 語意去重」為非議題

STATE「下一步」長期掛 (G-1):「`--rig`×pivot per-bone 語意去重 —— effect 件在 rig 下掛 root/body
**仍可受惠** pivot-rotate,現以 `not rig` 全域關掉」。本閘查證此想法**不適用**:

- effect 件(光暈)**無接觸縫** → `rig_layout` 給 `joint==False` → **不在** `pivot_of`(keyframe 機制)
  **也不在** `rig_joints`(rig 機制)的關節集合。
- `apply_pivots` 只補償 `bone in pivot_of` 者(line 253 `if bone not in pivot_of ... continue`)→
  effect 件在**非 rig 的 pivot 模式下本來就不被補償**(恆繞件中心)。
- ⇒ **沒有「關節 pivot」可讓 effect 件去繞**;兩機制都不對它做 pivot 補償。**無 per-bone 路由可做**。

故 (G-1) 的真正可做內容 = 把上面的組合正確性釘成整合閘(非新生成能力)。

## AC(4,客觀可量測;真實 robot:3 關節 limb=右手/頭/左手 × 5 主秀節拍)

- **R1 present + joint-set 一致 + routing**:三版 build(RIG/PIVOT/NAIVE)皆成功;RIG `rig_joints` 鍵 ==
  PIVOT `pivot_joints` 鍵(同一 S5 幾何推得同組關節 limb)且世界座標 ≤0.2px 一致;非關節件(光暈/身體)
  **不在**任一關節集合;每個旋轉/縮放主秀節拍(hit/combo/charge/burst/cascade)在 RIG 與 PIVOT 兩版皆動 ≥1 關節 limb。
- **R2 crux — 機制等價(皆繞關節)**:
  - rig 側(結構):每關節 limb `parent=="b_身體"`(結構鏈,非 root)、世界 bone 原點(父鏈累加)== 關節
    (≤0.2px)、**無 translate 通道**(自身變換繞原點=繞關節)。
  - pivot 側(補償):每(主秀節拍×關節 limb)補償後繞關節不動點殘差 **0.39px < 0.5**(重算 (G-2))。
  - ⇒ 兩機制皆把 limb 旋轉中心落在關節。
- **R3 crux 負對照 — 疊加雙重補償(守衛必要)**:真實 RIG 關節 limb **無** translate(守衛在產線成立);
  對 RIG 動畫副本跑 `apply_pivots`(餵件中心 O + 關節 P)→ 對關節 limb 注入**假** translate **max 161.2px**
  (≥8)→ 把 body-local 關節點推離 P → 證**疊加真的破壞不動點**、`not rig` 守衛**必要**(非任意選擇)。
- **R4 isolation — 非關節件兩機制一致**:非關節件(光暈=effect/身體=body)在 RIG `build_meta.joint==False`
  (bone 在件中心、無 pivot)、在 PIVOT 不在 `pivot_joints`(無 keyframe 補償)→ **兩機制皆不對其做 pivot 補償**。

## 關鍵發現

1. **同一幾何目標的兩條機制必須證「等價 + 不可疊加」才算組合正確** —— 等價(R2:兩者都把旋轉中心落在
   關節)解釋為何可擇一;不可疊加(R3:疊加注入 161px 假 translate 破壞不動點)解釋為何**必須**擇一。
   守衛 `... and not rig` 不是任意程式風格,是防雙重補償的正確性防線。
2. **rig 的「繞關節」是結構事實,不需密集取樣驗** —— bone 自身 rotate/scale 在 Spine 中本就繞 bone 原點;
   只要證「bone 原點(父鏈)== 關節 且 無 translate 通道」即證結構性繞關節(對比 pivot 側須量補償殘差)。
3. **一個掛了多個 session 的「待辦」可能是非議題** —— (G-1) 原想的 per-bone effect 受惠經查不成立
   (effect 無接觸縫→無關節 pivot 可繞,兩機制皆然)。誠實結論:把它轉成組合正確性閘,而非硬做一個無效果的路由。
4. **R3 的雙重補償量在 burst 最大(161px)** —— burst 首幀刻意塌陷(scale 0.02 / rot 25°),`(M−I)(O−P)` 的
   `M−I` 在極端 scale 下很大 → 假 translate 量級最大,最突顯疊加之害(同 (G-2) M3 的 161px 量級來源)。

## honest boundary(仍在)

- **單一 rig 真值**(robot 一件可拆肢體)—— 同 S5 一路硬缺口(多 rig 真值屬使用者資源,C 類)。
- 本閘驗旋轉/縮放主秀節拍;**shear 節拍**(wobble/squash/twist)的 rig×shear-pivot 組合另屬他閘範圍
  (現 shear-pivot 亦走 `not rig` 守衛,同一守衛涵蓋;本閘的 R3 已含 include_scale,shear 另需時可擴)。
- 繞 pivot 的**手感**(幅度/曲線)仍是美術(A 類);本閘只驗客觀幾何 + 組合正確性。
- cap `rig_pivot_compose` L2 併入 `spine-anim-forge`,該區塊**仍 HOLD**(防固化半成品)。
