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

- [S3×S4 端到端:PSD→mesh→對照 Award](s3-psd-to-award.md) — PSD 件→生成 mesh→對真實生產 Award mesh(光暈/身體/左手)驗收全 PASS,生成覆蓋率 ≥ 藝術家。發現:①Award 件 weighted+無 deform → 變形閘 N/A(需 BBW,修正「都用 deform 場驗」假設);②epsilon 由外形複雜度決定→覆蓋率驅動細化;③修生成器凹形孤兒頂點 bug(`prune_orphans`)。

- [S2 補圖閘](s2-inpaint-evaluator.md) — GT-free 三準則(破洞/**局部化接縫**/**Laplacian** 紋理)+ GT MAE;以 robot_parts 真實圖層互遮(美術層畫全=真值)校準,正對照全過、黑洞/平色/噪聲全抓(平色**無真值也抓得到**)。量化證實降階鏈:cv2 只夠平滑件(光暈 10),細節件(20~31)需升級。

- [S2 骨架閘](s2-skeleton-evaluator.md) — 結構閘 + pivot 空間關聯(d_norm≤0.5 ≥95%,以 main_draw/Award 分佈校準)。含 setup 世界變換(weighted mesh 支援)。**關鍵發現:負對照必須 rebind**(bone-relative 幾何下,單純移骨美術跟著跑,量不變;壞 rig = 畫面對、骨錯)。**S2 四閘至此齊備**。

- [S4 下游:切件→完整 Spine 資產](s4-skel-to-json.md) — `skel_to_json.py`(件→Spine JSON,setup pose=PSD 佈局,4 AC 全過:位置 0px/結構/mesh 格式/光柵重建 MAE 0.031 且視覺正確)+ `pack_atlas.py`(件→.atlas+PNG,用真實-atlas 讀取碼裁回 MAE 0)。完整資產 JSON+atlas+PNG 一致。誠實邊界:未在 Spine runtime 實載(CDN 擋);rotation=0 平面 setup(綁定屬 S5)。

- [S5 骨架草案產生器](s5-skeleton-draft.md) — 件重疊分析 → 骨階層+pivot 草案(effect/trunk/limb 分類、**trunk 優先**防 z 交叉假邊、關節=重疊區質心)。對 Award 藝術家骨架:**拓樸全中、pivot 全在 6.9% 對角線內**(頭 4.3px)。skel_to_json --draft 組階層化 skeleton 佈局不變。光暈場景錨=A 類留人。

- [權重 + 可動資產](s5-weights.md) — envelope 綁定(own+parent 關節 smoothstep,wmax=0.85 錨自藝術家)+ LBS。±40° 掃描 0 自交/0 翻面;**錨定 AC** 位移比 0.395(剛性負對照=1.0)。pose 渲染證實整隻可動(figures/robot_pose_strip.png)→ 渲染器=未來影片逼近迴圈雛形。子件變形骨(需運動資訊)與光暈跨件綁定列範疇外。

- [AI 自主切圖規則](s4-ai-slicing-rules.md) — 動畫需求反推分件(運動決定拆件):DJ 貓 3 層→13 件,含重疊帶補繪/旋轉自覆蓋 copy/切邊羽化/像素優先權。psd_resegment.py + 規格 JSON。自驗 MAE 0.007 全過;**待美術版交叉比對**。修 psd-tools 中文層名與 preview 假性失敗兩 bug。

- [W1+W2:切圖評分器+重疊架構](s4-w1w2-overlap-reseg.md) — 評分器自證(GT=100/v4=51.6/負對照全抓);廢互斥改「完整物件+被蓋補全」→ **60.9,掏空根治(頭 1.0)**。剩:recall(W4 粒度)、chamfer(W3)、cv2 補全品質(有真值基線 42%/77.5%)。

- [W3+W4b1:邊緣吸附+粒度批1](s4-w3w4-edge-snap.md) — GrabCut 吸附(per-piece 開關:低對比不吸)+ 耳罩重定位/雙節臂/依真值不切 → **64.4、零過切、右罩 0.915/1.2px**。眼內件 100% 藏鏡片後=合成圖資訊極限(A 類)。

> 每次新增 knowledge 檔案時,在此補一行：`- [標題](檔名.md) — 一句話摘要`
