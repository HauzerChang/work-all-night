# gpt-image-2 API key 設定指引(候選17 授權)

目標:讓 S4 排程(Claude Code on the web 雲端 session)能呼叫 OpenAI `images/edits`(`gpt-image-2`)做生成式補圖驗證。
程式端只讀環境變數 `OPENAI_API_KEY`(`tools/mesh_gen/s4_openai_client.py`),**key 不進 repo、不進 log**。

## 步驟

1. **取得 key**:<https://platform.openai.com/api-keys> → *Create new secret key*。
   - 建議用**專用 project + 專用 key**(Project 內設獨立 *budget / usage limit*),不要用個人主 key。
   - key 只顯示一次,複製後不要貼到對話、commit、issue 裡。
2. **設費用上限(重點)**:Platform → *Settings → Limits*(或 Project 的 Limits)設月上限,例如 US$10。
   帳戶需有 billing 餘額;gpt-image 系列可能需要 **Organization Verification**(*Settings → Organization → General → Verify*),否則 API 回 403/404。
3. **放進排程環境(不是 repo)**:claude.ai/code → 該 Routine 使用的 **Environment** → 編輯 → *Environment variables* 新增
   `OPENAI_API_KEY=sk-...`。(環境變數僅在該 environment 的 session 內可見;不要寫進 setup script 或 repo 檔案。)
4. **網路政策**:Environment 的網路存取需允許 `api.openai.com`(*Trusted/預設* 清單未必包含;若選 *Custom* 請加入該網域)。
   2026-10-12 實測:目前環境**已可連到** `api.openai.com`(用假 key 得 401,表示路徑通)。
5. **驗證(免費,不產圖)**:新 session 內執行
   `python3 tools/mesh_gen/s4_openai_check.py` → 三行 OK 即就緒。
   - `FAIL 1/3`:環境變數沒帶進來(第 3 步)。 `401`:key 錯。 `403/404`:未通過組織驗證或帳號沒有該模型。 `429`:額度/billing。

## 授權後排程會做什麼(請確認可接受)

- 依 `STATE_S4.md` 候選17:用既有 `s4_openai_client.edit_image`,在**小樣本**(先 ≤ 6 次呼叫、`quality=low`)跑「挖洞→生成補圖→與真值比對」;
  每次呼叫記錄到 `tools/mesh_gen/s4_data/openai_usage.jsonl`(只記 metadata,不含 key/圖)。
- 先定評分方式再擴大樣本(chunk 35 教訓:生成式輸出不適合沿用 CPU 版閘門)。
- 請你在回覆裡給我一個**總呼叫次數或金額上限**,我會寫進 `STATE_S4.md` 當硬上限,超過即停。
