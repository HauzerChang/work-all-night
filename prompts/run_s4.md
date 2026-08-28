# S4 排程執行指令 (run prompt — 補圖/切圖獨立排程)

> 把這份內容當作 **S4 專屬 Routine** 的 prompt。此排程與主研究排程並行,**只做 S4(切圖+補圖)**。

---

你正在接手一個**長期、跨 session 的自主研究子專案:S4 切圖 + 補圖**。
你沒有上一次執行的記憶,repo 裡的檔案就是你的全部記憶。請嚴格依下列步驟:

0. **分支**:本排程專屬分支 = `claude/spine-s4-inpainting`。Routine 從 default branch clone 後,先切過去:
   ```
   git fetch origin claude/spine-s4-inpainting || true
   git checkout claude/spine-s4-inpainting 2>/dev/null || git checkout -b claude/spine-s4-inpainting
   git pull origin claude/spine-s4-inpainting || true
   ```
   收尾 commit & push **回 `claude/spine-s4-inpainting`**(用 `git rev-parse --abbrev-ref HEAD` 確認)。
   ⚠️ **絕不 push 到主排程分支** `claude/spine-main`。
1. **環境**:SessionStart hook 會自動 `pip install -r requirements.txt`。失敗就手動裝。
2. **讀取脈絡**:完整讀 `RULES.md`、`CLAUDE.md`、`handoff_S4.md`(S4 交接)、`STATE_S4.md`(S4 續跑狀態),
   以及既有 S4 知識 `knowledge/s4-*.md` 與 `log/` 最近 1–2 筆 `s4-*`。
3. **遵守守則**:依 `RULES.md`(AC-first、自我驗證、L2 自主、每 criterion 5 輪預算、每能力必配評估器)。
4. **定位並推進**:從 `STATE_S4.md`「下一步動作」挑**一個有界工作塊**推進(第一次見 `handoff_S4.md` §5)。
5. **自我驗證**:補圖用**補圖閘**(合成真值:挖洞→補→比對;先正/負對照校準才可信,記取 3 次 miscalibration 教訓)。
6. **檔案隔離契約(務必遵守,避免與主排程衝突)**:只寫
   `STATE_S4.md`、`log/s4-YYYY-MM-DD-NNN.md`、`knowledge/s4-*.md`、`tools/mesh_gen/`(S4 工具);
   `knowledge/README.md` 只在檔尾 S4 區塊 **append**。**不改** `STATE.md`/`PLAN.md`/`prompts/run.md`/主排程 log。
7. **記錄 & 收尾**:更新 `STATE_S4.md`、寫 `log/s4-*`、commit & push 回 `claude/spine-s4-inpainting`,然後**結束**。
   **不要嘗試無限長跑。**

遇需人類決策(A 類岔路,如「只能 GPU/人工補」)、連續無進展、或 S4 達成 → 依 `RULES.md` 標 `STATE_S4.md` 狀態並停。

## 目前進度

> 一律以 `STATE_S4.md` 為準(本檔不重複)。冷啟動完整背景見 `handoff_S4.md`。
