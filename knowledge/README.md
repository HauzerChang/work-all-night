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

- [S3 weighted mesh 變形評估器](s3-weighted-deform-evaluator.md) — **補上 deform_eval 只驗 unweighted 的缺口**:Python 重現 Spine 3.8 bone world transform + weighted skinning + timeline 取樣,對 Award 3 個機器人 weighted mesh 逐真實動畫量化自交/翻面/塌陷。`validate_weighted_deform.py` 三道校驗全 PASS(setup 自一致、藝術家不透明件 si=0、負對照放大分離 amp4 藝術家 si=0/打亂 si=54)。修 1 bug(scale timeline 缺 channel 預設應為 1 非 0)+ 相對面積 degeneracy(避免 big-win scale-from-0 誤判)。發現軟性加成件(光暈)容許重疊 → pass/fail 需依 attachment 語意分類。是 BBW 權重生成(候選 2)的前置閘。

- [S3 weighted mesh 生成器(內部取樣 + heat-diffusion 權重)](s3-weighted-mesh-generator.md) — **候選 2 主體完成**:輪廓→triangle 三角化(max-area 控內部密度)→ heat-diffusion 骨綁權重(BBW 純 CPU 近似,`(L+H)W=HP` 天然 partition of unity)→ Spine weighted 格式。對 Award 不透明件(身體/左手)過同一道變形閘,4 AC 全 PASS(body nv 調到 == 藝術家 98、左手變形比藝術家更平滑)。誠實限制:軟性件(光暈極端 reveal)si 未追平藝術家手工非均勻拓樸(additive 無害,不列硬性 fail);尚未端到端接 build_spine。使 spine-weighted-forge 的生成能力 L0→L2。

- [S1 分鏡 → 動畫 keyframe](s1-storyboard-to-animation.md) — **candidate 0d:讓產出素材「會動」**:把 analyze_target `#3 動作分鏡`(role/action 文字)確定性轉成可載入的 Spine 3.8 `animations`(bone TRS + slot alpha)。純 Python Spine 3.8 timeline 取樣器 `spine_anim.py`(緊湊 bezier/stepped/linear,無瀏覽器)+ `gen_animations.py`(role×category→運動基元,loop 正弦取樣端點強制相等→無縫)+ `build_spine.py --animate` 端到端。對 robot(slot_bigwin)/Symbol_Ww(slot_reveal)自我驗收 **4 AC 全 PASS + 負對照全偵測**(intro/loop/outro 介面全落在 setup identity → 任意串接無跳變);setup-pose round-trip 不受擾動。誠實界定:role→運動基元為先驗手感提案(非學自真值),緩動美感留使用者;mesh deform timeline 未生成。

- [S5 rig pivot 推斷器(關節=父子件接觸縫)](s5-rig-pivot-inference.md) — **S5 首個能力**(路線圖「唯一卡死環節」的可客觀化子問題):給拆件幾何 + 父子樹,推斷每根子骨關節 pivot = 子件與父件的接觸縫質心(確定性、純 CPU 無 ML)。對 Award 機器人 rig 3 關節藝術家真值 **4 AC 全 PASS**(頭/左手/右手 err 2–5% 軀幹尺度、勝質心 baseline、random/swap/rect 三負對照皆爆閘)。關鍵發現:**pivot 準度 = 件輪廓保真** —— 用 region bounding-rect 代理右手誤差 406px,改從 atlas alpha 取真實輪廓後降到 25px(PSD-first 論點在 rig 階段再現)。**多 rig 擴充(2026-08-30)**:新增 `main_draw` 貓 rig(全 region、左右手共用鏡射貼圖)為第二真值,contact-seam **2 rig 全 AC PASS**(cat 5 關節 max 0.096 軀幹尺度);修掉「region 該用 attachment 鍵而非 slot 名查 atlas」通用性 bug,重構通用 `load_rig`。誠實限制:pivot→bone 樹仍未接 build_spine(`pivot_end2end` L0→L1)→ `spine-rig-pivot` 區塊仍 **HOLD**;軸向精修屬美術(A 類)。

> 每次新增 knowledge 檔案時,在此補一行：`- [標題](檔名.md) — 一句話摘要`
