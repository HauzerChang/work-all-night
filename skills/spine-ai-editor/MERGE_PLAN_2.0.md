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
- [x] **B3 繞關節 pivot 變換**（2026-10-14 run 004 ✅）：`pivot_rotation.py`（`Δ=(M−I)(O−P)`）抽成 skill 入口
      `skills/spine-ai-editor/assets/gen_lib/pivot_axis.py`（`apply_joint_pivots`/`bone_origins_from_skel`）——**不動骨架結構**，
      只在既有動畫上疊補償 translate，使件繞**關節 pivot**（肩/頸）轉。補 `references/structural_expansion.md` **SOP E**
      （keyframe 級繞關節 + SOP A 動骨架 vs SOP E 動 keyframe 選用表）；`make_beat.py` 加 `generate_idle`/`IDLE_DEMO_PARTS`
      （limb 走 rotate，繞關節典型來源），`generate_bigwin` 逐位元不變（B2 零回歸）。閘 `tools/analyzer/validate_b3_pivot.py`
      **5 AC 全 PASS**（對映 repo 既有 7 AC + 新增雙真值 G2）：B3-1 入口可呼叫 + 被轉 bone 恰為給 pivot 的 limb +
      轉後過 `validator_v1` 0 error（含末鍵 curve 檢查）/B3-2 真實 Award 左手繞肩殘差 **0.0115px**（repo AC1，經入口）/
      B3-3 繞件中心負對照 48.8px（ratio 4247×）+ 最遠點動 94.3px + 剛性 0.0115px（AC2/AC3/AC5）/B3-4 θ=0 Δ=0 無縫 +
      轉後 idle 首尾相等 → loop 閉合 0 問題（AC4 + 雙真值）/B3-5 對 **B2 pop beat** scale bone `include_scale=True`
      繞 pivot 縮放（ℓ_P 殘差 0.0004px，**接回 B2**）+ bezier 緩動 fixed-point 0.0596px（AC7）+ 守衛 pivot≈原點/未知 bone 跳過。
      **關鍵發現**：密網格重取樣把補償輸出成純線性鍵 → 地雷 #12 天生不觸發（editor-safe）；結構軸有 SOP A 動骨架 / SOP E 動 keyframe
      兩互補解法；scale-about-pivot 同一入口把 B3 接回 B2。回歸 0 RED（新增 cap `b3_pivot` L2）。見 `knowledge/s2-v2-pivot-b3.md`。
- [x] **B4 序列 compose/crossfade/loop（C1）**（2026-10-14 run 005 ✅）：把 repo 跨 beat 序列組合
      （`compose_sequence`/`crossfade_sequence` + C1 判準）抽成 skill 入口
      `assets/gen_lib/sequence.py`（`compose_bigwin_sequence`/`crossfade_bigwin_sequence`/`compose_idle_loop`/
      `build_beat_library`/`write_sequence` + CLI），在**序列層**機械化驗 G2 雙真值。閘
      `tools/analyzer/validate_b4_sequence.py` **5 AC 全 PASS**：B4-1 公開 API 產單一 composed 序列（schema 合法）/
      B4-2 compose 與 crossfade 多 beat 序列皆過 `validator_v1` **0 error**（含末鍵 curve 地雷 #12 檢查），
      序列層末鍵 curve **實測 0**/B4-3 純接續 `is_c1_continuous_sequence`=False（C0 無縫但接點 C1 kink 15~114）、
      crossfade+smoothstep=True（閉式 kink 0）、linear=False/B4-4 Loop `is_c1_loopable`=True + Loop×2 loop 閉合 0 問題
      （首尾可接 Loop）+ crossfade stiffness 3.98 ≤ compose 29.53（stiffness 不升反降）/B4-5 roundtrip + 注入接點末鍵
      curve 被抓 + 破壞 Loop 閉合被抓（閘非恆真）。**關鍵發現：B1 指名「序列才是 G1 真正戰場」被實測關掉——compose
      去重「丟前者尾幀」（`_bez` 必乾淨的 clip 末幀）+ crossfade 純線性重取樣 → 此生成器家族**結構上 editor-safe**，
      G1 拔 0 條；且 crossfade+C1 斜坡不但消接點 kink 還降 stiffness（~7×）。** 回歸 0 RED（新增 cap `b4_sequence` L2）。
      見 `knowledge/s2-v2-sequence-b4.md`。

### Phase C — mesh / rig 併接
- [x] **C1 mesh 生成 + 變形自交閘**（2026-10-16 run 006 ✅）：`generate_mesh_v2` + `deform_eval` 併進**結構軸的 mesh 分支**
      （v1.3.0 只**檢查** mesh、不**生成**）。抽成 skill 入口 `assets/gen_lib/mesh.py`
      （`generate_part_mesh`/`deform_si_gate`/`generate_and_gate_part`）。閘 `tools/analyzer/validate_c1_mesh.py`
      **5 AC 全 PASS**：C1-1 公開 API 對窗簾件產 **strip** mesh（schema 合法、unweighted、hull∈(0,nv]）+ 機器人件合法 mesh/
      **C1-2 headline**：curtain_left 與 curtain_right 生成 strip mesh 套**真實 deform 位移場**（最大幀 main_draw_close）
      → **si==0 / flips==0 / degen==0**（= AC「真實 deform si=0」，area_ratio ~1.14）/C1-3 2 窗簾 + 3 機器人件 IoU ≥ 藝術家基準−0.03/
      C1-4 閘真值校準（repo `benchmark_real` 真實 4 mesh×9 動畫 worst 全 0 → 過閘與真值一致）+ weighted 件退回靜態拓樸檢查/
      C1-5 閘非恆真（生成 mesh 對調兩非相鄰 hull 頂點造 tangle → 窗簾真實閘 si=44、機器人靜態閘 si=53 皆抓到）。
      **關鍵發現：「真實 deform si=0」是拓樸選擇問題——strip（邊界點順拉伸軸）天生耐單向拉伸，Delaunay 散點會自交；
      weighted 件真實場不適用 → 退回靜態拓樸檢查仍有牙。** 回歸 0 RED（新增 cap `c1_mesh` L2）。見 `knowledge/s2-v2-mesh-c1.md`。
- [x] **C2 weighted mesh + rig 自動推斷**（2026-10-17 run 007 ✅）：把 repo 三個確定性純 CPU 器
      ——weighted mesh 生成（`generate_weighted_mesh`:三角化內部密度 + heat-diffusion/BBW 近似權重）、
      關節 pivot 推斷（`infer_pivots`:父子接觸縫）、肢體父子樹推斷（`infer_tree`:接觸距離 Dijkstra）
      ——抽成 skill 入口 `assets/gen_lib/rig.py`（`generate_weighted_part_mesh`/`generate_and_gate_weighted`/
      `infer_limb_tree`/`infer_joint_pivots`/`rig_from_parts`），成為**結構軸的 rig 分支**（C1 解「件沒有
      mesh」,C2 解「件有 mesh 但沒綁骨 / 一堆件沒組成骨架」）。閘 `tools/analyzer/validate_c2_rig.py`
      **5 AC 全 PASS**（全經公開 API）：C2-1 對 Award 不透明件產 Spine **weighted** mesh（schema 合法:
      partition of unity 權重和=1、≤4 骨、hull∈(0,nv]）+ 頂點 ≤1.4× 藝術家（身體 98/98、左手 104/80）/
      **C2-2 headline**:生成 weighted mesh 放回**真實動畫** skinning → setup 乾淨 + 逐幀 si=0/flip=0 +
      平滑度不劣於藝術家;真值校準:藝術家同件 mesh 經同 checker 亦 si=0（checker_validated）→ 過閘與真值一致/
      C2-3 pivot max err/rig=0.051（<0.10）勝質心 baseline（中位 21.6<43.0px）+ rect 代理爆閘 0.82（PSD-first 再現）/
      C2-4 tree Award root==身體 且 拓樸==真值 ROBOT_TREE + τ_frac band 穩定 + 合成鏈 recover 鏈 + 合成星形/
      C2-5 閘非恆真:(a) pivot 隨機/互換 0.44/0.28>>TAU (b) tree 隨機命中 0.015 + 納 effect 汙染樹 (c) weighted
      hull-tangle → setup si>0（身體 150、左手 65）皆抓到。**關鍵發現:①weighted「真實變形 si=0」靠
      heat-diffusion partition-of-unity 平滑權重(藝術家同件亦 si=0,追平真值),對照 C1 unweighted strip 靠拓樸
      選擇耐單向拉伸——兩條變形機制各有生成策略;②pivot/tree 準度取決於件輪廓保真(rect 爆閘=PSD-first 再現);
      ③effect/structural 語意分類須作為輸入(光暈會奪 root 汙染樹),是 honest boundary 非 bug;④weight-scramble
      不一定破(根件諸骨近似剛性),hull-tangle 動拓樸才是可靠負對照。** 回歸 0 RED(新增 cap `c2_rig` L2)。
      ⚠️ 真實多 rig 真值仍屬**使用者資源**（S5→L3 硬缺口）,本 chunk 只搬可自主的合成 fixture + Award 單 rig 真值。
      見 `knowledge/s2-v2-rig-c2.md`。

### Phase D — 統一品質閘 validator_v2
- [x] **D1**（2026-10-17 run 008 ✅）：把 repo 的閘紀律 + v1.3.0 `validator_v1` 合成單一
      `assets/validator_v2.py`：一條指令同時驗「runtime 可載入 / editor 可匯入 / loop 閉合 /
      stiffness / deform si / C1」六維度（各自 PASS/FAIL/NA/UNAVAILABLE）。**核心 1–4 self-contained**
      （validator_v0 + curve_tools），**延伸 5–6**（deform_si = gen_lib.mesh / c1 = gen_animations）
      過渡期 lazy import repo，import 不到標 UNAVAILABLE（不拖垮核心）。閘
      `tools/analyzer/validate_d1_validator_v2.py` **5 AC 全 PASS**：D1-1 對 2.0 生成（gen_lib 公開 API）
      大獎動畫一鍵輸出六維度結構完整報告/**D1-2 headline**：該 2.0 大獎全可檢維 PASS（runtime 0 error +
      editor 0 地雷#12 + loop 首尾 identity + stiffness 16.46 有限）→ overall_pass=True（G2 一鍵）/
      D1-3 deform_si 真值校準：對真實資產 main_draw 4 mesh×deform → 逐 mesh clean（si=0，藝術家真值本身過閘=
      checker_validated）/D1-4 c1 鑑別：idle Loop → C1-loopable PASS vs 一次性大獎 beat → FAIL/
      D1-5 四維各一負對照（末鍵 curve→editor FAIL、破壞 scale 末鍵→loop FAIL、移除 root→runtime FAIL、
      mesh hull-tangle→deform_si FAIL si=34）皆抓到。**關鍵發現：①兩套品質閘 + deform_si + C1 可合成單一
      可重跑機讀閘 → G2 不必人工開 Spine editor；②NA vs FAIL 語意分離是誠實關鍵（一次性 beat 不傳
      --loop-anims 時 C1 標 NA 非 FAIL，overall 只看非 NA/非 UNAVAILABLE 維度）；③核心四維 self-contained、
      延伸兩維 graceful degrade，使閘在使用者端仍可跑核心。** 回歸 0 RED（新增 cap `d1_validator_v2` L2）。
      見 `knowledge/s2-v2-validator-d1.md`。

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
