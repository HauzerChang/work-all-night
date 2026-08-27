# skill 化完成度快照 (READINESS)

> 由 `python3 tools/check_readiness.py` 產出。真相以指令即時輸出為準;本檔為人讀快照,里程碑時更新。
> 產生於 2026-08-27。

```
==============================================================================
skill 化完成度矩陣(已實跑全部 validator)
==============================================================================

■ spine-mesh-doctor — mesh 品質 / 變形評估閘套件
  區塊成熟度 L3 → READY ✅
  目標:新 skill《spine-mesh-doctor》(補 spine-ai-editor 只可視化、無量化 pass/fail 的空白)
    [L2] 靜態輪廓 IoU 閘                             閘:GREEN (eval)
    [L2] unweighted 變形閘(真實位移場)                  閘:GREEN (eval)
    [L2] weighted 骨綁變形閘                         閘:GREEN (eval)  «今日新增;3 robot 真值 + 負對照»
    [L3] 整合 AC(端到端 4 mesh)                      閘:GREEN (pipeline)

■ spine-asset-forge — 目標圖/PSD → 可載入 Spine 素材(靜態)
  區塊成熟度 L3 → READY ✅
  目標:新 skill《spine-asset-forge》(補 spine-ai-editor 明說『mesh 交給 editor』的空白)
    [L2] 反推分析:分層 PSD → 五段規格                     閘:GREEN (gen)
    [L2] PSD → 各部位件 + manifest                  閘:GREEN (gen)
    [L2] 件 → mesh 拓樸(strip)                     閘:GREEN (gen)
    [L3] SkelToJson 組裝(端到端 round-trip)          閘:GREEN (pipeline)  «限制:只驗靜態幾何/貼圖,不含 animation/weighted/pivot»

■ spine-slicing — 切圖 / atlas 無損重組閘
  區塊成熟度 L2 → HOLD ⛔
  目標:併入 forge 為子模組(或獨立輕量 skill)
    [L2] PSD 切件保真                               閘:GREEN (gen)
    [L2] atlas 重組保真閘(45/45)                     閘:GREEN (eval)
    [L2] 多頁 atlas 切圖(CW derotate)               閘:—     (gen)  «方向 bug 已修;由 evaluate_slicing 間接覆蓋»

■ spine-target-analysis — 反推分析 / 需求規格(上游)
  區塊成熟度 L2 → HOLD ⛔
  目標:HOLD:折入 forge 前端,或併 spine-ai-editor 的可行性評估
    [L2] 分層 PSD → 規格(件/特效/分鏡/拆圖/補圖)             閘:GREEN (gen)
    [L2] 分鏡先驗庫(2 類型已驗/2 未驗)                     閘:GREEN (gen)  «覆蓋率 1.0 但僅 2 類型有真值»
    [L1] 平圖(未分層)自動拆件                            閘:GREEN (gen)  «誠實負結果:同材質語意召回 0,CPU 到頂需 GPU;非能力,是契約依據»
    [L0] 影片 → 規格                                閘:—     (gen)  «repo 無影片資產,未開始»

■ spine-weighted-forge — weighted mesh 生成 + BBW 權重(候選 2 主體)
  區塊成熟度 L2 → HOLD ⛔
  目標:HOLD(示範防固化):生成器未做,不可打包
    [L2] 變形品質閘(前置)                              閘:GREEN (eval)
    [L0] BBW/heat-diffusion 權重生成                閘:—     (gen)  «❗未做:閘就緒但生成能力缺 → 禁止 skill 化»
    [L1] 內部取樣密度控制                               閘:—     (gen)  «boundary-dense 已有;內部密度控制未做»

==============================================================================
可 skill 化(達門檻): spine-mesh-doctor, spine-asset-forge
HOLD(防固化半成品): spine-slicing, spine-target-analysis, spine-weighted-forge
```
