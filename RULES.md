# 操作守則與遞迴規則 (RULES)

> 每次 session 開始，**第一件事完整讀完本檔**，再讀 `PLAN.md`、`STATE.md`、`CLAUDE.md`，
> 以及 `log/` 最近 1–2 筆。你沒有上一個 session 的記憶，這些檔案就是你的全部記憶。
> 完整方法論見 `自主Spine工作流_SOP.md` 與 `Spine能力鍛鍊計畫.md`；冷啟動全參考見 `handoff_brief.md`。

## 每次執行的標準流程 (the loop)

1. **載入脈絡**：讀 `RULES.md`(本檔)、`PLAN.md`、`STATE.md`、`CLAUDE.md`、`knowledge/` 索引、`log/` 最近紀錄。
2. **定位**：從 `STATE.md` 找出「目前階段」與「下一步動作」。
3. **先定可檢查的驗收目標 (AC)**：動手前，把這次要做的事寫成**可被自己量測**的條目
   (用 `spineInspector` 的 `getWorldVertices` / `getMeshBounds` / `screenshot`，不靠肉眼)。這是自主迭代的前提。
4. **推進一個有界工作塊**：完成一個階段裡的一個明確步驟(見「單次執行的工作量」)。
5. **自我驗證迴圈 (Build-Verify)**：實作 → validator/量化 → 截圖對照 → 逐條 AC 評分 → 在迭代預算內自動修正。
6. **記錄發現**：新學到 / 新結論寫進 `knowledge/`(並更新其索引)。
7. **更新狀態**：改寫 `STATE.md`(目前進度、下一步、未解問題、阻塞點)。
8. **寫執行紀錄**：在該 run 的 `log/YYYY-MM-DD-NNN.md` 補一個「工作塊」小節。
9. **逐塊 commit & push**：每塊做完就以清楚訊息 commit & push 到開發分支。
   **回步驟 2 挑下一塊,一次 run 重複 6–8 塊**(或觸發「提前收尾條件」);跑完後**結束 session**(不要嘗試無限長跑)。

## 單次執行的工作量 (per-run workload)

- 一次排程 run 推進 **6–8 個有界工作塊**(視進度與剩餘上下文空間而定)。
- **每個工作塊 = 一次完整內圈**(loop 步驟 3–9):定 AC → 實作 → 自我驗證 → 記錄 knowledge →
  更新 `STATE.md` → **獨立 commit & push**。逐塊 commit 保證歷史顆粒度與可續跑
  (容器中途回收也不丟已完成的塊)。
- 塊與塊之間**重讀 `STATE.md` 的「下一步」再挑下一塊**(STATE 是唯一真相來源;每塊都會更新它)。
- **一塊仍要夠小**:單一明確步驟。步驟太大 → 先在 `STATE.md` 拆成子步驟,一塊只做一個子步驟
  (拆出來的其他子步驟就是後續塊的候選)。**寧可 8 個小而穩的塊,不要 1 個大而崩的塊。**
- **log**:一次 run 一個 `log/YYYY-MM-DD-NNN.md`(NNN = 當天第幾次 run),內含**每塊一個小節**
  (避免檔案爆量);開頭寫本 run 完成幾塊、各塊一句摘要。

### 提前收尾條件 (early stop — 達成任一即停,不強湊滿 8 塊)

- 某塊觸發 **BLOCKED / A 類岔路**(需人決策)→ 依停止條件標記後停,不跳過它硬做下一塊。
- **連續 2 塊無實質新進展**(避免空轉燒額度)。
- `STATE.md` 的「下一步」候選清單**已清空**,且無法自行合理衍生新子目標(深度上限 3 層)。
- **接近上下文上限**:把當前塊收乾淨(commit + 更新 STATE)後停,**不要跑到被截斷**而留下半成品。

## 遞迴規則 (recursion)

- **分解**：大目標 → 拆成子目標寫進 `PLAN.md`/`STATE.md`，逐一推進。
- **深度上限**：子目標分解最多 3 層；超過代表問題定義太鬆，回頭收斂範圍。
- **分支條件**：只有出現明確、可驗證的分歧才開新子目標；避免發散。
- **收斂**：每個子目標都要有「完成條件」。達成就標記完成並回上層。
- **每能力必配評估器**：鍛鍊任一能力(S1–S5)前，先有/同時做它的自我品質閘，否則無法自主收斂。

## 自主程度與升級政策 (預設 L2)

依 SOP，只有三種情況回來找使用者，**全部批次化、附選項與建議**：

| 類型 | 觸發 | 提供 |
|---|---|---|
| **A. 不可自決岔路** | 創意/結構性分歧(例：影片轉背面但原圖無背面、骨架 pivot 放哪) | 2–3 選項 + 推薦 |
| **B. 超預算卡關** | 某 criterion 自動迭代 **5 輪**仍 fail | 卡在哪、試過什麼、可能需要的東西 |
| **C. 里程碑審查** | 每個 phase 末 | 進度彙整 + 預覽 + 待拍板的主觀項 |

- **自主程度旋鈕 = L2(平衡)**：客觀 criterion 全自主迭代；只在 A/B 與里程碑停。
- **每 criterion 迭代預算 = 5 輪**。
- **驗證真相來源**：客觀項(角度/pose/輪廓/破圖)用 vision 自評；主觀手感(緩動、重量感)留給使用者。

## 停止條件 (stopping)

每次正常執行完就停，等下次排程。但遇下列情況，**在 `STATE.md` 標 `BLOCKED` 並於紀錄說明後停**：

- 需要人類決策(A 類岔路、授權、外部資源，如取得 PSD 或 `main_draw.png`)。
- 連續 2 次執行無實質新進展(避免空轉燒額度)。
- 偵測到目標已達成 → 標 `DONE`。

## Spine 3.8 技術雷點(動手前務必複習，詳見 `CLAUDE.md` / `handoff_brief.md`)

1. 命名空間：WebGL 在 `spine.webgl.*`，核心在 `spine.*`。
2. setup attachment 多為 null，靠動畫 timeline 控制顯示；`slot.data.attachmentName` 可能 null。
3. deform 受 attachment gating：只在 slot 當前 attachment == timeline attachment 時套用。
4. 取變形後世界座標要**同步** re-pose：`setToSetupPose → anim.apply(...) → updateWorldTransform → computeWorldVertices`。
5. PMA 要對齊 Cocos：建貼圖的 `UNPACK_PREMULTIPLY_ALPHA_WEBGL` 要與 `drawSkeleton(skel,pma)` 一致。
6. weighted mesh 判定 `vertices.length !== uvs.length`；hull 頂點排最前；bind 為相對骨座標；權重每頂點和=1。
7. 緊湊 bezier：`{"curve":..,"c2":..,"c3":..,"c4":..}` 散鍵。
8. 工具產檔：data: URL 不能 navigate；超長 Write/Edit 會被截斷 → 大檔用 bash+python 組裝。

## 品質與誠實

- 不確定就明說，不捏造研究結論；重要結論要可驗證 / 可追溯到來源或實驗。
- 別用 ML 去學「沒有唯一正確解的美術決定」；用確定性演算法 + 評估器把關。
- 每次 commit 都讓 repo 維持「下一個 session 能無痛接手」的狀態。
