# S3 weighted mesh 骨綁權重生成 + 變形穩健閘(對 Award 真值)

- **結論**:補上此前 S3 唯一未驗維度「weighted mesh 骨骼變形平滑度」。以 heat-diffusion
  (Pinocchio 式)純 CPU 演算法為 Award 機器人 3 個 weighted mesh(光暈/左手/身體)重算骨綁權重,
  在**美術自己的 mesh 幾何 + Award 真實骨架**上、以 **Award 真實骨骼動畫**驅動變形,
  生成權重 **3 件全 PASS**:partition-of-unity 精確、稀疏(≤4 骨/頂點)、平滑度不劣於美術、
  真實動畫下 **0 自交/0 翻面/0 退化**且**不比美術差**(光暈 gen 0 vs 美術 35;身體 gen 0 vs 美術 6)。
- **依據**:`tools/mesh_gen/bone_weights.py` + `validate_bone_weights.py`;真值 `assets/Award.json`
  (77 bones/47 slots/12 anims,3 mesh 件皆 weighted)。指令 `python3 tools/mesh_gen/validate_bone_weights.py`(exit 0)。
- **信心**:高(對真實生產骨架 + 真實動畫;有負對照鑑別力;skinning 經 setup 不變量驗證)。
- **相關階段**:專案第 2 階段 / S3(mesh) + S2(評估器)。圖:`figures/s3_bone_weights.png`。

## 為什麼閘要量「變形」而非「權重值」

第一版把生成權重逐值比對美術權重(dominant 一致率、L1)→ **失敗且方向錯**。診斷發現:

- **左手**:美術把 80 頂點**全部以骨 62 為主導**(骨 66 僅次要 blend ≤0.38);
  但幾何上約 44 頂點最近骨 66。→ 美術權重 = **rig 意圖**(哪根骨「擁有」哪塊肉),
  不是幾何最近骨。逐值比對會**罰掉一個合法且更平滑的替代解**,違反本專案原則
  「別用演算法學沒有唯一解的美術決定」。
- 正解:**權重是為變形服務的,就量變形品質**。故閘 = 用生成權重蒙皮 → 驅動真實骨骼動畫 →
  查幾何(自交/翻面/退化)。dominant 一致率(0.44~0.83)僅作 diagnostic,不當 pass 條件。

## 方法(bone_weights.py)

1. **Spine FK**:`local_mat`(transformMode=normal, shear=0)+ `fk_world` 由 bones 前向運動學算世界矩陣;
   `fk_world_posed(deltas)` 對指定骨加旋轉並經 FK 傳給子骨。
2. **weighted rest 還原**:`[nBones,boneIdx,bindX,bindY,weight,...]` × 骨 world → 每頂點 rest 世界座標。
3. **heat-diffusion 權重**:在三角網格上解 `(L + M·diag(1/d²)) W = M·diag(1/d²) P`,
   L=cotangent Laplacian、M=lumped Voronoi 面積、d=頂點到最近骨段距離、P=最近骨 one-hot。
   - **尺度不變**:L 無量綱、M~面積、1/d²~面積⁻¹ → 兩項同量綱,故 α=1 **無需對真值調參**。
   - **數學保證 PoU**:∑_b w_b 解 `(L+H)x=H·1` 而 x=1 為解 → ∑列=1(實測 max|Δ|<1e-8)。
   - **稀疏化**:每頂點只留權重前 K=4 骨再重正規化(熱擴散長尾否則掛到全部骨)。
4. **LBS 蒙皮**:`bind_local`(inv(WorldRest_b)·restWorld)+ `skin_deform`(∑ w·WorldPosed·bind)。
   setup 不變量:zero-delta 蒙皮 == rest(max err ~5e-3,量化誤差),0 artifacts。

## AC 與結果(3 件全 PASS)

| 件 | 骨 | 運動源 | AC1 PoU | AC2 稀疏 | AC3 平滑 ratio | AC4 變形(gen/美術 artifacts) | AC5 鑑別(gen/hard) |
|---|---|---|---|---|---|---|---|
| 光暈 | 60/61/62/63 | 真實動畫(In+Loop) | ✅0 | ✅4 | ✅0.25 | ✅ 0 / 35 | ✅ 0 / 11 |
| 左手 | 62/66 | 真實動畫(In+Loop) | ✅0 | ✅2 | ✅1.69 | ✅ 0 / 0 | ✅ 0 / 13 |
| 身體 | 60/64/65 | 合成 sweep* | ✅0 | ✅3 | ✅0.28 | ✅ 0 / 6 | ✅ 0 / 8 |

- **AC4(核心,相對閘)**:所用運動下 gen artifacts ≤ 美術;有真實運動時 gen 須絕對乾淨。
  gen 在 3 件全 0 artifacts;光暈/身體甚至比**出貨的美術 mesh 更穩健**(見下註)。
- **AC5(鑑別力)**:同一極端 ±sweep 下,硬最近骨 0/1 權重必壞(8~13 artifacts),證明閘抓得到爛權重。

## 誠實界定 / 雷點

- **運動源的真相原則**(延續 deform_eval 的 stress_field 教訓):第一版用「單骨獨轉 ±25°、鄰骨不動」
  的合成 sweep → **過度嚴苛**(連美術 mesh 都被判自交),重演 miscalibration。改用 **Award 真實骨骼
  rotate timeline**(協同旋轉、幅度 LEG6 −27°~0 等)作核心運動源;沒有真實骨旋轉的件才退回合成 sweep。
- **「gen 比美術更乾淨」的正確解讀**:光暈是**加成發光 mesh**,美術權重較稀疏讓它在腿旋轉時自重疊
  (發光視覺可接受、非缺陷);我方平滑熱權重把它分散到 4 骨故 0 自交。這說明「自交數」對發光件
  是**保守**指標,相對閘仍成立(gen ≤ 美術)。
- **身體無真實骨旋轉**:LEG3 為剛體根(整塊隨轉不產生內部剪切)、LEG7/8 為零長輔助骨(無 rotate key)
  → 真實動畫對身體 mesh 無鉸接;只能以合成 sweep 佐證。屬此 rig 的客觀限制,非工具缺陷。
- **未涵蓋**:BBW 的嚴格 bounded/約束最佳化(此處用 heat-diffusion 近似,已足夠平滑且純 CPU 可自驅);
  bind pose 以外的 transformMode(onlyTranslation/noScale 等)未處理(Award 相關骨皆 normal)。

## 下一步候選

- 把 `bone_weights.heat_weights` + `emit_weighted_vertices` 接進 `build_spine.py`,
  讓 S1 端到端產出的素材對「需骨變形的件」直接生成 weighted mesh(目前 build_spine 只出 unweighted/region)。
- 需要**骨架**才有骨可綁 → 與候選 (e) 關節 pivot 推斷 / S5 骨架半自動綁定。
