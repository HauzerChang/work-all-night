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
6. **收尾**:用清楚訊息 commit & **push 回你啟動時所在的那條分支(排程 trigger 直接指向開發分支,
   目前為 `claude/vibrant-franklin-yhvu37`,不再走 PR/merge 流程;分支名以啟動時 `git branch --show-current`
   為準)**,讓下次排程從同分支接手時能讀到更新後的 `STATE.md`。然後結束。**不要嘗試無限長跑。**

遇到需人類決策(A 類岔路)、連續無進展、或目標達成,依 `RULES.md` 停止條件標記狀態並停止。

## 目前進度

> ⚠️ 進度與「下一步」**一律以 `STATE.md` 為準**(本檔不再重複,以免過時誤導)。
> 讀完 RULES/PLAN/STATE 後,從 `STATE.md` 的「下一步動作」挑一個有界塊推進即可。

工具索引(細節見各 `knowledge/*.md`):
- S3 mesh:`generate_mesh`(v1)/ `generate_mesh_v2`(strip,預設)/ `evaluate_mesh`(靜態)/
  `deform_eval`(真實 deform 閘)/ `validate_against_real`(整合 AC)。
- S2 切圖閘:`evaluate_slicing`(atlas 重組保真)。
- S4 PSD:`make_test_psd`(合成 fixture)/ `psd_slice`(PSD→件+manifest+自驗閘)。
- 資產:`assets/main_draw.{json,atlas,png}` 已在 repo;真實分層 PSD 待補。
