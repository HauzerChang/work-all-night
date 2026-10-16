# C1 — gen_lib.mesh:mesh 生成 + 變形自交閘(結構軸的 mesh 分支)

> spine-ai-editor 2.0 MERGE_PLAN Phase **C1**(2026-10-16 run 006)。承 B1..B4(動畫生成軸),
> C1 開 **mesh 生成軸**:把 repo 的 S3 mesh 生成引擎 + 變形自交評估器抽成 skill 入口。

## 這個 chunk 解什麼

v1.3.0 的 skill **只能檢查既有 mesh**(拓樸合法、頂點經濟),**不能生成 mesh**。當「結構性無法
做到」是因為**件根本沒有 mesh**(只能整塊剛體位移、無法彎折/飄動,如窗簾、旗幟、頭髮)時,
B3 的「動 keyframe / 動骨架」都救不了——需要**先生成一張能變形的網格**。C1 把這能力搬進 2.0:

- **入口**:`skills/spine-ai-editor/assets/gen_lib/mesh.py`
- **對外 API**:
  - `generate_part_mesh(image_path, rows=10, cols=3, mode="auto")` → Spine 3.8 mesh attachment dict。
  - `deform_si_gate(mesh, skeleton, slot, name)` → 真實 deform 位移場轉移後的幾何品質(si/flips/degen/clean)。
  - `generate_and_gate_part(...)` → 件 → 生成 → 靜態 IoU + 真實 deform 自交閘,一條龍自驗。
  - 輔助:`mesh_is_schema_valid` / `has_real_deform` / `static_iou` / `artist_baseline_iou`。

## 閘:`validate_c1_mesh.py` 5 AC 全 PASS

| AC | 驗什麼 | 結果 |
|---|---|---|
| C1-1 entrypoint+schema | 公開 API 對窗簾產 **strip** mesh(schema 合法、unweighted、hull∈(0,nv])、機器人件合法 | PASS(curtain 30 頂點 hull 22 strip) |
| C1-2 **real-deform si=0** | curtain_left & curtain_right 套**真實 deform 位移場**(總位移最大幀 `main_draw_close`)→ **si==0/flips==0/degen==0** | PASS(area_ratio 1.141/1.153) |
| C1-3 iou≥baseline | 2 窗簾 + 3 機器人件 IoU ≥ 藝術家基準−0.03 | PASS(窗簾 0.933>0.914;機器人 0.96~0.99) |
| C1-4 gate-calibration | repo `benchmark_real` 真實 4 mesh×9 動畫逐幀 worst si/flips/degen 全 0(真值一致)+ weighted 件退回靜態 | PASS(_checker_validated=True) |
| C1-5 gate-non-vacuous | 生成 mesh 對調兩非相鄰 hull 頂點造 tangle → 窗簾真實閘 si=44、機器人靜態閘 si=53 皆抓到 | PASS |

跑:`python3 tools/analyzer/validate_c1_mesh.py [--json]`。

## 關鍵發現

1. **「真實 deform si=0」是拓樸選擇問題,不是參數調校問題**。窗簾在動畫下是**單向拉伸**
   (area_ratio ~1.14);**strip 拓樸**(掃描線格點、邊界點順拉伸軸)天生耐這種拉伸 → si=0。
   對照 `s3-real-asset-finding.md`:Delaunay 散點靜態 IoU 高但大單向拉伸下會自交。
   → mesh 生成器的價值不在「覆蓋率高」(Delaunay 也高),而在「**變形下拓樸穩**」。

2. **weighted 件自動退回靜態拓樸檢查**。Award 機器人件是 weighted(靠骨骼變形、無逐頂點
   deform timeline)→ 真實位移場轉移不適用(`real_deform_field` 假設 unweighted)。
   `deform_si_gate` 先驗 `has_real_deform`:無 → 改驗**生成 mesh 的 setup 靜態拓樸**(仍有牙,
   C1-5 證機器人 tangle si=53 被抓)。生成 mesh 一律 **unweighted** → 可直接 reshape 驗拓樸,
   與美術 weighted mesh 互補(生成器產 unweighted 形狀,weight 另由 C2 BBW 補)。

3. **真值校準讓「過閘」有意義**。C1-4 用 repo `benchmark_real`:真實美術 4 mesh × 9 動畫逐幀
   si/flips/degen 全 0 → 現實中窗簾 deform 本就不撕裂。故生成 mesh 過 si 閘 = **與真值一致**,
   不是閘太鬆的假性通過;配 C1-5 負對照(tangle 被抓)= 閘「不鬆也不恆真」。

## 護欄 / 誠實邊界

- **G(真值來源)**:閘一律用 `real_deform_field`+`transfer_deform_check`(真值校準、可轉移),
  **絕不用** `deform_eval.stress_field`(未校準合成場,mag 過大造假性失敗,見該函式註解)。
- **過渡期相依**:`mesh.py` 目前 import repo `tools/mesh_gen`(透過 `_wire_repo_tools()` shim),
  與 B2/B3/B4 一致;**E1** self-contained bundle 後移除。依賴 numpy/cv2/scipy(hook 已裝)。
- **排程 scope 邊界**:Cocos/viewer 實機載入與 PMA 視覺 = 使用者端;排程用真實 deform 幾何量化等價。
- **留給後續**:weighted mesh 生成(BBW/heat)= **C2**(仍 HOLD,生成能力未達 L2 GREEN);
  真實多 rig 真值 = 使用者資源(S5→L3 硬缺口)。單一真值資產(main_draw 4 mesh + Award 3 件)。

## 回歸

`check_readiness.py` 新增 cap `c1_mesh` L2(併入 `spine-anim-forge`,仍 HOLD——生成庫整體尚未
跨 skill 化門檻)。既有 B1..B4 + S1/S3/S5 閘逐一 PASS(mesh.py / validator 皆純新增,無改任何
既有生成/產線值)。
