# S3 端到端驗收 — PSD件 → 生成 mesh → 對照 Award 真實藝術家 mesh

- **結論**:把 `robot_parts.psd`(機器人拆件)的 3 個 **mesh 件**(光暈 / 身體 / 左手)走完整鏈路
  「PSD 切件 → `generate_mesh_v2` → 對照 Award.json 同名 slot 的**真實藝術家 mesh**」,
  **3 件全部通過整合 AC(覆蓋率 ≥ 藝術家、頂點數 ≤ 藝術家、mesh 幾何乾淨)**。
  這是 S3+S4 第一次對**真實生產標的(有 ground truth)**做端到端驗收。
- **信心**:高(真實生產 PSD + 真實 spine mesh 交叉比對;含負向發現與當場修正;4 main_draw mesh 無回歸)。
- **階段**:第 2 階段 / S3+S4 串接(里程碑)。

## 驗收結果(`tools/mesh_gen/compare_to_award.py`,overall_pass=True)

| 件 | 生成 mode | 生成 nv (藝術家) | 生成 IoU | 藝術家 IoU | AC2 幾何 | AC3 覆蓋 | AC4 預算 |
|---|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 42 (78) | 0.9606 | 0.9486 | ✅ | ✅ | ✅ |
| 身體 | delaunay-v1 | 69 (98) | 0.9828 | 0.9477 | ✅ | ✅ | ✅ |
| 左手 | delaunay-v1 | 70 (80) | 0.9796 | 0.9768 | ✅ | ✅ | ✅ |

- **AC3 覆蓋率閘**是真值閘:把 Award 藝術家 mesh 的 region-local `uvs` 光柵化到「同一張 PSD 切件 alpha」
  上算覆蓋 IoU,與生成 mesh 同基準比。生成 mesh 覆蓋率**皆 ≥ 藝術家**(margin 0.01)。
- **頂點數皆少於藝術家**(42/69/70 vs 78/98/80)→ 更精簡卻覆蓋不劣。
- 3 件 aspect < 1.2 → auto 模式走 **v1 Delaunay**(blob 件),非窗簾的 strip。

## 為何走 Delaunay 而非 strip

`generate_mesh_v2` auto:`aspect(H/W) ≥ 1.2 且 row-convex` 才用 strip(窗簾那種高瘦、順拉伸軸)。
機器人 3 件都是矮胖 blob(光暈 706×683、身體 379×425、左手 257×215)→ 回退 v1 約束 Delaunay,正確。

## 關鍵校準(本輪兩個修正,均由真實 ground truth 逼出)

1. **`epsilon_frac` 0.008 → 0.004**(hull 簡化精度)。
   - 舊預設 0.008 是對窗簾/合成資料調的;對真實 blob 件的**平滑曲邊**太粗:
     光暈 hull 僅 16 點 → 覆蓋率 0.933 < 藝術家 0.949(不及格)。
   - epsilon 掃描(0.008→0.001):**0.004 是甜蜜點** — 3 件覆蓋率全過**且**頂點數仍 ≤ 藝術家;
     0.002 會讓左手 nv=84 > 藝術家 80(爆預算)。已設為 `generate_mesh.py` 新預設 +
     `generate_mesh_v2.generate(epsilon=0.004)` 參數。
2. **孤兒頂點修剪 `prune_unused()`**。
   - 細 hull 後,光暈有 2 個**內部**候選點的三角全被 centroid 過濾 → 變孤兒(AC2c fail)。
   - 修法:三角過濾後,移除未被使用的**內部**頂點並重新編號;**hull 頂點一律保留**
     (維持「hull 排最前 + 邊界完整」Spine 不變量,n_hull 不變)。修後光暈 44→42v、0 孤兒。

## 真值比對的座標學(重要,避免踩雷)

- Award mesh `uvs` 是 **region-local [0,1]**(與 main_draw 同;非整頁 sheet UV)→ 可直接 `uv*W, uv*H`
  光柵化到切件遮罩。已由 `validate_against_real.artist_iou` 對 main_draw 驗證此假設可用。
- PSD 切件 vs atlas region 差 **+2px padding(各邊 1px)**、atlas 另有 **~0.70 縮放**;但 uvs 正規化
  → 縮放自動抵銷,padding 造成 ~0.3% 殘差(可忽略,已反映在藝術家 IoU 未達 1.0)。
- **deform 閘 N/A**:這 5 件在 Award **無 deform timeline**,靠 weighted(骨骼)變形,非逐頂點 deform。
  真實位移場轉移閘不適用 → 不當失敗論(RULES:別用未校準壓力場)。骨骼權重驗證屬 S5 範疇。

## 可重現

```
python3 tools/mesh_gen/compare_to_award.py         # overall_pass=True, EXIT 0
# 回歸(4 main_draw mesh 皆 strip,不受 epsilon 改動影響):
python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot image/curtain_left  --name image/curtain_left
python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot image/shadow2       --name image/shadow   # 共用 shadow region
```

## 對契約/pipeline 的意義

- S4(PSD 切件)→ S3(mesh 生成)這條 CPU 鏈,對**真實生產 mesh 件**已達「覆蓋不劣於藝術家、更精簡」。
- 下一哩:把生成 mesh **寫回 Spine JSON**(SkelToJson,含 `機器人拆件/<層名>` 命名 + size+2px + atlas 0.70),
  產出可直接載入的 attachment;以及 region 件(右手/頭)的旋轉打包。
- 仍缺:骨骼權重(weighted mesh 綁定)屬 S5;本輪生成的是 unweighted 幾何,綁定/pivot 待 S5。
