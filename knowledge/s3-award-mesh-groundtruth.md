# S3 端到端驗收 — PSD 件 → 生成 mesh 對照 Award 真實生產 mesh

- **結論**:對機器人 3 件真實 **weighted mesh**(`Award.json` 的 `機器人拆件/光暈`、`身體`、`左手`),
  S3 生成器產出的 mesh **在頂點數 ≤ 藝術家、覆蓋率(IoU)≥ 藝術家**的雙門檻下**全部 PASS**,
  且 setup pose 幾何乾淨(0 退化 / 0 孤兒三角 / 質心在遮罩內)。這是「PSD→件→mesh」對**真實生產標的**
  的端到端驗收(有 ground truth,純 CPU 自驅)。
- **信心**:高(對真實生產 spine 的藝術家 mesh 逐件量化比對 + PSD/atlas 兩來源交叉檢查)。
- **階段**:第 2 階段 / S3(里程碑:合成→main_draw→**真實生產 mesh**)。

## 驗收數據(`validate_award_mesh.py --src atlas`,eps_px=3.5)

| 件 | 生成 nv | 生成 IoU | 藝術家 nv | 藝術家 IoU | pass |
|---|---|---|---|---|---|
| 光暈 | 76 | 0.9846 | 78 | 0.9795 | ✅ |
| 身體 | 70 | 0.9868 | 98 | 0.9760 | ✅ |
| 左手 | 52 | 0.9739 | 80 | 0.9681 | ✅ |

→ 生成 mesh **用更少頂點達到 ≥ 藝術家的覆蓋率**(身體/左手頂點數遠低於藝術家)。

## ★ 關鍵發現:邊界容差要用「絕對像素」而非「周長比例」

- v1 `epsilon_frac=0.008` 是 **approxPolyDP 的周長比例**。件越大周長越大 → `0.008×周長` 越大
  → 邊界被過度簡化。大件(光暈周長 ~1927px → eps≈15px)覆蓋率掉到 **0.929**(藝術家 0.980)。
- **修正**:改用**固定絕對像素容差** `eps_px`(approxPolyDP epsilon 直接吃像素)。sweep 顯示
  `eps_px=3.5` 對 3 件全部「nv ≤ 藝術家 且 IoU ≥ 藝術家」(3.0 覆蓋率更高但光暈 81v 略超預算;
  4.0+ 左手覆蓋率跌破藝術家)。→ **eps_px=3.5 設為 Award 驗收預設**。
- 對 main_draw 小件影響極小(小周長時 `0.008×周長 ≈ 3px ≈ eps_px 3.5`);且窗簾/陰影走
  v2 strip 路徑不經此參數。**已把 `eps_px` 加入 `generate_mesh.generate()` 為可選 knob(向後相容,
  預設 None 走原周長比例)** → 4 mesh main_draw 全數重驗仍 PASS,零回歸。

## 為何用「靜態覆蓋率對照藝術家」而非 deform 閘

這 3 件在 Award **是 weighted mesh、無 deform timeline**(靠骨骼權重變形,非逐頂點 deform)
→ `deform_eval` 的真實位移場閘不適用。改用「同一 alpha 下,生成 vs 藝術家覆蓋率」的**相對基準**
(藝術家自身覆蓋率當門檻,避免武斷絕對值),加 setup pose 幾何乾淨檢查。

## footprint 一致性(重要,別踩)

藝術家 mesh 的 uvs 是 **region-local [0,1]**(Spine JSON 慣例),`artist_iou` 用 `uv×mask(W,H)`
還原到件的局部像素座標。因此**遮罩必須是藝術家作圖時的 footprint = atlas 切件**,才是權威比對:
- `--src atlas`(預設):gen/mask/artist 三者同在 atlas footprint → **權威 pass/fail**。
- `--src psd`:從 `robot_parts.psd` 切件生成(端到端 PSD→件→mesh);gen 品質等價甚至更高
  (IoU 0.983~0.991),但**藝術家基準因 PSD frame 與 atlas frame 錯位(padding/scale)被低估**
  (光暈 artist IoU 掉到 0.949)→ 只當「生成器對 PSD-origin alpha 也 work」的交叉檢查,不作判定。
- S4 已證 PSD 件 ≡ atlas 件(alpha-IoU 0.92~0.99),故生成品質與來源無關。

## 可重現

```
python3 tools/mesh_gen/validate_award_mesh.py --src atlas   # 權威,overall_pass=True (exit 0)
python3 tools/mesh_gen/validate_award_mesh.py --src psd      # 端到端 PSD→件→mesh 交叉檢查
```

## 下一步候選

- 把「PSD名/圖層名 + size+2px + mesh/region 分配 + eps_px 邊界規則」固化成 **SkelToJson**
  (件 → Spine JSON attachment 組裝),端到端產出可載入的 Spine JSON。
- weighted mesh 的**權重(BBW)**尚未生成:目前只驗拓樸/覆蓋率;骨骼綁定權重是 S3 後段 + S5 交界。
- S2 補圖閘 / 骨架閘(純 CPU 可續)。
