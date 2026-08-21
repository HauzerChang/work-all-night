# S3 — weighted-mesh deform 評估器(骨骼權重變形品質閘)

- **結論**:補上上一里程碑(`s3-robot-mesh-vs-award.md`)唯一未驗維度 ——「weighted mesh 的骨骼變形
  平滑度」。新工具 `tools/mesh_gen/weighted_deform_eval.py` 由 skeleton bone 資料 + 動畫 timeline 做
  **FK(前向運動學)**,以 **Spine 加權 computeWorldVertices(LBS)** 把 mesh 頂點推到世界座標,對
  Award 機器人 3 個 weighted mesh 件(身體/左手/光暈)在**真實 bone 動畫**下量化變形品質。
  評估器經正/負對照自驗**可信**;`gate_candidate()` 提供未來 BBW 生成權重的品質閘。
- **信心**:高(對真實生產 spine 的美術權重 + 真實 bone timeline 量化;正對照全乾淨、負對照可鑑別)。
- **階段**:第 2 階段 / S3(evaluator-first 樞紐;先有閘才能自主收斂 weighted 權重生成)。

## 標準指令

```
PYTHONPATH=tools/mesh_gen python3 tools/mesh_gen/weighted_deform_eval.py
# → 印 3 件正/負對照報告;_checker_validated=True;gate 示範。exit 0。
```

## 做了什麼(技術)

1. **FK**:`fk_world()` 依 Spine 3.8 `updateWorldTransform`(**normal** transform mode,Award LEG 骨全 normal)
   由 bone 的 setup (x,y,rotation,scale,shear) + 動畫 `rotate/translate/scale/shear` timeline 合成每根骨的
   世界仿射 (a,b,c,d,wx,wy)。timeline 語意:rotate/shear/translate 為**加**於 setup,scale 為**乘**。
   拓樸序(parent 先)遞迴求解。
2. **LBS**:`skin_vertices()` = 加權 `computeWorldVertices`:頂點世界座標 = Σ weightᵢ·(boneᵢ 世界矩陣 · bindᵢ)。
3. **timeline 取值**:`_val()` 在 keyframe 間**線性內插**(忽略緊湊 bezier 形狀 → 在 keyframe 時間點精確;
   之間近似)。缺鍵補預設(translate/rotate/shear→0、scale→1)。
4. **量化**:沿用 `deform_eval` 的 `check`(自交/翻面/退化)+ 新增 `edge_strain`(每邊長變化率)。

## 量化結果(Award_Legend_Loop,穩態可見)

| 件 | 綁定骨 | 藝術家 max_strain | 硬指派 max_strain | 比值 h/a | 混合承重? | 藝術家拓樸 |
|---|---|---|---|---|---|---|
| 身體 | LEG3/7/8 | 0.394 | 0.371 | 0.94 | 否 | clean |
| 左手 | LEG5/9 | 0.760 | 0.001 | 0.002 | 否 | clean |
| 光暈 | LEG3/4/5/6 | 0.151 | 1.568 | **10.35** | **是** | clean |

`_checker_validated=True`:藝術家權重在 Loop **3 件全拓樸乾淨**(正對照;FK/LBS 若有 bug 這會失敗)
+ 至少一件(光暈)負對照可鑑別。

## 三個關鍵發現

### 1. 混合權重只在「綁定骨彼此相對旋轉/發散」處承重
- **光暈**綁 4 根扇形張開的腿骨(LEG3/4/5/6,setup rotation 分別 87/9/-79/130°)→ 動畫下彼此旋轉發散
  → 軟權重混合是**必要**的;抽掉(硬指派最大權重骨)→ max_edge_strain 暴增 **10×**(0.15→1.57),
  大幅度動畫下更自交。
- **身體/左手**綁的骨在 Legend 只做**共同平移**(無相對旋轉)→ 硬指派 vs 軟權重幾乎無差
  → **這兩件不需軟權重**(誠實回報 `blend_load_bearing=false`,非閘失敗)。
- 教訓:BBW 密內部頂點 + 軟權重的槓桿,集中在「跨多根相對運動骨」的件;共動骨件近乎剛體,省權重合理。

### 2. max_edge_strain 幅度 ≠ 品質(不可設絕對門檻)
- 左手藝術家 strain 0.760 是**對的**(手隨動畫大幅擺動);硬指派 0.001 反而「太剛」。
  幅度大不代表壞、小不代表好 → **品質閘必須對照同動畫的藝術家基準做相對比較**,不是絕對門檻。
- `gate_candidate()` 因此採 **repo 既有範式**:拓樸硬閘(自交/翻面/退化=0,絕對)+ 平滑度相對閘
  (candidate max_strain ≤ 藝術家 ×(1+margin),margin=0.15)。
- 驗證:對硬指派 candidate,光暈 **REJECT**(1.568 > 0.174),身體/左手 PASS(誠實:該件混合非承重);
  藝術家權重全 PASS 自己的閘(正對照)。

### 3. 動畫選擇:用 Loop(穩態),In/Out 是轉場不宜當基準
- **Out** 是退場的**全域均勻縮放**(3 件同時 max_strain=0.589、max≈p95、topology clean)→ 均勻縮放非撕裂。
- **In** 進場含 attachment gating 下的隱藏極端 pose(光暈藝術家在 In 竟 self-int=71)→ CLAUDE.md 雷點 #2/#3:
  attachment 未顯示時的 deform 不代表可見品質。
- → 品質閘預設鎖 **Award_Legend_Loop**(角色穩定可見);In/Out 僅供轉場幅度參考。

## API(給後續 BBW 權重生成器當閘)

```python
eval_weighted(sk, bones, slot, name, anim="Award_Legend_Loop")
   → {artist, hard_negctrl, strain_ratio_hard_over_artist, blend_load_bearing, ...}
gate_candidate(sk, bones, slot, name, candidate_bindings, anim, margin=0.15)
   → (pass:bool, detail)   # 拓樸硬閘 + 對藝術家基準的平滑度相對閘
```

## ⚠️ 誠實限制 / 下一步

- FK 只實作 normal transform mode(Award LEG 全 normal;其他資產若含 IK/path/非 normal 需擴充)。
- timeline 內插忽略 bezier 形狀(keyframe 時間點精確,之間線性近似;對「最壞幀」量化足夠)。
- **閘已就位 → 下一步:S3 weighted 權重**生成**器**(內部取樣密度 + BBW / heat-diffusion 權重),
  對光暈這類「混合承重」件生成權重,用 `gate_candidate` 對藝術家基準自主收斂。這是本閘要服務的目標能力。
