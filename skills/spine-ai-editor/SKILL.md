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
  (6) 【資產前處理 · 純 CPU】從 PNG(alpha) 自動生成可載入、耐變形的 Spine mesh（strip / Delaunay 拓樸 + IoU/變形/拓樸量化閘）、從分層 PSD 依「一圖層=一部位」契約自動切件、驗證/重組 atlas 切圖 —— 在組進 spine 之前先把資產做乾淨並自我驗收。

  觸發詞：「spine 動畫」「.spine」「spine 角色」「改 spine」「新增動作」「spine 骨架」「胸口怎麼動」「spine 結構擴充」「影片轉動畫」「分鏡圖轉 spine」「課題二」「課題三」「結構性 bug」；資產前處理：「PNG 轉 mesh」「自動生成 mesh」「mesh 拓樸」「mesh 會不會撕裂/自交」「deform 驗證」「PSD 切件」「atlas 切圖/重組」「頂點覆蓋率 IoU」「S2」「S3」「S4」。

  Requires: Python 3（patch 腳本 + 資產前處理，必須）；資產前處理另需 numpy/opencv-python-headless/scipy/triangle/psd-tools（見 assets/mesh_gen/requirements.txt，純 CPU）；Cocos Creator MCP（DaxianLee/cocos-mcp-server 或同等）+ ffmpeg 為 Cocos/影片流程所需。
---

# spine-ai-editor

把 Spine 2D 角色變成一個可以隨意被 AI 改寫、即時驗證的可程式化資產。

---

## 何時觸發

| 使用者徵兆 | 對應能力 |
|---|---|
| 上傳 .spine / .json / .atlas，想知道裡面有什麼 | (1) Parse |
| 「幫我加一個動作」「讓他做 X」「改這支 idle」 | (2) Edit / Generate |
| 給 AI 生成影片或手繪分鏡圖，要轉成 Spine 動作 | (3) Video / Storyboard → Animation |
| 「胸口要能單獨動」「頭跟不上身體」「需要新配件」等結構性限制 | (4) Structural expansion |
| 「推到 Cocos 看一下」「Cocos preview」 | (5) MCP push & preview |
| 「PNG 幫我做成 mesh」「PSD 切件」「mesh 會不會撕裂」「切圖對不對」 | (6) 資產前處理 pipeline(S2/S3/S4) |

---

## 核心能力（4 條主軸）

### 1. 識別與解析 Spine 檔案

讀 `.json` + `.atlas` + 4 張 png（典型 spine 多 atlas page 結構），輸出：

- **anatomy.md**：bones hierarchy / slot 表 / skin attachments / animations 清單
- **animation_breakdown.json**：每支動畫的 timeline / keyframe / easing 機讀資料
- **atlas region 對照**：哪些 region 被用、哪些是浪費
- **可行性評估**：哪些動作可加、哪些受結構限制

詳見 `references/spine_3_8_reference.md`。**第一步永遠是用 `assets/validator_v0.py` 跑 schema 驗證**，後續任何 patch 都複用它做回歸測試。

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

詳見 `references/cocos_mcp_push_sop.md`。

### 5. 資產前處理 pipeline（S2 / S3 / S4，純 CPU）★上游

在把資產「組進 spine JSON」之前,先自動把圖層/貼圖做成乾淨、耐變形、可**量化驗收**的 mesh 與切件。
工具在 `assets/mesh_gen/`(純 CPU,附機讀 pass/fail 閘,不靠肉眼)。

- **S3 PNG(alpha) → mesh**:strip(掃描線直條,耐大拉伸)/ Delaunay(blob 凹形件)自動選;
  `generate(target_verts=N)` 用頂點預算反推輪廓解析度對齊藝術家覆蓋率。
  ```bash
  pip install -r assets/mesh_gen/requirements.txt
  python3 assets/mesh_gen/generate_mesh_v2.py part.png -o part_mesh.json
  python3 assets/mesh_gen/evaluate_mesh.py part_mesh.json part.png     # 靜態閘
  python3 assets/mesh_gen/deform_eval.py ...                          # 變形閘(真實位移場,勿用 stress_field)
  ```
- **S4 分層 PSD → 切件**:`psd_slice.py --eval`(切件+manifest+重組無損)。契約 `references/psd_contract.md`;
  slot 命名 = `<PSD檔名>/<圖層名>`、一圖層=一 slot、size 對應 spine +2px。
- **S2 atlas 切圖/重組保真**:`atlas_crop.py`(多頁+CW derotate)/ `evaluate_slicing.py`。

合流:`psd_slice`(切件)→ `generate_mesh_v2`/`generate(target_verts=)`(mesh)→ `evaluate_mesh`/`deform_eval`(驗收)
→ 交給本 skill 的 patch_templates 組進 spine → validator_v0 → Cocos 9 步推送。
**完整 SOP 見 `references/mesh_pipeline_sop.md`;累積發現/校準教訓見 `references/mesh_findings.md`。**

---

## 工作流程框架

對於任何「給我做 X」型的請求：

```
Step 1: 確認資產位置
  - workspace 上傳（會在 /sessions/.../uploads/）
  - 已在 Cocos 專案內（用 asset_query find_by_name 找）
  
Step 2: 若 anatomy doc 不存在，先 Parse
  - 用 validator_v0.py 跑一遍當 sanity check
  - 寫一份 anatomy summary（人類看的）
  
Step 3: 判斷請求類型
  ┌─ 只加動畫           → SOP 4.2 (animation patch)
  ├─ 改既有動畫         → SOP 4.2 with overwrite
  ├─ 結構性限制要解     → SOP 4.3 (structural expansion)  
  ├─ 結構性 bug 要修    → SOP 4.4 (reparent + transform mode)
  ├─ 影片轉動畫         → SOP 4.5 (video pipeline)
  └─ 分鏡圖轉動畫       → SOP 4.6 (storyboard)
  
Step 4: 寫 patch_*.py 腳本（永遠用 Python，不靠 LLM 自己拼 JSON）
  - 可重跑、可版本控制、可驗證
  - 使用 patch_templates/ 內的範本起手

Step 5: 跑 validator 確認 valid（0 error）

Step 6: Minify JSON
  - pretty-printed Spine json 通常 50~60KB
  - minified 通常 20~30KB，剛好 fit 在一次 tool call

Step 7: 跑 Cocos MCP 9 步流程

Step 8: 等使用者預覽 + 回報視覺結果

Step 9: 根據回報調整數值，重跑 Step 4-8（每輪 < 30 秒）
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
10. **【mesh】評估器先驗可信度再信**：每個閘先跑正對照(藝術家真值應 pass)+ 負對照(壞的應 fail)。踩過四次 miscalibration(stress_field 過猛、PSD 透明區填白、atlas derotate 方向、固定頂點預算對大件過緊)
11. **【mesh】變形閘只用真實位移場 `transfer_deform_check`,不要用未校準的 `stress_field`**(合成場會假性失敗)
12. **【mesh】weighted + 無 deform timeline 的件靠骨骼權重變形**,沒有逐頂點位移場 → 只能驗靜態幾何,變形交給骨架/權重
13. **【mesh】unweighted mesh 格式**:`len(vertices)==2×頂點數==len(uvs)`、**hull 頂點必排最前**、座標 y-up 以圖中心為原點、uv 為 0..1
14. **【atlas】貼圖可能被縮小打包**(Award ~0.70);attachment width/height 記原始邏輯尺寸,texture 比對需先 resize 對齊;**round-trip 自洽 ≠ 絕對正確,需外部真值校驗方向**

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
2. 若無 anatomy doc，先讀 .json 跑 validator_v0
3. 設計 keyframe（看 references/animation_patch_patterns.md「揮手」pattern）
4. 寫 patch_wave.py 用 patch_templates/add_animation.py 改
5. 跑 patch → validator → minify
6. push 9 步流程（含 3 條補償）
7. 提示使用者 preview + 告訴他要觀察什麼
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

詳細各條 SOP 看 `references/` 子目錄。
