# 知識累積 / 能力培訓 (knowledge)

研究過程中學到、確認、可重用的東西放這裡 — 專案的「長期記憶」與「能力培訓」成果。

## 組織方式

- 一個主題 / 一個發現 → 一個 `.md` 檔，檔名用簡短主題(例如 `s3-mesh-evaluator-notes.md`)。
- 每個檔案開頭寫：結論、依據/來源、信心程度、相關階段。
- 在下方索引維護清單。

## 既有交接知識(在 repo 根目錄)

> 這些是從 cowork 對話「Spine mesh system analysis」帶入的核心知識,根目錄自動載入優先:

- `CLAUDE.md` — 專案精煉 context(Spine 工具、Phase-2 API、3.8 技術雷點、能力路線圖)。
- `handoff_brief.md` — 完整冷啟動交接(API 全參考、兩次遞迴結果、SOP/計畫摘要)。
- `自主Spine工作流_SOP.md` — 自主迭代工作流(驗收契約、自我驗證迴圈、升級政策、旋鈕)。
- `Spine能力鍛鍊計畫.md` — 反推框架 + 鍛鍊五件套 + 四能力拆解 + S1–S5 路線(含 2026 工具研究與來源)。
- `main_draw_解析報告.md` — 測試資產完整解析(28 bones/40 slots/9 anims/4 unweighted mesh)。
- `spine_inspector.html` — 工具本體(瀏覽器開,`window.spineTool` API)。

## 索引(本次執行起新增的發現)

- [S3 mesh 生成器](s3-mesh-generator.md) — 純 CPU PNG→Spine mesh 原型 + 評估器,合成資料 6 條 AC 全過(IoU 0.99)。

- [deform-aware 評估器](s3-deform-evaluator.md) — Spine deform 重現 + 自交/翻面閘;真實 4mesh×9anim benchmark 全乾淨,負對照可抓壞網格。

- [真實資產驗證【含更正】](s3-real-asset-finding.md) — 先前「耐變形失敗」是合成壓力 miscalibration;**更正後 v1 真實變形下乾淨、IoU 0.98 通過**。教訓:評估器需校準+自驗。

- [推廣到全部 4 mesh](s3-four-mesh-generalization.md) — **v1 不通用**(curtain_right/shadow 真實 deform 自交);**v2 strip 通用**(4 mesh 全乾淨)。IoU 由 rows 決定、cols 不影響;rows=10 設為 v2 預設,4 mesh 全過。

- [S2 切圖評估器](s2-slicing-evaluator.md) — 端到端「切圖→重組」保真閘;main_draw 45/45 region MAE=0/0孤兒/0重疊全過,證明 atlas_crop 對 12 rotate region 全正確。雙向負對照確認鑑別力(rotate 對稱 region 不可區分為已知局限)。

- [S4 PSD-first 切圖契約](s4-psd-contract.md) — 使用者拍板走 PSD 契約。完成 psd_slice.py(PSD→各部位件+manifest)+ 自驗閘 + 合成 fixture;含給美術的交檔規範(已用真實檔校準)。

- [S4 真實驗收 + PSD→spine 對應](s4-psd-to-spine-real.md) — 2 份生產 PSD 切圖無損 PASS;機器人拆件 5 圖層 ⇄ Award spine slot `機器人拆件/<圖層名>` 逐件吻合(+2px padding)。揭示真實命名慣例、mesh/region 分配。閘第三次 miscalibration(透明區白底)→ 改 premultiplied 比對校正。

- [S3 端到端 → 對照 Award 真實美術 mesh](s3-robot-mesh-vs-award.md) — **S3 首次對真實生產美術 mesh 驗收**:機器人 3 mesh 件(光暈/左手/身體)靜態覆蓋率達美術基準且頂點更省(37~48 vs 78~98),3 件全 PASS。發現:**mesh uvs 是 region-local(非 atlas 分數)**;新增 `boundary-dense` 軟邊 blob 模式(光暈 0.92→0.98)+ 通用 `prune_orphans` 修正。誠實限制:靜態 IoU PASS ≠ weighted 骨骼變形平滑度對等(需 BBW 權重能力補齊)。

- [S1 目標圖反推分析器](s1-target-image-analyzer.md) — **落實使用者新增研究項目 + 具體化 S1**:分層 PSD → 五段規格(運動構件/周邊特效/動作分鏡/拆圖策略/補圖項目)。`tools/analyzer/`;對 `robot_parts.psd ⇄ Award` 真值 **5 項校驗全 PASS**(件召回 1.0、特效 5/5、幾何無 mismatch、分鏡 beats+4 檔位全中、露出 4/4)。誠實界定:**補圖需求是輸入契約相依**(分層 PSD 0 封閉破洞 → PSD-first 繞開補圖);#3 分鏡為類型先驗提案。範例:`s1-example-robot-spec.md`、`specs/robot_parts.spec.json`。

- [S1 端到端 → 可載入 Spine 素材(SkelToJson)](s1-build-spine-end-to-end.md) — **規格→實際素材端到端打通**:`build_spine.py` 串 analyze_target+psd_slice+generate_mesh_v2 → Spine 3.8 json+atlas+png;`validate_build.py` round-trip(重建 setup pose==原圖)對 robot(5件)/Symbol_Ww(18件)**全 PASS**(MAE 0.03/0.24、0 孤兒、0 未解析)。誠實界定:只驗靜態幾何/貼圖編碼,動畫 keyframe/mesh 變形/關節 pivot 屬後續。

- [S3 weighted-mesh 骨綁變形評估器](s3-weighted-deform-evaluator.md) — **補上「靜態 IoU PASS ≠ 骨綁變形平滑度對等」的唯一未驗維度(真值端)**:`weighted_deform.py` 忠實重現 Spine 3.8 bone FK(全繼承 + compact bezier)+ LBS,把 Award 機器人 3 件(weighted、無 deform timeline)在唯一驅動動畫 `Award_Legend_Loop` 下逐幀變形量化。3 件 × AC0–AC4 全 PASS:**AC0 reproducer 自信任**(Σw=1、動畫 t=0 逐頂點重合 setup 0.0000px)、真實變形乾淨(0 翻面/自交)、非平凡(位移 2.4~10.8% of diag)、負對照(30×)抓得到。下一步:自產 mesh 配 BBW/骨距權重套同閘,回答「內部取樣密度不足是否犧牲變形平滑度」。

- [S1 平圖流程 + 分鏡先驗庫](s1-flat-pipeline-and-priors.md) — **(A) 平圖(未分層)自動拆件 baseline**(純 CPU):真值召回閘(壓平 PSD 對比已知圖層)顯示同材質/重疊角色 **0/5、0/18 語意召回**,只有「不相連塊」可靠(正對照 3/3)→ 量化佐證 PSD-first。**(B) 分鏡先驗庫**:`slot_bigwin`(Award)、`slot_reveal`(main_draw)覆蓋率皆 **1.0**;+ 2 個未驗證類型明標。修 2 bug:decomposability 反向誤判(重校準為 fg_components 主導)、動畫名分類子字串誤判(`end∈legend`,改整 token+後綴優先)。

> 每次新增 knowledge 檔案時,在此補一行：`- [標題](檔名.md) — 一句話摘要`

## S4 區塊(獨立排程 `claude/spine-s4-inpainting`,見 `handoff_S4.md`/`STATE_S4.md`)

> 此區塊只由 S4 排程 append,不改動上方主排程索引行。

- [S4 補圖閘 v1 + CPU baseline 邊界](s4-inpaint-evaluator.md) — 合成挖洞法(`interior`/`edge` 兩種洞)+
  4 項指標(premult_mae/alpha_mae/seam_grad_diff/ssim)+ 正負對照校準;對真實機器人拆件件量化出
  **CPU baseline(nearest-fill/cv2.inpaint)在平滑漸層區全 PASS、在機械細節紋理區任何洞尺寸皆 fail**
  的誠實邊界,呼應 PSD-first 契約策略。

- [S4 圖片預覽器](s4-preview-tool.md) — `tools/mesh_gen/psd_preview.html`(單檔瀏覽器工具,拖資料夾
  即用):切圖分頁即時疊圖 + 對參照 composite 的差異熱圖;補圖分頁 8 格(真值/破洞/正負對照/3 baseline)
  卡片式並排比對 + 點圖開大圖看差異熱圖。`psd_slice.py`/`inpaint_eval.py` 隨附新增預覽用檔案輸出
  (composite.png / holed+original PNG / manifest.json),向後相容、下游工具無回歸。用 Playwright+
  headless Chromium 驗證互動正確(重組 diff MAE 0.02、關圖層/差異熱圖精準定位)。

- [S4 補圖問題定義修正:三種情境](s4-inpaint-taxonomy.md) — 使用者釐清補圖不是單一難度分級問題,
  分 **1a 拆件破綻・需表演**(要真的畫對)、**1b 拆件破綻・防穿幫**(標準寬鬆很多)、**2 動畫規劃驅動
  視角外推**(原圖不存在的內容,補圖演算法無效,屬 S1 需求前移範疇)。指出既有補圖閘結論是用 1a 嚴格
  標準測的,1b 情境需另一組寬鬆閘重新檢視。

- [S4 切圖/補圖都在 PSD 內編輯,統一座標系](s4-psd-inplace-edit.md) — 使用者要求:補圖不該對
  匯出的裁切 PNG(局部座標)編輯,應直接在 PSD 內編輯,讀寫都用同一組全域 `layer.left/top`,
  結構上排除 offset 手動換算的錯誤空間。新增 `psd_inplace_patch.py`(找圖層→補→用同座標寫回
  →存檔,`--eval` 自驗)。過程中修正兩個真實 psd-tools 陷阱:(1) 中文圖層名寫入 crash,改用
  `luni` tagged block 比照真實 Photoshop 慣例;(2) **重存後的 PSD 預設 `composite()` 會吃到
  壞掉的合併預覽(無 alpha)**,`psd_slice.py` 兩處呼叫已加 `force=True` 修正,原生 PSD 回歸
  測試無影響。端到端驗證:身體/左手兩層 patch 後 `overall_pass: true`。

- [S4 補圖 1b 防穿幫寬鬆閘](s4-inpaint-1b-lenient-gate.md) — 實作自我參照(不比對真值內容)的
  1b 判定:`alpha_gap`/`seam_ratio`/`tone_gap` 三指標,正負對照校準通過。**核心結果驗證假設**:
  先前標記「CPU 補不動」的機械紋理案例(身體/左手),在 1b 標準下三個 CPU baseline 全部 PASS——
  「補不動」是 1a 嚴格標準的結論,1b(防穿幫)情境下同一批廉價 baseline 其實夠用。範圍收斂:
  1b 只在 `interior` 模式成立(edge 模式輪廓天然有 tone/alpha 梯度,套自我參照假設會誤判)。
  `psd_preview.html` 補圖卡片現在顯示雙判定燈(1a/1b)。

- [S4 1b `tone_gap` 在新材質上的界限](s4-inpaint-tone-gap-limits.md) — 修正 `punch_hole`
  interior 模式的 margin 退化 bug(材質太薄時原本靜默偽造不合規範的洞,現在改為縮小洞或
  明確報錯);嘗試兩種 `tone_gap` 正規化(位置比對取樣基準、局部粗糙度基準)想讓門檻可攜到
  新材質(`框`/`臉部陰影`),**兩者皆失敗**——量化證明 `臉部陰影` 的 gt 與 `左手` 的 random
  在任一正規化下的分布本身重疊,無法用單一全域門檻同時滿足兩者。結論:`tone_gap` 僅在
  機器人拆件這個材質家族內可信,跨材質家族需重新校準,不是調門檻能解決。

- [S4 補圖「評分→採用→落地」自動鏈路](s4-inpaint-auto-select-pipeline.md) — 打通
  `inpaint_eval.py`(評分)→`psd_inplace_patch.py`(落地寫回)。真實情境無真值,用 1b 分數
  盲選候選 baseline(`score_candidates`/`select_best`);修正一個新踩到的坑——1b 只在
  `interior` 模式校準過,新增 `applicable` 旗標(呼叫端明確傳 `mode`)避免 `edge` 洞被誤標
  高信心的 `pass_1b`。自我驗證:合成挖洞模擬盲選情境,寫回後才揭曉 1a 分數驗證選擇邏輯誠實;
  edge 模式正確不再宣稱 pass_1b,舊 `--method` 路徑與 `psd_slice`/`inpaint_eval` 回歸無影響。

- [S4 `fill_cv2_inpaint` edge 模式 alpha 修正](s4-inpaint-evaluator.md#fill_cv2_inpaint-edge-模式-alpha-修正2026-08-28見logs4-2026-08-28-008md) —
  修正「洞內強制拉滿不透明」的舊缺陷。實測兩個直覺解法(alpha 整顆跑 cv2.inpaint / alpha 單點
  最近鄰外推)反而更差;改用「距離場×局部量測漸縮寬度」(`estimate_alpha_taper`)全面改善,
  跨 7 個真實件(3 舊+4 新)edge 模式 alpha_mae 一致下降、6 處 1a 判定翻盤方向皆正確
  (False→True,無反向)。刻意不動 `fill_nearest`——同一顆函式套上去會讓環形鏤空件(`框`)
  的 ssim 判定翻盤(PASS→FAIL),故只用在 RGB 本就獨立通道的 `fill_cv2_inpaint`。順帶發現
  1b 的 `tone_gap` 校準在新材質(`框`/`臉部陰影`)上不成立(與本次改動無關,列為新候選)。

- [S4 遮擋真值法(候選 1)](s4-inpaint-real-occlusion.md) — 新增 `real_occlusion_eval.py`,用
  機器人拆件 5 層兩兩疊合的真實遮擋輪廓當洞(比合成挖洞的隨機圓更貼近實戰);過程中揪出並修正
  1b `seam_ratio` 的全域基準 miscalibration(材質局部漸層不均勻時全域平均基準會失真,`光暈←右手`
  真實案例讓正對照本身誤判 fail;改成洞周圍固定寬度的局部環狀帶當基準,6 個既有材質×模式回歸
  零反向)。**核心結果**:機械紋理(身體←左手)判定與合成挖洞閘完全一致(1a fail/1b pass);
  但光滑漸層材質(光暈)在大面積/不規則真實遮擋形狀下,1a 的 `seam_grad_diff` 會超標(合成
  圓形小洞從未量到),雖然 1b 仍全數 pass——修正並確認候選 0 的「光暈 CPU 補得動」結論隱含
  「小面積圓形洞」前提,不是無條件成立。

- [S4 遮擋真值法擴大樣本(候選 9)](s4-inpaint-real-occlusion.md#候選-9session-011延伸擴大配對樣本至-8-組) —
  `real_occlusion_eval.py` PAIRS 從 4 組擴到 8 組(新增小面積/懸殊比例配對,排除「X←光暈」
  全覆蓋退化案例),`calibration.pass` 維持 `True`。機械紋理結論可攜到 `右手`(新材質)、
  且對本檔測過最小絕對洞尺寸(829px)依然成立。**核心發現**:小尺寸圖層(`頭`,內容僅
  6405px)的真實遮擋洞天生更容易同時碰到自己的內容邊界,兩個測試配對都被 `classify_mode()`
  判成 `edge`——1b 目前只在 `interior` 校準,對這類小尺寸素材完全沒有可用的驗收線(只能退回
  1a 嚴格標準,而 1a 對機械紋理材質全 fail)。這是真實樣本量出來的評估器覆蓋率缺口,不是
  理論假設,候選 2(1b edge 模式支援)優先度應上修。

- [S4 1b edge 模式支援(候選 2)](s4-inpaint-1b-edge-gate.md) — `score_1b()` 新增
  `mode="edge"`:第一版「比對真實輪廓其他段落的天然變化」構想量化後證實鑑別力不足
  (premultiplied 在背景側恆 0,亂補與正確填補的落差量級相近),改採「排除貼真實輪廓的
  邊界段落,只評內容內部轉接」,直接複用 interior 既有的 `local_ring` baseline。機器人
  拆件家族(光暈/身體/左手)edge 模式 1b 校準通過,且候選 9 揭露的關鍵缺口案例
  `頭←右手`(小尺寸圖層 edge 洞)現在有真正判定,3 個 CPU baseline 全 pass。過程中踩到
  一個真實 bug:`content` 在校準流程與真實落地流程語意不同(是否含洞區域),導致
  `patch_layer_auto`/`demo_auto_patch` 端到端測試 `applicable` 恆 `False`——改用
  `content|mask` 統一語意後修正。interior 模式與既有 Symbol_Ww `框`/`臉部陰影` 的
  已知 tone_gap 限制(候選 8)完全無回歸。

- [S4 光暈材質 1a 邊界再校準(候選 10)](s4-inpaint-1a-shape-boundary.md) — `punch_hole`
  新增 `shape="ellipse"`(獨立控制面積/長寬比/朝向)+ `center`(固定洞心做控制變因實驗)。
  用控制實驗分別檢驗「形狀狹長度」與「位置」兩個候選解釋,**都不足以重現**候選 1 觀察到
  的非單調 pass/fail(固定位置掃 aspect 1~3、固定形狀沿真實方向掃位置,`seam_grad_diff`
  在可行範圍內都遠低於門檻)。誠實結論:光暈這類材質的 1a 邊界無法化約成單一合成洞參數,
  需要真實遮擋洞的大面積+真實形狀+位置一起看(呼應候選 1/8,1b 才是實戰驗收線)。
  **意外發現**並除錯到根因:`estimate_alpha_taper` 在特定橢圓 interior 洞下出現真實 bug
  (RGB 補對,alpha 因小樣本(n=7)污染而催毀性低估,60 vs 真值 255),既有測試案例
  皆未觸發(回歸零反向),列為新候選未修。

- [S4 `estimate_alpha_taper` 穩健性量化(候選 13)](s4-inpaint-alpha-taper-robustness.md) —
  跨 12 個材質 × circle/ellipse 多種洞形狀共 1233 次取樣量化候選 10 意外撞見的小樣本 bug
  觸發頻率:確認失敗集中在 `ring_count∈[5,20)`(剛好卡在舊門檻 5 之上、樣本仍不足以讓中位數
  穩定的縫隙),`mae` 平均 4~12、最差 139.9。用同一批資料掃過候選門檻 10~28,20~22 是最後
  零負面案例的安全帶(25 開始出現因誤傷有效局部樣本而變差的反向案例)——**`min_ring` 從
  5 提高到 20**。3 組既有回歸案例(機器人 3 材質 interior/edge、8 組真實遮擋、Symbol_Ww
  2 材質、`psd_inplace_patch.py --auto`)完整 JSON diff 為空,因為它們的 `ring_count` 本來
  就落在不受此次調整影響的桶。**誠實範圍界定**:同一批資料也發現另一個完全不同根因、大樣本
  數(50~700+)下依然崩壞的獨立失敗模式(`右手` edge 小洞 alpha_mae 115.6、`光暈` 特定橢圓
  洞 alpha_mae ~100),`min_ring` 對這批無效,列為候選 14(未修)。
