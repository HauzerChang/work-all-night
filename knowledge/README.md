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

- [S4 候選 14 調查:兩個獨立根因,4 種修法皆非零回歸](s4-inpaint-alpha-taper-candidate14.md) —
  拆解候選 14 成兩個獨立問題:(1) 硬邊材質(`右手`)ring 內被材質內部 alpha 紋理雜訊污染
  (271 樣本中 180 個是離背景 8~15px 的雜訊、只有 55 個是離背景 1~1.4px 的真邊界像素),
  中位數被雜訊支配誤判成軟邊;(2) 光滑材質(`光暈`)ring 本身測到的斜率一致偏低(非雙峰),
  是「單一常數 ell 線性外推全洞」模型結構對非線性材質失效,非統計量問題。用全部 1233 筆
  量化資料測試 4 種修法(距背景固定半徑過濾/只換統計量 percentile/只做方向濾波/兩者組合):
  最佳方案(方向濾波+p90)13 fixed、9 newly broken(`n_mae_gt_20` 39→35,mean_mae
  2.668→1.978),**淨提升但非零回歸**,不符合本專案落地門檻,故本次未修改
  `inpaint_eval.py` production 代碼。留 A 類岔路候選(trade-off 是否可接受)給使用者裁決。

- [S4 候選 4:LaMa 深度 inpaint 可行性探測](s4-lama-feasibility.md) — 網路政策部分允許
  (PyPI `torch`/`simple-lama-inpainting`、GitHub release 的 `big-lama.pt` 權重皆可下載;
  `download.pytorch.org`/`huggingface.co` 被擋)但唯一可行安裝路徑會多付 ~2GB CUDA 依賴代價
  (預設 PyPI 的 `torch` wheel 非 CPU-only)。實測通用預訓練 LaMa(未微調)對已知 1a fail 的
  機械紋理材質(`身體`/`左手`)量化跑分:6/8 指標贏過全部 3 個 CPU baseline(如 `身體` ssim
  0.441→0.574),但**沒有一個案例跨過 1a 門檻**(`ssim>0.75`)。誠實結論:通用權重是穩定的
  量化改善、非質變,要解 1a 大機率需針對本專案素材微調(超出可行性探測範圍);而 1b(防穿幫,
  本專案實戰驗收線)CPU baseline 已經 pass,LaMa 換不到新增益,當前優先序下不建議投入,
  也不寫進 `requirements.txt`(避免每個 session 重裝 ~2GB)。

- [S4 候選 6:擴大樣本至 `Symbol_Ww.psd` icon 類其他 11 層](s4-inpaint-tone-gap-limits.md#候選-62026-08-31擴大樣本至-symbol_wwpsd-icon-類其他-11-層交叉驗證邊界) —
  補測之前未測過的 11 層(手部/耳機/鬢角/音符 icon 圖形)。**1a 邊界延續**:僅真正平坦的
  `左手3` 通過,其餘細節材質(含 icon 類的耳機弧線、手指關節、鬢角毛流)全部落入既有的
  「CPU 補不動」判定,結論可攜到 icon 類材質,不限機械紋理。**1b 邊界多數延續**(8 層
  CPU baseline 全 pass,再次驗證機器人拆件家族的核心結論可攜到 icon 材質),但新揪出 2 筆
  `tone_gap` 正對照(gt)fail(`音符1/2`、`右手2` edge 壓線)——量化證實驅動 miscalibration
  的是材質色調變化量級而非面積大小(`鬢角1`/`鬢角2` 面積幾乎相同但一 fail 一 pass),屬候選 8
  已知限制的再驗證,**維持不調整全域門檻的原決策**。另用更小尺度樣本(120~637px)再次確認
  小尺寸材質 edge 模式 1b 覆蓋率缺口(候選 9/2 已知問題)依然成立。本次僅擴大測試樣本,
  未改動任何 production 代碼。

- [S4 候選 7:vision 代理反向校準 1b 閾值](s4-inpaint-1b-lenient-gate.md#候選-72026-08-31用-claude-vision-當人工標註代理嘗試反向校準閾值調查完成) —
  新增 `tools/mesh_gen/s4_vision_proxy_compare.py`(裁切+疊棋盤格+放大拼圖),用 Claude 自身
  vision 讀圖代理缺失的人工「有沒有穿幫」標註,跑 6 個涵蓋四種材質類型的案例。負對照/平滑
  漸層/全平坦案例 vision 與既有數字判定 100% 一致;`鬢角1` 的 gt 用 vision 直接確認無破綻,
  補上候選 8 tone_gap false-positive 結論的第一手視覺證據。**核心發現**:`身體`/`左手`
  (既有 1b pass)的 CPU baseline 補丁近距離看會丟失機械紋理的高頻細節,但這不是現有三指標
  (alpha_gap/seam_ratio/tone_gap)量錯門檻,是三者共同缺少「高頻細節保留度」這個維度,調
  `THRESH_1B` 解不了。**誠實限制**:本代理是靜態放大單層裁切,不是真實動畫尺度/速度下的
  觀察條件,弱於真人標註。結論:不變更 `THRESH_1B`,候選 7 調查收斂;留候選 16(加第 4 個
  1b 指標,或把補圖貼回真實 Award spine 場景跑動畫截圖比對)給後續獨立工作塊。

- [S4 外部知識:Photoshop `GPT Fill` UXP 插件 v1.18](s4-gptfill-plugin-knowledge.md) —
  吸收使用者自製生產插件(`gpt-image-2` via `api.openai.com`,完整讀過 `main.js` 1986 行)。
  **取得 mask 慣例外部真值**:重建洞 dilate 8px 融合邊界、移除物件 footprint dilate 24px
  給陰影重建、任務模式自動判定門檻「洞占比 ≥30%」、mask 編碼 `alpha=255-selection`。
  **揭露我們一個沒意識到的方法論限制**:插件給重建的上下文下限 512px,而我們的補圖閘只吃
  單層裁切、零上下文——「1a 機械紋理全 fail」是在「只看單層」條件下量的(→候選 19,純 CPU
  可立即驗)。**記錄生成結果不會像素對位**(漂移+整體縮放)與插件的五層對位管線(平移/縮放/
  8 錨點 IDW 位移場/次像素/「改善不顯著就不套用」門檻)——我們 `psd_inplace_patch.py` 的
  就地假設一接生成路徑就破。**獨立佐證候選 7 的發現**:插件 prompt 的 SHADOW REASONING 明確
  禁止 flat 填補,與 vision 觀察到的「奶油糊」同構 → 候選 16 具體化為「邊界證據延續性」。
  另:插件獨立收斂到 premultiplied 插值、便宜幾何代理指標盲選候選、自我輸出污染自我評估的
  防呆,三者皆與本 repo 既有做法同型。誠實界定:尚未對本 repo 素材跑分(候選 17)。

- [S4 候選 19:上下文假設重測(CPU baseline 加大輸入上下文)](s4-inpaint-context-window.md) —
  新增 `tools/mesh_gen/s4_context_window.py`。同一顆隨機挖洞分別套進「孤立層裁切」與
  「以 PSD 真實場景當背景、比照插件 512px 下限的大畫布視窗」兩種輸入,重跑既有三個 CPU
  baseline(`nearest`/`cv2_telea`/`cv2_ns`)配對比較。過程踩到兩層校準坑(先用
  `psd.composite()` 當上下文被後畫圖層污染目標層本身內容;改用 `alpha_composite` 貼回
  又在半透明邊緣像素撞見「場景合成 alpha」與「圖層自身 alpha」語意不同的假警報)——最終
  用硬覆蓋(不經 alpha 混合)讓 6 案例校準全部逐位元通過。**核心結果**:`身體`/`左手`
  (已知 1a 全 fail 材質)在 **interior 模式下,windowed 版與孤立版三個 baseline 輸出逐位元
  相同(delta 恰好 0.0000)**——機制解釋:`nearest`(最近有效值)與 `cv2.inpaint`
  (極小半徑 FMM)都是局部演算法,視野本來就被演算法自身限制死,不是被裁圖裁掉的。edge
  模式效果小且方向不一致(`nearest` 因誤用鄰近圖層像素反而變差),量級遠不足以讓任何案例
  跨過 1a 門檻。**結論:「1a 機械紋理材質全 fail」不是「只看單層零上下文」的人工產物**,
  收窄候選 19 原假設——512px 上下文對生成式模型(候選 17)才有意義,對現有 CPU baseline
  無效。未改動任何 production 代碼(`inpaint_eval.py` 本身不變,新增獨立驗證腳本)。
- [S4 候選 18:「邊界證據延續性」第 4 指標校準,結論設計方向有結構性偏差不採用](s4-inpaint-1b-lenient-gate.md#候選-18邊界證據延續性第-4-指標實作與校準2026-08-31chunk-21結論設計方向本身有結構性偏差不採用) —
  新增 `tools/mesh_gen/s4_boundary_evidence.py`,把 chunk 19 讀到的 GPT Fill 插件 SHADOW
  REASONING prompt 具體化成 `grad_continuity_gap`(洞內像素離「洞外邊界局部梯度線性外推
  預測值」的 MAE)。校準發現機械紋理材質(身體/左手)的**正對照(gt,真實內容)分數反而比
  平坦複製(`nearest`)差**,`probe_depth` 從 6px 降到 2px(緊貼邊界)偏差依然成立——根因
  是這個指標的預測基準本身是「平滑外推」,越平滑的補丁天生越貼近自己的平滑預測值,偏誤方向
  跟設計意圖(抓「過度平滑的奶油糊」)剛好相反,換算比值也救不回來。不採用,未改動
  `inpaint_eval.py`/`THRESH_1B`;建議候選 16 改走「局部高頻能量/方差比」方向而非梯度外推。
- [S4 候選 20:「局部高頻能量/方差比」第 4 指標校準,結論兩個獨立失效模式不採用](s4-inpaint-1b-lenient-gate.md#候選-20局部高頻能量方差比第-4-指標實作與校準2026-09-01chunk-22結論兩個獨立失效模式不採用) —
  新增 `tools/mesh_gen/s4_energy_ratio.py`,把候選 16 路徑 (a) 做成 `energy_ratio`(洞內 core
  局部方差 / 既有 `score_1b` `local_ring` 基準的局部方差,只測 interior)。撞到兩個獨立根因:
  (1) 光暈正對照本身失真(gt `energy_ratio`=0.0036 比全部 CPU baseline 都低,呼應候選 10 的
  材質局部統計不均勻性,同候選 8/18 那類根因);(2) 左手負對照鑑別力崩潰——跨 4 個 seed 重跑
  確認,`random` 與 `gt` 同量級分不開,且排序方向與既有 vision/1a ssim 證據矛盾(已知拼貼
  假邊的 `nearest` 反而比公認較好的 `cv2_telea`/`cv2_ns` 更貼近 gt)。根因是局部方差只量
  「跳動量級」不量「樣式對不對」,逼近 1a `ssim` 職責重疊。不採用,未動 `score_1b`/
  `THRESH_1B`;候選 16 路徑 (a) 兩次嘗試(候選 18/20)皆已排除,建議後續優先做路徑 (b)
  (貼回真實 Award spine 場景跑動畫截圖比對)。
- [S4 候選16路徑(b):補圖貼回真實 Award spine 場景,headless 動畫截圖比對](s4-inpaint-spine-render-compare.md) —
  新增 `tools/mesh_gen/atlas_patch.py`(`atlas_crop.py` 逆操作,round-trip 自我驗證 5 region
  全 `max_diff=0`)、`tools/mesh_gen/s4_spine_render_harness.html`(新的 headless 渲染
  harness,多頁 atlas 正確支援——`spine_inspector.html` 的 textureLoader 固定回傳同一張貼圖,
  對 Award 雙頁 atlas 會讓其中一頁全部貼錯圖,故不可共用,只新增不改動該檔)、`tools/mesh_gen/
  s4_award_screenshot_compare.py`(orchestrator)。跑通 `機器人拆件/左手`:atlas 解析度挖洞→
  1b 盲選補丁(`nearest` 勝出)→貼回 `Award.png` 副本→`Award_Legend_In`/`Loop` 11 個時間點
  截圖比對。**踩坑**:相機不能只用 setup pose 框(爆衝動畫會把材質甩出偏移的視野),改成先
  跑全部取樣時間點的姿態包圍盒聯集再固定相機。**核心結果**:(1) 全場景像素比對差異只有
  205px 且精確落在目標 slot 範圍內,其他 40+ slots 零差異,證明雙頁貼圖路由正確;(2) 該材質
  在此相機框架下只佔全場景 ~0.5~0.6% 面積;(3) 兩個獨立時間點 10x 放大人眼複查:候選7已知
  的「高頻細節丟失/奶油糊」瑕疵仍在,但不構成一眼可見的接縫/破洞/色差。**誠實限制**:單一
  材質/單一 seed/單一盲選方法;相機框架未對照真實遊戲實機顯示縮放比例。未改動
  `spine_inspector.html`/`inpaint_eval.py` 等既有 production 代碼。
- [S4 候選16路徑(b)第二案例:機器人拆件/身體,驗證 rotate=true 路徑(chunk 24)](s4-inpaint-spine-render-compare.md#第二個案例機器人拆件身體chunk-242026-09-01驗證rotatetrue路徑) —
  沿用 chunk 23 通用工具重跑,不改動任何 production 代碼,只換 `--slot`/`--att-name` 參數。
  選 `身體` 是因為其 atlas region `rotate=true`(`左手` 是 `rotate=false`),之前只驗過非
  旋轉路徑。**核心結果**:(1) 全 11 個時間點截圖逐像素比對,差異像素 100% 落在目標 slot
  螢幕框內、零外洩——首次在真實 spine-webgl 渲染管線下驗證 `atlas_patch.py` 的旋轉還原
  正確,不只是 `--selftest` 的靜態自測;(2)「高頻細節丟失但不構成一眼可見穿幫」結論可攜到
  第二個材質,即使其實際螢幕佔比(~1.0~1.1%)是 `左手`(~0.5~0.6%)的近兩倍。
- [S4 候選16路徑(b)第三案例:機器人拆件/光暈,第三種材質類型(chunk 25)](s4-inpaint-spine-render-compare.md#第三個案例機器人拆件光暈chunk-252026-09-01第三種材質類型平滑漸層) —
  沿用同一套工具重跑,補齊三種材質類型覆蓋(機械紋理×2 + 平滑漸層×1)。**核心結果**:(1)
  零外洩驗證通過;(2) 差異量級(`mae_0_255` 0.01~0.04)比前兩個機械紋理案例(0.9~1.05)
  低約兩個數量級;(3) 實際螢幕佔比(3.4~7.3%)是三案例中最大的,但 8x 放大人眼複查仍完全
  看不出差異——排除「佔比小才不明顯」的替代解釋,支持「材質紋理複雜度才是決定因素」的既有
  結論(候選0/8/10)。候選16路徑(b)三種材質類型覆蓋完成,達成初始目標。

- [S4 里程碑審查:切圖+補圖是否已達成自然收斂點(chunk 26,結論:核心研究問題已閉環)](s4-convergence-review.md) —
  依 chunk 25「下一步」指定執行的 C 類里程碑審查,綜合盤點既有 25 個 chunk,未新增量化實驗
  /未改動 production 代碼。逐項清點原始使命(切圖可靠性/補圖評估器/CPU補圖能力邊界/1a-1b邊界
  實戰意義/LaMa投資值不值得/分類法有效性/類別2歸屬)後**確認每一項都已有交叉驗證的答案**,
  剩餘候選15(alpha_taper trade-off)、候選17(headless生成式補圖需API key授權)性質是「答案
  已有、待裁決是否套用」的執行層決策,不是研究缺口。**建議**:S4 核心目標已達成,維持
  `ACTIVE` 但降低排程優先度,資源轉向 S1/S2/S3/S5(符合 `PLAN.md` 既有槓桿排序);不建議標
  `DONE`(候選15/17 仍是合理後續工作,且未來接上 S1/S5 pipeline 可能冒出新材質類型)。三項
  具體決策點(候選15/17/排程方向)彙整交還使用者裁決。

- [S4 候選17:gpt-image-2 headless 補圖第一次真實驗證(chunk 35)](s4-inpaint-candidate17-gptimage2.md) —
  使用者授權 API key + 放行網路政策後,新增獨立(不依賴 Photoshop)呼叫模組
  `s4_openai_client.py` + 用量儀表板 `s4_usage_dashboard.html`,對已知 1a 全 fail 的機械
  紋理材質(左手)跑第一次真實測試。**關鍵發現**:1a 逐像素 ssim 依然 fail(0.274,同量級於
  LaMa 的 0.260),但**視覺上完全看不出破綻**(材質風格/反光/明暗全部一致),1b 三指標是
  本專案至今最佳(tone_gap 5.04)——矛盾的根源是 1a 用逐像素比對 gt 的方法論,對「生成風格
  一致但形狀不同的合理替代方案」這種生成式輸出的本質不公平,可能從一開始就量錯了維度。
  n=1,未做正負對照校準,建議下一步先幫生成式方法設計專屬評分方式(1b 或 vision-proxy),
  再擴大樣本。

- [S4 AI 補圖 Viewer:純瀏覽器端 Photoshop 插件替代品(chunk 36)](s4-ai-viewer-tool.md) —
  使用者要求不被 Photoshop 綁定的「視覺化即時切圖補圖工具」。關鍵前提驗證:
  `api.openai.com` 對 CORS preflight 回傳 `access-control-allow-origin: *`,證實瀏覽器
  可以直接跨來源呼叫 OpenAI API,不需要中介後端。新增 `tools/mesh_gen/s4_ai_viewer.html`
  (載入圖層→畫遮罩→prompt→直接呼叫 API→結果比對→套用/下載,key 只存本機
  localStorage),用 Playwright mock API 呼叫驗證前端邏輯(未打真實付費 API)。同時建立
  `.claude/skills/spine-asset-request/SKILL.md`(初步版):把「使用者描述動畫需求→判斷
  缺口類型→驅動切圖/補圖工具→驗證→記錄」的既有工具串成一套可重複流程,含缺口分類表、
  CPU優先/生成式後補的決策順序、以及誠實列出目前無法自動處理的情況(視角外推/平圖拆件/
  生成結果像素漂移)。