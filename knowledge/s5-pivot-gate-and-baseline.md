# S5 骨架 pivot 閘 + baseline 推斷(對 Award 真 rig)

> 里程碑 2026-08-28。工具:`tools/analyzer/pivot_eval.py`(S2 骨架閘)、
> `tools/analyzer/infer_pivots.py`(baseline)、`tools/analyzer/validate_pivots.py`(整合驗收)。
> 圖:`figures/s5_pivot_gate_baseline.png`。

## 為什麼先做這個

S5(骨架半自動)在路線圖是「唯一真正卡死處」——每個關節的 pivot(骨原點)放對,限肢繞對的軸擺動,
動作才不歪。RULES 要求「每能力必配評估器」且「先做評估器」;而 S2 套件也**獨缺骨架閘**。
一石二鳥:先把「量化一組 pivot 對不對」的閘做出來、驗到可信,再給它一個 baseline 打分。

## 關鍵數學:pivot 歐氏誤差就是充分且正確的量

一根骨帶 attachment 是**剛體**,繞 pivot 轉 θ 時整片圖跟著繞同一 pivot。設真 pivot=c_true、
提案 pivot=c_prop、Δ=c_true−c_prop,骨上任一點 p 轉 θ 後兩種 pivot 的世界位移差:

    P_true − P_prop = (I − Rot(θ))·Δ ,   ‖(I−Rot(θ))·Δ‖ = 2·sin(θ/2)·‖Δ‖

—— **與 p 無關(tip 消掉)、且各向等向**(沿骨軸/垂直分量貢獻相同)。所以:
- 不必另設「功能性擺動」指標;pivot 的歐氏誤差 ‖Δ‖ 已充分且正確。
- 但 ‖Δ‖ 對人不直觀 → 閘同時回報物理後果 **swing@30° = 2·sin15°·‖Δ‖ ≈ 0.518·‖Δ‖**
  (「限肢擺 30° 時每個像素偏離應到位置多少 px」),並以骨長 normalize(`err/len`)得跨骨/跨資產可比尺度。
- 判準預設 `err/len ≤ 0.15`(pivot 落骨長 15% 內;擺 30° 像素偏移 ≈ 8% 骨長,肉眼幾乎看不出擺錯軸)。

**被評對象**:只評帶 length 且有 parent 的骨(真限肢節段;Award 23 根)。root/無 length 的容器骨
(光效群組)pivot 語意不同,不列入。

## 閘可信度(validate_pivots.py 三道校驗,對 Award **OVERALL PASS**)

① **自洽(正對照)**:餵真 pivot → 誤差 0、23/23 pass。閘無系統性偏差。
② **鑑別力(負對照)**:對真 pivot 加高斯噪音 σ·骨長,誤差與 fail 率單調上升 —— 
   σ=0.1→mean 0.098/pass 83%;σ=0.3→0.295/26%;σ=1.0→0.985/**4%**。閘真的分得出「準 vs 亂放」。
③ **baseline 分級**:見下。

## baseline 推斷(rig-only,只吃 parent 骨幾何,不偷看子骨真 pivot)

- **parent_tip**「關節端對端相接」:子骨 pivot = parent 骨尖端(parent world 套 (length,0))。
- **parent_origin**(弱對照):子骨 pivot = parent 骨原點。

對 Award 打分:

| baseline | 全體 pass | serial pass | branch pass | mean err/len |
|---|---|---|---|---|
| parent_tip | 3/23 (13%) | **3/5 (60%)** | **0/18 (0%)** | 1.08 |
| parent_origin | 1/23 (4%) | 1/5 (20%) | 0/18 (0%) | 1.77 |

**結論(誠實)**:
- parent_tip 只在**序列骨鏈(serial)中段關節**成立(前臂在上臂末端這種直覺);對**岔出骨(branch)**
  必然失手 —— 岔出子骨不在 parent 軸尖端(圖右紅線 = 誤差,全連到 branch 關節)。
- 兩個 serial 失手的是 1_OMG2 / 2_SUP2:其 parent 是角色根骨(無 length)→ tip 退回 origin → 大誤差。
  這是「軀幹-第一節」關節,本就非序列延續。
- parent_tip 明顯優於 parent_origin(13% vs 4%),證明閘能分「好啟發式 vs 爛啟發式」。

## 這告訴 S5 下一步什麼

最簡確定性啟發式(只靠骨鏈幾何)天花板 = 序列中段關節。**branch 關節要放對,需要影像證據**:
相鄰件(parent-part / child-part)的像素 footprint 重疊區 → pivot ≈ 重疊區質心 / 邊界最近點。
這需要 **per-part mask**(可由 Award atlas 切件 + slot→bone 綁定取得,`atlas_crop.py` 已有多頁切件)。
→ 下一個 bounded chunk 候選:**overlap-centroid baseline**(吃 per-part mask),用同一閘打分,
目標把 branch pass 率從 0% 拉起來。閘已就緒,可直接續驗。

## 對 skill 化的意義

S5 首度有了**可信的骨架閘**(填上 S2 最後缺口)。但**閘就緒 ≠ 生成器就緒**:pivot 生成能力仍在
L1(rig-only baseline,branch 0%),依防固化規則 S5 區塊維持 HOLD,勿打包。閘本身可併入
`spine-mesh-doctor`(品質閘家族)的候選。
