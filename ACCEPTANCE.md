# 階段驗收指南(人為測試用)— 2026-07-03 里程碑

> 對象:第 2 階段「四能力鍛鍊」的人為測試與階段驗收。
> 每項功能都列:**一鍵指令**(機器自動判準,exit 0 = PASS)+ **人眼檢查點**(你要看什麼)。
> 產物已預先生成在 `acceptance/`,不跑 python 也能直接驗最重要的東西。

## 🔑 最重要的一項人為測試(只有你能做)

**把 `acceptance/robot_asset/`(robot.json + robot.atlas + robot.png)載入真正的 Spine 工具**:

1. **Spine 3.8.99 編輯器**(或版本相容的 runtime):直接 import robot.json,設定 images 路徑
   → 應看到機器人以 PSD 原佈局呈現;骨階層 root→b_身體→{b_頭, b_左手, b_右手},b_光暈 掛 root;
   轉動 `b_左手` → 手臂繞肩旋轉、肩部因權重保持連接。
2. **`spine_inspector.html`**(repo 根目錄,你的機器瀏覽器開;CDN 在你端可用):
   拖入 robot.json + robot.atlas + robot.png → 檢查 mesh 線框、骨頭、頂點。
3. **Cocos Creator 3.7.3**:當一般 spine 資產匯入。

> 這補上我們環境做不到的「**Spine runtime 實載驗**」(排程容器網路政策擋 CDN)。
> 目前只驗到:結構/幾何 round-trip 0px、光柵重建 MAE 0.03、atlas 可被讀真實 atlas 的程式碼裁回 MAE 0。
> **若實載有任何報錯/顯示異常,請把訊息貼回來 —— 那是我們最需要的回饋。**

## 驗收包內容(`acceptance/`)

| 檔案 | 是什麼 |
|---|---|
| `robot_asset/robot.{json,atlas,png}` | **完整可載入 Spine 資產**(階層化骨架+weighted 左手 mesh) |
| `robot_asset/skeleton_draft.json` | 骨架草案(角色/樹/pivot,工具自動產) |
| `renders/setup_reconstruction.png` | 由 skeleton 位置重合成的 setup pose(應 == PSD 原圖) |
| `renders/pose_strip.png` | 三 pose 動作幀(左:左手-22°/右手+14°/頭-8°;中:setup;右:反向) |
| `inpaint_samples/righthand_*.png` | 補圖閘人眼樣本:GT/遮擋後/cv2補繪/平色負對照(綠框=洞區) |
| `gate_results.md` | 全部自動閘的最新結果(全 ✅) |

## 能力清單(10 項,依 pipeline 順序)

環境準備(要重跑指令時):`pip install -r requirements.txt`,並先切件+產草案:
```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
python3 tools/mesh_gen/skeleton_draft.py -o /tmp/robot_draft.json
```

### 1. PSD 切圖(S4)
```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd --eval     # exit 0
python3 tools/mesh_gen/psd_slice.py assets/Symbol_Ww.psd  --eval     # exit 0
```
- 機器判準:重組 premult MAE < 2、0 孤兒像素。
- 人眼:`/tmp/robot_parts/*.png` 五件應乾淨無殘缺;manifest offset/size 對得上 PSD。

### 2. atlas 裁切/重組保真(S2 切圖閘)
```
python3 tools/mesh_gen/evaluate_slicing.py                            # main_draw 45 region
python3 tools/mesh_gen/atlas_crop.py assets/Award.atlas assets/Award.png '機器人拆件/右手' /tmp/r.png
```
- 人眼:`/tmp/r.png` 應是方向正確(非旋轉 90°)的右手+劍。

### 3. mesh 自動生成(S3)+ 對 main_draw 真實 deform 驗
```
python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot image/curtain_left --name image/curtain_left
```
- 機器判準:IoU ≥ 藝術家自身覆蓋率、真實位移場轉移後 0 自交/0 翻面。
- 4 個 mesh(curtain_left/right、shadow;shadow2 與 shadow 共用 region,用 shadow 驗)。

### 4. PSD件→mesh→對照 Award 藝術家 mesh(S3×S4)
```
python3 tools/mesh_gen/validate_psd_to_mesh.py                        # 光暈/身體/左手,exit 0
```
- 機器判準:生成 mesh 靜態覆蓋率 ≥ 藝術家(0.964/0.966/0.980 vs 0.949/0.948/0.977)。

### 5. 骨架草案(S5)+ 對照 Award 藝術家骨架
```
python3 tools/mesh_gen/validate_draft_vs_award.py                     # exit 0
```
- 機器判準:拓樸完全一致;pivot 距離 ≤0.15 對角線(實際:頭 0.027、右手 0.039、左手 0.054、身體 0.069)。
- 人眼:`acceptance/robot_asset/skeleton_draft.json` 的樹與 pivot 是否合理。

### 6. 組裝成完整 Spine JSON(S4 下游)
```
python3 tools/mesh_gen/skel_to_json.py --draft /tmp/robot_draft.json --weights --eval --render /tmp/recon.png
```
- 機器判準:位置 round-trip ≤1.5px(實際 0.001)、光柵重建 MAE <2(實際 0.031)。
- 人眼:`renders/setup_reconstruction.png` 應與 PSD 原圖無差別。

### 7. atlas 打包
```
python3 tools/mesh_gen/pack_atlas.py --eval                           # 裁回 MAE=0
```
- 人眼:`robot_asset/robot.png` 五件不重疊、無裁切殘缺。

### 8. 補圖閘(S2)
```
python3 tools/mesh_gen/evaluate_inpaint.py --bench                    # 24 列校準表
```
- 機器判準:GT 全過;黑洞/平色/噪聲全被抓;cv2 級只在平滑件過 fidelity(降階鏈)。
- 人眼:`inpaint_samples/righthand_gt_occluded_telea_flat.png` —— 從左到右:原圖(真值)/
  遮擋後/cv2 補繪(模糊但連續)/平色填充(綠框內應明顯看得出「糊掉一塊」= 閘該抓的)。

### 9. 骨架閘(S2)
```
python3 tools/mesh_gen/evaluate_skeleton.py assets/main_draw.json --selftest
python3 tools/mesh_gen/evaluate_skeleton.py assets/Award.json --selftest
```
- 機器判準:正對照過(98.6%/100%)、強負對照(位移/造環/壞slot)全抓。

### 10. 權重 + 可動(S3 權重 × S5 綁定)
```
python3 tools/mesh_gen/validate_weights.py --skeleton acceptance/robot_asset/robot.json
python3 tools/mesh_gen/validate_weights.py --skeleton acceptance/robot_asset/robot.json \
        --render-pose '{"左手":-30,"右手":20}' --pose-out /tmp/my_pose.png    # 自訂角度玩
```
- 機器判準:權重和=1、±40° 掃描 0 自交/翻面、錨定位移比 0.395(剛性=1.0)。
- 人眼:`renders/pose_strip.png`;或自訂角度渲染 —— 重點看**肩部連接處**是否自然、有無破圖。

## 已知限制(驗收時請勿期待這些)

1. **未在 Spine runtime 實載過**(等你這次測 → 最重要回饋)。
2. **setup pose = PSD 平面佈局、bone rotation 全 0**:Award 生產檔那種 posed rotation/骨長度
   是綁定精修,不在自動產物內。
3. **子件級變形骨沒有**(藝術家的肩部輔助骨/前臂鏈需運動資訊才推得出;目前一件一骨+關節混合)。
4. **光暈(effect 件)是剛性**:藝術家讓它綁 4 根部位骨跟著全身動 —— 特效歸屬是 A 類人決策。
5. 補圖 cv2 級只夠平滑件/小洞;細節大洞閘會判「需升級」(LaMa/GPU/人工)—— 這是設計,非 bug。
6. pivot 的美術手感(頸底 vs 頸中)是草案精度,預期人微調。
7. pose 渲染器是驗證用近似(逐三角 affine),非 Spine runtime 渲染。

## 建議驗收順序

1. 先看圖:`renders/`(30 秒)→ 2. **Spine 編輯器實載 robot_asset**(關鍵)→
3. 跑 `acceptance/gate_results.md` 裡的指令複核(可選)→ 4. 對照「已知限制」確認理解一致 →
5. 回饋:實載結果 + 哪些 A 類決策要拍板(光暈歸屬、pivot 手感、排程頻率)。
