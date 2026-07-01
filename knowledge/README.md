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

- [S3×S4 端到端(對真實生產 mesh)](s3-award-mesh-endtoend.md) — S3 生成器對 Award 機器人 3 mesh(光暈/左手/身體)**覆蓋率達到/超過藝術家真值且頂點更少**(3 件 overall_pass)。釐清兩種 regime:weighted+無 deform → 覆蓋率保真閘(v1 Delaunay + auto-epsilon,UV 拓樸);vs unweighted+有 deform → 位移場轉移閘(v2 strip)。通則:覆蓋率由邊界 epsilon 決定,內部頂點不影響。評估器自我校驗+雙向負對照確認鑑別力。

- [S4 SkelToJson(件→完整 skeleton JSON)](s4-skel-to-json.md) — 新 `skel_to_json.py` 把「切件+生 mesh」組裝成完整 Spine 3.8 skeleton JSON,補齊 pipeline 最後一環。對真實 robot_parts.psd 產出結構與 Award 逐 slot 吻合(4 AC 全過:schema/loader-roundtrip/layout/Award-parity)。固化慣例:`<prefix>/<層>` 命名(prefix 是 authoring 選擇、可覆寫,發現 Award 前綴=中文群名≠檔名)、draw order=z、每件一根骨、+2px=atlas padding。尚缺權重/綁定=S5。

- [S2 骨架閘 + 補圖閘(S2 四評估器補齊)](s2-skeleton-inpaint-gates.md) — 新 `evaluate_skeleton.py`(結構/attachment/rig 權重;正對照 main_draw+Award+gen 全過,先驗揪出 clipping 誤判 bug)+ `evaluate_inpaint.py`(完整度/接縫/對真值 MAE;補圖能力梯三態可分、作升級決策)。**S2 四評估器(切圖/mesh/骨架/補圖)全到位** → 自主收斂樞紐完成。

- [S5 骨架階層草案(rig_draft.py)](s5-rig-draft.md) — 由件 alpha 重疊自動推骨架階層(重疊圖→生成樹→父子鏈)+ 關節 pivot 草案,世界版面保真、過 evaluate_skeleton。自動 root 誤選背景件光暈=「root 需人確認」案例;`--root 身體` 得合理階層。誠實界定:自動=連接/生成樹/關節質心;待人=root 確認/pivot 微調/mesh 權重綁定(PLAN 明示 pivot 唯一卡死)。

- [S1 塊1 運動場提取](s1-motion-field.md) — `tools/s1/motion_field.py`:Farneback 稠密光流對真實舞蹈影片(`assets/robot_dance.mp4`)定位動態前景 + 偵測律動(3 AC 全過)。熱圖揭示手臂/拳頭是主要動作源、頭中等、軀幹/腿穩定、背景靜態;誠實發現垂直幅度(21.9px)> 水平(5.9px)。方向與現有 robot_parts/rig_draft 一致,可作真值對照。下一步:運動分群成件 → 需求規格。

- [S5 mesh 權重綁定](s5-weight-binding.md) — `bind_weights.py`:unweighted mesh → Spine weighted mesh 綁到 rig 骨架。誠實判斷:part-based rig 用 rigid(每頂點權重1給自身件骨)正確,完整 BBW 僅適用單一連續 mesh(附 inverse-distance blend 近似為選用)。端到端產出 `assets/robot_parts_rigged.json`;變形測試(繞 pivot 旋轉/其他件不動/rest 保真)全 0.0px。pipeline 五段串通,機器人成可變形 rig。

> 每次新增 knowledge 檔案時,在此補一行：`- [標題](檔名.md) — 一句話摘要`
