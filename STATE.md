# 進度狀態 (STATE) — 續跑核心

> 每次 session 結束前**必須**更新此檔。

## 專案狀態

`ACTIVE`  <!-- SETUP / ACTIVE / BLOCKED / DONE -->

## 目前階段

**專案三階段：第 2 階段(用工具鍛鍊四能力)。**
- 第 1 階段(可視化工具)已完成 → `spine_inspector.html`(含 `window.spineTool` API)。
- **S3 mesh 生成器：完成且對 4 個真實 mesh 收斂達標**(v2 strip 通用,見 `knowledge/s3-four-mesh-generalization.md`)。
- **S2 評估器套件:切圖閘已完成** — `evaluate_slicing.py`,main_draw 45/45 region 重組 MAE=0/0孤兒/0重疊,
  雙向負對照確認鑑別力(見 `knowledge/s2-slicing-evaluator.md`)。S2 尚缺:補圖閘、骨架閘。
- **S4 PSD-first 切圖:已對真實生產檔驗收通過(里程碑)** — `psd_slice.py` 對 2 份真實 PSD
  (`Symbol_Ww` 18件 / `robot_parts` 機器人 5件)切圖無損 PASS;機器人 5 圖層 ⇄ 真實 spine `Award` 的
  slot `機器人拆件/<圖層名>` 逐件吻合(+2px padding)。閘經 premultiplied 校正(透明區白底假性失敗)。
  見 `knowledge/s4-psd-to-spine-real.md`、`s4-psd-contract.md`(已用真實檔校準)。
- **S3 端到端對真實美術 mesh 驗收(里程碑,2026-08-19)** — `compare_robot_mesh.py` 對 Award
  機器人 3 mesh 件(光暈/左手/身體)生成 mesh,同 region 框內靜態覆蓋率 IoU **3 件全 PASS**
  (達美術基準 −0.03 內、0 孤兒),且頂點更省(37~48 vs 美術 78~98)。發現 **mesh uvs 是 region-local**;
  新增 `boundary-dense-v1` 軟邊 blob 模式(光暈 0.92→0.98)+ 通用 `prune_orphans`。
  ⚠️ 限制:weighted mesh 骨骼變形平滑度未驗(靜態 IoU 不涵蓋)。見 `knowledge/s3-robot-mesh-vs-award.md`。
- **S1 目標圖反推分析器:首個原型 + 真值驗收(里程碑,2026-08-19,使用者新增研究項目)** —
  `tools/analyzer/analyze_target.py`(分層 PSD → 五段規格:運動構件/周邊特效/動作分鏡/拆圖策略/補圖項目)
  + `validate_analyzer_award.py`(對 `robot_parts.psd ⇄ Award` 真值)**5 項校驗全 PASS**
  (件召回 1.0、特效 5/5、幾何無 mismatch、分鏡 In/Loop/Out+4 檔位全中、露出 4/4)。
  誠實界定:補圖需求**輸入契約相依**(分層 PSD 0 封閉破洞);#3 分鏡為類型先驗提案。見 `knowledge/s1-target-image-analyzer.md`。
- **S1 擴充:平圖流程 + 分鏡先驗庫(2026-08-19,使用者指定)** —
  (A) `segment_flat.py`+`validate_flat_recall.py`:平圖純 CPU 自動拆件 baseline;壓平 PSD 對真值召回顯示
  同材質/重疊角色 **0/5、0/18 語意召回**,僅「不相連塊」可靠(正對照 3/3)→ 佐證 PSD-first。
  (B) `genre_priors.py`+`validate_priors.py`:先驗庫 `slot_bigwin`(Award)、`slot_reveal`(main_draw)
  覆蓋率皆 **1.0** + 2 未驗證類型。修 2 bug(decomposability 反向、動畫名子字串誤判)。
  見 `knowledge/s1-flat-pipeline-and-priors.md`。
- **S1 端到端「目標圖→可載入 Spine 素材」打通(里程碑,2026-08-19)** —
  `build_spine.py`(analyze_target+psd_slice+generate_mesh_v2 → Spine 3.8 json+atlas+png)+
  `validate_build.py`(round-trip 重建 setup pose == 原 PSD composite)。robot(5件)/Symbol_Ww(18件)
  **全 PASS**(premult MAE 0.03/0.24、0 孤兒、0 未解析 attachment)。mesh/region 分派沿用分析器建議。
  誠實界定:只驗靜態幾何/貼圖編碼;動畫 keyframe / mesh 變形 / 關節 pivot 屬後續。見 `knowledge/s1-build-spine-end-to-end.md`。
- **S3 weighted mesh 變形評估器完成(里程碑,2026-08-27)** — 補上 `deform_eval` 只驗 unweighted 的缺口。
  `weighted_deform_eval.py` 在 Python 重現 Spine 3.8 bone world transform(transform=normal)+ weighted
  skinning + timeline 取樣(緊湊 bezier);`validate_weighted_deform.py` 對 Award 3 機器人 weighted mesh
  **三道校驗全 PASS**:①setup 自一致(3 件重建 0 自交);②藝術家不透明件(身體 98v/左手 80v)真實動畫
  全幀乾淨 si=0;③負對照鑑別力(左手打亂 si=21;身體近剛體用 amp=4 分離:藝術家 si=0 vs 打亂 si=54)。
  修 1 bug:**scale timeline 缺 channel 預設應為 1 非 0**(否則 mesh 塌陷成假性自交);degeneracy 改
  相對面積(避免 big-win scale-from-0 誤判)。發現**軟性加成件(光暈)容許自我重疊**(reveal t=0 精確 keyframe
  si=71,additive 混合無害)→ pass/fail 需依 attachment 語意分類。見 `knowledge/s3-weighted-deform-evaluator.md`、
  圖 `figures/s3_weighted_deform_eval.png`。**這是候選 2(BBW 權重生成)的前置品質閘,現已就緒。**
- **S5 rig pivot 推斷:首個能力 + 真值閘(里程碑,2026-08-29)** — 路線圖「唯一卡死環節」的
  **可客觀化子問題**:給拆件幾何 + 父子樹,推斷每根子骨關節 pivot。`tools/rig/infer_pivots.py`
  (contact-seam:關節=子件最靠近父件的 q 分位點質心,確定性純 CPU)+ `tools/rig/validate_pivots.py`。
  對 Award 機器人 rig 3 關節藝術家真值 **4 AC 全 PASS**(頭 22px/左手 11px/右手 25px,皆 2–5% 軀幹尺度;
  勝質心 baseline 21.6 vs 43px;random/swap/rect 三負對照皆爆閘)。**關鍵發現:pivot 準度=件輪廓保真**——
  region bounding-rect 代理右手誤差 406px,改從 atlas alpha 取真實輪廓降到 25px(PSD-first 論點在 rig 階段再現)。
  `spine-rig-pivot` 區塊 L2 → **HOLD**(僅單一 rig、pivot→bone 樹未接 build_spine)。軸向精修屬美術(A 類)。
  見 `knowledge/s5-rig-pivot-inference.md`、圖 `figures/s5_pivot_inference.png`。
- **S3 weighted mesh 生成器完成(里程碑,2026-08-27,候選 2 主體)** — `generate_weighted_mesh.py`:
  輪廓 → triangle 三角化(max-area 控**內部取樣密度**)→ **heat-diffusion 骨綁權重**(BBW 純 CPU 近似,
  `(L+H)W=HP` 天然 partition of unity)→ Spine weighted 格式(bind 經逆骨變換)。`validate_weighted_gen.py`
  對 Award 不透明件**身體/左手 4 條 AC 全 PASS**(body nv 調到 == 藝術家 98、左手變形比藝術家更平滑、
  真實 Legend 動畫 si=0)。誠實限制:**軟性件(光暈極端 reveal)si 未追平藝術家手工非均勻拓樸**
  (additive 無害,閘歸 si-tolerant,不列硬性 fail);尚未端到端接 build_spine(達 L3 才 skill 化)。
  使 `spine-weighted-forge` 的 `bbw_weights`/`interior_sampling` L0/L1 → **L2**。見 `knowledge/s3-weighted-mesh-generator.md`、圖 `figures/s3_weighted_mesh_gen.png`。
- **S3 weighted mesh 端到端接 build_spine(里程碑,2026-08-27 → weighted-forge READY)** — `build_spine.py --weighted`
  端到端產出含 weighted skin 的可載入 Spine(輪廓→PCA 軸骨→heat 權重→全域骨 index + `build_meta.json`
  effect/structural 語意);`validate_weighted_build.py` 4 AC(可載入/setup 重建/輪廓 IoU/合成骨變形)對
  robot_parts **OVERALL PASS**(身體 IoU 0.937 變形 si=0;光暈 effect additive 容忍)。`weighted_end2end` L0→**L3**,
  `spine-weighted-forge` 區塊**達 skill 化門檻 READY**(check_readiness 實跑確認)。
- **skill 化機制建立(2026-08-27,使用者指定)** — 研究成果分區塊、防半成品固化成 skill。
  完成度機制 `tools/check_readiness.py`(實跑各區塊 validator → 成熟度矩陣 + skill 化門檻判定);
  策略 `skills/README.md`(L0–L4 階梯、門檻「核心能力≥L2 GREEN 且≥1 條 L3」、SemVer 維護政策);
  快照 `skills/READINESS.md`。**5 區塊**:`spine-mesh-doctor`(READY ✅)、`spine-asset-forge`(READY ✅)、
  `spine-slicing`(併 forge)、`spine-target-analysis`(折入 forge)、`spine-weighted-forge`(HOLD:BBW 未做)。
  **已固化首個 skill 套件** `skills/spine-mesh-doctor/`(v0.1.0,自含 evaluators + SKILL.md + references,
  自 assets 目錄可獨立跑,PASS)。防固化規則:評估器就緒≠生成器就緒(weighted-forge 閘 L2 但 BBW L0 → HOLD)。
  自驅迴圈 `prompts/run.md` 加步驟 4.5(里程碑跑 readiness + 達門檻才打包升版 + C 類回報)。
- **S1 分鏡→動畫 keyframe 完成(里程碑,2026-08-27,candidate 0d,讓素材「會動」)** —
  `tools/analyzer/spine_anim.py`(純 Python Spine 3.8 timeline 取樣器:緊湊 bezier/stepped/linear,無瀏覽器)
  + `gen_animations.py`(把 `#3 動作分鏡` 的 role×category 確定性轉成 bone TRS + slot alpha;loop 正弦取樣端點強制相等
  →無縫)+ `build_spine.py --animate` 端到端。`validate_anim.py` 對 robot(slot_bigwin)/Symbol_Ww(slot_reveal)
  **4 AC 全 PASS + 負對照(--selftest)全偵測**;intro/loop/outro 介面全落在 setup identity(任意串接無跳變),
  setup-pose round-trip 不受擾動。誠實界定:role→運動基元為先驗手感提案(非學自真值),緩動美感留使用者;
  mesh deform timeline 未生成。見 `knowledge/s1-storyboard-to-animation.md`。
- **⇢ S4(切圖+補圖)已交接給獨立排程(2026-08-28,使用者決策)** — S4 由專屬 Routine 跑在
  `claude/spine-s4-inpainting`(交接 `handoff_S4.md`、狀態 `STATE_S4.md`、指令 `prompts/run_s4.md`);
  **本主排程自此不再推進 S4**。切圖半邊已完成(PSD-first 對 2 真實 PSD 無損 + ⇄ Award 逐件吻合);
  補圖半邊為該排程主任務。S2 補圖閘亦隨之移出本排程(只留骨架閘)。
- **分支策略定案(2026-08-28,使用者決策)** — 診斷出 remote 累積 200+ 條 `claude/vibrant-franklin-*` 之因:
  舊 `run.md` 收尾用動態偵測啟動分支 + routine 每 run 自動開隨機名工作分支 → 每 run 增生一條。
  改為**主排程釘 `claude/spine-main`、S4 釘 `claude/spine-s4-inpainting`**,開頭 checkout 固定分支、收尾 push 回同名。
  本 `spine-main` 分支經**一次性合流**:以最完整的研究線(weighted 生成器+評估器+skill 機制)為底,
  併入 S1 keyframe(擇優 zjze4k 版)、S4 交接、分支釘定,去除重複評估器。見 `log/2026-08-28-003.md`、`log/2026-08-28-004.md`。

- **S5 rig pivot 多 rig 真值擴充(里程碑,2026-08-30)** — 補上「僅單一 rig 驗過」缺口的一半。
  新增第二個真實藝術家 rig:`main_draw` 貓角色(身體→臉/雙手/尾;臉→鈴鐺,**全 region、左右手共用鏡射貼圖**)。
  contact-seam 演算法 **2 rig(robot+cat)AC1-3 全 PASS**(cat 5 關節 max err/rig=0.096:臉0.072/雙手0.042/尾0.096/鈴鐺0.026;
  勝 baseline 10.8<82.1;random 0.356 / swap 0.237 皆爆閘)。修掉通用性 bug:**region 要用 attachment 鍵(`_region_name`=path>name>attkey)查 atlas,非 slot 名** ——
  貓右手 `image/hand2` 共用 `image/hand` 貼圖,舊碼用 slot 名查不到 → 掉 rect;修後拿真實 alpha、與左手對稱(11px)。
  重構通用 `load_rig`(robot 結果逐值不變,回歸通過)。新增 `tools/rig/plot_pivots.py` → `figures/s5_pivot_multirig.png`。
  `check_readiness`:`pivot_end2end` L0→**L1**(多 rig ✅,build_spine 骨樹寫入仍缺);`spine-rig-pivot` **仍 HOLD**
  (達 L3 唯一剩:pivot→bone 父子樹寫入 build_spine)。見 `knowledge/s5-rig-pivot-inference.md`、圖 `figures/s5_pivot_multirig.png`。
  ⚠️ 註:Award 其他角色 `1_OMG`/`2_SUP`/`3_MEG` 經查為**單 slot 角色**(子 bone 只驅動小燈/光暈,無拆件肢體真值)→ 不適合當 rig 真值。

## 真實資產(已收進 `assets/`)

- `assets/main_draw.json`(真實骨架:28 bones / 40 slots / 9 anims / 4 unweighted mesh)。
- `assets/main_draw.atlas`(region 矩形;sheet `main_draw.png` 2023×1896)。
- **`assets/Symbol_Ww.psd`**(symbol,180×180,18 圖層)、**`assets/robot_parts.psd`**(機器人拆件 big win,713×693,5 圖層)。
- **`assets/Award.json` + `assets/Award.atlas` + `assets/Award.png`(2040²)+ `assets/Award2.png`(1780×1376)**
  (機器人對應的生產 spine,77 bones/47 slots/12 anims,雙頁 atlas;貼圖被縮小 ~0.70 打包)。
- ⚠️ **`main_draw.png` 像素檔尚缺**(只在對話中顯示,未存成檔)。像素級工作(裁切貼圖、
  texture IoU、實機截圖)在拿到該 PNG 前 BLOCKED;但 **deform 幾何分析不需要 PNG**。

## 下一步動作 (next action)

**S3 已推廣到全部 4 個 mesh(里程碑,2026-06-26)**:整合 AC 跑 curtain_left/right + shadow/shadow2。
- **v1(散點 Delaunay)不通用**:靜態 IoU 高但 curtain_right(19 si)/shadow(64 si)真實 deform 自交。
- **v2(strip)通用**:4 mesh 全 deform 乾淨;`rows=10,cols=3`(30v)IoU 全過藝術家基準 → 設為 v2 預設。
- 關鍵副產:**IoU 由 rows 決定、cols 不影響覆蓋率**;評估器先以藝術家真值自一致性(4 mesh si=0)確認可信。
- 詳見 `knowledge/s3-four-mesh-generalization.md`。標準指令 `validate_against_real.py --gen v2` 對 4 mesh 全 overall_pass。

> ⚠️ **範圍變更(2026-08-28)**:S4(切圖+補圖)已交獨立排程(見上「⇢ S4 已交接」),
> 下列候選 **3(SkelToJson)、4(補圖閘)不再由本主排程做**;本排程專注 S1/S2骨架閘/S3/S5。

下一個 bounded chunk 候選:
0. **S1 分析器接續**:(a) ~~規格 → 實際素材~~ ✅;(b) ~~平圖流程~~ ✅ baseline(CPU 到頂);
   (c) ~~分鏡先驗庫~~ ✅ 2 類型;(d) ~~分鏡 → 動畫 keyframe~~ **✅ 完成(2026-08-27,candidate 0d,見上)**;
   **續**:(e) 關節 pivot 推斷(件中心→相鄰件關節),供 S5;(f) keyframe 補 hit/open/reveal 主秀 beat 模板。
1. ~~PSD件→S3 mesh→對照 Award 真實 mesh~~ **✅ 已完成**。3 件靜態覆蓋率全 PASS。
2. **~~S3 weighted mesh + 內部取樣密度 + BBW 權重~~ ✅ 全部完成(2026-08-27,weighted-forge READY)**。
   - ✅ **前置閘已完成(2026-08-27)**:`weighted_deform_eval.py` + `validate_weighted_deform.py`,
     可量化任一 weighted mesh 在真實 bone 動畫下的自交/翻面/塌陷,且對藝術家真值 + 負對照雙向驗證可信。
   - ✅ **權重生成完成(2026-08-27)**:`generate_weighted_mesh.py`(heat-diffusion/BBW 近似 + 內部取樣密度)
     對不透明件 body/hand 4 AC 全 PASS(si=0、平滑度≈藝術家、body nv==98)。軟件(光暈)未追平為已知限制。
   - ✅ **端到端完成(2026-08-27,weighted-forge 達 L3 → READY)**:`build_spine.py --weighted`
     產 weighted mesh(輪廓→PCA 軸骨→heat 權重→全域骨 index)+ `validate_weighted_build.py`(4 AC:
     可載入/setup 重建/輪廓 IoU/合成骨變形)。robot_parts OVERALL PASS(身體 IoU 0.937 變形 si=0、
     光暈 effect additive 容忍)。依 `build_meta.json` 的 effect/structural 語意分類。
   - **下一步(仍在本排程)**:weighted-forge 併入 `spine-asset-forge` skill(C 類回報拍板);次要:軟件非均勻拓樸追平光暈、rig pivot(S5)。
3. ~~切圖→Spine JSON 組裝(SkelToJson)~~ **⇢ 屬 S4 範圍,已交獨立排程**(且 build_spine 已可端到端產可載入 Spine)。
4. **S2 骨架閘**(補齊 S2 樞紐;純 CPU)。⚠️ **S2 補圖閘已隨 S4 交接**,本排程不做。
5. **S5 骨架半自動**:關節 pivot 推斷 —— **接觸縫子問題 ✅(2026-08-29)+ 多 rig 真值 ✅(2026-08-30,見上里程碑)**。
   **續(達 L3 → 脫離 HOLD,唯一剩餘缺口)**:(b) pivot→bone 父子樹**寫入 `build_spine`**
   (目前每件綁 root,無關節鏈;推斷器 `infer_pivots` + 兩 rig 真值閘已就緒,只差把 pivot 接進骨架生成)。
   ~~ (a) 多 rig 真值~~ ✅ 完成(robot+cat)。次要:(c) 肢體父子樹自動推斷(目前取自先驗)。人形 RTMPose/MediaPipe、非人形光流分群為後續。
6. **S1 反推分析器(影片輸入)**:需一支 benchmark 影片(repo 無影片資產,屬使用者提供)。
7. ~~spine_inspector 實機 round-trip~~:**⛔ CDN(jsDelivr)被網路政策擋(403);需使用者改政策或提供離線 spine-webgl。**

> **主排程近況**:S1(分析器+build+keyframe)、S3(mesh 生成+weighted 生成+變形評估,weighted-forge READY)、
> S2(切圖閘)皆已達里程碑;**S5 rig pivot:接觸縫子問題(2026-08-29)+ 多 rig 真值(2026-08-30,robot+cat)已完成,仍 L2 HOLD**;S4 已交獨立排程。
> 建議下一個 bounded chunk(擇一):**(1) S5 達 L3 脫離 HOLD**:把 pivot→bone 父子樹**寫入 `build_spine`**
> (推斷器+兩 rig 閘皆已就緒,只差骨架生成端接上關節鏈;這是 spine-rig-pivot 唯一剩餘缺口);
> **(2) weighted-forge 併入 spine-asset-forge skill**(C 類需使用者拍板)。
> 建議先做 (1)(可自主、直接讓 spine-rig-pivot 達 L3、通往「素材會動且關節正確」)。

## 環境前置(已驗證可用)

- 排程容器為臨時,CPU 套件需每次重裝。**已確認可裝**:numpy 2.4.6 / opencv-python-headless 4.13.0 /
  triangle / scipy 1.17.1(見 `requirements.txt`)。
- 每次排程執行前先 `pip install -r requirements.txt`。

## 未解問題 / 阻塞 (open questions / blockers)

- ❓ 排程頻率未定(使用者尚未決定)。
- ✅ `main_draw.png`(2023×1896,含 alpha)已收進 `assets/`;texture/IoU 已解鎖。atlas 切圖工具見 `tools/mesh_gen/atlas_crop.py`。
- ❓ 切圖/補圖(S4)最大槓桿是「能否要到分層 PSD」— 屬使用者層級決策。
- ℹ️ spine_inspector 實機 round-trip 需瀏覽器自動化(headless),尚未設置。

## 進度摘要 (progress log)

- 2026-08-30:**S5 rig pivot 多 rig 真值擴充(里程碑)** — 新增 main_draw 貓 rig(全 region、共用鏡射貼圖)為第二真值;
  contact-seam 2 rig 全 AC PASS(cat max 0.096 軀幹尺度);修 region-由-attachment-鍵-查-atlas 通用性 bug;
  重構通用 `load_rig`(robot 回歸不變)+ 多 rig 閘 + `plot_pivots` 圖。`pivot_end2end` L0→L1,仍 HOLD(只差接 build_spine)。
  見 `log/2026-08-30-001.md`。⚠️ **分支注意**:本 run 在 harness 指派分支 `claude/focused-dirac-y68r27` 上,
  **非** SCHEDULE.md 設定的固定分支 `claude/spine-main`(見該 log「分支狀況」)。
- 2026-08-28:**跨分支成果乾淨合流 + 分支釘定(使用者決策 B)** — 發現 200+ 條 `claude/*` 是平行且重複的研究線
  (routine 每 run 從同 default clone、重做同一 chunk、push 到隨機新分支,從不合流)。以最完整線 `3r9ey4`
  (weighted 生成+評估+skill 機制)為底,擇優併入 S1 keyframe(zjze4k 版,5 選 1)、S4 交接、分支釘定,去重評估器。
  合流後單一 tree 全綠(keyframe 4AC+負對照 PASS、check_readiness 3 區塊 READY)。定為 canonical `claude/spine-main`。
  見 `log/2026-08-28-004.md`。**使用者待辦**:把 repo default 改 `claude/spine-main`、更新主 Routine Prompt、清舊分支。
- 2026-08-28:**S4 交獨立排程 + 分支策略定案** — S4(切圖+補圖)拆給 `claude/spine-s4-inpainting` 排程;
  主排程釘 `claude/spine-main`(見 `log/2026-08-28-002/003.md`)。
- 2026-08-27:**S1 keyframe(candidate 0d)+ S3 weighted 生成器/端到端 + skill 化機制**(多平行 run,已於 08-28 合流)。
- 2026-06-24：建立自驅研究框架骨架(RULES/PLAN/STATE/knowledge/log/prompts)。
- 2026-06-24：匯入「Spine mesh system analysis」完整交接;PLAN/RULES/STATE 依實際研究內容填妥,狀態轉 `ACTIVE`。
- 2026-06-24：**S3 第一輪** — 探測並安裝 CPU 套件;完成 mesh 生成器 + 評估器 + 合成測試;6 條 AC 全過(IoU 0.99)。
- 2026-06-24:收到真實 `main_draw.json` + `.atlas`(存入 `assets/`);解析確認 4 mesh + 9 anim deform;
  下一課題定為 deform-aware 評估器(純 CPU,不需 PNG)。
- 2026-06-24:**deform 評估器課題完成** — Python 重現 Spine deform;真實 4mesh×9anim benchmark 全乾淨
  (_checker_validated);負對照可抓自交/翻面;生成 mesh 耐變形 ≈ 藝術家手做(撐過 315px)。
- 2026-06-24:**真實資產驗證(里程碑)** — 收到 main_draw.png;atlas_crop 切真實貼圖;生成 mesh 靜態 IoU 0.98 過
  但耐變形失敗 → 發現「靜態≠變形穩健」,藝術家直條拓樸更耐變形。下一步定為 S3 v2 deform-aware 生成器。
- 2026-06-24:**S3 驗證 + 自我更正** — 真實位移場轉移評估器(自一致性驗證);推翻先前『耐變形失敗』
  (合成壓力 miscalibration);更正後 v1 對 curtain_left 整合 AC 通過(IoU 0.98、真實變形乾淨)。
- 2026-06-24:**排程就緒(B)** — 建 SessionStart hook(.claude/,自動裝 CPU 套件+PYTHONPATH,已驗證)、
  硬化 prompts/run.md、寫 SCHEDULE.md turnkey 指南。剩使用者在 web 建每日 trigger。
- 2026-06-26:**S3 推廣到全部 4 mesh(里程碑)** — v1 不通用(curtain_right/shadow 真實 deform 自交);
  v2 strip 通用(4 mesh 全乾淨)。發現 IoU 由 rows 決定、cols 不影響;v2 預設 rows 8→10,4 mesh 全 overall_pass。
  評估器先以藝術家真值自一致性(4 mesh si=0)確認可信再下判定。開 PR #1(zealous→hopeful default,a 方案)。
- 2026-06-26:**S2 切圖閘完成** — `evaluate_slicing.py` 端到端重組驗證;main_draw 45/45 region MAE=0/0孤兒/0重疊;
  雙向負對照確認鑑別力(rotate 對稱 region 不可區分為已知局限)。發現 spine_inspector round-trip 被 CDN 政策擋(blocker)。
- 2026-06-26:**S4 PSD 契約 pipeline 打通(使用者拍板)** — psd-tools 可裝;`make_test_psd.py`(合成 fixture)+
  `psd_slice.py`(PSD→各部位件+manifest+自驗閘);4 層 PSD 重組 MAE=0.01/0孤兒,漏層負對照抓到。
  寫 `knowledge/s4-psd-contract.md`(給美術的交檔規範)。待真實 PSD 驗收。
- 2026-06-26:**分支策略定案** — 排程 trigger 改**直接指向開發分支 `claude/zealous-noether-y2ecwu`**,
  不再走 PR/merge(零摩擦)。更新 `prompts/run.md`(分支說明 + 移除過時快照,改以 STATE 為準)、`SCHEDULE.md`。
  PR #1 已 merge;PR #2 關閉(改用分支直讀)。
- 2026-08-19:**S1 端到端「目標圖→可載入 Spine 素材」(里程碑)** — `build_spine.py`+`validate_build.py`;
  robot/Symbol_Ww round-trip 重建 == 原圖 全 PASS。規格→素材打通。下一步定為分鏡→動畫 keyframe。
- 2026-08-19:**S1 擴充:平圖流程 + 分鏡先驗庫(使用者指定)** — (A) 平圖純 CPU 拆件 baseline + 真值召回閘
  (同材質角色 0/5、0/18 語意召回,僅不相連塊可靠 → 佐證 PSD-first);(B) 先驗庫 slot_bigwin/slot_reveal
  對 Award/main_draw 覆蓋率 1.0。修 2 評估器 bug(decomposability 反向、動畫名子字串誤判)。
- 2026-08-19:**S1 目標圖反推分析器(里程碑,使用者新增研究項目)** — 分層 PSD → 五段規格
  (運動構件/周邊特效/動作分鏡/拆圖策略/補圖項目);`tools/analyzer/` + 對 Award 真值 5 項校驗全 PASS
  (件召回 1.0)。誠實界定補圖需求為輸入契約相依(分層 PSD 0 破洞)、#3 分鏡為類型先驗提案。
- 2026-08-19:**S3 端到端對真實美術 mesh 驗收(里程碑)** — `compare_robot_mesh.py`:Award 機器人
  3 mesh 件靜態覆蓋率全 PASS(頂點更省 37~48 vs 78~98)。校正 STATE 舊假設:**mesh uvs 是 region-local**
  (非 atlas 分數,4 組合實測 vflip=False)。新增軟邊 blob `boundary-dense-v1` 模式(光暈 0.92→0.98)+
  通用 `prune_orphans`(修 filter 造孤兒)。4 curtain/shadow strip 迴歸全 PASS。誠實限制:weighted 骨骼
  變形平滑度未驗 → 下一步定為 S3 weighted+BBW。見 `knowledge/s3-robot-mesh-vs-award.md`。
- 2026-06-26:**S4 真實驗收(里程碑)** — 使用者提供 2 份生產 PSD + 機器人對應 spine(Award)。
  psd_slice 對兩檔切圖無損 PASS;機器人 5 圖層 ⇄ Award slot `機器人拆件/<圖層名>` 逐件吻合(+2px)。
  抓修閘第三次 miscalibration(composite 透明區白底 → 改 premultiplied 比對 + 套圖層 opacity)。
  收 Award.json/atlas + 2 PSD 進 assets;校準契約。
- 2026-06-26:**texture 級驗證 + atlas_crop 修正(里程碑)** — 收到 Award.png/Award2.png(雙頁,~0.70 縮小)。
  PSD 切件 ↔ atlas 切件 alpha-IoU 0.92~0.99 → 確認同素材,PSD↔spine↔atlas 閉環。
  **用 PSD 外部真值揪出 atlas_crop derotate 方向 bug(CCW→CW),被 round-trip 自洽掩蓋**;
  升級 atlas_crop 多頁 + 修方向 + 修 evaluate_slicing.repack;main_draw 4 mesh + slicing 重驗全過(rotate=false 不受影響)。
