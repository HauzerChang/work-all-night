# 自動配權（bone-distance heat）— S3 unweighted mesh → weighted，可被骨鏈驅動

- **結論**：`tools/mesh_gen/auto_weight.py` 把 S3 的 unweighted mesh + **沿主軸自動佈的骨鏈**
  配成 **weighted mesh**（Spine 格式 `[n,(boneIdx,bindX,bindY,weight)*n,...]`），讓件可被多骨驅動。
  以「頂點到骨段距離」inverse-distance + top-K + 沿 mesh 邊 Laplacian 平滑配權。對 2 個真實衍生 mesh
  （curtain_left strip 30v / 3 骨、robot 左手 blob 67v / 2 骨）**3 條 AC 全過**，彎折 60° 掃描下
  **0 自交 / 0 翻面**。**確定性、純 CPU**。
- **信心**：高（真值自一致性 + 正/負對照 + 復用已驗證的 deform 幾何閘）。
- **階段**：第 2 階段 / S3→S5 銜接（把中性骨架的 unweighted mesh 推進到「骨骼可驅動」）。

## 方法（純 CPU 確定性，非 ML）

1. **骨鏈**：沿 mesh 點雲較長軸等距佈 `n_bones` 根（root→tip），joints 落在另一軸中位線。
2. **配權 = bone-distance heat**：每頂點對各骨段算距離 → `w = 1/(d+eps)^power` → 只留最近 `k` 根
   → 歸一 → **沿 mesh 邊做 Laplacian 平滑**（避免相鄰頂點權重跳變 → 變形平滑）→ 再歸一。
3. **bind 座標**：setup 下頂點在該骨局部座標 `R(-θ)·(v-o)`（θ/o = 骨段角度/起點）；存 3 位小數。
4. **輸出**：hull 頂點排最前（沿用 S3 順序）、每頂點權重和=1、bones/vertex ≤ 上限（預設 4）。

> ⚠️ 這是 **bone-distance heat**，非真正 **BBW**（bounded biharmonic，需解 mesh 內部 biharmonic
> 系統）。對「骨鏈帶動 strip/blob」已足以平滑變形；BBW 列為後續精度升級。

## 自驗閘（復用 `deform_eval` 的自交/翻面幾何閘）

| AC | 檢查 | 結果 |
|---|---|---|
| AC1 partition-of-unity | 每頂點權重和=1、≥0、bones/vertex≤4 | PASS（和 ∈ [1,1]） |
| AC2 setup 重建 | 骨在 setup 位姿時 LBS 還原 setup 頂點 | PASS（誤差 ≤0.0027px） |
| AC3 deform 掃描 | 沿骨鏈漸進彎折 ±10..60°、FK+LBS 變形後幾何 | PASS（0 自交/0 翻面/0 退化） |

- **FK+LBS**：forward kinematics 算彎折後各骨世界位姿 → 線性混合蒙皮算變形頂點 → 丟進
  `deform_eval.eval_pose` 判幾何。AC2 殘差來自 bindX/Y 存 3 位小數,遠低於可見尺度（門檻 0.05px）。

## 評估器可信度（校準）

- **真值自一致性**：Award **7 個真實 weighted 件**（角色們 + 機器人光暈/左手/身體）partition-of-unity
  全 OK（權重和 ∈ [0.99999, 1.00001]）→ 閘的核心判準與生產真值一致。Award 實測 ≤2 骨/頂點。
- **負對照**：把配權換成「硬指派最近單骨（k=1、不平滑）」→ 兩件在彎折下 **AC3 失敗**
  （self_intersections=10、flips=2）→ 閘**有鑑別力**，正過/負敗。
- **正過 + 負敗 = 鑑別力** 內建進自我測試（`python3 auto_weight.py` 無參數即跑,EXIT 0/1）。

## 可重現

```
python3 tools/mesh_gen/auto_weight.py                 # 內建自測:真值自一致性+2件AC+負對照,EXIT 0
python3 tools/mesh_gen/auto_weight.py mesh.json --bones 3 -o weighted.json   # 對單一 S3 mesh 配權
```

## 範圍限制 / 下一步

- 目前骨鏈是**沿主軸自動佈的直鏈**（適合 strip/單肢）；**分叉骨架（多肢/人形）與 pivot 位置**屬 S5 核心
  （pivot 仍需人微調,計畫中唯一卡死處）。
- **接 SkelToJson**：把 `auto_weight` 產的 weighted vertices 寫回 skin、並在 bones 陣列加入骨鏈
  → 端到端「PSD→件→S3 mesh→自動配權→可骨驅 Spine JSON」。
- 精度升級：bone-distance heat → BBW（需 mesh 內部 FEM/Laplacian 解）。
