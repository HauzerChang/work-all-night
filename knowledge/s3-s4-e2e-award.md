# S3+S4 端到端:PSD 件 → 生成 mesh → 對照 Award 真實藝術家 mesh(里程碑)

- **結論**:把 S4(PSD 切件)與 S3(mesh 生成)串成端到端,並用**真實生產真值**(big win
  spine `Award` 的藝術家 weighted mesh)對照。三個機器人 mesh 件(光暈/身體/左手)**全部 AC1
  通過**:生成 mesh 的輪廓保真(IoU vs 件 alpha)>= 藝術家 mesh 自身的包覆基準 - 0.02,且用
  更少頂點覆蓋同一 footprint。
- **信心**:高(外部真值 = 生產檔;純 CPU 可重現)。
- **相關階段**:第 2 階段(S3 mesh / S4 切圖),為第 3 階段 pipeline 的端到端骨幹。
- **工具**:`tools/mesh_gen/e2e_psd_award.py`(標準指令 `python3 tools/mesh_gen/e2e_psd_award.py`)。
- **圖**:`knowledge/figures/e2e-psd-award-mesh.png`(左=藝術家橘線框,右=生成綠線框)。

## 數據(2026-07-14)

| 件 | 藝術家 頂點/三角/hull | 藝術家 IoU(vs alpha) | 生成 頂點/三角/mode | 生成 IoU | 生成↔藝術家覆蓋 IoU | AC1 |
|---|---|---|---|---|---|---|
| 光暈 | 78 / 76 / **78(全 hull)** | 0.9486 | 35 / 49 / v1 | 0.9331 | 0.9179 | ✅ |
| 身體 | 98 / 154 / 40 | 0.9477 | 60 / 97 / v1 | 0.9660 | 0.9284 | ✅ |
| 左手 | 80 / 116 / 42 | 0.9768 | 59 / 97 / v1 | 0.9642 | 0.9572 | ✅ |

- 三件在 `generate_mesh_v2` auto 模式下皆走 **v1(Delaunay)**:長寬比 <1.2(近方形),
  非 strip 適用形狀。生成頂點數約藝術家的 45–75%,更精簡而輪廓不輸。
- 光暈藝術家 mesh 是**純外框環**(78 頂點全為 hull、無內部點)—— glow 素材典型做法。

## 兩個關鍵確認

1. **uv → region 局部座標的方向慣例確定**(解掉 log 006 留的開放問題):Award mesh `uvs` 為
   region 局部 0..1,乘件影像 W/H **直接對映(不翻 y)** 就對齊藝術。實測 direct vs flip-y 的
   IoU 差距 0.34–0.52(光暈 0.9486 vs 0.4264),毫無歧義。與 `validate_against_real.artist_iou`
   既有慣例一致。
2. **件尺寸 ↔ attachment 尺寸**:PSD 圖層 size 與 Award attachment `width/height` 差 +2px
   (光暈 706×683 ↔ 708×685;身體 379×425 ↔ 381×427;左手 257×215 ↔ 259×217),即 s4 已知的
   +2px padding。本工具用件影像自身 W/H 對映 uvs,規避 padding 位移。

## 限制 / 待續

- **只做靜態輪廓**:Award 三件皆 **weighted(骨驅動 skinning,無 deform timeline)**,故無法用
  `deform_eval.transfer_deform_check`(那是 unweighted deform 位移場轉移)對照變形。
  weighted deform 對照需另寫「bone bind-pose skinning 重現」,列為下一 chunk。
- 生成 mesh 目前為 **unweighted**;要真正取代藝術家 weighted mesh,需 S3 補權重(BBW / heat)
  並綁到 Award 骨架 —— 屬更後段能力。
- 本閘度量的是「輪廓/覆蓋保真 + 頂點預算」,不度量「拓樸是否耐 weighted deform」。
