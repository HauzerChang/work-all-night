# 累積研究發現(蒸餾版)

> 來源:`work-all-night` 研究 repo `knowledge/*.md` 的濃縮。每條都經正/負對照或真實資產驗證。
> 需要完整推導 / log 時回上游 repo。

## S3 mesh 生成器

- **純 CPU「PNG(alpha) → unweighted Spine mesh」可全自動**:findContours → Douglas-Peucker(hull)
  → Canny 內部邊界 + 格點補點 → 約束 Delaunay(triangle `'p'`)→ 重心過濾 → 孤兒頂點修剪 → Spine JSON。
- **兩種拓樸,各有適用**:
  - **strip(掃描線直條)**:高瘦、row-convex 件(窗簾)。變形時各條平滑滑動 → **大單向拉伸下最耐**(不自交)。
  - **delaunay**:blob / 凹形件(光暈、身體、手)。`generate_mesh_v2(mode="auto")` 依長寬比+row-convex 自動選。
- **靜態 IoU 高 ≠ 變形穩健**:v1 散點 Delaunay 對窗簾靜態 IoU 0.98,但真實 deform 下自交;strip 才通用。
- **IoU 主槓桿 = 邊界取樣密度,內部密度近乎無關**:strip 是 `rows` 決定、`cols` 不影響;
  delaunay 是 `epsilon`(輪廓解析度)決定、`max_interior` 不影響。→ `generate(target_verts=N)` 二分搜 epsilon 反推。
- **對藝術家真值收斂達標**:main_draw 4 mesh(v2 strip,rows=10)全過;Award 3 真實生產 mesh(光暈/左手/身體)
  對齊頂點成本下生成 IoU **全 ≥ 藝術家**(0.986/0.994/0.995)、拓樸乾淨。

## deform-aware 評估器

- Python 重現 Spine unweighted deform(緊湊 bezier `{"curve","c2","c3","c4"}`、deform 受 attachment gating)。
- **藝術家好網格的門檻 = 完全乾淨**:main_draw 4 mesh × 9 動畫逐幀取樣,0 自交/0 翻面/0 退化。
- **正式閘用 `transfer_deform_check`(真實最大位移幀轉移到任一拓樸)**;`stress_field`(合成場)未校準,只作最壞裕度參考,**不當 pass/fail**。
- 負對照(故意壞網格)可穩定抓到自交/翻面 → 閘有鑑別力。

## S2 切圖評估器 + atlas_crop

- `evaluate_slicing.py`:端到端「atlas 切件 → 依 xy/size/rotate 重組」對照原 sheet。main_draw **45/45 region MAE=0、0 孤兒、0 重疊**。
- `atlas_crop.py`:多頁 atlas + **CW derotate**(rotate 件)。
- **教訓:round-trip 自洽掩蓋方向 bug** —— extract↔repack 方向一起反仍 MAE=0;用 PSD 切件當外部真值才發現原本 CCW 是錯的(CW 才對,alpha-IoU 0.92–0.98 vs 0.40–0.57)。

## S4 PSD-first 切圖

- 策略:**改輸入契約比硬攻演算法划算**。要到分層 PSD,切圖+補圖兩大難題大半消失。
- `psd_slice.py`:分層 PSD → 各部位件 PNG + manifest + 重組無損自驗。對 2 份真實生產 PSD(`Symbol_Ww` 18層 / `robot_parts` 5層)**切圖無損 PASS**。
- **真實命名慣例(可寫進契約)**:slot = `<PSD檔名>/<圖層名>`;一圖層=一 slot;size 對應 spine +2px(atlas 每邊 1px padding)。
- mesh vs region 由美術依需求分配:會 warp 的件(光暈/身體/左手)做 mesh,剛體件(頭/右手)用 region+旋轉。
- **PSD 切件 = spine 生產貼圖同素材**:PSD 切件 ↔ atlas 切件 resize 對齊後 alpha-IoU 0.92–0.99,PSD↔spine↔atlas 三者閉環。
- **閘校準教訓**:`PSDImage.composite()` 對 RGB PSD 透明區填白(255)→ 直接比 RGB 假性失敗;改 **premultiplied-alpha 比對** + 套圖層 opacity 才對。

## 跨能力方法論(RULES 精神)

1. **每能力必配評估器(自我品質閘)**:沒有機讀 pass/fail,自主迴圈無法收斂。
2. **評估器先校準再信**:正對照(真值應過)+ 負對照(壞的應擋)。本專案踩過四次 miscalibration。
3. **AC 相對真值**:IoU 用「≥ 藝術家」、頂點用「≤ 藝術家」,不用武斷常數。
4. **端到端對真實多樣件驗收**:合成/單一資產測不到的路徑,換真實件才會踩到(orphan bug、derotate 方向)。
5. **別用 ML 學沒有唯一解的美術決定**:用確定性演算法 + 評估器把關。

## 已知阻塞 / 開放

- **補圖(inpainting)閘、骨架閘**未做(S2 樞紐尚缺兩塊)。
- **weighted 件的變形驗證**需 S5(骨架/權重);目前只保證靜態幾何。
- **S1 反推分析器**需 benchmark 影片(研究 repo 無影片資產)。
- **骨架 pivot** 是整條 pipeline 唯一真正需人力集中處(S5)。
- spine_inspector 實機 round-trip 被 CDN 政策擋(需離線 spine-webgl 或改網路政策)。
