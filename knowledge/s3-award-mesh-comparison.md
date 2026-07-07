# S3 端到端驗收：PSD 件 → generate_mesh_v2 → 對照 Award 真實生產 mesh

- **結論**：把 `robot_parts.psd` 的 3 個 mesh 件(光暈/左手/身體)經 S4 切圖 → S3
  `generate_mesh_v2` 生成 mesh,與美術在真實 spine `Award` 手做的**生產 mesh** 做覆蓋率對照。
  **3 件全通過「藝術家相對」驗收**:S3 mesh 用 **1.95–2.65× 更少頂點**達到與藝術家
  mesh 相當(±0.02)甚至更好的靜態覆蓋率。端到端「PSD→件→mesh」對真實生產標的成立。
- **信心**:高。兩個獨立 rasterizer 互相佐證(evaluate_mesh AC1 ≈ 直接畫,差 <0.005);
  方位窮舉對「id」壓倒性勝出(校驗對應方向正確,能抓 rotate 方向 bug);跨 PSD/atlas 真值。
- **階段**:第 2 階段 / S3+S4 端到端(里程碑:單能力 → 兩能力串接對真實標的)。

## 量化結果(`compare_award_mesh.py`,對 PSD 件 alpha)

| 件 | 我方頂點 | 藝術家頂點 | 我方 IoU | 藝術家覆蓋 IoU | 最佳方位 | 方位決定性 | 頂點省 | 通過 |
|---|---|---|---|---|---|---|---|---|
| 光暈 | 33 | 78 | 0.9321 | 0.9487 | id | ✅(2nd=0.70) | 2.36× | ✅ |
| 左手 | 41 | 80 | 0.9642 | 0.9808 | id | ✅(2nd=0.76) | 1.95× | ✅ |
| 身體 | 37 | 98 | 0.9685 | 0.9493 | id | ✅(2nd=0.60) | 2.65× | ✅ |

- 「通過」= 我方 IoU ≥ 藝術家覆蓋 IoU − 0.03(**藝術家相對**閘,非武斷 0.95;
  見下方「0.95 絕對閾值不適用羽化件」)。身體我方**優於**藝術家。
- 3 件 `generate_mesh_v2` auto 皆回退 **delaunay-v1**(件為圓潤/塊狀、非高瘦 row-convex);
  strip 模式是給窗簾那種 deform-timeline warp 件。auto 選路正確。
- 3 件 evaluate_mesh 幾何全過(format/退化/孤兒/重心);光暈 overall 因絕對 IoU 閾值 fail(見下)。

## ★ 關鍵發現

1. **Award mesh 的 `uvs` 是 region 局部 [0,1] 正規化,不是 atlas 頁 UV**(更正先前
   `s4-psd-to-spine-real.md` 末的假設「uvs 為 atlas UV,需先轉 region 局部」)。
   實測:左手 uv u∈[0.008,1.0](若為頁 UV 應是 [0.152,0.241])→ 顯非頁座標。
   **決定性證據**:身體 uv u_max=0.7589,而身體 PSD alpha 內容右緣 = 286/379 = **0.7546**
   → region 局部座標下內容邊界吻合(<0.4% 差)。故對照時**直接用原始 uvs 畫進件框**即可,
   不需頁→region 轉換。
2. **這 3 件在 Award 為 weighted mesh、無 deform timeline** → 逐頂點 deform 轉移閘 **N/A**
   (不是失敗)。它們靠骨骼權重變形;deform 耐受性是另一問題(需在骨骼旋轉下測,非本次範圍)。
   對照:main_draw 窗簾有 deform timeline,才走 `deform_eval`。
3. **絕對 IoU=0.95 對羽化邊件過嚴**:光暈(柔邊發光)連**藝術家自己**的生產 mesh 都只到
   0.9487。→ 印證 `validate_against_real` 早已採用的「藝術家相對覆蓋率」才是對的閘;
   evaluate_mesh 內建 0.95 應視件性質放寬,或一律改用藝術家基準。

## 方法論(可信度來源,對抗自欺)

- **方位窮舉自校驗**:藝術家 uvs 以 8 種二面體變換對齊件 alpha,取 IoU 最大。correct
  方位(id)對全 3 件壓倒性勝出(0.95/0.98/0.95 vs 次高 0.70/0.76/0.60)→ 同時
  (a) 得覆蓋率基準 (b) **證明對應方向正確**。這正是專案「外部真值 + 試兩個方向」的一貫做法,
  能抓先前踩過的 atlas derotate 方向 bug。
- **雙 rasterizer 互證**:我方 mesh 覆蓋率由 evaluate_mesh(AC1,像素框)與本工具直接畫
  兩條獨立路徑算出,結果一致(0.932/0.928 等)→ 無座標框 bug。
- **踩坑記錄**:初版 `rasterize_norm` 對 mesh **自身 bbox** 正規化 → 身體(內容只占框左
  0.754)被拉伸致錯位(自檢 sanity 0.63 而非 0.96)當場抓出。改為「我方直接 x/W,y/H;
  藝術家用已是 [0,1] 的原始 uvs」後,3 件 sanity 全復原。**教訓(重申):正規化到錯誤參考框
  會靜默錯位,務必留自檢通道。**

## 可重現

```
python3 tools/mesh_gen/compare_award_mesh.py -o /tmp/award_cmp.json
# 3 件 my_covers_as_well 全 True → exit 0
```

依賴:`assets/{Award.json,Award.atlas,robot_parts.psd}`(皆已在 repo)。純 CPU。

## 下一步候選

- 把 `機器人拆件/<圖層名>` 命名 + size(+2px)+ region-local uvs 慣例固化成
  **件→Spine mesh attachment 組裝器(SkelToJson)**,端到端產可載入的 Spine JSON。
- S2 補圖閘 / 骨架閘(補齊 S2 樞紐)。
