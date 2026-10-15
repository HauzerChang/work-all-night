# spine-ai-editor 2.0 — C1 mesh 生成 + 變形自交閘入口(strip 生成 + 真實位移場轉移)

> 2026-10-15 run 006(排程主線 = 產出 spine-ai-editor 2.0;MERGE_PLAN Phase **C1**,開 C 階段)。
> 承 B 階段(B1 橋接閘 / B2 單 beat / B3 繞關節 pivot / B4 序列)。B 讓件**動起來**;C1 讓件能**變形**。

## 做了什麼(全新增,無改任何既有生成/產線值)

1. **skill 入口** `skills/spine-ai-editor/assets/gen_lib/mesh.py`(承 make_beat 的 `_wire_repo_tools`,
   包 repo `tools/mesh_gen` 的 `generate_mesh_v2`(strip 拓樸)/ `deform_eval`(真實位移場轉移)/ `atlas_crop`):
   - `generate_mesh(image_path, rows, cols, mode)` → Spine 3.8 unweighted mesh dict(auto 選型)。
   - `mesh_from_region(skeleton, atlas, png, region, …)` → 從 atlas 切 region 緊湊貼圖 → 生成 mesh(端到端便捷)。
   - `mesh_schema_errors(mesh)` → 機械化 Spine 3.8 schema 閘(len(v)==len(uv)、hull 排前、三角索引在範圍、無孤兒頂點)。
   - `real_deform_field_for(skeleton, slot, name)` → 取某 mesh「總位移最大幀」的真實逐頂點位移場(UV 座標,可轉移)。
   - `deform_si_check(mesh, uvs_src, field)` → 把真實場內插到 mesh 頂點套用,回 {self_intersections, triangle_flips, degenerate, area_ratio, clean}。
   - CLI:`python3 mesh.py <png> [--mode] [--out]` / `python3 mesh.py --self-test`(對 main_draw 4 mesh 跑生成 + 真實 deform 閘)。
2. **C1 閘** `tools/analyzer/validate_c1_mesh.py`(5 AC;從 skill 公開 API 生成 → 幾何真值 + 真實位移場轉移)。
3. `gen_lib/__init__.py` 匯出 C1 入口;`tools/check_readiness.py` 新增 cap `c1_mesh`。

## 為什麼這個 chunk 有價值(從「只能檢查」到「能生成且自驗」)

v1.3.0 的 validator **只能檢查既有 mesh、不能生成**。要讓 B 階段動起來的件能**變形**(窗簾彎、陰影拉伸、
衣物飄),就需要 mesh。C1 讓 skill 能**從一張件 PNG 自動生成 deformable mesh**,並用 main_draw 的**真實位移場**
證「這張自動生成的 mesh 在遊戲真實變形下不撕裂(si=0)」——把 MERGE_PLAN 頭條「對 robot/curtain 件生成 strip
mesh,真實 deform si=0」機械化成一條可重跑機讀閘。

## 關鍵發現 — strip 拓樸選型是「真實 deform si=0」的原因,不是附帶

**同一真實位移場**下(main_draw 的 deform timeline 轉移):

| mesh | strip(本入口預設) | naive Delaunay(v1) |
|---|---|---|
| curtain_left  | si=0 clean ✅ | si=0 clean ✅(變形溫和處不鑑別) |
| curtain_right | si=0 clean ✅ | **si=19 flip=3 撕裂** ❌ |
| shadow        | si=0 clean ✅ | **si=64 flip=10 撕裂** ❌ |
| shadow2       | si=0 clean ✅ | **si=64 flip=10 撕裂** ❌ |

naive Delaunay 靜態 IoU 反而更高(curtain_left 0.98 vs strip 0.93),但**真實 deform 下在 curtain_right/shadow
撕裂**。strip 直條拓樸(每列取 alpha 左右邊界放點、順著拉伸軸)讓各帶平滑滑動 → 耐變形。**「靜態像得好」≠
「變形下不壞」;生成器的拓樸選型正是 si=0 可達成的原因。** 這是 `knowledge/s3-real-asset-finding.md` 的結論在
2.0 入口層的實測復現(真實場,非合成 stress field——後者 mag=315 面積比 2.0 會造假性失敗,見 deform_eval.py 警語)。

## 5 AC(全 PASS;真值 = main_draw 4 mesh 的真實 deform timeline + robot_parts.psd 身體件)

- **C1-1 entrypoint+schema**:`generate_mesh` / `mesh_from_region` / `deform_si_check` / `real_deform_field_for` /
  `mesh_schema_errors` 皆可呼叫;對 **curtain 件**(main_draw region,auto→strip)與 **robot 件**
  (robot_parts.psd 身體,強制 strip)皆產 strip mesh 且 `mesh_schema_errors()`==[];`mesh_from_region` 端到端 atlas→mesh 亦 schema 乾淨。
- **C1-2 real-deform si=0(頭條)**:main_draw 4 mesh(curtain_left/right、shadow、shadow2)經公開 API 生成 strip
  mesh(各 30 頂點 / hull 22 / 36 三角)→ 轉移真實位移場 → **si=0 ∧ flip=0 ∧ degen=0**(clean)全數通過。
- **C1-3 strip crux vs naive**:同一真實場下 naive Delaunay 在 curtain_right(si=19)/ shadow(si=64)撕裂,
  strip 全乾淨 → 證 strip 拓樸選型是 si=0 的原因;curtain_left 溫和處兩者皆乾淨(不鑑別,honest)。
- **C1-4 coverage+budget**:strip IoU(0.93/0.93/0.95/0.95)**≥ 藝術家 mesh 基準**(0.918/0.914/0.473/0.473)
  → 覆蓋保真不欠覆蓋;頂點數 30 ≤ 預算 64 → 精簡可控(rows×cols)。
- **C1-5 gate non-vacuous + mode**:`deform_si_check` 抓 (a) 人工對角線自交 bowtie mesh(si=1,零場即觸發)
  (b) naive Delaunay 真實 deform 撕裂(clean=False)→ 閘有牙;auto 選型**資料驅動**:高瘦 row-convex 窗簾→`strip`、
  軟邊 blob(羽化帶=1.0 的光暈 LG_glow_ball_00)→`boundary-dense-v1`、方正件(robot body aspect 1.12<1.2)→`delaunay-v1`。

## honest boundary

- **mesh deform timeline 由動畫層負責;本模組只生 setup mesh 幾何**(頂點/UV/三角/hull),不涉 G1 末鍵 curve
  (那是 timeline 的事)。要讓 mesh 真的在遊戲裡變形,仍需動畫層寫 deform timeline(C2/未來)。
- **robot 件無自身真實 deform 真值**(robot_parts.psd 是靜態分層圖,無動畫)→ 其 strip mesh 以 schema + 轉移
  main_draw 真實場驗,**真實 deform si=0 的真值僅來自 main_draw 的 4 mesh**(單一真值資產)。
- naive Delaunay 的「撕裂」是對照組,用來證 strip 選型有價值;並非說 Delaunay 一律不可用(curtain_left 溫和變形下仍可)。
- viewer / Cocos 實機載入 = 使用者端(排程 scope 邊界);本閘用純 CPU 幾何真值(自交/翻面/退化計數 + IoU)替代。
- weighted mesh 生成 + rig 自動推斷留 **C2**;統一品質閘 validator_v2 留 **D1**。
- 過渡期 import repo `tools/mesh_gen`(Phase E1 bundle 進 assets/ 後 standalone)。
- cap `c1_mesh` L2 併入 `spine-anim-forge`(仍 HOLD:生成能力為確定性演算法 + 評估器,未學自真值,符合「評估器就緒 ≠ 可固化」)。

## 檔案

- `skills/spine-ai-editor/assets/gen_lib/mesh.py` — C1 skill 入口(新)。
- `tools/analyzer/validate_c1_mesh.py` — C1 mesh 生成 + 變形自交閘(5 AC,新)。
- `skills/spine-ai-editor/assets/gen_lib/__init__.py` — 匯出 C1 入口。
- `tools/check_readiness.py` — 新增 cap `c1_mesh`。

相關:`knowledge/s3-real-asset-finding.md`(strip 拓樸的原始發現:散點靜態好但拉伸自交)、
`knowledge/s1-mesh-deform-generation.md`、`s2-v2-sequence-b4.md`(B4 序列)、`s2-v2-pivot-b3.md`(B3)、
`s2-v2-genlib-b2.md`(B2)、`s2-v2-bridge-b1.md`(B1)、`skills/spine-ai-editor/MERGE_PLAN_2.0.md`(Phase 清單)。
