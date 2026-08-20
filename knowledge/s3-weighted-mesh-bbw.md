# S3 weighted mesh 骨骼變形平滑度 — biharmonic 權重(BBW 鬆弛版)對美術真值驗收

- **結論**:純 CPU、確定性的 **biharmonic 權重求解器**(cotangent Laplacian 的 BBW 鬆弛版)對 Award
  **3 個真實美術 weighted mesh**(光暈/左手/身體)驗收 **AC-A 全 PASS** —— 重現美術權重變形的一致性
  誤差 ≤ **6.8% 對角線**,且**我方翻面數 ≤ 美術翻面數**在**所有 pose 全成立**(我方權重至少和美術一樣平滑)。
  這補上了 `compare_robot_mesh` 誠實界定的**唯一未驗維度**:weighted mesh 的骨骼變形平滑度。
- **關鍵發現(修正舊假設)**:**變形平滑度(0 翻面)的槓桿是「權重平滑度」,不是「內部頂點密度」**。
  身體件 hull 重新三角化的密度掃描(nV 106→221)**在 ≤35° pose battery 全 0 翻面、與密度無關**;
  極端 +50°(超出美術自身耐受)則各密度**一致只有 1 個邊界 sliver 翻面**。
  → 推翻 `s3-robot-mesh-vs-award.md` 的「dense interior = smoothness」假設:biharmonic 權重讓
  **邊界為主的省頂點 mesh 也能乾淨變形**,可同時保住頂點經濟度 + 變形品質。
- **信心**:高(對真實生產 spine 的美術權重逐 pose 量化;求解器先以美術真值校準可信度再下判定)。
- **階段**:第 2 階段 / S3(里程碑:weighted mesh 生成能力 + 其自我品質閘,補齊 S3 最後未驗維度)。
- **工具**:`tools/mesh_gen/bbw_weights.py`(模組)、`tools/mesh_gen/validate_bbw.py`(閘)。

## 標準指令

```
python3 tools/mesh_gen/validate_bbw.py --sweep    # AC-A 3件全 PASS → exit 0;--sweep 附密度掃描
```

## 量化結果(pose battery = 每骨旋轉 {+10,+20,-20,+35}°)

| 件 | nV | 骨數 | 最差一致性誤差(佔對角線) | 我方翻面 ≤ 美術翻面 | AC-A |
|---|---|---|---|---|---|
| 光暈 | 78 | 4 | 3.75% | ✅(+35°:我 0 / 美術 1) | PASS |
| 左手 | 80 | 2 | 6.79% | ✅(全 0) | PASS |
| 身體 | 98 | 3 | 2.45% | ✅(+35°:我 0 / 美術 3) | PASS |

身體密度掃描(hull 重新三角化,`triangle pq30a<area>`):

| max_area(%bbox) | nV | nT | ≤35° 翻面 | +50° stress 翻面 |
|---|---|---|---|---|
| 5.0 | 106 | 158 | 0 | 1 |
| 2.0 | 107 | 160 | 0 | 1 |
| 0.8 | 122 | 189 | 0 | 1 |
| 0.3 | 221 | 376 | 0 | 1 |

視覺證據:`knowledge/figures/s3_bbw_weights_body.png`(左二:美術 vs 我方 bone0 權重色圖,梯度相近;
右二:+35° 變形,美術 flips=3 底部纏繞 / 我方 flips=0 乾淨)。

## 方法(純 CPU,無 ML)

1. **FK**:Spine 3.8 bones(x/y/rotation/scale/parent)→ setup 世界矩陣;`pose_bones` 施加旋轉增量再 FK。
2. **加權蒙皮**:Spine `[nb, boneIdx,bindX,bindY,w, ...]`,世界頂點 = Σ_b w·(BoneWorld_b·[bindX,bindY])。
   用美術權重跑 = 真值變形;用我方權重跑 = 待驗變形。
3. **biharmonic 權重**:`Q = Lᵀ M⁻¹ L`(L=cotangent Laplacian, M=voronoi 質量);每骨在其 handle 頂點
   (= 骨 setup 世界原點最近的 mesh 頂點)w=1、其餘 handle w=0,解 Dirichlet biharmonic → clamp≥0 →
   正規化成 partition-of-unity。是 BBW 去掉 0≤w≤1 硬約束的鬆弛版(平滑、確定、稀疏解)。
4. **綁定**:由 setup 世界頂點反算各骨 bind 座標(inverse boneWorld · V0),可 `to_spine_vertices` 寫回 Spine。

## 評估器可信度(對美術真值校準)

- AC-A 直接把「我方權重的變形」與「美術權重的變形」在同一骨姿下逐頂點比對,誤差以對角線正規化;
  再加「我方翻面 ≤ 美術翻面」確保不是用糊掉的權重換低誤差。三件全 pose 成立 → 求解器可信。
- 負面/極端對照:+50°(超出美術耐受,美術身體 +35° 已 3 翻面)我方仍僅 1 邊界 sliver 翻面 → 平滑度上限高。

## ⚠️ 誠實界定 / 限制

- 「一致性誤差」量的是**與美術特定權重解的差距**,非絕對正確 —— weighted 權重無唯一解,美術/BBW 皆合法;
  真正的品質判準是**翻面數(拓樸合法性)**,故 AC 以「我方翻面 ≤ 美術翻面」為硬條件、誤差為輔助上限。
- handle 目前用**單一最近頂點定錨**;骨為線段(非點)時,線段 handle 會更貼近美術沿骨的權重分布(後續可升級)。
- 只驗 in-plane 旋轉骨姿;平移/縮放骨姿與多骨耦合極端姿未窮舉(pose battery 可擴充)。
- 密度掃描用**美術件 hull 重新三角化**(真幾何),尚未接 `generate_mesh_v2` 的自產輪廓 → 端到端
  「S3 生成輪廓 + 內部密度 + BBW → 寫回 Spine weighted mesh」為下一步(需把生成 mesh 對映進骨架世界空間)。

## 下一步候選

- **端到端 weighted 生成**:`generate_mesh_v2` 輪廓 + 內部取樣 + `bbw_weights` → 寫回 Spine json 的
  weighted attachment(`to_spine_vertices` 已備);對映進 Award 骨架世界空間後跑同一 flip 閘。
- **線段 handle**:骨用線段而非點定錨,量測是否進一步降低與美術權重的一致性誤差。
- **回接 S1 build_spine**:讓 `build_spine.py` 對「判為 mesh 且落在多骨影響區」的件自動綁 BBW 權重。
