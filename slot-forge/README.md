# slot-forge

Slot 遊戲自動生成研究(lulainnotech「過熱的CPU」)。目標:輸入 demo 網站 → 產出可在 Cocos Creator 3.7.3 開啟並 Spin 的專案。

- `STATE.md` 進度與阻塞 · `LOG.md` 每次紀錄 · `VERIFY-QUEUE.md` 待人工驗證
- `refs/` 參考原始碼(唯讀,Hauzer 提供)
- `schemas/` rules / pacing / art-manifest / spin 協議 schema + 1070s 範例
- `skills/slot-*` skill 草稿 · `knowledge/<track>/` 知識筆記 · `maps/` MAP 圖

驗證 rules.json:`python3 skills/slot-rules-ingest/scripts/validate_rules.py schemas/examples/1070s.rules.json`
