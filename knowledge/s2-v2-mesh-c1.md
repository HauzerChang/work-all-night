# spine-ai-editor 2.0 — C1 mesh 生成 + 變形自交閘入口（結構軸 mesh 面）

> 2026-10-15 run 006（排程主線 = 產出 spine-ai-editor 2.0；MERGE_PLAN Phase **C1**，開 Phase C）。承 B1–B4
> （動畫軸：橋接閘 / 單 beat / 繞關節 pivot / 序列組合）。把 repo 的 **deform-aware mesh 生成器 + 真實位移場
> 自交閘** 抽成 skill 入口，機械化驗 **mesh 軸的雙真值 G2**。

## 做了什麼（全新增，無改任何生成/產線值）

1. **skill 入口** `skills/spine-ai-editor/assets/gen_lib/mesh_forge.py`（承 make_beat 的 `_wire_repo_tools`
   掛 repo `tools/mesh_gen`；包 `generate_mesh_v2` / `deform_eval` / `evaluate_mesh` 成對外契約）：
   - `generate_strip_mesh(image_path, rows=10, cols=3, mode="auto")` → Spine mesh attachment dict。
     mode=auto：高瘦 row-convex 件（窗簾）→ **strip**（順拉伸軸掃描線格點，耐變形）；blobby/軟邊件 → 回退
     Delaunay / boundary-dense。
   - `scaffold_skeleton(mesh)` → 繞 mesh 建**最小但完整、可載入**的 Spine 3.8 skeleton（五必備 key，真值 A 驗收用）。
   - `install_mesh(skel, slot, att, mesh, bone)` → 就地把 mesh 併進**既有** skeleton（補 bone/slot/skin），
     = mesh 軸 × 動畫軸的結構組合（非孤立 scaffold）。
   - `deform_safety_check(mesh, ref_skel, ref_slot, ref_name)` → 把**真實位移場**（自 ref 的 deform timeline
     『總位移最大幀』、以 UV 為座標）轉移到 mesh 頂點並套用，回傳 {si, flips, degenerate, area_ratio, clean, frame}。
     ⚠️ **用真實場轉移，不用未校準 `stress_field`**（合成場 mag=315 面積比 2.0 >> 真實 1.14，假性失敗）。
   - CLI（`--image/--out/--scaffold/--self-test`）。
2. **mesh 軸雙真值閘** `tools/analyzer/validate_c1_mesh.py`（5 AC；從 skill 公開 API 生成 → subprocess 呼叫
   **真正的** v1.3.0 `validator_v1`）。
3. `gen_lib/__init__.py` 匯出 C1 入口；`tools/check_readiness.py` 新增 cap `c1_mesh`。

## 為什麼這個 chunk 有價值（mesh 軸補上 animation 閘從不碰的真值）

使用者既有 `validator_v1`（v1.3.0）對 mesh **只檢查 schema**（型別/引用/hull），**不生成、也不驗變形期拓樸**。
但 mesh 的致命失敗是**變形下自交/翻面**（撕裂/破圖）——這是 mesh 軸獨有、所有 animation 閘（loop 閉合 / stiffness /
末鍵 curve）從不檢查的真值。C1 把「件貼圖 → strip mesh → 裝進 skeleton → 兩真值驗收」固化成 skill 對外契約。

**mesh 軸的雙真值 G2**（對映 animation 軸的「遊戲能播 且 編輯器能匯入」）：
- **真值 A（可載入 / schema）**：生成 mesh 裝進完整 skeleton → 真正的 `validator_v1` **0 error**（runtime 能載入、
  editor 能匯入；hull-first 契約、引用存在 slot）。且可**併進既有 skeleton**（install_mesh 進 2-bone 骨架）= 結構軸組合。
- **真值 B（變形安全）**：真實位移場轉移後 si=0 / flips=0 / degenerate=0。

## 驗收結果（validate_c1_mesh.py 5 AC 全 PASS）

- **C1-1** `generate_strip_mesh` 公開 API 對真實 curtain_left 產 **strip**（30 頂點 / hull 22 / 36 三角），過
  evaluate_mesh 格式閘（hull-first 0<hull≤nv、三角索引在範圍、degenerate=0、orphans=0、頂點預算）。
- **C1-2 真值 A**：scaffold（生成 mesh）→ validator_v1 **0 error**；併進 **2-bone 骨架**（mesh 掛 arm bone）→
  0 error（結構軸組合成立）；寫檔→重讀→0 error（端到端到可載入檔）。
- **C1-3 真值 B（headline）**：4 真實 deform 件（curtain_left/right、shadow、shadow2）各生成 **strip** → 真實位移場
  轉移 → **si=0 且 flips=0 且 degenerate=0**（area_ratio 0.99~1.153，即真實變形幅度；frame=main_draw_close/open）。
- **C1-4 robot 3 件**（weighted、無 deform timeline）→ auto **正確回退非 strip**（光暈/身體 boundary-dense、
  左手 delaunay）→ 靜態覆蓋率 IoU（0.9602~0.9926）≥ 藝術家基準−0.03（最小裕度 −0.0079，在 margin 內）且拓樸合法。
- **C1-5 負對照（閘非恆真）**：(a) tangle mesh（內部頂點推到對側極端）→ 真值 B **抓到自交**（si=12、clean=False）；
  (b) 壞 slot 引用（skin 指到不存在 slot）→ validator_v1 **抓到** `attachment under unknown slot`；
  (c) 越界三角索引 → 格式閘拒收。

## 關鍵發現

1. **strip 不是「所有件都該 strip」，是窗簾類 row-convex 件的 deform-aware 拓樸選擇**。順拉伸軸的掃描線格點讓各帶
   平滑滑動 → 大單向拉伸下 si=0（對照 knowledge/s3-real-asset-finding：Canny 散點內部佈局靜態 IoU 高但大拉伸自交）。
   blobby/軟邊件（機器人光暈/身體）auto **正確回退非 strip** = 正確生成行為，**非 bug**。這是 C1 的 honest 核心：
   生成器的 mode=auto 分流本身就是對「件形狀 → 拓樸選擇」的確定性決策。
2. **變形自交真值只對有 deform timeline 的件適用**（窗簾：unweighted、靠逐頂點 deform 變形）。weighted、靠骨綁
   變形的件（機器人）無逐頂點 deform → 真值 B 不適用，改以靜態覆蓋率 + 拓樸合法性（真值 A）驗收。這把「X 就緒 ≠
   產線成立」落到 mesh 軸：**不同件類走不同真值組合**，閘據件的 deform 性質分流。
3. **mesh 軸雙真值與 animation 軸正交**：animation 閘驗時間維（loop/stiffness/末鍵 curve）、mesh 閘驗空間維
   （變形下拓樸）。install_mesh 證兩軸可在同一 skeleton 組合，為 Phase D（統一 validator_v2）鋪路——D1 要把兩軸
   真值合成一條指令同時驗「runtime 可載入 / editor 可匯入 / loop 閉合 / stiffness / **deform si** / C1」。

## honest boundary

- **變形閘用真實位移場轉移，不用 stress_field**（run.md 步驟 4 明令；stress_field 僅供最壞情況裕度探測，不當 pass/fail）。
- 真值 B 的真實場目前取自 main_draw 窗簾（單一真值資產；shadow/shadow2 共用同一 region）。更多件類的真實 deform 真值
  屬使用者資源（S4/S5 硬缺口）。
- Cocos/viewer 實機載入 = 使用者端（排程 scope 邊界），本閘用 spine-webgl 無頭等價（validator_v1）替代。
- 過渡期 import repo `tools/mesh_gen`（E1 self-contained bundle 後移除）。
- 哪個件該用 strip vs 手繪 mesh、mesh 密度（rows/cols）細調仍可留美術微調；本閘固化的是「auto 分流 + 兩真值機械化驗收」。

## 下一步

**Phase C2**：weighted mesh + rig 自動推斷（`generate_weighted_mesh` + `infer_pivots`/`infer_tree`）併進結構軸。
AC：合成肢體鏈 fixture 端到端通過（repo 既有 5AC 可移植）。⚠️ 真實多 rig 真值仍屬使用者資源（S5→L3 硬缺口），
此 chunk 只搬可自主的合成驗收。
