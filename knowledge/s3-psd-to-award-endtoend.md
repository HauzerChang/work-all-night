# S3 端到端驗收 — PSD 件 → S3 mesh v2 → 對照 Award 真實生產 mesh

- **結論**:把 S4(PSD 切件)與 S3(mesh 生成)**串成端到端**,並第一次對**真實生產 mesh(Award)當真值**驗收。
  `robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手)自動生成的 mesh,**覆蓋率 IoU 全達到或超過藝術家 mesh 基準**
  (margin 0.03),且格式合法、頂點在預算內 → **PSD→件→mesh 這條 pipeline 對真實標的可用**。
- **信心**:高。有真實藝術家 mesh 當真值 + 雙向負對照確認閘的鑑別力。
- **階段**:第 2 階段 / S3×S4 串接(里程碑:合成/單資產 → 生產真值端到端)。

## 做法(`tools/mesh_gen/validate_psd_to_award.py`)

每件:PSD 切件 alpha(`psd_slice`)→ `generate_mesh_v2(auto)` → ① 生成 mesh 覆蓋率 IoU
② Award 藝術家 mesh 對**同一 alpha** 的覆蓋率 IoU(真值基準)③ AC:生成 ≥ 基準 − 0.03、格式合法、頂點 ≤ 預算。

真值對齊依據:PSD 切件與 Award attachment 為**同一素材**(前次 alpha-IoU 0.92~0.99 已證);
兩者 uvs 皆 normalize 到各自 region [0,1],rasterize 到同一張 alpha mask 上比對即座標一致。

## 結果(overall PASS,exit 0)

| 件 | 生成 mode | 生成 v/hull/tri | 藝術家 v/hull/tri | 生成 IoU | 藝術家基準 | 判定 |
|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 35 / 16 / 49 | 78 / 78 / 76 | 0.933 | 0.949 | PASS(margin 內) |
| 身體 | delaunay-v1 | 60 / 20 / 97 | 98 / 40 / 154 | 0.966 | 0.948 | **PASS(勝過藝術家)** |
| 左手 | delaunay-v1 | 59 / 19 / 97 | 80 / 42 / 116 | 0.964 | 0.977 | PASS(margin 內) |

## 關鍵發現

1. **auto-mode 路由正確**:3 件皆為 blobby(aspect < 1.2、非高瘦條狀)→ 全部**落到 v1 Delaunay**。
   印證 v2 的設計:strip 拓樸專給窗簾類單軸拉伸件,blob 件用 Delaunay 散點才對。**同一入口自動選對拓樸**。
2. **生成 mesh 更精簡卻覆蓋相當**:生成 35/60/59 頂點 vs 藝術家 78/98/80,IoU 仍打平或勝出
   (身體 0.966 > 藝術家 0.948)→ 自動拓樸在「覆蓋率/頂點數」性價比上不輸手做。
3. **藝術家 mesh 的頂點多半用在變形自由度,不是覆蓋率**:光暈是純 hull fan(78v=78hull),
   身體/左手 hull 40/42 但總頂點 98/80(大量內部點)。這些頂點是給**骨骼權重變形**用的自由度,
   靜態覆蓋率用不到 → 純覆蓋率評估會低估藝術家意圖,但對「能否生成可用 mesh」的 AC 已足夠。
4. **這 3 件在 Award 無 deform timeline**(weighted,靠骨骼變形)→ **不套真實位移場 deform 閘**
   (無可轉移場;硬套合成場即前述 miscalibration 陷阱)。此處真值 = 靜態覆蓋率 + 格式 + 頂點預算。

## 閘可信度(負對照)

對藝術家 mesh 自身做劣化,確認閘能抓到(baseline − 0.03 為門檻):

| 件 | baseline | uvs 縮 0.7 | uvs 平移 +12%x | 抓到 |
|---|---|---|---|---|
| 光暈 | 0.949 | 0.458 | 0.599 | ✅ |
| 身體 | 0.948 | 0.479 | 0.598 | ✅ |
| 左手 | 0.977 | 0.500 | 0.723 | ✅ |

正對照 = 藝術家 mesh 自身(0.95~0.98,自一致);劣化 mesh 全掉到 0.46~0.72(遠低於門檻)→ 閘有鑑別力、未過頭。

## 局限 / 待續

- 生成 mesh 目前是**unweighted**;真實件靠**骨骼權重**變形。要真正取代藝術家 mesh,還缺 **BBW 權重綁定**
  (S3 路線圖的後半:mesh + BBW 權重 + SkelToJson)。本次只驗「拓樸/覆蓋率」層。
- Award 這批件無 deform timeline → 無法在此資產驗「生成 mesh 的耐變形」。耐變形已在 main_draw 窗簾
  (有 deform)驗過(見 `s3-four-mesh-generalization.md`)。兩資產互補。

## 可重現

```
python3 tools/mesh_gen/validate_psd_to_award.py     # overall PASS, exit 0
```
