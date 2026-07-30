# S3×S4 端到端 — PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh(有真值驗收)

- **結論**:把 S4 切圖(`psd_slice`)與 S3 生成(`generate_mesh_v2`)串成端到端,對 `robot_parts.psd`
  的 3 個 mesh 件(光暈/身體/左手)生成 mesh,並與生產 spine `Award.json` 的**藝術家手做 mesh**
  逐件對照。**3 件全 `overall_pass`**:生成 mesh 覆蓋率 ≈ 藝術家(margin 內或更好)、頂點少 26~55%、
  setup 0 自交、外來真實場(scale-normalized)下 0 自交/0 翻面 ≤ 藝術家。
- **信心**:高(對真實生產 mesh ground truth 比對 + 覆蓋率量測獨立交叉驗證 + 雙負對照確認鑑別力)。
- **階段**:第 2 階段 / S3×S4 里程碑(端到端「PSD→件→mesh」對真實標的驗收)。
- **工具**:`tools/mesh_gen/benchmark_psd_mesh.py`(可重現:`python3 tools/mesh_gen/benchmark_psd_mesh.py`)。

## 結果(2026-07-30)

| 件 | 生成 IoU | 藝術家 IoU | 生成頂點 | 藝術家頂點 | 省 | setup 自交 | deform 探針 gen(si/flip) | artist(si/flip) |
|---|---|---|---|---|---|---|---|---|
| 光暈 | 0.933 | 0.949 | 35 | 78 | 55% | 0 | 0/0 | 0/1 |
| 身體 | 0.966 | 0.948 | 60 | 98 | 39% | 0 | 0/0 | 0/0 |
| 左手 | 0.964 | 0.977 | 59 | 80 | 26% | 0 | 0/0 | 0/0 |

- 3 件皆 `delaunay-v1`(長寬比 < 1.2、非 strip 型 → v2 auto 回退 v1;窗簾式直條拓樸只適用高瘦 warp 件)。
- 生成 mesh 用**遠少的頂點**(26~55% less)達到與藝術家相當的紋理覆蓋率 → S3 對真實 blob 件可用且更精簡。

## ★ 踩過的雷(座標基準,務必記住 — 又一次差點誤判)

初版用藝術家 mesh 的 **local `vertices`** 以 `v/wh+0.5` 映到件像素框算覆蓋率,得藝術家 IoU
**0.47~0.62**(假性偏低,看起來像「藝術家 mesh 蓋不住自己」的荒謬結論)。查因:

- Award mesh 的 local `vertices` **不是**以中心原點、跨滿 `width×height`。光暈 local 跨 **803×781**、
  範圍 x[-489,313] 不對稱,而 `width/height` 只有 708×685 → 有 attachment 層級的偏移/縮放。
- **正確基準 = `uvs`**(region-normalized [0,1] 紋理座標),與 `generate` 的 uv 慣例(u=x/W,v=y/H)
  同一空間。改用 uvs 映到件像素框後,藝術家 IoU = **0.949 / 0.948 / 0.977**(合理)。

> 教訓(延續 stress_field / composite 白底 / atlas derotate 三次前例):**任何跨資產座標比對,
> 先用獨立真值把「參照側」量測校準到合理值,再信 pass/fail。** 這裡的獨立校驗 = 藝術家理應
> 蓋好自己的紋理(IoU 應 ~0.9+),0.47 立即暴露基準錯誤。

## deform 閘設計(件無自身 deform 時的 honest 做法)

這 3 件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform,見 `s4-psd-to-spine-real.md`)
→ 沒有自身真實位移場可當閘。做法:

1. 取 `main_draw` **curtain_left 的真實最大位移場**(315px,經校準的真實場;run.md 守則:
   不用未校準 `stress_field`)。
2. **scale-normalize**:場正規化成「佔 curtain 自身 bbox 對角線比例」(消 px 尺度);
   兩 mesh(生成 + 藝術家)都放進同一單位框(geometry = uv×256)受同一正規化場。
3. 探針幅度 = 「跟 curtain 最硬真實幀一樣猛、等比縮到本件」→ 單位框中最大位移 ~126/256(≈件的 49%)。

結果:此強度外來場下,生成 mesh 3 件全 0 自交/0 翻面,≤ 藝術家(藝術家光暈 fan 拓樸出現 1 flip)。
**標記為外來場探針**(honest:非本件真實運動),僅作拓樸穩健度相對比較,不宣稱動畫手感。

## 評估器可信度(負對照,確認鑑別力)

- **NEG-1(undercoverage)**:粗糙 3 頂點 mesh(epsilon=0.15)覆蓋左手 IoU **0.565** << 藝術家 0.977 → AC_cover 會 fail。
- **NEG-2(cross-piece)**:左手生成 mesh 對「左手 alpha」0.964,對「身體 alpha」**0.521** → 覆蓋率量的是真實輪廓配準,非常數。

兩負對照皆塌陷 → 覆蓋率閘有鑑別力,可信。

## 揭示 / 對契約的補充

- Award mesh 的 `vertices`(local)含 attachment 偏移/縮放,**件內幾何比對一律走 `uvs`**;
  之後 SkelToJson 寫出件→attachment 時,uvs 用 `x/W,y/H`、vertices 用置中(如 `generate.to_spine`)即可,
  但**若要對照既有生產 mesh 的 local 座標,需先知道其 attachment transform**(此處用 uvs 繞開)。
- 生成器對 blob 型件(光暈/身體/左手,aspect < 1.2)走 Delaunay-v1;strip(v2)專屬高瘦 warp 件(窗簾)。

## 下一步候選

- **SkelToJson 組裝**:把「件(size+2px padding + `PSD名/圖層名` slot 命名) + 生成 mesh」固化成一支
  寫出完整 Spine JSON 的工具 → 端到端「PSD → 可用 Spine skeleton」。
- 生成 mesh 的內部頂點佈局可再對齊藝術家的「關節/彎折處加密」策略(目前 Canny+格點;藝術家在會折的地方放點)。
