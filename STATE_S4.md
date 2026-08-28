# S4 進度狀態 (STATE_S4) — 補圖/切圖獨立排程續跑核心

> 本檔僅供 **S4 專屬排程** 使用(分支 `claude/spine-s4-inpainting`)。主排程請看 `STATE.md`。
> 每次 S4 session 結束前**必須**更新此檔。冷啟動背景見 `handoff_S4.md`,執行指令見 `prompts/run_s4.md`。

## 專案狀態

`SETUP`  <!-- SETUP / ACTIVE / BLOCKED / DONE — 由第一次 S4 排程執行後轉 ACTIVE -->

## 範圍

S4 = 切圖 + 補圖。**(A) 切圖已大致完成**(PSD-first 對 2 真實 PSD 無損 + ⇄ Award 逐件吻合);
**(B) 補圖未開始 = 本排程主任務**。詳見 `handoff_S4.md`。

## 已完成(繼承自主排程,切圖半邊)

- ✅ PSD-first 切圖 pipeline `psd_slice.py` + 重組無損閘(合成 + 2 份真實生產 PSD 全 PASS)。
- ✅ PSD 圖層 ⇄ Award spine slot `機器人拆件/<圖層名>` 逐件對應(+2px padding)、texture-IoU 閉環(0.92~0.99)。
- ✅ `atlas_crop.py` 多頁 + derotate 方向修正(CW);給美術的 PSD 交檔契約 `knowledge/s4-psd-contract.md`。
- 誠實界定:平圖(未分層)自動拆件在 CPU 到頂(同材質語意召回 0),升級需 GPU → 屬資源決策。

## 下一步動作 (next action)

**尚未開始補圖。第一個有界工作塊(見 `handoff_S4.md` §5):**
- **chunk 0:補圖閘 v1 + 邊緣外擴/`cv2.inpaint` baseline(純 CPU)。**
  1. `tools/mesh_gen/inpaint_eval.py`:合成真值(挖洞→補→比對),正/負對照自校準(premult-alpha 比對)。
  2. 對 1–2 個真實件(如機器人身體/左手,或 Symbol_Ww 層)人工洞跑 baseline,量化補全品質。
  3. 誠實標出 CPU 補得動 vs 必須升 LaMa/GPU/人工 的界線。
- 後續候選:遮擋真值法(多件疊合)補圖閘、cv2 兩演算法對比、結構性缺口的降階觸發規則。

## 未解問題 / 阻塞 (open questions / blockers)

- ❓ LaMa 等深度 inpaint 權重下載是否被網路政策擋?(第 3 級才需要;先用 CPU 1–2 級推進)
- ❓ 補圖真值來源:目前用「合成挖洞」自造;是否能要到「美術在 PSD 把被遮區畫全」的真實件當真值?(屬契約層決策)

## 進度摘要 (progress log)

- 2026-08-28:**S4 拆為獨立排程(由主排程交接)**。建 `handoff_S4.md` / `prompts/run_s4.md` / 本檔。
  切圖半邊繼承既有成果(已完成);補圖半邊為本排程主任務,狀態 `SETUP`,待第一次執行推進 chunk 0。
