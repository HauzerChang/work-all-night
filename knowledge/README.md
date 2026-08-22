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

- [S1 平圖流程 + 分鏡先驗庫](s1-flat-pipeline-and-priors.md) — **(A) 平圖(未分層)自動拆件 baseline**(純 CPU):真值召回閘(壓平 PSD 對比已知圖層)顯示同材質/重疊角色 **0/5、0/18 語意召回**,只有「不相連塊」可靠(正對照 3/3)→ 量化佐證 PSD-first。**(B) 分鏡先驗庫**:`slot_bigwin`(Award)、`slot_reveal`(main_draw)覆蓋率皆 **1.0**;+ 2 個未驗證類型明標。修 2 bug:decomposability 反向誤判(重校準為 fg_components 主導)、動畫名分類子字串誤判(`end∈legend`,改整 token+後綴優先)。

- [S3 weighted mesh 骨骼變形品質閘](s3-weighted-deform-gate.md) — **補上唯一未驗維度**:`weighted_deform.py` 重現 Spine weighted skinning,對 Award 3 件在真實 `Legend_In/Loop` 骨骼 pose 下驗變形,3 AC 全 PASS(AC1 setup 自一致錨定數學、AC2 硬不變量 0 翻面/0 退化、AC3 負對照鑑別)。2 大發現:①**可見性 gating 必要**(光暈 alpha=0 期間骨骼劇烈位移不算數,71→4 自交);②**軟邊件自交用藝術家基準非硬 0**(光暈單一 keyframe 4 自交是出貨資產可容忍值)。下一步:BBW 生成 weighted mesh 對照此基準。

> 每次新增 knowledge 檔案時,在此補一行：`- [標題](檔名.md) — 一句話摘要`
