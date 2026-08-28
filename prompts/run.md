# 每次排程執行的指令 (run prompt)

> 把這份內容當作 Scheduled session / Trigger 的 prompt,或在 trigger 裡直接寫:
> 「請依照 prompts/run.md 的指示推進這個研究專案。」

---

你正在接手一個**長期、跨 session 的自主研究專案**(Spine mesh 系統研究與鍛鍊)。
你沒有上一次執行的記憶,repo 裡的檔案就是你的全部記憶。請嚴格依下列步驟:

0. **釘固定分支(避免分支增生)**:本主排程**只在固定分支 `claude/spine-main` 上累積**。
   Routine 一律從 default clone 並自動開一條隨機名 `claude/...` 工作分支,若「push 回啟動分支」會**每次 run 都產生新分支**
   (本 repo 一度累積 200+ 條 `claude/vibrant-franklin-*` 即此原因)。故**開頭先切到固定分支**
   (理想上把 repo default 設為 `claude/spine-main`,則這步是 no-op):
   ```
   git fetch origin claude/spine-main
   git checkout claude/spine-main 2>/dev/null || git checkout -b claude/spine-main
   git pull --ff-only origin claude/spine-main || true
   ```
   之後所有讀寫、commit、push **都在 `claude/spine-main`**。⚠️ 絕不用 `git rev-parse` 動態偵測分支名當 push 目標。
0.5 **環境**:SessionStart hook 會自動 `pip install -r requirements.txt` 並設好 `PYTHONPATH`。
   若工具 import 失敗,先手動跑 `pip install -r requirements.txt`。
1. **讀取脈絡**:完整讀 `RULES.md`、`PLAN.md`、`STATE.md`、`CLAUDE.md`,以及 `knowledge/` 索引與 `log/` 最近 1–2 筆。
2. **遵守守則**:依 `RULES.md` 的標準流程與遞迴規則行事(AC-first、自我驗證、L2 自主、5 輪預算)。
3. **定位並推進**:從 `STATE.md` 找出下一步,推進**一個有界工作塊**(一個階段裡的一個明確步驟)。
4. **自我驗證**:用 `tools/mesh_gen/` 的評估器量化(靜態 `evaluate_mesh`、變形 `deform_eval` 真實位移場轉移、
   整合 `validate_against_real`)。⚠️ 變形閘**用真實位移場轉移,不要用未校準的 `stress_field`**。
   評估器本身也要可信(對照藝術家真值 / 負對照)。
5. **記錄**:新發現寫進 `knowledge/`(更新索引);更新 `STATE.md`(進度/下一步/未解);
   在 `log/YYYY-MM-DD-NNN.md` 新增一筆。
4.5 **skill 化檢查(里程碑時)**:若本次是里程碑,跑 `python3 tools/check_readiness.py` 更新
   `skills/READINESS.md`。若某 HOLD 區塊跨過 skill 化門檻 → 產出/更新 `skills/<id>/` 套件並升版
   (SemVer;只有 ≥L2 GREEN 能力可進),並依 RULES **C 類**回報使用者拍板是否 sync。
   ⚠️ **評估器就緒 ≠ 生成器就緒**:生成能力仍 L0/L1 的區塊保持 HOLD,勿打包。策略見 `skills/README.md`。
6. **收尾**:用清楚訊息 commit & **push 回固定分支 `claude/spine-main`**
   (`git push -u origin claude/spine-main`),讓下次排程接手時讀到更新後的 `STATE.md`。然後結束。
   **不要嘗試無限長跑。**
   > ✅ **分支策略(2026-08-28 定案,取代舊的動態偵測)**:主排程固定用 `claude/spine-main`,每次 run 線性累積,
   > 不再增生分支。S4(切圖+補圖)由**獨立排程**跑在 `claude/spine-s4-inpainting`(見 `handoff_S4.md`/`prompts/run_s4.md`),
   > 兩者互不干擾;本排程**不推進 S4**。repo default 建議設為 `claude/spine-main`(見 `SCHEDULE.md`),則步驟 0 checkout 變 no-op。

遇到需人類決策(A 類岔路)、連續無進展、或目標達成,依 `RULES.md` 停止條件標記狀態並停止。

## 目前進度

> ⚠️ 進度與「下一步」**一律以 `STATE.md` 為準**(本檔不再重複,以免過時誤導)。
> 讀完 RULES/PLAN/STATE 後,從 `STATE.md` 的「下一步動作」挑一個有界塊推進即可。

工具索引(細節見各 `knowledge/*.md`):
- **S1 目標圖反推分析器**(`tools/analyzer/`):`analyze_target`(分層 PSD→五段規格)/
  `validate_analyzer_award`(對 Award 真值)/ `genre_priors`+`validate_priors`(分鏡先驗庫)/
  `segment_flat`+`validate_flat_recall`(平圖拆件 baseline)/ **`build_spine`+`validate_build`
  (規格→可載入 Spine 素材 json+atlas+png,round-trip 閘)**。
- S3 mesh:`generate_mesh`(v1)/ `generate_mesh_v2`(strip,預設)/ `evaluate_mesh`(靜態)/
  `deform_eval`(真實 deform 閘)/ `validate_against_real`(整合 AC)/ `compare_robot_mesh`(對 Award 美術 mesh)。
- S2 切圖閘:`evaluate_slicing`(atlas 重組保真)。
- S4 PSD:`make_test_psd`(合成 fixture)/ `psd_slice`(PSD→件+manifest+自驗閘)/ `atlas_crop`(多頁+CW)。
- 資產:`assets/main_draw.{json,atlas,png}`、`assets/Award.{json,atlas,png,png2}`、
  `assets/robot_parts.psd`、`assets/Symbol_Ww.psd` 已在 repo。
