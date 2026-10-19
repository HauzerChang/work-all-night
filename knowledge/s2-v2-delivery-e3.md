# s2-v2-delivery-e3 — 2.0 Phase E3：check_readiness 更新 READINESS + 打包 `.skill` 交付檔

> run 011（2026-10-19）。承 E2（SKILL.md→2.0.0 文件升版）。MERGE_PLAN_2.0 **Phase E3**（E 階段最後一個排程可自決 chunk；E4 屬帳號層級 C 類）。

## 做了什麼

把 2.0 的整包 skill 固化成**實際可交付、可重現、經隔離驗證的 `.skill` 檔**，並刷新成熟度快照。

1. **`tools/pack_skill.py`（新工具，deterministic packer）**：INSTALL.md 路線 B 的 `zip -r ../x.skill .`
   會因檔案 mtime 每次不同 → 產出 zip 位元每次都變（binary churn 進版控）。改用 Python `zipfile` +
   **固定 date_time（1980-01-01）+ 固定權限位 + 排序條目 + 排除 `__pycache__`/`*.pyc`** →
   **同內容必得同位元組**，可安心 commit。產出 `skills/spine-ai-editor.skill`（35 檔 / ~218KB）。
2. **`skills/spine-ai-editor.skill`（交付檔）**：解壓即是 skill 根（SKILL.md / INSTALL.md /
   MERGE_PLAN_2.0.md / references ×5 / assets 含 gen_lib 5 入口 + validator_v2 + `_vendor` 13 模組），
   可直接拖進 Cowork 或複製進 plugin `skills/`。
3. **`skills/READINESS.md`**：跑 `python3 tools/check_readiness.py`（全跑，含 heavy weighted 閘）刷新快照，
   stamp 到 run 011 / E3。

## 驗收（AC-first，machine-checked）

`tools/analyzer/validate_e3_delivery.py` **5 AC 全 PASS**——測的是**實際交付的 zip**（比 E1 複製目錄更貼近交付真相）：

- **E3-1 manifest**：`.skill` 是合法 zip（CRC 全過）；含整包樹（頂層 3 文件 + references≥5 + gen_lib 5 入口 +
  validator_v2 + `_vendor` 13 模組）；**不含** `__pycache__`/`*.pyc`；`_vendor` 13 模組逐一與 repo 原檔 **byte-identical**。
- **E3-2 headline**：把 `.skill` **解壓到無 repo tools/、清 PYTHONPATH 的隔離根** → `gen_lib.make_beat.generate_bigwin`
  （cascade）→ `validator_v2.validate_v2` 六維度：硬閘 runtime/editor/loop **PASS** + overall **PASS**；
  維度 5 deform_si / 維度 6 c1 皆成功 wire（非 unavailable）。證**交付的那一包本身** self-contained 可用。
- **E3-3 docs-shipped**：解壓出的 SKILL.md `version: 2.0.0` + Changelog 2.0.0 條目 + INSTALL.md 路線B/gen_lib +
  MERGE_PLAN_2.0.md 在包內 → E2 文件隨交付出貨。
- **E3-4 neg-control**：解壓後刪掉 `_vendor/gen_animations.py` → generate_bigwin 如預期 **ImportError**
  → 證 zip 內 `_vendor` 確為交付包真正被用的相依（閘非恆真）。
- **E3-5 determinism**：連打包兩次 → 兩個 `.skill` **位元組完全相同**（sha256 一致）；且已 commit 的交付檔 ==
  重打包結果 → reproducible，commit 無 churn。

回歸：`check_readiness.py` 全跑 → **0 RED**（E3 不改任何既有 cap 的被測路徑；新增 `.skill` 為交付產物）。

## 關鍵發現

1. **交付真相測的是 zip 本身，不是目錄**：E1 證「skill 目錄」self-contained（複製目錄）；E3 進一步解壓**實際的
   `.skill`** 跑生成+六維度驗收——若打包漏檔、把 `_vendor` 排除、或 zip 壞了，E1 不會抓到、E3 會。交付閘要咬在使用者真正拿到的那一包。
2. **交付檔要 deterministic 才能進版控**：`zip -r` 的 mtime 嵌入使 commit 每 run 變 binary → 噪音。
   固定時戳 + 排序 + 固定權限位讓「同內容 → 同位元」，E3-5 把這條做成可自動驗（連打兩次比 sha）。
3. **E1 的隔離手法可直接搬到交付閘**：`.skill` 解壓到 tmp 根 + 清 PYTHONPATH，`_wire_repo_tools()` 算出的
   repo 層不含 tools/ → 唯一 import 來源就是解壓出的 `_vendor/`，negative control（刪 vendored 必炸）沿用。

## 下一步

- **E4**：依 RULES **C 類**回報使用者拍板是否 sync（把 `skills/spine-ai-editor.skill` 安裝到帳號 / 打包同步屬帳號層級動作，需人決定）。
  repo 這端 2.0 的**備料已全部就緒**（生成庫 self-contained + 文件 2.0.0 + 統一閘 + 可交付 `.skill` + 全閘綠）。

## 續跑守則(重要,E3-5 實際抓到過)

- **凡改動 `skills/spine-ai-editor/` 內任何檔(含 `MERGE_PLAN_2.0.md`——它在 skill 包內!),必須
  `python3 tools/pack_skill.py` 重打包 `skills/spine-ai-editor.skill`,再 `python3 tools/analyzer/validate_e3_delivery.py` 確認 E3-5 綠**,
  否則 commit 的交付檔會比 skill 目錄落後(E3-5 會 FAIL 擋下)。本 run 就因「先打包、後改 MERGE_PLAN 打勾」被自己的閘抓到 → 重打包修好。
- 順序:先把 skill 目錄所有編輯定稿 → 再 `pack_skill` → 再 `validate_e3_delivery`。

## honest boundary

- E3 只保證「交付包解壓後，確定性生成 + 六維度自驗」在無 repo 環境可跑；**手感（緩動/重量感）、Cocos 實機 round-trip、
  多 rig 真值**仍屬使用者端（B1..D1 各閘的 honest boundary 不變）。
- 是否把 `.skill` sync 到使用者帳號 = **E4 / C 類**，非排程可自決。
