# 交接文件 — S4「切圖 + 補圖」獨立排程

> 目的:把 **S4(切圖 + 補圖)** 從主研究排程拆出,交給**獨立的 Routine** 單獨推進。
> 主排程(`STATE.md` / `prompts/run.md`)自此**不再碰 S4**,專注 S1/S2/S3/S5。
> 本檔是 S4 排程的冷啟動說明;每次執行的實際指令在 `prompts/run_s4.md`,續跑狀態在 `STATE_S4.md`。

---

## 0. 這條排程是誰、跑在哪

- **身分**:專責 S4 的自驅研究排程,與主排程並行、互不干擾。
- **分支**:**專屬分支** `claude/spine-s4-inpainting`(必須 `claude/` 開頭才能 push)。
  **絕不 push 到主排程分支** `claude/spine-main`,以免兩排程互相覆蓋。
- **檔案隔離契約(避免兩排程衝突,務必遵守)**:
  - S4 只寫:`STATE_S4.md`、`log/s4-YYYY-MM-DD-NNN.md`、`knowledge/s4-*.md`、`tools/mesh_gen/`(新增/擴充 S4 工具)。
  - S4 **不改** `STATE.md`、`PLAN.md`、`prompts/run.md`、主排程的 `log/YYYY-MM-DD-NNN.md`。
  - `knowledge/README.md` 索引:S4 新增行追加在檔尾「S4 區塊」,只 append 不改他人行(降低 merge 衝突)。
- **讀取脈絡**:仍完整讀 `RULES.md`(守則/遞迴/L2 自主/5 輪預算)、`CLAUDE.md`(Spine 3.8 雷點)、本檔、
  `STATE_S4.md`、以及既有 S4 知識(見 §3)。守則與主排程共用,唯「狀態/下一步」以 `STATE_S4.md` 為準。

## 1. S4 使命(範圍界定)

S4 = 把「一張(或分層)原始美術圖」變成「可綁進 Spine 的乾淨部位件」,兩個子能力:

| 子能力 | 現況 | 本排程重心 |
|---|---|---|
| **(A) 切圖(slicing)** | ✅ **大致完成** — PSD-first 契約 pipeline 對 2 份真實生產 PSD 無損驗收 + ⇄ Award spine 逐件吻合 | 只做硬化/邊界情況;非主戰場 |
| **(B) 補圖(inpainting)** | ⬜ **未開始** — 這是 S4 真正缺口 | ★ **主任務**:補圖分級降階 pipeline + 補圖閘 |

> 核心策略(來自 `PLAN.md`,別忘):**改輸入契約比硬攻演算法划算** —— 能要到分層 PSD,切圖+補圖兩大難題大半消失。
> 故補圖研究要同時回答「什麼情況下 CPU 補得動 / 什麼情況只能靠美術在 PSD 裡畫全」,把界線量化清楚,而非硬幹。

## 2. 為什麼補圖是缺口(問題定義)

角色動起來時,原本被遮擋的部位會**露出**。若切出的件在被遮區沒有像素,動畫幀會出現**破洞 / 破圖**。
補圖 = 為每個件把「會露出的被遮區」補上合理像素。難度分級(降階 fallback):

1. **邊緣外擴 / 鏡射延伸**(純 CPU,最省)—— 適合純色/漸層/規則紋理的小缺口。
2. **OpenCV inpaint**(`cv2.inpaint`,Telea / Navier-Stokes,純 CPU)—— 中等缺口、非結構性紋理。
3. **LaMa 等深度 inpaint**(需模型權重,可能需 GPU)—— 大缺口 / 結構性內容。
4. **GPU 生成 / 人工**(最後手段)—— CPU 級數搞不定時上移為資源決策,回報使用者。

**S4 排程要做的**:把 1–2 級(純 CPU)做成可自驅工具 + **補圖閘**(量化「補得好不好」),
並**誠實標出** 1–2 級搞不定、必須升 3–4 級的情況(給使用者資源決策)。

## 3. 現成資產與工具(冷啟動可直接用)

### 既有 S4 工具(`tools/mesh_gen/`)
- `psd_slice.py <檔.psd> [--eval] [-o 目錄]` — 分層 PSD → 各部位件 PNG + manifest;`--eval` 跑重組無損閘。
- `atlas_crop.py <atlas> <png> <region名> <out.png>` — 從 atlas 切件(多頁 + **CW derotate**,已修方向 bug)。
- `evaluate_slicing.py` — 切圖→重組保真閘(main_draw 45/45 region MAE=0)。
- `make_test_psd.py` — 造合成分層 PSD fixture(psd-tools 寫入 API)。

### 既有 S4 知識(**必讀**)
- `knowledge/s4-psd-contract.md` — 給美術的 PSD 交檔契約(★=已對真實檔驗證);含「被遮處要畫全(補圖需求前移)」條款。
- `knowledge/s4-psd-to-spine-real.md` — 2 份真實 PSD 驗收 + 機器人 5 件 ⇄ Award spine 對應 + texture-IoU 閉環;
  **含 3 次評估器 miscalibration 教訓**(premultiplied 比對、composite 白底、derotate CCW→CW)。
- `knowledge/s2-slicing-evaluator.md` — 切圖閘方法與局限(rotate 對稱 region 不可區分)。

### 真實資產(`assets/`)
- `robot_parts.psd`(713×693,5 扁平圖層,中文層名)、`Symbol_Ww.psd`(180×180,18 層,含 opacity 153 陰影層)。
- `Award.json/.atlas/.png/.png2`(機器人對應生產 spine;貼圖 ~0.70 縮小雙頁打包)。
- `main_draw.*`(28 bones/40 slots/9 anims)。

### 環境
- SessionStart hook 自動 `pip install -r requirements.txt`(numpy / opencv-python-headless / scipy / triangle / psd-tools)。
  `cv2.inpaint` 在 opencv-python-headless 內建,補圖 1–2 級純 CPU 可跑。若要 LaMa,需另評估權重下載(可能被網路政策擋)。

## 4. 每能力必配評估器 —— 補圖閘的設計(先做閘,再做補圖)

依 `RULES.md`「每能力必配評估器」:**動手補圖前,先有可機讀的補圖閘**,否則無法自主收斂。建議:

- **合成真值法(自造 ground truth)**:取一張完整件 → **人工挖洞(mask)** → 用補圖工具補 → 與**原完整件**比對。
  指標:洞區 premult-RGB MAE / SSIM / 邊界接縫梯度。有真值 → 可正/負對照校準(記取前 3 次 miscalibration 教訓:
  先用 premultiplied-alpha 比對、先跑負對照確認鑑別力再下判定)。
- **遮擋真值法(更貼近實戰)**:用 Award/機器人多件疊合 composite → 已知某件被上層遮住的區域 →
  補該件被遮區 → 若該件在 PSD 有畫全(被遮區有真值像素),即可比對。
- **AC 範式**:洞區補全後 `破洞像素=0`、接縫梯度 < 閾、與真值 MAE < 閾;負對照(不補 / 亂補)須 fail。

## 5. 第一個有界工作塊(建議起點)

> 只做一個,穩定可續跑優先(見 `RULES.md` bounded chunk)。

**建議 chunk 0:補圖閘 v1 + 邊緣外擴 baseline(純 CPU)。**
1. 寫 `tools/mesh_gen/inpaint_eval.py`:合成真值法(挖洞→補→比對),含正/負對照自校準。
2. 實作最省的「邊緣外擴 / cv2.inpaint」baseline,對 1–2 個真實件的人工洞跑閘,量化補得好不好。
3. 誠實界定:哪種缺口 CPU 補得動、哪種一定露破(→ 升 3–4 級 / 回報)。
4. 記 `knowledge/s4-inpaint-evaluator.md`、更新 `STATE_S4.md`、寫 `log/s4-*.md`、commit & push 到 `claude/spine-s4-inpainting`。

## 6. 升級 / 停止(沿用 RULES,回報對象=使用者)

- **A 類岔路**:如「大結構缺口只能 GPU/人工」→ 附 2–3 選項 + 推薦,標 `STATE_S4.md` 為 `BLOCKED` 後停。
- **B 類超預算**:某 criterion 自動迭代 5 輪仍 fail → 回報卡點。
- **C 里程碑**:補圖閘完成、第一個真實件補圖過閘等 → 彙整回報。
- 連續 2 次無實質進展 → 標 `BLOCKED` 並說明後停,避免空轉燒額度。

## 7. 收尾檢查表(每次執行結束前)

- [ ] 只動了 §0 允許的檔案(沒碰主排程檔)。
- [ ] `STATE_S4.md` 已更新(進度 / 下一步 / 未解)。
- [ ] `log/s4-YYYY-MM-DD-NNN.md` 新增一筆。
- [ ] 新發現寫進 `knowledge/s4-*.md` 並在 README 索引 S4 區塊 append。
- [ ] `git rev-parse --abbrev-ref HEAD` 確認在 `claude/spine-s4-inpainting`,commit & push,然後**結束**。
