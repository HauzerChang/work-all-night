# 每次排程執行的指令 (run prompt)

> 把這份內容當作 Scheduled session / Trigger 的 prompt,或在 trigger 裡直接寫:
> 「請依照 prompts/run.md 的指示推進這個研究專案。」

---

你正在接手一個**長期、跨 session 的自主研究專案**(Spine mesh 系統研究與鍛鍊)。
你沒有上一次執行的記憶,repo 裡的檔案就是你的全部記憶。請嚴格依下列步驟:

0. **環境**:SessionStart hook 會自動 `pip install -r requirements.txt` 並設好 `PYTHONPATH`。
   若工具 import 失敗,先手動跑 `pip install -r requirements.txt`。
1. **讀取脈絡**:完整讀 `RULES.md`、`PLAN.md`、`STATE.md`、`CLAUDE.md`,以及 `knowledge/` 索引與 `log/` 最近 1–2 筆。
2. **遵守守則**:依 `RULES.md` 的標準流程與遞迴規則行事(AC-first、自我驗證、L2 自主、5 輪預算)。
3. **定位並推進**:從 `STATE.md` 找出下一步,推進**一個有界工作塊**(一個階段裡的一個明確步驟)。
4. **自我驗證**:用 `tools/mesh_gen/` 的評估器量化(靜態 `evaluate_mesh`、變形 `deform_eval` 真實位移場轉移、
   整合 `validate_against_real`)。⚠️ 變形閘**用真實位移場轉移,不要用未校準的 `stress_field`**。
   評估器本身也要可信(對照藝術家真值 / 負對照)。
5. **記錄**:新發現寫進 `knowledge/`(更新索引);更新 `STATE.md`(進度/下一步/未解);
   在 `log/YYYY-MM-DD-NNN.md` 新增一筆。
6. **收尾**:用清楚訊息 commit & push 到開發分支,然後結束。**不要嘗試無限長跑。**

遇到需人類決策(A 類岔路)、連續無進展、或目標達成,依 `RULES.md` 停止條件標記狀態並停止。

## 目前進度快照(2026-06-24)

- 工具齊備:`generate_mesh`(v1 Delaunay)/ `generate_mesh_v2`(strip)/ `evaluate_mesh`(靜態)/
  `deform_eval`(真實 deform 轉移閘,已自一致性驗證)/ `atlas_crop` / `validate_against_real`(整合 AC)。
- 真實資產 `assets/main_draw.{json,atlas,png}` 已在 repo。
- S3 對 `curtain_left` 已通過整合 AC(v1 IoU 0.98 > 藝術家 0.918、真實變形乾淨)。
- **建議下一步**:把 `validate_against_real.py` 推廣到其餘 3 個 mesh(curtain_right / shadow / shadow2)。
