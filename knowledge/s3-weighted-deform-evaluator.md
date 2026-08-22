# S3 — weighted-mesh (LBS) deform 評估器

- **結論**:補上先前唯一未驗維度「weighted mesh 骨骼變形品質」的**自我品質閘**已完成並校準可信。
  對真實 Award 機器人 3 個 weighted mesh 件驗收:AC1/AC2/AC3 三項全 PASS(見下)。
- **依據/來源**:`tools/mesh_gen/weighted_deform_eval.py`;真值 = `assets/Award.json`
  (weighted mesh 的骨綁權重 + 骨階層 + `Award_Legend_In/Loop` 動畫 rotate/translate/scale timeline)。
- **信心**:高(LBS 核心經雙件正對照 + 幾何回溯交叉驗證;負對照量化鑑別力)。
- **相關階段**:專案第 2 階段 S3;呼應 STATE「❗最高優先(補上靜態 IoU 未涵蓋的變形維度)」。

## 做了什麼

`deform_eval.py` 只處理 **unweighted** mesh(per-vertex deform offset)。weighted mesh 由**骨骼**
經 linear blend skinning(LBS)驅動,需自建:

1. **骨 world transform**:從骨階層(bones list 已階層序)+ 動畫 timeline 逐時間算
   `(a,b,c,d,worldX,worldY)`。約定(Spine 3.8,已驗):rotate/translate 值為 setup 的**加量**、
   scale 值為 setup scale 的**乘數**(預設 1);角度為度;無 shear 用簡化旋轉矩陣。
2. **weighted computeWorldVertices**(Spine 3.8 雷點 #6):
   `wx = Σ_b w_b·(bindX·a_b + bindY·b_b + worldX_b)`(y 同理),bind 座標在 **bone-local** 空間。
3. **幾何閘**:重用 `deform_eval.eval_pose`(自交 / 翻面 / 退化 / 面積比)。

## 驗收(AC,`run_robot()` 自動判定,overall_pass=True)

| AC | 判準 | 結果 |
|---|---|---|
| **AC1** LBS 正確性 | 3 件 setup pose 骨綁 world 幾何乾淨 | ✅ |
| **AC2** 藝術家基準 | **結構件**(身體/左手)在全部真實動畫下 0 自交 / 0 翻面 | ✅ |
| **AC3** 鑑別力 | 骨區交錯結構件(身體)上,smooth 權重比 hard 單骨撐更大彎角才首次撕裂 | ✅ 80° vs 50° |

- **AC3 量化**:身體 bend LEG7 到 90° 掃描 —— 藝術家 smooth 到 **80°** 才首次出現缺陷(worst si=14/flip=2);
  hard 單骨 **50°** 就撕裂(worst si=49/flip=6)。→ 此閘能為未來 **BBW 生成器**的權重品質自動評分。

## 校準發現 / 誠實界定(評估器本身要可信)

1. **『0 自交』非通用閘 — 需依件角色分級**。藝術家自己的 **光暈(軟 glow)** 在 `Award_Legend_In`
   的 streak 段自交 71 / 翻面 7(exact keyframe t=0.233,非取樣誤差):單骨 `4_LEG6` 刻意飛離
   ~470px 並 scale 1.67×,其餘 3 骨守在 setup → 光暈被拉成流光而重疊。軟效果件重疊視覺無害,
   屬藝術家刻意。故閘分 `STRUCTURAL`(從嚴)/ `soft-effect`(容許重疊)兩級。
2. **拓樸閘量『撕裂/翻面』,不量『彎折平滑度』**。骨區**可分離**的件(左手,LEG5/LEG9 兩塊分開)
   hard 指派剛體平移**也不撕裂**(bend LEG9 到 90° 全乾淨,反比 smooth 的 85° 乾淨)—— 但彎折僵硬/faceted。
   要分辨「平滑 vs 剛體」需另配 **seam 連續性 / 應變**指標(後續)。故 AC3 必須挑**骨區交錯**的件(身體)才成立。
3. **LBS 核心正確性佐證**:身體 + 左手 在真實動畫下全乾淨(同一段 LBS 程式碼);光暈的 71 自交可逐幀
   回溯到真實 keyframe 的極端骨位移 → 排除「數學 bug」,確認是真實幾何。

## 對「候選 2:S3 weighted mesh + BBW」的意義

- **閘先於生成器**(RULES「每能力必配評估器」):本次先把「怎麼判斷一組權重好不好」做成可機讀、
  且對藝術家真值校準過的閘。下一步才是 **BBW 權重生成器**,用 AC3 的 joint-bend 掃描
  (smooth 首次撕裂彎角 ≥ 藝術家)+ 未來的 seam 連續性指標自動收斂。
- 真值齊備:Award 這 3 件的骨綁權重、骨架、動畫都在 `assets/Award.json`,純 CPU 可自驅。

## 標準指令

```
PYTHONPATH=tools/mesh_gen python3 tools/mesh_gen/weighted_deform_eval.py assets/Award.json
```
