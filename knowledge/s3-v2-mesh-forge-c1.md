# spine-ai-editor 2.0 — C1 mesh 生成 + 變形自交閘入口(strip 生成 → 真實位移場轉移)

> 2026-10-15 run(排程主線 = 產出 spine-ai-editor 2.0;MERGE_PLAN Phase **C1**,「mesh/rig 併接」第一塊)。
> B 階段(B1–B4)把**動畫生成**接上 v1.3.0 雙真值;C1 轉到 **mesh 軸**:把 repo 的確定性 **strip mesh 生成**
> 與**真實位移場轉移自交閘**抽成 skill 入口,機械化證「生成的網格在真實 deform 幅度下不撕裂」。

## 為什麼是這個 chunk(v1.3.0 的空白)

v1.3.0 只**檢查**既有 mesh(viewer A/B、拓樸可視化),**不生成**、也沒有「會不會在動畫拉扯下撕裂」的機讀閘。
repo 半年累積了兩件 v1.3.0 缺的東西,C1 把它們抽成一條 skill 層級流程:

1. **確定性 strip mesh 生成**(`generate_mesh_v2`):對高瘦、row-convex(每掃描線單一 alpha 區段)的件
   (窗簾 / 肢體),用「掃描線邊界格點」三角化成規則梯狀 —— 邊界點為主、順拉伸軸 → **耐變形**;頂點數=rows×cols
   可控(預設 10×3=30);hull 頂點排 vertices 最前(Spine 格式)。非 strip 件(blob,如機器人身體)auto 模式
   **自動回退 Delaunay(v1)**,不硬塞 strip。
2. **真實位移場轉移閘**(`deform_eval.transfer_deform_check`):把真實資產(main_draw 窗簾)在所有動畫中
   「總位移最大幀」的逐頂點位移,以 **UV 座標**內插轉移到**任一拓樸**的生成 mesh,施加後檢查
   self-intersection / triangle-flip / degenerate → **si=0 ⇔ 生成的網格在真實 deform 幅度下不撕裂**。

這是「生成器就緒 ≠ 評估器就緒」在 **mesh 軸**的實例:B 階段證動畫生成能過雙真值,C1 證 mesh 生成能過變形幾何閘。

## 做了什麼(全新增,無改任何生成/產線值)

1. **skill 入口** `skills/spine-ai-editor/assets/gen_lib/mesh_forge.py`(承 make_beat 的 `_wire_repo_tools`,
   包 repo `tools/mesh_gen` 的 `generate_mesh_v2` / `deform_eval` / `evaluate_mesh` / `atlas_crop` 成對外契約):
   - `generate_strip_mesh(image_path, rows=10, cols=3, mode="auto")` → Spine mesh dict(unweighted、hull-first、`_mode` 標記)。
   - `load_real_deform_field(skeleton_path, slot, name)` → `(uvs_src, field, best_anim)`:真實位移場(UV 座標,可轉移)。
   - `deform_safety_check(mesh, uvs_src, field)` → `{self_intersections, triangle_flips, degenerate, area_ratio, bbox, clean}`。
   - `coverage_iou(mesh, mask)`(證乾淨非空殼)、`crop_atlas_region(...)`(真實件切圖)、`forge_and_gate(...)`(端到端)。
   - CLI(`--image` / `--self-test`)。
2. **變形自交閘** `tools/analyzer/validate_c1_mesh.py`(5 AC;從 skill 公開 API 生成 → 真實位移場轉移 → 幾何檢)。
3. `gen_lib/__init__.py` 匯出 C1 入口;`tools/check_readiness.py` 新增 cap `c1_mesh`(L2 pipeline,併入 spine-anim-forge)。

## 驗收結果(validate_c1_mesh.py 5 AC 全 PASS)

- **C1-1 entrypoint+strip**:公開 API 對真實 curtain_left 產 strip mesh —— mode==strip、30 頂點(hull 22)、36 三角、
  unweighted(vertices.len==uvs.len)、hull 排最前、winding 一致、0 退化、頂點在預算內。
- **C1-2 curtain-real-si0(headline)**:真實 **curtain_left + curtain_right** 各經 forge strip → 轉移**自身**真實
  deform 場(`main_draw_close` 幀,area_ratio ~1.14–1.15)→ **si=0 / flips=0 / degen=0**,且 **IoU 0.934/0.934 ≥
  藝術家基準 0.918/0.914**(乾淨 **且** 非空殼)。
- **C1-3 robot+transfer-si0**:(a) 真實 **robot 身體**件(aspect 1.12,blob)經 forge auto → **回退 Delaunay**
  (60 頂點,**不硬塞 strip**=正確路由)→ 轉移真實窗簾場 → si=0;(b) 合成 **肢體**(tall row-convex)→ **strip**
  (30 頂點)→ 轉移同一真實窗簾場(area_ratio 1.72)→ si=0。證 forge+閘在**不同件形狀 × 真實位移場**下一致過。
- **C1-4 checker-validated**:`benchmark_real(main_draw)` 對 **4 片真實藝術家 mesh × 9 動畫** worst
  si/flips/degen **全 0**(`_checker_validated`==True)→ 閘的 checker 與藝術家真值一致(有校準、非武斷寬鬆)。
- **C1-5 non-vacuous(neg)**:對 C1-2 的乾淨 strip mesh 做三種拓樸破壞,閘由**對應通道各自抓到**:
  換 hull 頂點 → **si=105**;折疊(鏡射半邊,相對原 winding)→ **flips=16**;塌陷(兩頂點重合)→ **degen=1**。證閘非恆真。

## 關鍵發現

1. **放大合成場破不破,取決於件幾何 → 放大場不是可靠的「閘有牙」示範子。**
   細長的合成肢體把真實窗簾場 **×8** 放大(面積比 ~42.5)仍 si=0;較寬的窗簾 ×8(面積比 ~6.6)就撕裂。
   故閘的「牙」**不能**用「放大合成場」示範(細長件會假性過關)—— 這正是 `deform_eval` docstring 警告
   「別拿未校準 `stress_field` 當 pass/fail 閘」(教訓 2026-06-24:合成 mag=315 面積比 2.0 造假性失敗)的**另一面**:
   不只「放大會假性失敗」,**「放大不破」也會假性通過**。對的閘 = **真實場轉移(過)+ 拓樸破壞(有牙)**。
2. **triangle_flips 須相對「原 mesh」winding 量,不能以破壞後 mesh 自身為基準。**
   以破壞後 mesh 自身算 setup_signs → flip 恆 0(折疊負對照會假性過關=沒抓到)。改以**原 mesh** 的 winding/面積
   為基準檢破壞後位置,才驗得出 flips —— 這與產線閘 `transfer_deform_check`(以**未變形** mesh 為基準檢變形後)
   同一語義。這是「負對照要測對東西」的實例。
3. **strip 的耐變形是其設計優點,也是為何它適合窗簾/肢體**:邊界點順拉伸軸、規則梯狀 → 真實 deform(甚至等比
   放大)下各帶平滑滑動不自交。auto 模式**只對 row-convex 高瘦件**走 strip,blob 自動回退 Delaunay —— 件形狀
   決定拓樸,不硬塞。

## honest boundary

- 生成的是 **unweighted mesh**(`vertices.length == uvs.length`);weighted mesh + rig 自動推斷是 **C2**(repo 既有
  `generate_weighted_mesh` / `infer_pivots` / `infer_tree`,待搬可自主的合成鏈驗收)。
- **真實 deform 真值只有 main_draw 窗簾**(9 支動畫全有 deform 的生產件);robot 件沒有自己的 deform timeline,
  以窗簾場的 **UV 可轉移性** 施加(合法做法,正是 `transfer_deform_check` 的設計目的),但不是 robot 自身的真值運動。
- Cocos/viewer 實機載入 = 使用者端(排程 scope 邊界);本閘用純 CPU 幾何量化(si/flips/degen)+ 真實場轉移替代。
- 過渡期 import repo `tools/mesh_gen`(透過 make_beat 的 `_wire_repo_tools`);**E1** 會 self-contained bundle 進 assets。
- 哪張圖該切成幾件、mesh 密度取捨仍含美術手感成分(A 類);本閘只把「生成 strip + 真實變形不撕裂」機械化。
- cap `c1_mesh` L2 併入 `spine-anim-forge`(仍 HOLD:該區塊的動畫運動基元為手感先驗,非學自真值,達 L3 前不打包)。
