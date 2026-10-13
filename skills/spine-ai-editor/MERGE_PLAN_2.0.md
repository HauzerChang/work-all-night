# spine-ai-editor 2.0 — 合併路線圖 (MERGE PLAN)

> **這是排程主線的新方向**（2026-10-12 使用者拍板，取代 cascade 微變體 soft-HOLD）。
> 目標：把本 research repo 半年累積的**確定性生成引擎 + 評估器紀律**，併進使用者既有的
> `spine-ai-editor v1.3.0`（已 import 在本資料夾），升成 **2.0**。
> 每次排程 run 推進**一個有界 chunk**（見下方 Phase B..E 清單），AC-first、自我量化驗收、更新 STATE、commit。

---

## 0. 定位：2.0 = v1.3.0 的五軸「廣度 + 實戰」 ＋ repo 的「生成深度 + 驗收嚴謹」

- **保留 v1.3.0 全部**（repo 沒有、不可退化）：
  - Cocos Creator MCP 9 步即時預覽 SOP（`references/cocos_mcp_push_sop.md`）。
  - 12 條實戰地雷（尤其 **#12 末鍵 curve → editor 匯入 AIOOBE crash**）。
  - 多圖層 A/B 預覽器 `assets/spine-viewer.html`。
  - 僵硬手感修復 `assets/curve_tools.py`（phase_shift lag / catmull_smooth / derive_tip / stiffness_metric）。
  - 影片/分鏡 → 動作 pipeline（ffmpeg）、結構擴充、patch 範本。
- **從 repo 併入**（v1.3.0 缺、是真升級）：
  1. **確定性動畫生成庫**（`tools/analyzer/gen_animations.py`）：cascade 跨件波（幾何導向方向）、
     pop/reveal/wobble/twist/squash/combo/charge、tier 變體、序列 compose/crossfade/loop（可證 C1）。
  2. **繞關節 pivot 變換**（`tools/analyzer/pivot_rotation.py`）：`Δ=(M−I)(O−P)`，rotate/scale/shear。
  3. **mesh 生成**（`tools/mesh_gen/generate_mesh_v2.py` strip + `generate_weighted_mesh.py` BBW/heat）＋
     變形自交評估（`deform_eval.py` / `weighted_deform_eval.py`）。
  4. **rig 自動化**（`tools/rig/infer_pivots.py` 接觸縫 pivot 推斷 + `infer_tree.py` 肢體樹推斷）。
  5. **評估器紀律**：每能力配量化閘 + 負對照 + 真值校準（repo 69 閘），併成 2.0 的 `validator_v2`。
  6. **spec → 可載入素材**（`tools/analyzer/build_spine.py`）：從零生成，不只 patch。

---

## 1. ⚠️ 併接時的硬性正確性護欄（違反會壞 v1.3.0 的實戰保證）

- **G1｜末鍵 curve 必拔**：repo 的 `gen_animations._bez` 會在 timeline 產生緊湊 bezier。
  任何「要回 Spine editor」的輸出，`json.dump` 前**必呼叫** `curve_tools.strip_last_frame_curves()`
  （地雷 #12，runtime 不炸、editor 炸）。2.0 的生成輸出一律過這關。
- **G2｜雙真值驗收**：repo 閘只驗「runtime 可載入」（spine-webgl）；v1.3.0 `validator_v1` 另驗
  「editor 可匯入 + loop 閉合 + stiffness」。2.0 的驗收 = **兩者都要過**（遊戲能播 **且** 編輯器能匯入）。
- **G3｜不覆蓋美術原檔**：沿用 v1.3.0 安全原則——生成一律加新動畫（`Xxx_v2`/`Xxx_ai`）並存 A/B。
- **G4｜命名空間/PMA**：repo 的 Spine 3.8 雷點（`spine.webgl.*`、PMA 對齊、deform gating）與
  v1.3.0 的 Cocos 雷點（refresh 重置 loop/PMA/useTint）**兩套都要併進 references，不可擇一**。
- **G5｜self-contained**：最終打包時生成碼要 bundle 進 `assets/`（trimmed copy），不可讓 skill
  在使用者端 import 不存在的 `tools/`。過渡期可先引用 repo `tools/`，Phase E 收斂成自帶。

---

## 2. Phase 清單（排程每次做一個有界 chunk；完成就在本檔打勾 + 更新 STATE）

### Phase A — 地基（本 run 2026-10-12 已完成 ✅）
- [x] import v1.3.0 base 進 `skills/spine-ai-editor/`。
- [x] 本 merge plan。
- [x] STATE/PLAN 改向、解除 soft-HOLD。

### Phase B — 生成庫併接（核心升級，逐 chunk）
- [x] **B1 橋接閘**（2026-10-12 run 002 ✅）：`tools/analyzer/validate_v2_bridge.py`——repo 最單純 cascade
      big-win beat →（G1）`strip_last_frame_curves` →（G2）subprocess 呼叫**真正的** v1.3.0 `validator_v1`。
      **5 AC 全 PASS**：0 error（含末鍵 curve 檢查）、loop 閉合 0 問題、stiffness=50.49 可量、
      **負對照**（注入末鍵 curve + 破壞 loop 皆被抓）證閘非恆真。**關鍵發現**：repo `_bez` 只 curve
      `frames[:-1]`，單 beat 生成本就無末鍵 curve（G1 拔 0 條）→ **地雷 #12 的真正風險在序列
      compose/crossfade（B4）/ 統一閘（D1），不在單 beat**。回歸 0 RED（新增 cap `v2_bridge` L2）。
      見 `knowledge/s2-v2-bridge-b1.md`。
- [x] **B2 cascade/pop/wobble/twist 生成進 skill**（2026-10-13 run 003 ✅）：生成入口包成
      `assets/gen_lib/make_beat.py`（`generate_bigwin`/`write_bigwin` 公開 API + CLI + 內建 `DEMO_PARTS`；
      過渡期 import repo `tools/analyzer`，E1 再 bundle），補 `references/animation_patch_patterns.md`
      **Pattern 12**（確定性大獎生成 SOP）。閘 `tools/analyzer/validate_b2_genlib.py` **5 AC 全 PASS**：
      B2-1 經公開 API 產 cascade beat 組 schema 合法 JSON（非臨時腳本）/B2-2 cascade/pop/wobble/twist
      四種皆 `validator_v1` **0 error**（含末鍵 curve 檢查）/B2-3 四 beat loop 閉合 0 問題/
      B2-4 stiffness 可量（cascade 16.46/wobble 62.16/twist 107.05）/B2-5 roundtrip+G1+負對照
      （write_bigwin 寫檔→重讀 0 error；apply_g1=False 注入末鍵 curve 被抓、預設 apply_g1=True 乾淨；破壞 loop 被抓）。
      **AC（viewer 載入）= 使用者端**（排程 scope 邊界）；CPU 可自主部分（schema 合法 + editor 可匯入 + loop 閉合）已過。
      回歸 0 RED（新增 cap `b2_genlib` L2）。見 `knowledge/s2-v2-genlib-b2.md`。
- [x] **B3 繞關節 pivot 變換**（2026-10-13 run 004 ✅）：把 repo `pivot_rotation.py`（確定性「繞任意點
      變換」Δ=(M−I)(O−P) keyframe 補償）抽成**結構軸 skill 入口** `assets/gen_lib/pivot_rig.py`
      （`apply_joint_pivots` 公開 API；mode=rotate/srt/affine），讓「件繞件中心動 → 件繞關節 pivot 動」
      成為可重用、**不動骨架結構**的 keyframe 面流程（補 `structural_expansion.md` **SOP E**，與 SOP A/B
      結構面解法互補）。輸出過 G1；過渡期 import repo tools（E1 bundle）。閘 `tools/analyzer/validate_b3_pivot.py`
      **5 AC 全 PASS**（真值=真實 Award 左手+`infer_pivots` 肩 pivot）：B3-1 經公開 API 左手繞肩 pivot 殘差
      0.01px（<0.5，移植 AC1）/B3-2 繞件中心負對照 48.8px>>補償版（移植 AC2）/B3-3 件最遠點位移 94px+
      剛性等距偏差 0.01px（移植 AC3/AC5）/B3-4 θ=0 Δ=0+bezier 緩動殘差 0.06px（移植 AC4/AC7）/
      B3-5 端到端+**雙真值**：可載入 skeleton Loop limb rotate 經入口補償→有限+loop 無縫+生成 loop pivot
      殘差 0.0003px+內建負對照未套用會動，且 **validator_v1 0 error（editor 可匯入）+loop 閉合 0 問題（G2）**
      +G1 wired（apply_g1=False 注入末鍵 curve 被抓）。**關鍵發現**：結構軸有兩面——結構面（SOP A/B）與
      keyframe 面（SOP E 繞 pivot），後者不動骨架即解肢體物理，且補償後輸出仍過 editor 雙真值；補償密網格
      天生無 curve → editor 乾淨（呼應 B1/B2 單 beat G1 拔 0 條）。回歸 0 RED（新增 cap `b3_pivot` L2）。
      見 `knowledge/s2-v2-pivot-b3.md`。
- [ ] **B4 序列 compose/crossfade/loop（C1）**：接 v1.3.0 的 idle-loop 與多 beat 大獎序列。
      **AC**：相異 beat 接點 C1 連續閘通過；首尾可接 Loop；stiffness 不升。

### Phase C — mesh / rig 併接
- [ ] **C1 mesh 生成 + 變形自交閘**：`generate_mesh_v2` + `deform_eval` 併進結構軸
      （v1.3.0 只檢查 mesh、不生成）。**AC**：對 robot/curtain 件生成 strip mesh，真實 deform si=0。
- [ ] **C2 weighted mesh + rig 自動推斷**：`generate_weighted_mesh` + `infer_pivots`/`infer_tree`。
      **AC**：合成肢體鏈 fixture 端到端通過（repo 既有 5AC 可移植）。
      ⚠️ 真實多 rig 真值仍屬**使用者資源**（S5→L3 硬缺口），此 chunk 只搬可自主的合成驗收。

### Phase D — 統一品質閘 validator_v2
- [ ] **D1**：把 repo 的閘紀律 + v1.3.0 `validator_v1` 合成單一 `assets/validator_v2.py`：
      一條指令同時驗「runtime 可載入 / editor 可匯入 / loop 閉合 / stiffness / deform si / C1」。
      **AC**：對一支 2.0 生成的大獎動畫，一鍵輸出全維度 pass/fail + 量化指標。

### ⚙️ 排程 scope 邊界（2026-10-12 使用者確認）
- **排程環境 = 純 CPU、無 Cocos Creator、無 ffmpeg GPU**。排程**只推進純 CPU 可自主驗收的部分**：
  Phase **B / C / D 全部**，以及 E 的 **E1–E3**（bundle / 改 SKILL.md / 跑 readiness + 重 zip）。
- **Cocos MCP 即時預覽、ffmpeg 影片抽幀、spine_inspector 實機 round-trip = 使用者端完成**（排程不碰、不 block）。
  驗收改用純 CPU 替代：spine-webgl 無頭載入檢查 + `validator_v1`/`validator_v2` 雙真值閘 + 幾何量化，
  Cocos 視覺確認留最後交付給使用者。**排程遇到需 Cocos/ffmpeg 的步驟 → 標記「待使用者端」跳過，不停等。**

### Phase E — 打包升版 & 交付（里程碑 / C 類拍板）
- [ ] **E1**：生成碼 bundle 進 `assets/`（self-contained，滿足 G5）；移除對 repo `tools/` 的硬相依。
- [ ] **E2**：改寫 `SKILL.md` → **2.0.0**（新增軸寫進核心能力表 + 觸發詞 + Changelog），更新 `INSTALL.md`。
- [ ] **E3**：跑 `check_readiness.py` 更新 `READINESS.md`；重 zip 成 `.skill` 交付檔。
- [ ] **E4**：依 RULES **C 類**回報使用者拍板是否 sync（打包/安裝屬帳號層級，需人決定）。

---

## 3. 排程續跑守則（給下一個 run）

1. 讀 `RULES.md`/`PLAN.md`/`STATE.md`/`CLAUDE.md` + 本檔。
2. 從本檔 Phase 清單挑**第一個未打勾**的 chunk（預設照 B1→B2→…順序；B1 是其餘的前提，先做）。
3. AC-first → 實作 → 自我量化驗收（跑閘/讀世界座標/截圖，不靠肉眼）→ 迭代預算 5 輪。
4. 完成就在本檔打勾、更新 `STATE.md`「下一步」、寫 `log/`、commit & push。
5. 遇到需美術手感或使用者資源的岔路（A 類）→ 依 RULES 升級通知，不自行臆造。
