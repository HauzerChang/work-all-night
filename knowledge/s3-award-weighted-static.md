# S3 對第二個生產骨架(Award)的 weighted mesh 靜態驗收 + contour 模式

- **結論**:S3 v2 auto 生成器現對 **Award 的 3 個真實 weighted 機器人 mesh(光暈/左手/身體)靜態覆蓋率全過且超越藝術家**,
  頂點更精簡。關鍵是新增的 **contour 模式**(外輪廓 loop + 受約束 PSLG 三角化),
  專治凹形/尖刺形(藝術家對這類正是用「全 hull 邊界環」hull==nv)。
- **依據**:`tools/mesh_gen/validate_award_static.py`(真值 = Award 藝術家 weighted mesh 的 `artist_iou`,只吃 uvs/triangles → 與權重無關,可信)。
- **信心**:高(靜態覆蓋);⚠️ **變形未驗**(見下「重要限制」)。
- **階段**:第 2 階段 S3(mesh 生成器)+ S4 對接(件→mesh 對真實生產標的)。

## 量化結果(2026-07-18)

| part | solidity | mode | gen nv | gen IoU | artist nv | artist IoU | 判定 |
|---|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | 0.793 | contour | 45 | **0.986** | 78 (hull78) | 0.980 | ✅ 超越 |
| 機器人拆件/左手 | 0.889 | contour | 42 | **0.990** | 80 | 0.968 | ✅ 超越 |
| 機器人拆件/身體 | 0.873 | contour | 45 | **0.994** | 98 | 0.976 | ✅ 超越 |

- 三件皆 setup 0 自交 / 0 退化 / 0 孤兒;Spine 格式合法(unweighted 輸出、hull==nv 全邊界,與藝術家同構)。
- **迭代歷程(AC-first)**:先跑 auto→2/3 過,光暈 fail(delaunay-v1 覆蓋 0.929 < 目標 0.96,且產生 1 個孤兒頂點)。
  診斷 = 光暈是尖刺凹形(射線),散點 Delaunay 切掉凹處。→ 加 contour 模式後 3/3 過。

## contour 模式(新增於 `generate_mesh_v2.py`)

- `gen_contour`:`findContours(external)` 取最大輪廓 → `approxPolyDP`(二分 epsilon 讓邊界點數落在 target..budget)
  → `triangle.triangulate(...,'p')`(PSLG,不加 Steiner 點)。凹多邊形被正確填滿,`nv==邊界點數==hull`。
- **auto 選擇**:`aspect≥1.2 且 row_convex → strip`;否則 `solidity<0.9 → contour`;再否則 → delaunay-v1。
- `solidity(mask)=area/convexHullArea`,低 = 有凹角/尖刺。
- **無回歸**:main_draw 4 個 unweighted mesh 仍全過(curtain_left/right/shadow/shadow2 走 strip,不受影響;
  標準指令見下)。contour 只在低 solidity 非 strip 形狀觸發。

## ⚠️ 重要限制:weighted mesh 的 deform 閘尚未驗

- `deform_eval` 目前假設 **unweighted**(`vertices.reshape(-1,2)`、offset 直接逐頂點加)。
  Award 3 mesh 全 **weighted**(`vertices` 為 `[boneCount,boneIdx,bindX,bindY,weight,...]` 攤平格式,
  deform timeline 的 offset 也在 packed 空間)。**直接套用會誤判**,故本次只做「靜態輪廓覆蓋」。
- **下一個 bounded chunk**:weighted-aware deform 閘 —— 需
  ① 正確解析 weighted `vertices`(每頂點 boneCount→bind 座標+權重);
  ② deform offset 對 packed 陣列的映射;③ 用骨變換算世界座標(或至少 local bind-space 位移)後套 `check()`。
  完成前,contour mesh 對 weighted 標的「耐變形」屬未證。

## 標準重跑指令

```
python3 tools/mesh_gen/validate_award_static.py          # Award 3 weighted 靜態,exit 0 = 全過
# main_draw 回歸(4 mesh,shadow2 的 region 名是 image/shadow):
for m in image/curtain_left image/curtain_right image/shadow; do
  python3 tools/mesh_gen/validate_against_real.py --slot "$m" --name "$m" --gen v2; done
python3 tools/mesh_gen/validate_against_real.py --slot image/shadow2 --name image/shadow --gen v2
```
