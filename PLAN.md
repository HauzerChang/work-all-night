# 階段目標 / 路線圖 (PLAN)

> 來源：cowork 對話「Spine mesh system analysis」交接(`handoff_brief.md`、`CLAUDE.md`、
> `自主Spine工作流_SOP.md`、`Spine能力鍛鍊計畫.md`、`main_draw_解析報告.md`)。

## 研究主題

把 Spine 2D 角色變成「**可程式化編輯、可即時視覺化驗證**」的資產，最終建立
「2D 原圖 / 目標影片 → Spine 動畫」且能**自主逼近目標**的 pipeline。
環境：lula slot game / Cocos Creator 3.7.3 / Spine 3.8.99。測試資產：`main_draw`。

## 總體目標 (north star)

讓 AI 能從「目標影片」反推出資產與綁定需求，並自主完成切圖 / 補圖 / mesh / 骨架，
產出貼近影片的 Spine 動畫，使用者只在三個關鍵點介入(定契約、岔路決策、里程碑審查)。

## 三階段(專案層級)

1. **可視化檢視/編輯工具** — ✅ 已完成(`spine_inspector.html`，含 `window.spineTool` Phase-2 API)。
2. **用工具鍛鍊四能力** — 切圖 / 補圖 / 新增編輯 mesh / 骨架設計，每項用工具的視覺+量化 API 自主驗收。⬅ **目前在這裡**
3. **整合成 pipeline** — 影片 → 需求規格 → 自主迭代 → 逼近目標影片。

## 能力路線圖 S1–S5(依「槓桿 ÷ 難度」排序，來自鍛鍊計畫)

> 順序邏輯：先有「需求規格(S1)」與「能自評(S2)」，後三項能力才有對的目標與自主收斂能力。
> 但 **S3 純 CPU、收益最大、能立即拆掉現有限制**，建議作為第一個實作的能力。

### S1 反推分析器
- 目標：影片 → **Asset & Rig Requirement Spec**(拆件 / 遮擋補圖 / 骨架 / mesh 需求)。
- 完成條件：對 benchmark 影片自動產出的件清單 ≈ 人工判斷(召回率達標)。
- 環境：人形 CPU 可行；非人形走 CPU 光流分群。
- 狀態：⬜ 未開始

### S2 評估器套件
- 目標：為四能力各寫「自我品質閘」(可機讀判準)。**樞紐：沒它自主迴圈無法收斂**。
- 完成條件：四個評估器都能對既有 `main_draw` 產出 pass/fail + 量化差距。
- 環境：純 CPU(含 vision 比對)。
- 狀態：⬜ 未開始

### S3 mesh 生成器  ★建議先做
- 目標：SpriteToMesh 式拓樸(findContours+多通道 Canny+Delaunay) + BBW 權重 + SkelToJson 讀寫。
- 完成條件：對一張 PNG 自動產出可用 mesh，寫入 Spine JSON，在 inspector 極端 deform 幀
  0 自交 / 0 撕裂 / 頂點數在預算內 / 輪廓吻合。
- 環境：純 CPU，可全自動(2026 SpriteToMesh 已驗證)。
- 狀態：⬜ 未開始

### S4 切圖 + 補圖
- 目標：PSD-first 契約(psd-tools) + CPU 半自動 fallback；補圖分級降階(外擴→cv2→LaMa→GPU/人工)。
- 完成條件：切圖重組還原原圖輪廓、0 孤兒像素；補圖極端姿態幀 0 破洞 / 0 明顯接縫。
- 環境：CPU 為主，大缺口 / 平面圖升 GPU。
- 狀態：⬜ 未開始

### S5 骨架半自動
- 目標：運動 → 關節草案 → 人微調 pivot(人形 RTMPose/MediaPipe；非人形 Farneback 光流+分群)。
- 完成條件：每骨單獨旋轉 pivot 正確；整體動作疊影片相似度達標。
- 環境：人形 CPU；非人形 CPU/GPU。**唯一卡死環節 — 人力集中於此**。
- 狀態：⬜ 未開始

## 關鍵策略結論(別忘)

- **改輸入契約比硬攻演算法划算**：能要到分層 PSD 就要，切圖+補圖兩大難題大半消失。
- **別用 ML 學「沒有唯一解的美術決定」**(SpriteToMesh 證明預測頂點不收斂)；用確定性演算法 + 評估器。
- **骨架 pivot 是唯一真正卡死處**，集中人力在此。
