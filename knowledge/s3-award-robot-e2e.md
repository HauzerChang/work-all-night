# S3 端到端里程碑:PSD件 → generate_mesh → 對照 Award 真實生產 mesh

- **結論**:把 S4(PSD 切件)與 S3(mesh 生成)串成端到端,對**真實生產標的**(Award「機器人拆件」
  的 3 個 mesh 件:光暈 / 身體 / 左手)驗收 —— 自動生成的 mesh 覆蓋率**達到藝術家手做 mesh 的水準
  (誤差 ±0.02 內,身體甚至更高),而頂點數明顯更省、0 退化三角**。這是 S3 首次在
  `main_draw` 以外的真實資產、且**有藝術家真值可比**的驗收。
- **信心**:高(對真實生產 spine 的藝術家 mesh 交叉比對 + 評估器先以藝術家真值校準)。
- **階段**:第 2 階段 / S3×S4 整合(端到端 PSD→件→mesh)。

## 端到端流程(純 CPU,可自驅)

```
robot_parts.psd
  → psd_slice.py -o /tmp/robot_parts        # 5 件緊湊 PNG + manifest(切圖無損已驗)
  → generate_mesh_v2.py (mode=auto)         # 每件 PNG alpha → Spine mesh
  → 覆蓋 IoU vs 件 alpha,對照 Award 藝術家 mesh 對同件 alpha 的覆蓋 IoU(baseline)
```

一鍵重現:`python3 tools/mesh_gen/validate_against_award.py`(overall_pass=true)。

## 量化結果(margin=0.02)

| 件 | piece px | 模式 | 藝術家 nv / IoU | 生成 nv / IoU | ΔIoU | 退化△ | pass |
|---|---|---|---|---|---|---|---|
| 光暈 | 706×683 | delaunay-v1 | 78 / 0.9486 | **35** / 0.9331 | −0.0155 | 0 | ✅ |
| 身體 | 379×425 | delaunay-v1 | 98 / 0.9477 | **60** / 0.9660 | **+0.0183** | 0 | ✅ |
| 左手 | 257×215 | delaunay-v1 | 80 / 0.9768 | **59** / 0.9642 | −0.0126 | 0 | ✅ |

- 生成 mesh 用 **45~56% 的頂點**達到相當覆蓋率;身體覆蓋率反而略勝藝術家(生成內部三角更均勻)。
- 光暈 −0.0155 的殘差來自**柔性羽化邊**:glow 外緣 alpha 漸淡,生成 hull 未完全包到最外圈半透明像素
  (藝術家 hull=78 全為外周點,貼得更緊)。仍在容差內。視覺對照見 `figures/s3-award-robot-mesh.png`
  (橘=藝術家、綠=生成,皆貼合輪廓)。

## 兩個確立的事實(修正/佐證先前 knowledge)

1. **Award mesh 的 `uvs` 是 region-local 0..1**(相對件自身矩形),不是 atlas-page 座標。
   佐證:把藝術家 uvs×[件W,件H] 疊到 psd_slice 切出的件 alpha,IoU=0.948/0.948/0.977(高度吻合)。
   → `s4-psd-to-spine-real.md` 內「uvs 為 atlas UV 需轉 region」一語不精確,此處以實測更正:
   直接當 region-local 用即可對齊件 alpha。
2. **psd_slice 切件 = Award mesh 對應素材**:件 alpha 與藝術家 mesh 覆蓋高度重合,和先前
   texture 級 alpha-IoU 0.92~0.99 一致 → PSD↔spine 素材同源再獲確認。

## ⚠️ 適用範圍與未驗項(誠實標註)

- 這 3 件在 Award **無 deform timeline**(靠骨骼權重變形,非逐頂點 deform)→ 本次**只驗靜態覆蓋
  + 頂點預算 + 拓樸健全**,**未驗 deform 耐受度**。deform 穩健性已在 `main_draw` 4 個 curtain/shadow
  mesh 用「真實位移場轉移」驗過(見 `s3-four-mesh-generalization.md`),兩者互補。
- 3 件長寬比皆 <1.2 → `generate_mesh_v2` auto 模式**回退 v1 Delaunay**(strip 條件不成立)。
  即本次驗的是 **v1 的靜態覆蓋通用性**,非 v2 strip。對這類「roundish、非強單向拉伸」件,v1 適用。
- 覆蓋 IoU 用三角光柵化面積,對半透明羽化邊以 alpha>8 二值化 —— glow 這類軟邊會有系統性小低估
  (對藝術家與生成一致,不影響相對比較)。

## 產出

- `tools/mesh_gen/validate_against_award.py`(端到端 AC,獨立可跑,exit code 反映 pass)
- `knowledge/figures/s3-award-robot-mesh.png`(藝術家 vs 生成 mesh 疊圖,3 件)

## 下一步候選

- 把「件→Spine mesh attachment」寫出組裝工具(SkelToJson):套用已知慣例(`PSD名/圖層名` slot、
  size+2px padding、mesh uvs region-local、atlas 0.70 縮放),端到端產出可載入的 Spine JSON 片段。
- 或補 S2 補圖閘 / 骨架閘(S2 樞紐尚缺兩閘)。
