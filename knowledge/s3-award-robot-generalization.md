# S3 泛化到 Award 機器人 mesh + epsilon 校正(第二份生產資產外部真值)

> 結論:generate_mesh_v2 從 main_draw 4 mesh 推廣到**另一份生產資產**(Award「機器人拆件」
> 光暈/左手/身體,真實 **weighted** mesh)。初測 光暈 覆蓋率不足(gap −0.05);根因是
> 固定 `epsilon_frac` 對羽化/星形輪廓取樣太疏 → 校正為 `epsilon_frac=0.003` + 頂點預算自適應
> (內部點讓位給 hull)後,3 mesh 全達/超越藝術家覆蓋率、全在 64 頂點預算內、全 AC 乾淨。
> **信心:高**(對真實藝術家 mesh 做 apples-to-apples IoU;根因用漏覆蓋像素定位、掃描驗證)。
> 相關階段:第 2 階段 S3。日期:2026-08-05。

## 為什麼做這個(動機)

先前 S3 只在 main_draw 的 4 個 mesh 驗過,有「只在單一資產過擬合」的風險。Award 機器人拆件
在生產 spine 裡是 3 個真實 mesh(光暈/左手/身體),且與 `robot_parts.psd` 逐件對應(S4 已驗),
是**現成的外部真值**。用它驗 S3 = 檢查生成器對「不同美術、不同拓樸」是否仍達藝術家水準。

## 方法(apples-to-apples,同一 atlas region 為單一來源)

`tools/mesh_gen/validate_robot_mesh.py`:
- atlas region(`atlas_crop.extract`,自動選對頁 + CW derotate)→ alpha mask。
- 生成:`generate_mesh_v2(mode=auto)` → IoU_gen(三角填滿 ∩ mask / ∪ mask)。
- 真值:藝術家 `uvs`(region-local [0,1],weighted 亦有效)同法 → IoU_artist。
- AC:`IoU_gen ≥ IoU_artist − 0.03`(對齊藝術家覆蓋率,非武斷 0.95)。

**副產驗證(rotate uv-frame)**:`best_artist_iou` 在 4 種取向(直/翻y × 直/swapXY)取最高並回報。
3 mesh 全選 `y/xy`(原樣)且 art_iou 0.968–0.980 → 確認 **atlas_crop 的 CW derotate 後,
Spine json 的 uvs 直接對齊裁切圖**(rotate region 的 uv 無需再翻/換軸)。這補上了 evaluate_slicing
未涵蓋的「rotate region uv↔pixel 對齊」一環。

## 三個 mesh 都用 delaunay-v1(不是 strip)

光暈 496×480(aspect 0.97)、左手 181×152、身體 267×299 —— 皆非「高瘦 row-convex」→ v2 auto
正確回退 **v1 Delaunay**。所以本回合實際鍛鍊/校正的是 **v1 路徑**(blobby 件),與 main_draw
的 strip 路徑互補。

## 失敗根因:固定 epsilon 對羽化輪廓取樣太疏(光暈)

初測(`epsilon_frac=0.008`):

| mesh | art_iou | gen_iou(舊) | hull(舊) | gap |
|---|---|---|---|---|
| 光暈 | 0.980 | **0.929** | 14 | **−0.050 FAIL** |
| 左手 | 0.968 | 0.960 | 18 | −0.008 pass |
| 身體 | 0.976 | 0.968 | 21 | −0.008 pass |

診斷光暈:region 496×480、**33% 像素半透明(soft edge,glow)**、無內部洞。
生成 mesh 漏覆蓋 **6364 px**(over 僅 1186;藝術家漏 13)→ 是 hull 剪掉星形凸角、
往內切造成。藝術家用 **78 hull 點**精描;v1 的 `approxPolyDP(0.008·peri)` 只給 **14 點**。

**關鍵洞見:覆蓋率(IoU)由 hull 取樣密度決定,內部點不影響覆蓋**(內部點只服務 deform 拓樸)。
epsilon 掃描(光暈):eps 0.008→0.003→0.002 = hull 14→32→38 = IoU 0.929→0.978→0.983。

## 校正(generate_mesh.py v1)

```python
def generate(path, max_interior=40, epsilon_frac=0.003, ..., vertex_budget=64):
    hull = boundary_points(mask, epsilon_frac)          # 0.008 → 0.003:hull 更密、貼羽化邊
    interior_budget = max(0, min(max_interior, vertex_budget - len(hull)))  # 內部點讓位給 hull
    inter = interior_points(..., interior_budget, ...)
```

兩處改動互補:降 epsilon 讓 hull 貼緊輪廓(修覆蓋);預算自適應把內部點收成 `budget − n_hull`,
保住總頂點 ≤64(內部點不影響覆蓋、故先讓位)。

校正後(全 PASS,全 ≤64v,evaluate_mesh 全 6 條 AC 乾淨):

| mesh | art_iou | gen_iou(新) | hull | nv | gap |
|---|---|---|---|---|---|
| 光暈 | 0.980 | 0.978 | 32 | 64 | −0.002 ✅ |
| 左手 | 0.968 | **0.987** | 36 | 59 | +0.018 ✅ |
| 身體 | 0.976 | **0.988** | 31 | 64 | +0.012 ✅ |

## 無回歸

改動只在 v1(delaunay)路徑。main_draw 4 mesh 皆走 **strip 模式**(不碰 v1 epsilon)→
`validate_against_real --gen v2` 對 curtain_left/right/shadow 仍 overall_pass、mode=strip、deform 乾淨。
(shadow2 與 shadow **共用同一 region `image/shadow`**,靠 `--name` 傳 region 名時要用 `image/shadow`;
這是既有命名慣例,非本次回歸。)

## 誠實的限制 / 下一步

- ⚠️ **weighted mesh 的 real-deform 閘尚未支援**:`deform_eval` 的 `load_mesh`/`real_deform_field`
  用 `reshape(-1,2)`,只對 **unweighted** 正確;Award 機器人 mesh 全 weighted(vertices 為變長
  bind 格式),故本回合**只驗靜態覆蓋率**,未驗這些 mesh 在真實動畫下是否耐變形。
  → 下一 chunk:讓 deform_eval 能解析 weighted vertices(算出 setup-pose local 座標 + 對映
  deform offset),對 Award 機器人 mesh 跑真實位移場轉移閘,補上「變形穩健」這一半。
- 覆蓋率達標 ≠ deform 達標(main_draw 已學過此教訓:靜態高但拉伸自交)。故 weighted deform 閘是
  讓「PSD→件→mesh」對機器人**完整**驗收的必要下一步。
