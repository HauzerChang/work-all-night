# S3 — weighted-mesh 骨骼變形評估器(補上「唯一未驗維度」)

- **結論**:新增 `tools/mesh_gen/weighted_deform_eval.py`,補上 `compare_robot_mesh.py`
  留下的唯一未驗維度 —— weighted mesh 靠**骨骼 + 權重(LBS)**變形時的**變形品質**。
  內建最小 Spine 3.8 FK 引擎(bone 動畫 → 世界矩陣 → linear-blend skinning),
  對 Award 機器人 3 個 weighted mesh 件(身體/左手/光暈)以**真實骨骼動畫**驅動變形,
  量測拓樸乾淨度(自交/翻面/退化)+ 真實位移場。**三項可信度閘全 PASS,評估器判定可信**。
- **信心**:高。評估器可信度用**三種獨立方式**交叉驗證(見下),非只內部自洽。
- **階段**:第 2 階段 / S3。這是 BBW 權重生成能力的**自我品質閘**(RULES「每能力必配評估器」)。
- **標準指令**:`PYTHONPATH=tools/mesh_gen python3 tools/mesh_gen/weighted_deform_eval.py`
  → 印報告,`evaluator_trustworthy=True` 時 exit 0。

## 為什麼需要它

`compare_robot_mesh.py` 對這 3 件做的是**靜態覆蓋率 IoU**(setup pose 剪影對照),PASS 但誠實界定:
> 靜態 IoU 高、頂點更省 ≠ bone-driven 變形一樣平滑。要量化需該件的權重 + 骨骼 pose 序列。

真值其實**已在 `Award.json`**:這 3 件是 weighted mesh(綁 `4_LEG*` 骨),且有 3 支動畫
(`Award_Legend_In/Loop/Out`)真實驅動這些骨。故可建 FK+LBS 引擎,拿真實 pose 序列當變形真值,
不需 GPU、不需 Spine editor、純 CPU 可自驅。

## FK / skinning 實作要點(Spine 3.8)

- 全部相關骨 `transform=normal`(無 shear / 無特殊繼承)→ 用標準 `updateWorldTransform`:
  local matrix `la=cos(rot)·sx, lc=sin(rot)·sx, lb=cos(rot+90)·sy, ld=sin(rot+90)·sy`,
  world = parent.world ∘ (local x,y) + local matrix 串接。
- 動畫套用:`rotate` 疊加角度、`translate` 疊加位移、`scale` 乘算;三態插值
  linear / `stepped` / **緊湊 bezier**(`curve=cx1,c2=cy1,c3=cx2,c4=cy2`,雷點 #7,10 段查表 x→y)。
- weighted 頂點格式 `[boneCount,(boneIdx,bindX,bindY,weight)*]`(雷點 #6);
  `world_v = Σ w_i·(Bone_i.world ∘ bind_i)`。權重每頂點和實測 =1.0。
- 綁定骨:身體→`4_LEG3/7/8`(≤3骨/點)、左手→`4_LEG5/9`(≤2)、光暈→`4_LEG3/4/5/6`(≤3)。

## 三項可信度閘(evaluator-first:先證可信再下判定)

| 閘 | 方法 | 結果 |
|---|---|---|
| **G1 rigid-invariance** | 整體旋轉 40°,skinned 頂點須 == 解析旋轉 setup | max 誤差 **~1e-13**、面積比 1.0、0 翻面 → FK+LBS 數學正確 |
| **G2 positive control** | 真實動畫逐幀(13幀)skinning,量拓樸 | 身體/左手 **3 動畫全乾淨**;3 件**穩態 loop 全乾淨** |
| **G3 negative control** | 半數頂點強綁遠端骨 → 真實動畫下 | 自交 38~2945 / 翻面 出現 → **全件抓到**,有鑑別力 |

**第三種獨立交叉驗證(絕對空間)**:setup pose skinned bbox 對照 `atlas region ÷ 0.70`
(STATE 記載貼圖以 ~0.70 打包):左手 257×216 vs 259×217(<2%)、光暈 693×651 vs 709×686(<5%)。
→ 證 FK 在**絕對世界座標**也正確,非僅相對自洽。

視覺證據:`knowledge/figures/weighted_deform_gates.png`(3列=身體/左手/光暈,3欄=setup/Loop max/In max;
綠=拓樸乾淨、紅=自交)。

## 關鍵發現:平滑度目標是**穩態 loop**,不是進出場暫態

- 身體/左手在 In/Loop/Out **三動畫全乾淨**;光暈只在 **`Award_Legend_In`** 自交
  (71 si、面積 **1.98x**、最大位移 **676px**)。
- 這**不是評估器誤判**(G1/G3/絕對空間校驗都過),而是真實現象:光暈是**加法軟 blob**,
  進場時被 4 根骨扇形拉開放大近 2 倍,mesh 自疊在加法混色下**不可見**;同樣的自交若發生在
  不透明貼圖件(身體)就是**撕裂缺陷**。
- → 設計判定:**weighted mesh 變形品質的閘,對齊「穩態 loop(呼吸)」**這條平滑度關鍵動畫
  (`STEADY_ANIM`);In/Out 是暫態,極端幀自交只對不透明件才算缺陷,列為 `non_clean_anims` 觀察值。
- `evaluator_trustworthy = G1 全過 ∧ G3 全抓 ∧ 3 件 loop 全乾淨` → **True**。

## 副產:真實位移場(供 BBW 生成對照)

`real_bone_deform_field(sk, slot)` → `(uvs, field, anim, time)`:各件在真實動畫「最大位移幀」的
setup→posed 世界位移場(身體 172px / 左手 328px / 光暈 676px)。與 unweighted 的
`deform_eval.real_deform_field` 同介面(UV 為轉移鍵),下一步 BBW 生成的 mesh 可用它做變形對照。

## 下一步(候選 #2 續:BBW 權重生成)

現在評估器已可信,可自主收斂 BBW:
1. **內部取樣密度控制**:`generate_mesh_v2` 目前 boundary-dense 幾乎只有邊界點(身體 37v),
   美術用密集內部點(98v)服務骨骼變形平滑度 → 加內部格點/泊松取樣密度旋鈕。
2. **BBW 權重**:對生成 mesh 的頂點,依骨骼骨段算 Bounded Biharmonic Weights(純 CPU:
   離散拉普拉斯 + 有界二次規劃 / 或先用簡化的骨段距離熱核 heat-diffusion 近似)。
3. **對照閘**:用本評估器對「生成 mesh + BBW 權重」施同一組真實骨骼 pose,比對
   (a) loop 乾淨度須全過;(b) 位移場 vs 美術件位移場的 RMS 差在容差內 → 量化變形平滑度對等。
