# ChatGPT 桌面版補圖步驟

1. 開 ChatGPT(使用有圖片生成功能的模型/GPT-image),附上 `1_upload_this.png`(洞=透明區)。
2. 貼上 `prompt.txt` 的提示詞送出。若介面提供「選取區域/編輯」,在洞的位置塗選後再送出。
3. 生成後下載結果圖(PNG),存成 `result.png`。建議同一張重試 2~3 次,各存 `result_1.png`、`result_2.png`…
4. 回到 repo 根目錄執行:
   `python3 tools/mesh_gen/s4_gptfill_package.py ingest tools/mesh_gen/s4_data/gptfill_pkg_demo result.png`
   (會自動把結果縮放對齊、**只採用洞內**,洞外強制保持原圖,並輸出 `filled.png` / `compare.png` 與漂移報告)
5. 把 `tools/mesh_gen/s4_data/gptfill_pkg_demo` 資料夾(含 result*.png 與 ingest 輸出)commit/push,或直接傳給我。
