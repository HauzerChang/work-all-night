# skill 化完成度快照 (READINESS)

> 由 `python3 tools/check_readiness.py` 產出。真相以指令即時輸出為準;本檔為人讀快照,里程碑時更新。
> 產生於 2026-08-28(session 005:S5 骨架 pivot 閘 + baseline;新增 spine-rig-pivot 區塊,HOLD)。

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
  區塊成熟度 L3 → READY ✅
  目標:READY:達門檻,可併入 spine-asset-forge(weighted 素材產線)
    [L2] 變形品質閘(前置)                              閘:GREEN (eval)
    [L2] heat-diffusion(BBW 近似)權重生成             閘:GREEN (gen)  «不透明件(身體/左手)過閘 + 平滑度≈藝術家;軟性件(光暈極端 reveal)未追平,屬已知限制»
    [L2] 內部取樣密度控制(triangle max-area)            閘:GREEN (gen)  «body 調到 nv=98 == 藝術家»
    [L3] build_spine --weighted 端到端產可載入 spine   閘:GREEN (pipeline)  «round-trip + 輪廓 IoU + 合成變形閘;結構件 si=0、特效件 additive 容忍»

■ spine-rig-pivot — 骨架 pivot 推斷(S5,唯一卡死環節)
  區塊成熟度 L2 → HOLD ⛔
  目標:HOLD:閘就緒但生成仍 baseline(L1);pivot 閘可先併入 spine-mesh-doctor
    [L2] pivot 品質閘(err/len + swing;S2 骨架閘)      閘:GREEN (eval)  «今日新增;對 Award 真 rig 自洽+負對照(σ 單調)+baseline 分級 OVERALL PASS»
    [L1] pivot 生成 baseline(parent_tip/origin)   閘:GREEN (gen)  «rig-only 啟發式:serial 60% / branch 0%;branch 須 per-part mask 重疊區證據,未做»

==============================================================================
可 skill 化(達門檻): spine-mesh-doctor, spine-asset-forge, spine-weighted-forge
HOLD(防固化半成品): spine-slicing, spine-target-analysis, spine-rig-pivot
```
