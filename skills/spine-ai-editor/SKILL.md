---
name: spine-ai-editor
description: |
  程式化解析、編輯、AI 生成 Spine 2D 骨架動畫（Spine 3.8 JSON 格式），並透過 Cocos Creator MCP 直接驅動編輯器做即時預覽迭代。

  Use when the user wants to:
  (1) 識別/檢查現有 Spine 檔（.json + .atlas + .png）的骨架結構、動畫清單、atlas region 使用情況；
  (2) 為現有 Spine 新增動作、修改既有動畫、純 JSON patch 不靠 Spine editor；
  (3) 給 AI 生成影片 / 參考影片 / 分鏡圖，要轉成 Spine 動作（含可行性評估、骨架對映、不可行項目回饋）；
  (4) 擴充 Spine 骨架結構（加 bone、重綁 slot、reparent + transform mode）解除「結構性無法做到」的視覺限制；
  (5) 把改好的 Spine 推進 Cocos Creator、refresh、設 sp.Skeleton 屬性、跑 preview 做來回迭代；
  (6) 診斷並修復動畫品質問題：待機 loop 僵硬、動作卡卡不順、全身同步紙板感、末梢甩不開、要求「更平滑」；
  (7)【2.0 新增】**從零確定性生成**大獎/待機動畫（cascade 跨件波、pop/reveal/wobble/twist…）、繞關節 pivot 變換、
  序列 compose/crossfade/loop、**mesh 生成**（strip/weighted BBW）與 **rig 自動推斷**（pivot/父子樹），
  並用**統一品質閘 validator_v2**（六維度：runtime 可載入／editor 可匯入／loop 閉合／stiffness／deform si／C1）一次驗收。

  觸發詞：「spine 動畫」「.spine」「spine 角色」「改 spine」「新增動作」「spine 骨架」「胸口怎麼動」「spine 結構擴充」「影片轉動畫」「分鏡圖轉 spine」「課題二」「課題三」「結構性 bug」「待機僵硬」「動作卡卡」「更平滑」「loop 優化」「律動感」「生成大獎動畫」「big win」「cascade 波」「生成 mesh」「自動綁骨」「rig 推斷」「序列組合」「validator_v2」「驗收閘」。

  Requires: Python 3（patch 腳本執行）。Optional: Cocos Creator MCP（DaxianLee/cocos-mcp-server 或同等，用於即時預覽迭代；無 MCP 時走人工預覽 fallback，見地雷 #11）、ffmpeg（影片流程用）。
---

# spine-ai-editor

把 Spine 2D 角色變成一個可以隨意被 AI 改寫、即時驗證的可程式化資產。

> **version: 2.0.0**（2026-10-19）
>
> Changelog：
> - **2.0.0** — **確定性生成軸併入**（把半年 research 的生成引擎 + 評估器紀律升進本 skill，見 `MERGE_PLAN_2.0.md`）。新增 `assets/gen_lib/` 生成庫與 `assets/validator_v2.py` 統一品質閘，v1.3.0 的五軸（parse/edit/video/structural/Cocos）+ 品質軸全部保留、零退化：
>   - **生成庫 `gen_lib`**（從零生成，不只 patch）：`make_beat`（`generate_bigwin`/`generate_idle` — cascade 跨件波 + pop/reveal/wobble/twist 單件運動基元）、`sequence`（`compose`/`crossfade`/`loop` 序列組合，可證 C1 連續）。
>   - **結構軸三分支**：`pivot_axis`（繞關節 pivot 變換 `Δ=(M−I)(O−P)`，不動骨架只疊補償 translate）、`mesh`（strip mesh 生成 + 真實 deform 位移場自交閘 si=0）、`rig`（weighted BBW/heat-diffusion mesh 生成 + pivot/父子樹自動推斷）。
>   - **統一品質閘 `validator_v2`**：一條指令輸出六維度 pass/fail + 量化（runtime 可載入／editor 可匯入／loop 閉合／stiffness／deform si／C1），把 v1.3.0 `validator_v1` 的「runtime 載不進」與「editor 匯入 crash（末鍵 curve 地雷 #12）」拆成兩獨立維度 = G2 雙真值機讀落點。
>   - **self-contained（G5）**：生成碼已 verbatim 複製進 `assets/gen_lib/_vendor/`（13 模組），使用者端無 research repo 亦可直接 import、生成、驗收（需 numpy/opencv/scipy）。
>   - **併接護欄**：G1 末鍵 curve 必拔（過 `strip_last_frame_curves`）、G2 雙真值、G3 不覆蓋美術原檔、G4 Spine 3.8 + Cocos 雷點並存。細節見 `MERGE_PLAN_2.0.md`。
> - **1.3.0** — spine-viewer 升級**多圖層版**（頁面標題 v9）。(a) 可同時載入多組骨架：一次拖多套、含子資料夾的整包、或分次拖皆可；每個骨架檔（.json/.skel）依「同資料夾優先」配對 .atlas、貼圖以相對路徑為主鍵（不同資料夾同名貼圖不互蓋），各成一個圖層原位重疊顯示；部分載入失敗會逐檔列錯，不整批中斷。(b) 圖層面板：👁 顯示開關、點名稱＝切「作用中圖層」（動作清單/Skin/Attachment/體檢面板永遠只對作用中圖層操作，debug 線框也只畫該層）、↑↓ 前後順序、⌖ 位置歸零、🗑 點兩下才移除、Tab 循環切換。(c) 動作清單每項新增 ➕：把該動作生成同骨架的獨立圖層同時播放 —— `Xxx` vs `Xxx_v2` 的 A/B 對位在單一視窗原位疊播完成。(d) 畫布直接拖曳角色＝暫移該圖層（⌖ 歸位）；Shift+拖曳或拖空白處＝平移視角。(e) 同路徑檔案重拖＝原地更新該圖層（保留拖曳定位/順序/顯示狀態）→ patch 迭代時改完重拖立即見新結果。(f) 修正：資料夾拖入補齊 Chrome readEntries 每批最多 100 筆的限制（舊版大資料夾會漏檔）、fitView 改為框住所有可見圖層、attachment 覆蓋改為每圖層獨立、mix 調整套用到全部圖層、skin 下拉會同步目前 skin。
> - **1.2.1** — spine-viewer 新增 Attachment 切換面板：每 slot 下拉（動畫控制/隱藏/各 attachment）、slot 過濾、「手動優先」模式（每幀覆蓋動畫換圖 key，模擬程式 setAttachment 常駐切換；取消勾選即可重現「loop 重播蓋回手動切換」的生產坑）。
> - **1.2.0** — 內建獨立網頁預覽器 `assets/spine-viewer.html`：拖入 .json/.skel + .atlas + .png 即可播放（3.8/4.1 runtime 切換、CDN 失敗可拖本機 spine-webgl.js）。含動作清單（前綴自動分組）、scrub/調速/混合、bone/mesh 線框、骨架體檢（對 dj_cat 基準）、mesh/權重分布面板（頂點/綁骨/影響數直方圖/承重骨）。這是地雷 #11 fallback 的標配工具，交付給使用者雙擊即用，勿再重寫。
> - **1.1.1** — 修 crash 級地雷 #12：curve_tools 產出的 timeline 最後一鍵曾帶 curve 欄位，Spine editor 匯入時 AIOOBE crash（runtime 正常所以測不到）。curve_tools 全函式已保證末鍵乾淨並新增 `strip_last_frame_curves()`；validator_v1 將此列為 error。實戰來源：美術匯入 AI patch 檔失敗的 spine.log。
> - **1.1.0** — 新增動畫品質軸：`assets/curve_tools.py`（環形相位平移、Catmull-Rom 穿透式切線、振幅增益、末節衍生、stiffness 量化指標）、`assets/validator_v1.py`（loop 閉合檢查 + `--metric` + 穿透式過衝豁免）、`references/animation_patch_patterns.md` 補 Pattern 8–11（loop 僵硬診斷修復）、地雷 #10/#11、無 Cocos MCP 的 fallback 流程。實戰來源：slot 遊戲主角待機 loop 去僵硬（量化 32.3→14.0）。
> - **1.0.0** — 初版：Parse / Edit / Video / Structural / Cocos MCP 五軸。

---

## 何時觸發

| 使用者徵兆 | 對應能力 |
|---|---|
| 上傳 .spine / .json / .atlas，想知道裡面有什麼 | (1) Parse |
| 「幫我加一個動作」「讓他做 X」「改這支 idle」 | (2) Edit / Generate |
| 給 AI 生成影片或手繪分鏡圖，要轉成 Spine 動作 | (3) Video / Storyboard → Animation |
| 「胸口要能單獨動」「頭跟不上身體」「需要新配件」等結構性限制 | (4) Structural expansion |
| 「推到 Cocos 看一下」「Cocos preview」 | (5) MCP push & preview |
| 「待機好僵硬」「卡卡的」「不夠順」「想要更有律動感」 | (6) Stiffness fix（Pattern 8–11） |
| 「生成一支大獎動畫」「big win」「cascade 跨件波」「做一支待機 loop」 | (7) **生成軸** `gen_lib.make_beat`（`generate_bigwin`/`generate_idle`） |
| 「組一條序列」「把幾個 beat 接起來」「crossfade/loop 閉合」 | (7) **生成軸** `gen_lib.sequence` |
| 「這件沒有 mesh」「要能彎折/飄動」「自動綁骨」「rig 推斷 pivot/父子樹」 | (7) **結構軸** `gen_lib.mesh`（strip）/ `gen_lib.rig`（weighted + rig） |
| 「繞肩/頸轉」「關節 pivot 旋轉而不動骨架」 | (7) **結構軸** `gen_lib.pivot_axis` |
| 「一次把生成結果六維度驗收」「validator_v2」「確認遊戲能播且 editor 能匯入」 | (7) **統一閘** `assets/validator_v2.py` |
| 「開預覽器」「我要看目前的 spine」「A/B 這幾支動畫」「原版改版疊起來對位」「多支動作同時看」 | `assets/spine-viewer.html`（交付給使用者雙擊開啟；1.3 起多圖層，多骨架/多動作可原位重疊對位） |

---

## 核心能力（v1.3.0 五軸 + 品質軸｜2.0 再加「生成軸」）

> v1.3.0 五軸（parse / edit / video / structural / Cocos）+ 品質軸（stiffness）如下 1–5 節，**2.0 全部保留不退化**；
> 2.0 新增的**確定性生成軸**見第 6 節（`gen_lib` 生成庫 + 結構軸 pivot/mesh/rig + `validator_v2` 統一閘）。

### 1. 識別與解析 Spine 檔案

讀 `.json` + `.atlas` + png（典型 spine 多 atlas page 結構），輸出：

- **anatomy.md**：bones hierarchy / slot 表 / skin attachments / animations 清單
- **animation_breakdown.json**：每支動畫的 timeline / keyframe / easing 機讀資料
- **atlas region 對照**：哪些 region 被用、哪些是浪費
- **可行性評估**：哪些動作可加、哪些受結構限制

詳見 `references/spine_3_8_reference.md`。**第一步永遠是用 `assets/validator_v1.py` 跑 schema 驗證**（v0 仍在，v1 向下相容並多做 loop 閉合與品質檢查），後續任何 patch 都複用它做回歸測試。

### 2. 編輯與修改

純 JSON patch 路線，不需要 Spine editor。涵蓋三大 pattern：

- **加新動畫**（不動骨架）→ 用 `assets/patch_templates/add_animation.py` 範本
- **改既有動畫**（替換 timeline）→ 同上 with overwrite flag
- **結構擴充**（加 bone / 重綁 slot / reparent）→ 用 `assets/patch_templates/add_bone_reparent.py`

詳見 `references/animation_patch_patterns.md` 與 `references/structural_expansion.md`。

### 3. 影片 / 分鏡圖 → 動作

兩條入口：

- **影片**：ffmpeg 抽 6~12 張 frame → 逐張看圖識別 pose → 對照目標 skeleton 限制 → 可行性報告 → keyframe 規格 → patch
- **分鏡圖**：直接從圖上的標註讀 6 大身體部位描述 → bone 對映 → patch

詳見 `references/video_to_spine_pipeline.md`。範本：`assets/patch_templates/video_to_animation.py`。

### 4. Cocos Creator MCP 來回迭代

固定 9 步流程（**踩過的雷已內建補償**）：

```
1. asset_operations.create  (overwrite: true)
2. asset_system.refresh
3. ⚠️ 重設 sp.Skeleton.loop = true
4. ⚠️ 重設 sp.Skeleton.premultipliedAlpha = true
5. ⚠️ 重設 sp.Skeleton.useTint = true  (若有 color timeline)
6. set defaultAnimation = "<animation_name>"
7. scene_management.save
8. console.get_logs(filter=error)  ← 確認 0 error
9. 請使用者 preview 並回報視覺結果
```

⚠️ 三條是 refresh 後 sp.Skeleton 屬性會被重置回 false 的補償。**忽略這三條 = 動畫只播一次 / blend 錯亂**。

詳見 `references/cocos_mcp_push_sop.md`。**Cocos MCP 不在線時不要卡住**：走地雷 #11 的 fallback。

### 5. Loop 僵硬診斷與修復（v1.1 新增）

「動畫會動但很僵」是一類可系統化診斷的問題。工具：`assets/curve_tools.py`。

| 症狀 | 成因 | 修法 |
|---|---|---|
| 節拍器感 | key 全 linear（三角波） | `to_ease()` |
| 紙板感、全身一體搖 | 所有骨頭同刻到極值 | `phase_shift()` 照骨架層級派 lag（頭2f/根3f/梢5-7f） |
| 走走停停、每拍煞車 | ease 上在連續揮動的 timeline | `catmull_smooth()` 穿透式切線 |
| 末梢甩不開 / 末節全沒動 | 無 follow-through | `amp_gain(1.1)` / `derive_tip()` |
| 重心是死的 | 軀幹只轉不移 | Pattern 11 body bounce（BPM 對齊） |

修復前後跑 `stiffness_metric()` 量化（linear 三角波 ~30+，修後 ~15 以下），
`loop_closure_report()` 保證首尾閉合。詳見 `references/animation_patch_patterns.md` Pattern 8–11。

**安全原則：永遠加新動畫（`Xxx_v2` / `Xxx_ai`）並存 A/B，不覆蓋美術原檔；改前備份。**

---

### 6. 確定性生成軸（2.0 新增）

v1.3.0 只能**檢查 / patch** 既有資產；2.0 讓本 skill 能**從零確定性生成**動畫、mesh、rig，並用**單一品質閘**驗收。
全部是**純 CPU 確定性演算法 + 評估器**（非 ML；美術手感決定留給使用者，見下方 honest boundary），
入口都在 `assets/gen_lib/`（self-contained，已 bundle 進 `_vendor/`，使用者端無 research repo 亦可跑；需 numpy/opencv/scipy）。

```python
# 生成庫入口（from skills/spine-ai-editor/assets）
from gen_lib.make_beat import generate_bigwin, generate_idle, write_bigwin, DEMO_PARTS, IDLE_DEMO_PARTS
from gen_lib.sequence  import compose_bigwin_sequence, crossfade_bigwin_sequence, compose_idle_loop, write_sequence
from gen_lib.pivot_axis import apply_joint_pivots, bone_origins_from_skel
from gen_lib.mesh      import generate_part_mesh, deform_si_gate, generate_and_gate_part
from gen_lib.rig       import generate_weighted_part_mesh, generate_and_gate_weighted, infer_joint_pivots, infer_limb_tree, rig_from_parts
```

| 分支 | 入口（`gen_lib/*`） | 能力 | 驗收 |
|---|---|---|---|
| **生成庫** | `make_beat.py` | `generate_bigwin`：cascade 跨件波（幾何導向方向）+ pop/reveal/wobble/twist 單件運動基元；`generate_idle`：待機 loop | 過 `validator_v1` 0 error + loop 閉合 + stiffness |
| **生成庫** | `sequence.py` | `compose`/`crossfade`/`loop` 跨 beat 序列組合（可證 C1 連續、接點不 kink） | 序列層雙真值 G2 + loop 閉合 |
| **結構軸·pivot** | `pivot_axis.py` | 繞關節 pivot 變換 `Δ=(M−I)(O−P)`——**不動骨架結構**，只疊補償 translate 使件繞肩/頸轉 | 真實 Award 左手繞肩殘差 ~0.01px + 負對照 |
| **結構軸·mesh** | `mesh.py` | `generate_part_mesh`：strip mesh 生成（解「件沒有 mesh、只能剛體位移」） | **真實 deform 位移場自交閘 si=0**（真值校準：藝術家 mesh 亦 si=0） |
| **結構軸·rig** | `rig.py` | weighted BBW/heat-diffusion mesh 生成 + `infer_joint_pivots`/`infer_limb_tree` 自動推 root/父子/關節 | 真實 skinning si=0 + pivot err<0.10 + 樹拓樸==真值 |
| **統一閘** | `assets/validator_v2.py` | **六維度一次驗收** | 見下 |

**統一品質閘 `validator_v2`（= 2.0 的驗收樞紐）**：對一支 2.0 生成的動畫，一條指令輸出**六維度 pass/fail + 量化**：

```
1. runtime 可載入   （spine-webgl 無頭載入，schema/cx 不超界）
2. editor 可匯入     （末鍵 curve 地雷 #12 檢查，runtime OK ≠ editor OK）
3. loop 閉合
4. stiffness         （量化僵硬度）
5. deform si         （mesh 變形自交，取不到標 na/unavailable）
6. C1                 （序列/loop 接點連續，一次性 beat 預設 info）
```

> **為何拆六維度**：v1.3.0 `validator_v1` 把「runtime 載不進」與「editor 匯入 crash」混在一份 error；
> `validator_v2` 依 error 前綴拆成**兩獨立維度** = MERGE_PLAN **G2 雙真值**「遊戲能播 **且** 編輯器能匯入」的機讀落點。
> `validator_v2` 是**編排層**（不新寫檢查邏輯）：維度 1–4 直呼 `validator_v1`、維度 5 呼 `gen_lib.mesh`、維度 6 呼生成庫 C1 判準 → 各維度的負對照/真值校準紀律自動繼承。

**併接護欄（違反會壞 v1.3.0 實戰保證，生成輸出一律遵守）**：
- **G1 末鍵 curve 必拔**：任何要回 Spine editor 的輸出，`json.dump` 前過 `curve_tools.strip_last_frame_curves()`（地雷 #12）。生成庫的 `write_*` 預設已套。
- **G2 雙真值**：驗收 = `validator_v2` runtime **且** editor 兩維度都過，不是只驗 runtime。
- **G3 不覆蓋原檔**：生成一律加新動畫（`Xxx_v2`/`Xxx_ai`）並存 A/B。
- **G4 雷點並存**：Spine 3.8 雷點（`spine.webgl.*`、PMA、deform gating）與 Cocos 雷點（refresh 重置 loop/PMA/useTint）兩套都在 references，不可擇一。
- **G5 self-contained**：生成碼已 bundle 進 `gen_lib/_vendor/`（13 模組 verbatim），使用者端不 import research repo 的 `tools/`。

**honest boundary（排程 scope 邊界）**：
- 生成是**確定性幾何 + 評估器**；運動**手感**（緩動、重量感、A/B 哪個好看）仍是美術主觀決定，交付給使用者判。
- 純 CPU 可自主驗收的部分（schema 合法 + editor 可匯入 + loop 閉合 + 真實 deform si=0 + rig 準度）已過閘；
  **Cocos 實機 round-trip / spine_inspector 視覺確認 / 真實多 rig 真值**屬使用者端資源，排程不代判。

完整路線圖、各 chunk 的 AC 與關鍵發現見 `MERGE_PLAN_2.0.md`。

---

## 工作流程框架

對於任何「給我做 X」型的請求：

```
Step 1: 確認資產位置
  - workspace 上傳（會在 /sessions/.../uploads/）
  - 已在 Cocos 專案內（用 asset_query find_by_name 找）

Step 2: 若 anatomy doc 不存在，先 Parse
  - 用 validator_v1.py 跑一遍當 sanity check
  - 寫一份 anatomy summary（人類看的）

Step 3: 判斷請求類型
  ┌─ 只加動畫           → SOP 4.2 (animation patch)
  ├─ 改既有動畫         → SOP 4.2 with overwrite
  ├─ 僵硬/不順/要更平滑 → Pattern 8–11 (curve_tools)，先診斷症狀再選 pattern
  ├─ 結構性限制要解     → SOP 4.3 (structural expansion)
  ├─ 結構性 bug 要修    → SOP 4.4 (reparent + transform mode)
  ├─ 影片轉動畫         → SOP 4.5 (video pipeline)
  └─ 分鏡圖轉動畫       → SOP 4.6 (storyboard)

Step 4: 寫 patch_*.py 腳本（永遠用 Python，不靠 LLM 自己拼 JSON）
  - 可重跑、可版本控制、可驗證
  - 曲線/相位/振幅操作一律 import assets/curve_tools.py，不要重造
  - 使用 patch_templates/ 內的範本起手

Step 5: 跑 validator_v1 確認 valid（0 error）；品質類修改加跑 --metric 留下前後對照

Step 6: Minify JSON
  - pretty-printed Spine json 通常 50~60KB
  - minified 通常 20~30KB，剛好 fit 在一次 tool call

Step 7: 跑 Cocos MCP 9 步流程（MCP 不在線 → 地雷 #11 fallback）

Step 8: 等使用者預覽 + 回報視覺結果

Step 9: 根據回報調整數值，重跑 Step 4-8（每輪 < 30 秒）
  - 常見回饋對照：「還是有點硬」→ lag 幀數 +1~2 或 CY_CLAMP 放寬；
    「太軟/太Q」→ 振幅增益降回 1.0、ease 改弱（0.15/0.85）；
    「幅度不夠」→ amp_gain 上調（每輪 ×1.2 內小步走）
```

---

## 已知地雷 / 必讀（救命 30 分鐘清單）

1. **Cocos `asset_system.refresh` 會重置 sp.Skeleton 的 `loop`/`premultipliedAlpha`/`useTint` 到 false** → 每次都要補回
2. **Spine 3.8 緊湊 Bezier 是 `{"curve": cx1, "c2": cy1, "c3": cx2, "c4": cy2}` 散裝鍵**，不是 array
3. **Cocos MCP `set_component_property` 的 `cameraComponent` 屬性 propertyType=component 但 value 要傳 NODE UUID**（不是 component UUID）
4. **Cocos MCP `node_transform` 寫 position 在這版本完全壞掉**（'in' operator error）→ 改用 cc.UITransform 或父節點代替
5. **新 bone 的 setup pose 必須是 (0,0,scale 1,1)** 才能保證既有動畫不破壞
6. **`transform: "onlyTranslation"`** 是「child 跟 parent 走但不繼承 scale/rotation」的關鍵，最常用於 reparent
7. **Cocos 2D 場景需要**：Canvas (cc.Canvas+UITransform+Widget) + Camera (cc.Camera projection=ORTHO=0, clearFlags=SOLID_COLOR=7, visibility 含 UI_2D=33554432) + Canvas.cameraComponent → Camera node UUID
8. **ffmpeg 的 `-ss` 用 `bc` 出來的 `.5` 開頭值會 fail**，要用 `0.5`
9. **bash output 上限 ~50KB**，pretty-printed json 會爆，**先 minify 再 cat**
10. **ease-in-out 不是萬靈丹**：它讓每個 key 速度歸零。折返型擺動（值 A-B-A）用它正確；連續揮動型（值 A-B-C-D 掃過）用它 = 走走停停的生硬感，要改 `catmull_smooth()` 穿透式切線。穿透式產生的 c2/c4 超出 [0,1] 是刻意過衝，Spine runtime 支援（僅 cx 必須在 [0,1] 內），validator_v1 已豁免為 info。
11. **Cocos MCP 不在線的 fallback**：直接改專案內的 .json（同名並存新動畫 + 備份），請使用者在 Cocos 手動 refresh 後自行預覽 —— 並「主動提醒」他 refresh 會重置 loop/PMA（地雷 #1 的人工版）。改名動畫後 defaultAnimation 需重選。快速 A/B 首選本 skill 內建的 `assets/spine-viewer.html`（v1.2 起標配）：複製給使用者雙擊開啟，拖 .json+.atlas+.png 即用，比 Cocos refresh 迴圈快得多。1.3（多圖層版）起 A/B 更省：原檔與 patch 檔一起拖入各成一層原位重疊，或在動作清單按 ➕ 把 `Xxx` 與 `Xxx_v2` 疊播直接對位；patch 改完把同路徑 .json 重拖＝原地更新該層（保留定位/順序），不用重開頁面。注意瀏覽器擴充開不了 file://，交付檔案讓使用者自己開。
12. **timeline 最後一個 keyframe 絕不可帶 curve 欄位**：Spine editor 匯入時 curves 陣列大小是 `(key數-1)*19`，末鍵 curve 會寫進越界 index → `ArrayIndexOutOfBoundsException`（6 鍵 timeline 就是經典的 `AIOOBE: 95`）。**runtime（Cocos）讀檔會默默跳過末鍵 curve，所以遊戲測不出來** —— 只有美術匯回 editor 才炸，屬「兩端行為不一致」型地雷。防呆：任何 patch 在 `json.dump` 前呼叫 `curve_tools.strip_last_frame_curves()`；validator_v1 已把它列為 error。驗收標準是「遊戲能播」**且**「editor 能匯入」。

---

## 對接的 Cocos MCP 工具

| 工具 | 用途 |
|---|---|
| `assetAdvanced_asset_query` | find_by_name 找 spine 資產位置 |
| `assetAdvanced_asset_operations` | create / copy / overwrite spine json + atlas + png |
| `assetAdvanced_asset_system` | refresh asset DB（每次 patch 後必跑） |
| `scene_scene_management` | create / open / save 場景 |
| `scene_scene_hierarchy` | 確認節點結構 |
| `node_node_lifecycle` | create node（Canvas / Camera / 掛 sp.Skeleton 的節點） |
| `component_component_manage` | add cc.Camera / sp.Skeleton 等 |
| `component_component_query` | 查 sp.Skeleton 的 enumList 確認 animations 都讀入 |
| `component_set_component_property` | 設 skeletonData / loop / defaultAnimation 等 |
| `debug_debug_console` | get_logs(filter=error) 做最終 sanity check |

---

## 範例：完整一輪「加新動作」流程

使用者：「我想讓機甲做一個揮手的動作」

```
1. 確認 spine 在哪：assetAdvanced_asset_query find_by_name "Fg_Main"
2. 若無 anatomy doc，先讀 .json 跑 validator_v1
3. 設計 keyframe（看 references/animation_patch_patterns.md「揮手」pattern）
4. 寫 patch_wave.py 用 patch_templates/add_animation.py 改
5. 跑 patch → validator → minify
6. push 9 步流程（含 3 條補償）
7. 提示使用者 preview + 告訴他要觀察什麼
```

## 範例：完整一輪「idle 太僵」流程（v1.1）

使用者：「待機 loop 好僵硬，幫我讓它順一點」

```
1. validator_v1.py Main.json --metric  → 記下 baseline stiffness
2. dump timeline：每骨 key 數 / curve 型態 / key 時間網格 / 振幅 / loop 閉合
3. 對照症狀表選 pattern（linear→8a；同網格→8b；連續揮動生硬→9；末梢→10；重心→11）
4. patch 腳本 import curve_tools，「加新動畫」不覆蓋原檔，備份
5. validator_v1 --metric 回歸：stiffness 預期降 40%+、loop closure 0 問題
6. 交付 + 提醒 Cocos refresh 補償 → 等視覺回報 → 只調參數重跑（每輪 <30s）
```

時間：從接到請求到推上 Cocos 預期 **< 5 分鐘**（不含使用者預覽時間）。

---

## 結語

這個 skill 不是要取代 Spine editor。Spine editor 仍是美術做 mesh / 設計骨架 / 細修 keyframe 的最佳工具。

這個 skill 是讓 **「程式化操作 Spine」** 成為可能：

- 用 Python 表達動畫設計 → diff 友善、版本可控
- 用 LLM 推導參考素材 → 文字、影片、分鏡圖都能接
- 用 MCP 即時推 Cocos → 5 分鐘從想法到預覽
- 用 SOP 保證不破壞既有動畫 → 大膽迭代
- 用量化指標驗收動畫品質 → 「有沒有變順」不再只憑感覺

詳細各條 SOP 看 `references/` 子目錄。
