# spine-asset-forge — 產線數學 / 座標契約 / round-trip 參考

本檔是 `spine-asset-forge` 的技術底:座標約定、atlas 打包、mesh uv、round-trip 驗收數學。
真相以 `assets/*.py` 原始碼與 `validate_build.py` 即時輸出為準;本檔為人讀參考。

## 1. 管線總覽

```
分層 PSD
  │  psd_slice.slice_psd         (每層 → 件 PNG + offset/size/opacity/z;無損)
  ├─ analyze_target.analyze      (五段規格:件清單 / mesh-vs-region / z序 / pivot草案 / 分鏡先驗)
  │                               genre_priors 提供分鏡節拍先驗(本靜態線不產 animation)
  ├─ generate_mesh_v2.generate   (mesh 件 → strip 拓樸:vertices/uvs/triangles/hull)
  │                               (--weighted 時另走 generate_weighted_mesh:輪廓 PCA 軸骨 + heat 權重)
  └─ build_spine                 (shelf 打包 atlas + 組 Spine 3.8 skeleton JSON)
        → skeleton.json + skeleton.atlas + skeleton.png   (標準三件組,可直接載入)

validate_build:  由「產出的 json+atlas+png」重建 setup pose,比對原 PSD composite。
```

## 2. 座標約定(builder 與 validator 必須完全一致)

- 影像:**左上原點、y 向下**。
- Spine:root 置**畫布左下、y 向上**。
- 某件影像中心 `(cx, cy)` → 其 bone `x = cx`, `y = H − cy`,`parent = root`。
- region / mesh 的頂點與 uv **皆相對該 bone**;`generate_mesh_v2` 已把拓樸置中 + y 上翻,故直接吻合 bone 局部座標。

> 任一側座標公式改動都會讓 round-trip MAE 飆高 —— 這正是 round-trip 閘能抓到產線回歸的原因。

## 3. atlas 打包

- **shelf packing**:各切件沿列擺放,`rotate` 全 false(避免 90° 旋轉 uv 的額外轉換)。
- 寫出 libgdx `.atlas`(size/format/filter/repeat header + 每 region 的 xy/size/orig/offset/index)。
- **mesh uvs 為 region-local**:相對該件在 atlas 的子矩形,不是 atlas-global 0..1。這是 Spine mesh 的慣例,
  也是早期踩過的雷(見 repo `knowledge/` 分析器發現)。

## 4. mesh vs region 判定

- `analyze_target` 依件的形狀/語意決定走 **mesh**(可變形,如布料/光暈/軟件)或 **region**(剛性矩形貼圖)。
- mesh 件:`generate_mesh_v2` strip 拓樸;IoU 由 rows 決定、cols 不影響覆蓋率(`rows=10,cols=3`=30v 為預設)。
- region 件:矩形 region,四角 uv。

## 5. weighted(骨綁)mesh(`--weighted`)

- 由件輪廓抽 PCA 主軸 → 佈軸骨 → **heat-diffusion(BBW 近似)**算每頂點對各骨權重(和=1)。
- 全域骨 index 對齊;`vertices` 格式為 `[骨數, boneIdx,bindX,bindY,weight, ...]` 變長攤平(hull 頂點排最前)。
- 結構件(身體/手)si=0、輪廓 IoU 高;**軟性件(光暈極端 reveal)未追平為已知限制**。
- 骨綁變形品質用 `spine-mesh-doctor` 的 `weighted_deform_eval` / `validate_weighted_deform` 量化(本 skill assets 內也含該 eval 以供 weighted 產線自驗)。

## 6. round-trip 驗收數學(`validate_build.py`)

重建流程:讀 bone 座標 → 由 atlas 取各件貼圖 → 依 z 序(由下而上)premultiplied-alpha 疊合 → 得重建 composite。
與原 PSD composite 逐像素比:

| AC | 指標 | 門檻 | 意義 |
|---|---|---|---|
| AC1 | 未解析 attachment 數 | = 0 | json 引用的 region/mesh 都能在 atlas+skin 找到 |
| AC2 | 結構完整(bones/slots/skin 齊備、可載入) | — | 產出是合法 Spine 3.8 骨架 |
| AC3 | `premult_rgb_mae` / `alpha_mae` | RGB < 3.0 | 重建 == 原圖(premult 對齊) |
| AC4 | `orphan_ratio`(原有不透明但重建無覆蓋) | < 0.01 | 無漏件 / 無錯位 |

真實基準(兩標的皆 `overall_pass: true`):

| 標的 | 件數 | bones/slots | 未解析 | premult MAE | 孤兒率 |
|---|--:|---|--:|--:|--:|
| robot_parts | 5 | 6/5 | 0 | 0.031 | 0.0 |
| Symbol_Ww | 18 | 19/18 | 0 | 0.236 | 0.0 |

## 7. 本 skill 不含(誠實邊界,見 SKILL.md)

- **animation / weighted deform timeline / pivot rig** —— 屬 `spine-anim-forge`(repo 內仍 HOLD:運動基元為手感先驗,未達 L3)。
- **平面未分層圖自動拆件** —— CPU 到頂語意召回 0,需 GPU/人工;本 skill 的輸入契約是**分層 PSD**。
