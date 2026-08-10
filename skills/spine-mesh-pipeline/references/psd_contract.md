# S4 PSD-first 切圖契約 + 工具(已打通 pipeline,等真實 PSD)

- **結論**:採「PSD 契約」策略(使用者 2026-06-26 拍板)。完成 PSD-first 切圖 pipeline:
  `psd_slice.py`(分層 PSD → 各部位件 PNG + manifest)+ 自驗閘(重組無損)+ 合成 PSD fixture。
  合成 4 層 PSD 端到端:**重組 MAE=0.0104、0 孤兒,overall_pass**;漏層負對照 MAE 1.97–11.4(抓到)。
- **信心**:高(pipeline 與閘經正/負對照驗證);**但尚未對「真實美術 PSD」驗過**(repo 無真實 PSD)。
- **階段**:第 2 階段 / S4(切圖)。**最大槓桿策略 = 改輸入契約**(見 PLAN「改契約比硬攻演算法划算」)。

## 為何走 PSD 契約

平面圖自動拆件+補繪在無 GPU 下基本做不到;若美術直接交**分層 PSD**,切圖與補圖兩大難題大半消失。
故把難題上移成「對美術的交檔規範(契約)」,工具只負責正確讀取與驗證。

## 給美術的 PSD 交檔契約(規範;★ = 已對真實生產檔驗證)

1. **檔案**:單一 `.psd`,8-bit。RGB / RGBA 皆可(真實檔為 RGB;工具一律轉 RGBA 處理)。
2. ★**一圖層 = 一可動部位**:每個會被骨架/動畫單獨驅動的部位,獨立成一個**可見 leaf 圖層**。
   隱藏圖層會被工具忽略。真實檔為**扁平結構(無群組)**、圖層名中文 OK。
3. ★**命名 → slot**:真實慣例 = **`<PSD檔名>/<圖層名>`**(見 `s4-psd-to-spine-real.md`:
   機器人拆件 PSD 的「右手」→ spine slot `機器人拆件/右手`)。同一 spine 混多來源 PSD 時靠此前綴分 namespace。
   也可用 PSD 群組表階層(工具以 `descendants` 展平)。避免同檔內重名。
4. ★**共用座標系**:所有圖層對齊同一畫布;圖層 offset(left/top)即部位擺位。
   切件 size 與最終 spine attachment size 吻合(差 +2px = atlas 各邊 1px padding)。
5. **被遮擋處要畫全(補圖需求)**:會露出的被遮部位,圖層在被遮區仍需完整像素,否則動起來露破洞。
   把補圖責任前移給美術一次畫好。
6. **不要**:合併圖層 / 裁切畫布 / 把多部位併成一層。
7. ★**opacity / blend**:圖層 opacity<255 可接受(工具記錄並在驗證時還原;真實 Symbol 有 153 的陰影層)。
   建議 blend 用 **NORMAL**(非 NORMAL 的重組保真不保證)。
8. **mesh vs region 留給特效/美術**:會 warp 的件(如光暈/身體/手臂)做 mesh、剛體件(頭)用 region+旋轉
   —— 此分配在 spine 階段決定,切圖階段一律輸出件 PNG;S3 可對需 mesh 的件自動生成拓樸。
9. **pivot(留待 S5)**:旋轉中心仍需人微調;規格待 S5 定。

## 驗收(自評閘)

```
python3 tools/mesh_gen/psd_slice.py assets/Symbol_Ww.psd  --eval    # 真實檔 PASS
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd --eval   # 真實檔 PASS
python3 tools/mesh_gen/psd_slice.py <檔.psd> -o psd_parts           # 實際切件 + manifest
# 合成 fixture(可選):python3 tools/mesh_gen/make_test_psd.py 再對 assets/test_layered.psd --eval
```

- **AC1 解析**:可見 leaf 圖層全數切出。
- **AC2 重組無損**:各件套 opacity 由下而上 alpha-over 重組 ≈ PSD composite,以
  **premultiplied-alpha** 比對(premult_rgb_mae 與 alpha_mae 皆 < 2)。
  ⚠️ 不可直接比 RGBA:composite 透明區填白、重組填黑,會假性失敗(見 s4-psd-to-spine-real.md 校正記)。
- **AC3 0 孤兒**:composite 內容像素皆被某件覆蓋。
- 互補性:漏「中間層」靠 AC2 抓;漏「唯一覆蓋層」才觸發 AC3 孤兒。

## 技術備忘

- psd-tools 1.17 `descendants()` 已是**由下而上**(index 0 = 最底層)→ 重組直接照此序疊(正序 MAE≈0.01,反序 15)。
- psd-tools 1.17 具寫入 API(`new`/`create_pixel_layer`/`save`),故能純 CPU 造合成 PSD 做自驗;pytoshop 在此環境 build 失敗。
- `layer.topil()` 給裁到該層 bbox 的緊湊像素;`layer.left/top` 為 offset。

## 下一步

- ❗**等使用者提供一份真實分層 PSD**(依上述契約),對它跑 `psd_slice --eval` → 真實驗收。
- 之後接:切件 → S3 生成 mesh(已備)→ 組 Spine JSON(SkelToJson)→ S5 骨架。
