# S3 端到端驗收 — PSD件/atlas → 生成 mesh → 對照 Award 真實 mesh(含 contour 模式)

- **結論**:S3 mesh 生成器對**真實生產標的**(Award spine 的機器人拆件 3 個 mesh:光暈/左手/身體)
  端到端驗收**全過**。過程揭露 v2 auto 對「非 strip 的 soft/roundish 件」(光暈)用散點 Delaunay
  會**留孤兒頂點 + 覆蓋不足**(IoU 0.929 < 藝術家 0.98);依藝術家真值(光暈=78 頂點**全 hull**、
  無內部點)新增 **contour 模式**(密集輪廓多邊形 + 約束三角化)後,3 件覆蓋 IoU 0.97/0.98/0.99,
  頂點數僅 26/32/30(遠低於藝術家 78/80/98)且靜態品質閘全過。
- **信心**:高(對真實生產 mesh ground truth 交叉比對 + 對齊自洽閘 E1 先確認量測正確 + 視覺疊圖)。
- **階段**:第 2 階段 / S3×S4 端到端(里程碑:從單能力 → PSD/atlas→件→mesh 對真實標的閉環)。

## 驗收框架(對齊自洽先行,再判生成)

工具 `tools/mesh_gen/compare_award_mesh.py`。座標統一在「atlas region derotate 後的局部像素」:

1. `atlas_crop.crop_region` 取件 alpha(經 PSD 外部真值校正的 **CW** derotate)。
2. Award 真實 mesh 的 `uvs` 是 **region-local 正規化**([0,1] over 該 region 邏輯 w,h;
   **不是 page 正規化** — 起初誤當 page 正規化 → art_iou 0.0~0.49,身體全 miss;改 region-local 後
   自洽 IoU 0.98)。直接 `u*W, v*H` 映到 derotate 局部框,光柵化三角覆蓋。
3. 生成 mesh 跑在同一 alpha crop 上 → 同框比較。

**AC(4 條,皆對真實標的)**:
| AC | 意義 | 門檻 | 結果(光暈/左手/身體) |
|---|---|---|---|
| E1 | 對齊自洽(先確認量測對) | artist 自身覆蓋 IoU ≥ 0.85 | 0.980 / 0.968 / 0.976 ✅ |
| E2 | 生成覆蓋不遜藝術家 | gen IoU ≥ art − 0.03 | 0.971 / 0.983 / 0.987 ✅ |
| E3 | 頂點數不比藝術家複雜 | gen nv ≤ art nv | 26≤78 / 32≤80 / 30≤98 ✅ |
| E4 | 生成靜態品質 | `evaluate_mesh` overall_pass | ✅ / ✅ / ✅ |

> 方法論(第四次實踐):評估器先用**藝術家真值自一致性**(E1)確認自己的對齊/量測可信,
> 再對生成物下判定。E1 抓到並修掉「uvs 當 page 正規化」的對映錯誤 —— 若無此閘會誤判生成器壞掉。

## contour 模式(新增於 `generate_mesh_v2.py`)

- **動機**:Award 藝術家對光暈(soft glow/halo,coverage 0.44、凹形不規則邊界)用 **78 頂點全 hull、
  76 三角**的密集邊界多邊形,無內部點。v2 auto 舊行為把非 strip 件丟給 v1 散點 Delaunay,
  對這種件(1)`filter_triangles`(重心過濾)在凹形處砍三角 → **留孤兒頂點**;(2)`epsilon 0.008`
  過度簡化邊界 → **IoU 0.929 < 藝術家 0.98**。
- **做法**:`findContours` → **二分搜 approxPolyDP epsilon** 命中頂點預算(預設 target 56)→
  `triangle 'p'` 約束三角化簡單多邊形(天然尊重凹形,**不需重心過濾** → 0 孤兒)。hull = 全部邊界點。
- **auto 路由**:`aspect ≥ 1.2 且 row-convex` → strip(窗簾/影子沿用,不受影響);否則 → **contour**
  (取代舊 delaunay-v1 fallback)。`mode` 新增 `contour` 可強制;`--target-pts` 可調密度。
- **副產收益**:左手/身體本來走 delaunay-v1(IoU 0.960/0.968),改 contour 後 **0.983/0.987**(反超藝術家),
  頂點更省。contour 對「有明確凹形輪廓、無強拉伸軸」的件是更對的拓樸。

## 無回歸(main_draw 4 mesh)

curtain_left/right + shadow 三個 distinct region **仍走 strip**(mode 未變、IoU 0.933/0.934/0.955、
真實 deform 0 自交/0 翻面全過);shadow2 與 shadow 共用同一 region(非獨立)。contour 是純新增,
只影響非 strip 件 → **strip 路徑零回歸**。

## ⚠️ 範圍與限制(誠實記錄)

- 本次驗的是**靜態覆蓋 + 拓樸格式**對真實 mesh。這 3 件在 Award 是 **weighted(骨骼驅動)、無 deform
  timeline** → 不做逐頂點 deform 閘(逐頂點 deform 穩健性已於 main_draw 窗簾/影子另行驗證)。
  生成的 contour mesh 若進生產需再綁權重(S3 尚無 BBW 權重步驟 — 見 PLAN.md S3 完整定義)。
- Award atlas 貼圖被縮小打包(~0.70),但本流程「切件→生成→比對」全在同一 atlas 尺度內自洽,不受影響。

## 可重現

```
python3 tools/mesh_gen/compare_award_mesh.py          # 3 件 overall_pass, exit 0
python3 tools/mesh_gen/generate_mesh_v2.py <glow.png> --mode contour --target-pts 56
# 無回歸:
for s in image/curtain_left image/curtain_right image/shadow; do
  python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot $s --name $s; done
```

圖:`knowledge/figures/s3-award-contour-mesh.png`(3 件 contour wireframe 疊 alpha,貼合輪廓)。

## 下一步

- **BBW 權重**:contour/strip mesh 目前皆 unweighted;要真正「件→可綁進 spine 的 mesh」需補權重步驟
  (PLAN.md S3 完整定義含 BBW)。可用 Award 真實 weighted mesh 的骨綁作對照真值。
- **切圖→Spine JSON 組裝(SkelToJson)**:把 `PSD名/圖層名` 命名 + size+2px + mesh/region 分配
  (光暈/身體/左手=mesh、右手/頭=region)+ 本次 mesh 生成串成端到端寫出工具。
