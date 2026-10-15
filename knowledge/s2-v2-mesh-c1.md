# C1 — gen_lib.mesh_gen:deform-aware mesh 生成 + 真實位移場自交閘(spine-ai-editor 2.0 Phase C)

> 里程碑 2026-10-15 run 006。承 B1-B4(動畫生成軸),C1 開 **mesh/rig 軸** 的第一步:
> 把 repo 的 **mesh 生成器**(`generate_mesh_v2`)+ **真實位移場自交閘**(`deform_eval`)抽成 skill 入口
> `skills/spine-ai-editor/assets/gen_lib/mesh_gen.py`,閘 `tools/analyzer/validate_c1_mesh.py` **5 AC 全 PASS**。

## 為什麼這個 chunk 有價值

- **v1.3.0 只「檢查」既有 mesh、不「生成」**。C1 讓 2.0 能**從一張件貼圖自動產出可變形 mesh**
  (strip / delaunay / boundary-dense 依件形狀自動選),補上結構擴充的上游缺口。
- **「評估器就緒 ≠ 生成器就緒」在 mesh 層的落點**:`deform_eval` 早證**真實 main_draw 4 mesh(藝術家 mesh)**
  在 9 支動畫全乾淨(`_checker_validated=True`),但那不代表**生成器自動產**的 mesh 也耐變形。C1 補證:
  **生成器自動產的 mesh**,吃該件**真實 deform 最壞幀**位移場轉移後,`self_intersections=0 / flips=0 / degenerate=0`。

## 入口 API(`gen_lib/mesh_gen.py`)

```
generate_mesh(image_path, rows=10, cols=3, mode="auto")   → Spine mesh attachment dict(含 _mode)
crop_region(atlas, png, name, out_path=None)              → 從 atlas 切 region 存 PNG,回路徑
real_deform_field(skeleton, slot, name)                   → (uvs Nx2, field Nx2, 來源 anim 名)
deform_gate(mesh, uvs_src, field)                         → {self_intersections, triangle_flips,
                                                             degenerate, area_ratio, clean}  ← si=0 閘
mesh_schema_ok(mesh) / setup_clean(mesh)                  → 生成拓樸合法性 / 未變形乾淨
generate_and_gate(skeleton, atlas, png, slot, name, ...)  → 端到端 {mesh, AC_iou, AC_real_deform, pass}
```

- CLI:`mesh_gen.py --image r.png --out m.json`(單圖→mesh)/ `--gate --slot image/curtain_left`(真實資產端到端)/ `--self-test`(4 mesh si=0 自檢)。
- 過渡期 import repo `tools/mesh_gen`(透過 `_wire_mesh_tools()`,複用 make_beat 路徑 shim);**Phase E1 bundle** 後 self-contained。

## 核心設計(來自 knowledge/s3-*.md)

- **strip 拓樸**:高瘦、row-convex 件(窗簾)→ 掃描線格點(邊界點順拉伸軸)→ 變形時各帶平滑滑動、耐大單向拉伸
  (Delaunay 散點內部佈局在大拉伸下會自交,見 `s3-real-asset-finding.md`)。
- **真實位移場轉移(正式 deform 閘)**:以 **UV 座標** 為基底,把某 mesh 在所有動畫中「總位移最大幀」的逐頂點位移,
  以 `griddata`(linear + nearest 補洞)內插到**任一拓樸**的新 mesh → 新 mesh 直接吃真實最壞變形做自交檢查。
  **sign 約定**:`mesh.vertices` 已 y-up、field 為 y-up local → 直接相加(`deform_eval` 已自一致性驗證)。
  ⚠️ **不要用未校準的 `stress_field`**(合成場 mag=315 時面積比 2.0 >> 真實 1.13,會假性失敗;見 RULES/run.md)。

## 5 AC(全客觀、可機讀;`tools/analyzer/validate_c1_mesh.py`)

- **C1-1 entrypoint+schema**:公開 API 皆 callable;真實 `image/curtain_left` region 經入口生成 → `_mode=="strip"`
  + Spine mesh schema 合法(`len(vertices)==len(uvs)==2·nv`、triangles 為 3 倍數且索引 `< nv`、`hull∈[1,nv]`、全有限)。
- **C1-2 real-deform si=0(核心)**:main_draw **4 mesh**(curtain_left/right/shadow/shadow2)皆經 `generate_and_gate`
  自動生成 → 各件**自身真實 deform 最壞幀**位移場轉移後 `self_intersections==0 且 triangle_flips==0 且 degenerate==0`。
  實測:4 件全 `mode=strip`、nv=30、**si=0**。(curtain 來源幀 `main_draw_close`,真實場 max mag ≈ 314.7px,面積比 1.141。)
- **C1-3 robot+auto-select**:Award robot 件(身體/左手)經 **auto** → schema 合法 + **setup 乾淨**
  (身體→`boundary-dense-v1`、左手→`delaunay-v1`,皆 setup clean);**且強制 `strip` 於緊湊身體(aspect 1.12)→ setup 不乾淨**
  (退化三角)→ 證 auto 的拓樸選擇是**載重的**(strip 非萬用,高長寬比 row-convex 件才適用)。
- **C1-4 iou-not-degraded**:兩窗簾生成 mesh 對真實 alpha 的 IoU(**0.9338 / 0.9335**)**≥ 藝術家 baseline**(0.9176 / 0.9140)
  → 生成忠實,不是只拓樸乾淨卻漏覆蓋。
- **C1-5 gate-non-vacuous**:真實場 baseline 乾淨(si=0);**打亂位移場空間平滑**(逐頂點 permute)→ **si=18、flips=5**(抓到);
  **放大幅度 ×6** → **si=19、flips=5**(抓到)→ 自交閘**非恆真**(抓得到壞變形)。

## 關鍵發現

1. **評估器就緒 ≠ 生成器就緒**(mesh 層):`deform_eval` 證藝術家 mesh 乾淨 ≠ 生成器自動產的 mesh 耐真實變形;
   C1 在**生成器輸出**上補證 si=0,才真的把「能生成可變形 mesh」這條能力釘住。
2. **auto 拓樸選擇是載重的**:同一件強制 `strip` vs `auto` 結果不同——緊湊低長寬比件(身體 aspect 1.12)強制 strip
   會在底部列塌成退化三角(setup 不乾淨);`auto` 依 `aspect≥1.2 且 row-convex` 才選 strip,否則回退 delaunay/boundary。
   這不是瑕疵而是設計:**strip 的耐變形性只對「順拉伸軸的高瘦件」成立**(窗簾),套到別的形狀反而壞。
3. **shadow/shadow2 共用同一 region 同一 attachment**(main_draw 原生),生成 mesh 相同(strip nv=30);
   生成 IoU 0.9549 遠高於藝術家 shadow mesh baseline 0.4733(藝術家只用 12 頂點粗四邊形描陰影)。

## honest boundary

- **真實 deform 僅 main_draw 4 mesh 有**(Award robot 件無 deform timeline)→ robot 只驗「生成 + setup 乾淨」,
  未驗真實 deform(其件也非 strip 形狀)。要驗 robot 件的真實變形需使用者端提供有 deform 的真實 rig(資源類)。
- 件 → 拓樸模式的選擇規則(strip/delaunay/boundary)為**幾何先驗**(aspect + row-convex + 羽化帶佔比),非學自真值。
- 過渡期 import repo `tools/mesh_gen`(E1 會 bundle 進 `assets/`,self-contained G5);單一真值資產(main_draw / Award)。
- Cocos/viewer 實機載入 = 使用者端(排程 scope 邊界);本閘用 CPU 幾何自交檢查(真實位移場)替代。

## 回歸

`check_readiness.py` **0 RED**(新增 cap `c1_mesh` L2 併入 `spine-anim-forge`,仍 HOLD——生成能力齊但區塊門檻
需 ≥1 條 L3 + 全核心 ≥L2,且本區塊定位為「運動基元是手感先驗,未達打包」)。既有 mesh 閘
(`validate_against_real --gen v2` 等)逐一 PASS。

## 下一步

Phase **C2**(weighted mesh + rig 自動推斷):`generate_weighted_mesh` + `infer_pivots`/`infer_tree` 抽成 skill 入口,
合成肢體鏈 fixture 端到端(repo 既有 `validate_rig_weighted_chain` 5AC 可移植)。真實多 rig 真值仍屬使用者資源
(S5→L3 硬缺口),C2 只搬可自主的合成驗收。
