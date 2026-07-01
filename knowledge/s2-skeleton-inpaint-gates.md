# S2 骨架閘 + 補圖閘 — S2 四評估器套件補齊

- **結論**:補上 S2 樞紐評估器的最後兩個 —— **骨架閘 `evaluate_skeleton.py`** 與 **補圖閘
  `evaluate_inpaint.py`**。至此 **S2 四評估器全到位**(切圖 / mesh / 骨架 / 補圖),
  「每能力必配評估器」的自主收斂前提完成。
- **信心**:高(兩閘都對真實資產正對照 + 破壞式負對照確認鑑別力)。
- **階段**:第 2 階段 / S2(樞紐完成)。

## S2 四評估器對照

| 能力 | 評估器 | 判準 | 真值校驗 |
|---|---|---|---|
| 切圖 | `evaluate_slicing.py` | atlas 重組 MAE / 孤兒 / 重疊 | main_draw 45/45 region MAE=0 |
| mesh | `evaluate_mesh.py` + `deform_eval.py` | 覆蓋率 IoU / 拓樸 / 真實 deform 轉移 | 藝術家真值自一致 + 負對照 |
| **骨架** | **`evaluate_skeleton.py`** | 結構 / attachment / rig 權重 | main_draw+Award+gen 全過 |
| **補圖** | **`evaluate_inpaint.py`** | 完整度 / 接縫 / 對真值 MAE | 補圖能力梯三態可分 |

## 骨架閘(evaluate_skeleton.py)

三條可機讀判準:
- **AC1 structure**:必要鍵;slot→bone 存在;bone 樹合法(單一 root / parent 存在 / 無環);
  slot 預設 attachment 存在於 skin(**attachment=null 允許** — 靠動畫 timeline 控制顯示,見雷點 #2)。
- **AC2 attachments**:mesh 三角索引在範圍 / hull∈(0,nv];region 尺寸>0;
  **clipping/boundingbox/path/point 依型別驗**(非 region 就不要求 width/height)。
- **AC3 rig_weights**:weighted mesh 每頂點 boneCount≥1、bone 索引在 bones 範圍、**權重和≈1(±1e-3)**。
  weighted 格式:`[boneCount,(boneIdx,x,y,w)*count]`(bind 為相對骨座標;bone 索引指 skeleton bones list)。

**又一次「先驗評估器」揪 bug**:初版對 **main_draw FAIL** → 把 `clipping`(root,CLAUDE.md 記載的
clipping×1)誤當 region 要求 width/height。**靠對真實真值驗證才抓到是評估器 bug**(非資產有問題)。
教訓延續:round-trip / 自製資產自洽 ≠ 對真實真值正確。負對照:破壞 slot-bone/三角/權重和/parent 各 FAIL 於對的 criterion。

## 補圖閘(evaluate_inpaint.py)

- **AC1_filled**(盲測):hole 區補後仍透明(alpha≤8)比例 = 0(補圖必須填滿)。
- **AC2_seam**(盲測):hole 邊界環帶梯度 / 內部基準梯度,偵測明顯接縫(越低越好)。
- **AC3_gt_mae**(有真值 self-test):hole 區 premultiplied-RGB MAE。
- **用途 = 升級決策**:cv2 Telea 對**紋理區**MAE 高(過不了 AC3)→ 閘輸出「升級到 LaMa/GPU/人工」訊號
  (呼應 PLAN 補圖分級降階)。三態驗證可分:強補圖(GT+微噪,MAE 3.7)過 / cv2 紋理(MAE 32.6)升級 /
  留洞(unfilled 1.0)缺。
- **發現**:補圖 MAE 依 hole 所在**局部紋理複雜度**而非只看洞大小(小洞落高細節區 MAE 反而更高)。

## 可重現

```
python3 tools/mesh_gen/evaluate_skeleton.py assets/main_draw.json   # PASS(clipping×1)
python3 tools/mesh_gen/evaluate_skeleton.py assets/Award.json       # PASS(7 weighted mesh)
python3 tools/mesh_gen/evaluate_inpaint.py <一張RGBA件.png>          # 補圖能力梯三態,exit 0
```
