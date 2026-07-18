# S3 端到端:PSD件 → mesh → 對照 Award 真實藝術家 mesh(靜態 IoU 閘)

- **結論**:S3 mesh 生成器對**真實生產標的**(Award spine 的 3 個機器人 mesh 件)通過端到端驗收:
  生成 mesh 的靜態輪廓 IoU **≥ 藝術家手做 mesh 基準**,且頂點數 **≤ 藝術家預算**。里程碑:S3 首次對「有真值可比的真實生產 mesh」達標,而非只對 main_draw 自家資產。
- **信心**:高(藝術家基準由真實 uvs+triangles 直接光柵化,為 by-construction ground truth;負對照鑑別力已驗)。
- **相關**:S3(mesh 生成)、S4(PSD→件)、階段二。承 `s3-four-mesh-generalization.md`、`s4-psd-to-spine-real.md`。

## 標的(Award.json 的 `機器人拆件/*`,對應 robot_parts.psd 5 圖層)

3 個 warp 件在 Award 中為 **weighted mesh**(靠骨骼權重動,**無 deform timeline**);2 個剛體件(右手/頭)為 region。

| 件 | 藝術家 mesh | 生成 mesh(v2 auto,eps=0.002) | IoU 對照 |
|---|---|---|---|
| 光暈(glow) | 78v / hull78 / 76tri | 73v / hull38 / 106tri | **0.9832 ≥ 0.9795** ✓ |
| 左手 | 80v / hull42 / 116tri | 67v / hull43 / 89tri | **0.9913 ≥ 0.9681** ✓ |
| 身體 | 98v / hull40 / 154tri | 77v / hull37 / 115tri | **0.9926 ≥ 0.9760** ✓ |

三件 `overall_pass=True`(exit 0)。標準指令:
```
python3 tools/mesh_gen/validate_against_real.py \
  --skeleton assets/Award.json --atlas assets/Award.atlas --png assets/Award.png \
  --slot 機器人拆件/光暈 --name 機器人拆件/光暈 --gen v2 --tmp /tmp/awmesh
```

## 關鍵發現:靜態輪廓 IoU 由 Douglas-Peucker `epsilon` 決定

平行於 strip mesh「IoU 由 rows 決定」的發現 —— **對非 strip(靜態/bone-driven)件,輪廓 IoU 由邊界簡化比例 `epsilon_frac` 決定**:

| epsilon | 光暈 IoU | 左手 IoU | 身體 IoU | 光暈頂點數 |
|---|---|---|---|---|
| 0.008(舊 v1 預設) | 0.929 ✗ | 0.960 ✗ | 0.968 ✗ | 54 |
| **0.002(新操作點)** | **0.983** ✓ | **0.991** ✓ | **0.993** ✓ | 73 |
| 0.001 | 0.992 | 0.996 | 0.995 | 92 |

- 舊預設 0.008 對**有機/羽化邊**(光暈)過粗 → 掉 5% IoU;對硬邊(左右手/身體)也略低於藝術家。
- **0.002 是甜蜜點**:三件都 ≥ 藝術家 IoU,且頂點數(73/67/77)仍 **≤ 藝術家預算**(78/80/98)—— 不是靠灌頂點作弊,而是達到與藝術家相當的精簡度與精度。
- 再細(0.0005)IoU 逼近 1.0 但頂點爆炸(115~250 hull),非必要。

## 落地改動

- `generate_mesh_v2.generate(..., epsilon=0.002)`:非 strip 件走 Delaunay 回退時,epsilon 預設 0.002
  (原 v1 standalone 仍 0.008 不動,避免擾動其自有測試)。strip 路徑不受影響。
- `validate_against_real.py`:偵測 `real_deform_field` 回傳 `frame is None`(無 deform timeline 的 bone-driven 件)
  → deform 閘標 **N/A、pass**,`overall_pass` 只看靜態 IoU;報表新增 `artist_vertices`;新增 `--epsilon`。

## 評估器可信度(先驗再判定)

- **藝術家基準 by construction**:`artist_iou` 直接用 Award.json 真實 uvs+triangles 光柵化 → 即 ground truth。
- **負對照**:粗糙 mesh(eps=0.05)IoU 掉到 0.61(光暈)/0.77(身體),遠低於 ~0.98 門檻 → 閘有鑑別力,非放水。

## 邊界 / 未解

- **deform 穩健性未測**:3 件靠骨骼權重動、無 deform timeline,故 deform 拓樸閘不適用(標 N/A)。
  若日後需驗這類件的 weight-driven warp,需另建「bone-weight 變形」閘(非本輪範圍)。
- 端到端鏈 = S4(PSD→件,alpha-IoU 0.92~0.99 已驗)+ S3(件→mesh,本輪 IoU ≥ 藝術家)。
  兩段共用的「件」為 atlas 抽出的 region(與 PSD 圖層同素材,前輪已證);對齊藝術家 uvs 需用 atlas 座標。
