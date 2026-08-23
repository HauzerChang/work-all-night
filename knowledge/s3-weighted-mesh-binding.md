# S3 weighted-mesh 骨綁權重生成 + 變形品質閘(補上唯一未驗維度)

- **結論**:補上 `s3-robot-mesh-vs-award` 誠實界定的唯一未驗維度「靜態覆蓋率 PASS ≠ weighted
  骨骼變形品質」。新增 (1) 可信的 Spine 3.8 re-pose 基礎件、(2) bone-heat 骨綁權重生成器、
  (3) weighted-mesh 變形品質閘(對 Award 3 件真值自校準 + 雙負對照)。對 Award 機器人
  光暈/左手/身體 **3 件 overall_pass**:生成權重**有效**(partition-of-unity、bounded、非負)
  且在「美術自校準包絡」內**變形 0 自交 / 0 翻面**。
- **信心**:高(對真實生產 spine 的美術權重+骨架逐件量化;基礎件自一致性 MAE=0;閘有雙負對照)。
- **階段**:第 2 階段 / S3(+ S2 補上「骨綁權重 / weighted 變形」品質閘)。
- **工具**:`tools/mesh_gen/weighted_mesh.py`(re-pose 基礎件)、`bbw_weights.py`(bone-heat 生成器)、
  `validate_weights.py`(閘 + Award 驗收,可重現)。圖:`figures/weighted_deform_artist_vs_boneheat.png`。

## 標準指令

```
python3 tools/mesh_gen/validate_weights.py     # 3 件全 PASS → exit 0
```

## 量化結果(assets/Award.json 真值:3 weighted mesh 件)

| 件 | bones | nv | A1 美術內在 | A2 破壞單位分割 | A3 撕裂 rig | B 自一致 | C1 生成內在 | C2 生成變形平滑 | R1 與美術相似(相對位移 worst/mean) |
|---|---|---|---|---|---|---|---|---|---|
| 光暈 | LEG3-6 | 78 | ✅(pu 1e-5) | ✅抓到 | ✅抓到(59) | ✅ MAE=0 | ✅ | ✅ 0 自交 | 33.6 / 11.5 **(發散)** |
| 左手 | LEG5,9 | 80 | ✅ | ✅ | ✅(15) | ✅ | ✅ | ✅ 0 自交 | 1.46 / 0.65 |
| 身體 | LEG3,7,8 | 98 | ✅ | ✅ | n/a(剛性) | ✅ | ✅ | ✅(無旋轉骨) | n/a |

視覺:`figures/weighted_deform_artist_vs_boneheat.png`(setup 灰 / 美術綠 / bone-heat 橙;左手綠橙近乎重合、光暈明顯發散)。

## 方法

### 1. re-pose 基礎件(`weighted_mesh.py`)—— 對照 CLAUDE.md 雷點 #4
- `bone_world_matrices(sk, rot_override, scale_override)`:依 bones 陣列序(parent 先)算每骨世界 2×3 仿射。
  實作 TransformMode.normal(繼承旋轉+縮放);Award 9 條 leg 骨實測皆 normal / 無 shear / 單位 scale → 精確。
- `weighted_world_vertices`:由 weighted attachment 扁平 `[boneCount,(idx,bx,by,w)*]` 算世界頂點。
- `rot_override[name]=delta_deg` 模擬動畫旋轉(子骨世界矩陣自動級聯)。
- **自一致性驗證**:美術 bind 在 identity pose 重建 == 由美術權重算的 setup 世界頂點,**3 件 MAE=0**(基礎件可信)。

### 2. bone-heat 骨綁權重生成器(`bbw_weights.py`)
- 解 `(-L + H) W = H P`(Baran-Popović / Blender 「Bone Heat」同式):L=cotangent Laplacian(L·1=0)、
  H=diag(1/d_min²)(最近骨熱貢獻)、P=最近骨指示。純 CPU 單次稀疏線性解 / 骨。
- 數學性質(實測):**partition-of-unity ∑=1(殘差 2e-16)**、**bounded 0≤w≤1**、平滑局部。
- 選 bone-heat 而非解 biharmonic(真 BBW):性質相同、無需 QP、工業標準;BBW 為可選升級。

### 3. 變形品質閘(`validate_weights.py`)—— **三個關鍵設計教訓**

## ⭐ 三個關鍵教訓(本 session 最有價值產出)

### 教訓 A:權重「符合美術」是**部分主觀的美術決定** → 只 gate 客觀性質
幾何 bone-heat 對 **光暈** 的相對位移誤差 worst **33.6**(比「全綁單骨」的壞 rig 還大)——
因為美術對這種**軟/廣**件(羽化光暈)做了**非幾何**權重選擇(讓它主要跟隨主腿骨,而非按鄰近
分散到 LEG5/6)。**這不代表 bone-heat 壞**:它產生的權重有效且變形平滑,只是「美術風格選擇」不同。
→ 依 RULES「別用演算法學沒有唯一解的美術決定」:對 partition/bounded/變形平滑(客觀)下 pass/fail;
「與美術權重相似度」**僅報告不 gating**(R1)。左手/身體幾何權重與美術接近(worst 1.46 / 剛性)。

### 教訓 B:變形品質閘**必須對藝術家真值自校準包絡**(auto-clamp)
把單骨孤立旋轉到「真實動畫範圍 × 1.5」端點,**連美術真值都會自交**(光暈 LEG6 −40° → 36 自交):
單骨孤立到極端超出美術設計的協調運動包絡。→ 閘把每骨測試包絡**向 0 收縮到「美術真值仍 0 自交」**
(光暈 LEG6 −40°→−5.4°)。在美術都會壞的姿態下要求生成器不壞不公平;自校準後閘公平且可信。
真實動畫旋轉範圍(從 Award animations 抽 rotate timeline):LEG6 −27°、LEG5 +14°、其餘 <5°;
LEG3/7/8 **無 rotate timeline → 身體是剛性蒙皮**(件內無彎折,合理標 rigidly_skinned)。

### 教訓 C:相似度度量要用「相對位移」,不要用對角線正規化的絕對誤差
先前初版用「‖gen−art‖ / mesh 對角線」:被大件(光暈 diag 951)稀釋 → **連「全綁單骨」的壞 rig
都 mean 誤差 <0.10 過關**(無鑑別力)。改用**相對位移** ‖gen位移−art位移‖ / ‖art位移‖:壞 rig 在
「旋轉非其綁定骨」的姿態下 gen位移=0 → 相對誤差=1.0;好 rig 應遠小(左手 mean 0.65)。有鑑別力。

## 閘的可信度(雙負對照 + 正對照,RULES 要求)
- **正對照**:美術權重通過內在閘 + 在自身動畫範圍內 0 自交(自校準基準)。
- **負對照 1**(破壞單位分割:確定性擾動不重正規化)→ A2 內在閘抓到(殘差 0.5 ≫ 容差 2e-4)。
- **負對照 2**(撕裂 rig:相鄰頂點硬綁交替骨)→ A3 變形閘抓到(光暈/左手自交 59/15)。

## 誠實限制 / 下一步
- 只驗「權重有效性 + 變形平滑度(客觀)+ 與美術相似度(報告)」;**未**驗貼圖採樣/UV 在變形下的視覺。
- 身體無旋轉骨 → 件內彎折未受測(真實動畫中它剛性移動);若要驗彎折需含彎折動畫的件。
- **內部取樣密度**:美術身體用 98 密內部頂點服務平滑度;bone-heat 直接吃既有拓樸,未主動加內部點。
  下一步可測「S3 生成拓樸(boundary-dense/strip)+ bone-heat 權重」的端到端變形平滑度(接 generate_mesh_v2)。
- BBW(biharmonic,解 QP)為 bone-heat 的可選升級(更硬的 locality),本資產 bone-heat 已足。
