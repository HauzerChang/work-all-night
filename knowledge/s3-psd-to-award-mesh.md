# S3 端到端驗收 — PSD 件 → 生成 mesh vs Award 藝術家真值(里程碑)

- **結論**:把 `robot_parts.psd` 切出的 3 個「在 Award 為 mesh」的件(光暈 / 左手 / 身體)
  跑 S3 `generate_mesh_v2`,與 **Award 生產 spine 的藝術家 mesh** 對照。生成 mesh 的覆蓋率 IoU
  **≈ 或優於藝術家**,且用 **少 20–35% 頂點**、全在 64 頂點預算內。首次把「PSD→件→mesh」
  對真實生產標的端到端驗收成功。
- **信心**:高(對真實生產件 + 藝術家 ground truth 雙向量化 + 目視疊圖確認)。
- **階段**:第 2 階段 / S3 × S4 串接(里程碑)。

## 對照結果(覆蓋率 IoU 各量在自己的輪廓上,尺度不變公平)

| 件 | 藝術家 nv / hull / IoU | 生成 nv / hull / IoU | 頂點節省 |
|---|---|---|---|
| 光暈 | 78 / 78 / **0.980** | 54 / 45 / **0.983** | 31% |
| 左手 | 80 / 42 / **0.968** | 64 / 30 / **0.980** | 20% |
| 身體 | 98 / 40 / **0.976** | 64 / 23 / **0.971** | 35% |

- 藝術家 mesh:`uvs`(region-local、v-down)× **atlas 裁出的自身貼圖 alpha**(`atlas_crop`)。
- 生成 mesh:`generate_mesh_v2` 頂點 × **PSD 切件 alpha**。
- 疊圖:`knowledge/figures/s3-psd-to-award-mesh.png`(左紅=藝術家、右綠=生成)。

## ★ 關鍵發現 1:固定 epsilon 不通用 → 改「自適應 epsilon + 預算感知內部點」

初跑 v2(auto → 這 3 件皆非高瘦,走 v1 Delaunay 回退):
- **光暈 IoU 0.933 FAIL** — 大而平滑的光暈(46% bbox 覆蓋、~40px 羽化圓弧輪廓),
  預設 `epsilon_frac=0.008` 只給 hull 16,16-gon 內切圓弧 → 覆蓋不足。
- eps 掃描:0.008→0.933、0.004→0.961、**0.002→0.980(nv 64 剛好過)**、0.001→0.992 但 **nv 81 爆 64 預算**。
- 但同樣把 eps 降到 0.002,**左手/身體反而爆預算**(hull 暴增 + 固定 40 內部點)。

**根因**:靜態覆蓋 IoU **只由 hull(邊界)決定,內部點完全不影響**(內部點只影響 deform)。
v1 固定花 40 個頂點在內部點,對覆蓋率零貢獻卻吃掉預算。件大小/周長不同,固定 epsilon 無法兼顧。

**修法(`generate_mesh.generate_auto`,並設為 v2 非 strip 件的回退)**:
1. epsilon 由粗到細沿梯度試,用「hull polygon 填滿 vs mask」的內建 IoU 自測,
   達 `iou_target=0.97` 即停(或 hull 逼近預算上限即停)。→ **先用 hull 買到覆蓋率**。
2. `max_interior = budget - n_hull`。→ **剩餘預算才給內部點**。

修後 3 件全 PASS 且在預算內(見上表)。這是比固定參數更通用的 v1。

## ★ 關鍵發現 2:Award mesh `uvs` 是 region-local [0,1]、且已「上正」(rotate 旗標與 uvs 無關)

- Award mesh 為 **weighted**(`len(vertices) != 2*nv`;285/278/369 筆 bind 資料),
  故**不能**直接把 `vertices` 當座標(要套骨骼變換)。改用 `uvs` 對貼圖比對。
- `uvs` 經多件驗證是 **region-local(0..1 在該 region 內)**,不是頁面正規化
  (左手 u∈[0.008,1.000] 幾乎填滿;若是 2040 頁面正規化不可能)。
- **rotate:true 對 JSON `uvs` 無影響**:光暈/身體 atlas `rotate:true`,但自校準 8 朝向中
  **rot0(不轉)IoU 最高** → uvs 存的是上正座標,旋轉只發生在 atlas 打包、runtime 還原。
- **v 軸為 v-down**(與影像 y 一致):v-down IoU 0.97–0.98,v-up 掉到 0.44–0.61。
- ⚠️ **陷阱**:把藝術家 mesh 疊到 **PSD 切件 alpha** 會因「atlas region 框 ≠ PSD 緊貼裁切框」
  (+2px padding、裁切基準不同)出現假性低 IoU(身體曾量到 0.64)。**必須疊在 uvs 真正索引的
  atlas 裁件貼圖上**(`atlas_crop` 取,經 s006 CW 校正),才反映 mesh 本身品質。

## 拓樸差異(供 deform 課題參考)

- 藝術家內部點沿**機體內部視覺邊界**分布(左手/身體可見成列);生成內部點走 Canny+格點。
- 光暈藝術家用 **78 點全 hull(0 內部)**——純外框 mesh;生成用 45 hull + 9 內部達同覆蓋。
- 這 5 件在 Award **無 deform timeline**(靠骨骼權重變形)→ 本輪無法用真實位移場做 deform 閘;
  變形穩健性對照留待「有 deform 的件」或合成位移場。

## 可重現

```
export PYTHONPATH=tools/mesh_gen
python tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts   # 切件
python tools/mesh_gen/generate_mesh_v2.py /tmp/robot_parts/03_身體.png -o /tmp/身體_gen.json
python tools/mesh_gen/evaluate_mesh.py /tmp/身體_gen.json /tmp/robot_parts/03_身體.png
# 對照藝術家:見 scratchpad/compare_final.py(atlas_crop + uvs region-local, v-down)
# 也可單獨用自適應 v1:python tools/mesh_gen/generate_mesh.py <png> --auto
```

## 下一步

- 把「件→Spine JSON 組裝」固化(SkelToJson):`PSD名/圖層名` 命名 + size+2px padding +
  mesh/region 分配 + 這裡的自適應 mesh 生成,端到端產出 Spine mesh attachment。
- deform 穩健性:找有 deform timeline 的 mesh 件(如 main_draw 窗簾)做真實位移場對照,
  或對機器人件加合成位移場;比較藝術家「沿內部邊界佈點」vs 生成佈點的耐變形差異。
