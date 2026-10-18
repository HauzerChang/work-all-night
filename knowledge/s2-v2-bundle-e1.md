# 2.0 (E1) self-contained bundle:gen 碼 bundle 進 assets/genpack,移除對 repo tools/ 的硬相依

- **結論**:spine-ai-editor 2.0 的生成/評估引擎已 **self-contained**(MERGE_PLAN_2.0 的 **G5**)。把
  `gen_lib`(make_beat/pivot_axis/sequence/mesh/rig)與 `validator_v2` 公開 API 會用到的 **13 個** repo
  `tools/` 純 CPU 模組,**byte-identical trimmed copy** 進 `skills/spine-ai-editor/assets/genpack/`,並把各
  `_wire_repo_tools()` 改為**優先用 bundle**、repo `tools/` 僅作開發環境 fallback。交付 `.skill`(只帶
  `assets/`)在使用者端**沒有 repo `tools/`** 時也能完整生成+驗收。
- **依據/來源**:閘 `tools/analyzer/validate_e1_bundle.py` **5 AC 全 PASS**(見下)。信心:高(headline AC
  在**真實隔離環境**——沒 sibling `tools/` 的暫存目錄 + `python3 -I` 子程序——跑公開 API,這正是交付佈局)。
- **相關階段**:專案第 3 階段(整合成可交付 pipeline/skill);MERGE_PLAN Phase **E1**。

## bundle 內容(13 模組,來源見 `assets/genpack/MANIFEST.json`)

| 類別 | 模組 | 來源 |
|---|---|---|
| 動畫生成 | `gen_animations` `beat_templates` `tier_variants` `spine_anim` `pivot_rotation` | `tools/analyzer/` |
| mesh 生成/變形閘 | `generate_mesh_v2` `generate_mesh` `deform_eval` `generate_weighted_mesh` `weighted_deform_eval` `atlas_crop` | `tools/mesh_gen/` |
| rig 推斷 | `infer_pivots` `infer_tree` | `tools/rig/` |

- 相依閉包是這樣算出來的:`gen_lib`/`validator_v2` 的公開 API → 直接 import 的模組 → 其**遞迴**非 stdlib
  import(含模組級 `tier_variants`、函式級 `beat_templates`/`spine_anim`/`generate_mesh`/`atlas_crop`)。
- **不在 bundle 內(honest boundary)**:`analyze_target`(分層 PSD→五段規格,S1 前端)**僅**
  `make_beat.parts_from_psd()` 的 PSD 輸入路徑用到 → 可選輸入前端(需 psd-tools/PIL/`psd_slice`/`genre_priors`),
  核心「parts/影像 → 生成 → 驗收」API 不需它;不含時退回 repo fallback。
- **第三方套件不 bundle**:numpy/opencv/triangle/scipy 屬 pip 相依(`requirements`),self-contained 的定義是
  「不需 repo `tools/`」,不是「不需 pip 套件」。

## wire 機制(優先 bundle,repo fallback)

各 `_wire_repo_tools()` 用 `sys.path.insert(0, ...)` 迴圈,**最後一項 = 最高優先**。順序:
repo `tools/{analyzer,mesh_gen,rig}`(低優先 fallback)→ `assets`(curve_tools/validator_v1)→
`assets/genpack`(**最高優先**)。故:
- 使用者端(無 repo `tools/`):只有 genpack 可 import → self-contained。
- repo 開發端:genpack 在 path 最前 → **repo 閘也驗 bundle**(B2..D1 全綠即證 bundle 行為等同 repo)。
- `pivot_axis`/`sequence` 不需改:前者走 `make_beat._wire_repo_tools()`,後者 `from make_beat import _wire_repo_tools`。

## 5 AC(`validate_e1_bundle.py`)

- **E1-1 manifest sync**:13 模組齊、每個與 repo 來源**逐位元一致**(sha256 比對 `MANIFEST.json`)。
  = **防漂移閘**:未來某 run 改了 repo `tools/` 卻忘了重 bundle → 閘 RED 擋下。
- **E1-2 (headline)隔離生成**:複製 `assets/` 到**無 sibling tools/** 的暫存目錄,`python3 -I` 子程序
  import 公開 API,五條生成軸全成功(make_beat cascade+idle / pivot_axis 繞肩 / sequence compose+crossfade /
  mesh 合成遮罩生 strip mesh(30 頂點)/ rig make_chain_parts→rig_from_parts root=torso),且解析到的
  模組檔**位於隔離 genpack**(assert `__file__` 路徑)。
- **E1-3 隔離 validator_v2**:同隔離環境 `validate_v2` 對生成大獎 beat → **overall PASS**;硬閘維度
  runtime/editor/loop 全 PASS,維度 5(deform_si)=`na`(region 占位 beat)、維度 6(c1)=`info`(一次性
  beat)—— 關鍵是**非 `unavailable`**:證維度 5/6 由 bundle 成功 wire(非 import 失敗被標 unavailable)。
- **E1-4 G2 雙真值**:隔離生成的大獎 beat 過隔離 `validator_v1` editor-import **0 error**(含末鍵 curve
  地雷 #12 檢查)—— bundle 的生成器仍 editor-safe。
- **E1-5 負對照(閘非恆真)**:隔離目錄把 `genpack` 移走 → 同一公開 API import **FAIL**(`ImportError`
  找不到 gen_animations)→ 證此測試**真的靠 bundle**,非洩漏的 repo 路徑讓它假性通過;並 assert 隔離目錄
  確實無 repo `tools/`。

## 關鍵發現 / 迭代踩雷

- **隔離要靠「沒有 sibling tools/ 的真實佈局」,不是靠 monkeypatch**:wire 函式無論如何都會把算出的
  `repo/tools/...` 塞進 sys.path;唯有把 `assets/` 複製到上層無 `tools/` 的目錄,那些 fallback 路徑才真的
  不存在 → 子程序只剩 bundle 可用。這同時**逐字模擬交付 `.skill`**(只帶 `assets/`)。`python3 -I` 進一步
  擋掉 PYTHONPATH/user-site 洩漏。
- **bundle 用 copy 而非 symlink/import re-export**:MERGE_PLAN G5 明指「trimmed copy」。repo `tools/` 仍是
  開發真相來源;genpack 是交付物。drift guard(E1-1 sha256)把「兩份副本」的維護成本轉成一條機讀閘。
- **E1 不改任何生成/產線值**:只新增 `genpack/` + 調 `_wire_repo_tools()` 的 path 順序 + 新閘。B2..D1 六閘
  + check_readiness 回歸全綠即證零行為回歸(且 repo 閘現在實際驗的是 bundle 副本)。
- **維度 5/6 的 `na`/`info` ≠ `unavailable`**:前者是「有 wire、算過、該 beat 無 mesh/非 C1」,後者是
  「import 失敗」。E1-3 專門分辨這兩者,才算真的證明 bundle 自帶了維度 5/6 的引擎。

## 待續(Phase E 其餘)

- **E2**:改寫 `SKILL.md` → 2.0.0(新增軸寫進核心能力表 + 觸發詞 + Changelog),更新 `INSTALL.md`。
- **E3**:跑 `check_readiness.py` 更新 `READINESS.md`;重 zip 成 `.skill` 交付檔。
- **E4**:依 RULES **C 類**回報使用者拍板是否 sync(打包/安裝屬帳號層級)。
