# S3 端到端對真實生產標的驗收 — Award 機器人拆件 mesh(靜態幾何)

- **結論**:把 S3 mesh 生成器接到**真實生產 spine(Award,big win)**的 3 個 mesh 件
  (`機器人拆件/光暈 | 身體 | 左手`),對照藝術家真值做靜態幾何驗收 → **3 件全 overall_pass**
  (生成 IoU ≥ 藝術家自身覆蓋率 + 0 退化/0 孤兒/重心全在 mask 內/合法 Spine 格式)。
  端到端「真實 atlas 切件 → S3 mesh → 對照真實藝術家 mesh」對生產標的成立。
- **依據**:`tools/mesh_gen/validate_award_static.py`(exit 0)。
- **信心**:高(評估器先以藝術家真值自一致性校準;3 件都有 ground-truth mesh 可比)。
- **階段**:第 2 階段 / S3(里程碑:合成/main_draw → 真實生產 Award)。

## 這批標的與 main_draw 的關鍵差異

| | main_draw 4 mesh | Award 機器人 3 mesh |
|---|---|---|
| 權重 | unweighted | **weighted** |
| deform | 9 anim 全有逐頂點 deform timeline | **無 deform timeline**(靠骨骼權重變形) |
| 密度 | 12~21 頂點(粗) | **78~98 頂點**(密、複雜輪廓) |
| atlas | rotate=false | 光暈/身體 **rotate=true**(atlas_crop derotate 對齊) |

→ 兩點方法論後果:
1. **不能用真實位移場 deform 閘**(`transfer_deform_check` 需 deform timeline)。這裡只驗**靜態幾何**;
   deform 穩健性留待有位移場的標的,**不用未校準的合成壓力**(RULES 明令,避免假性結論)。
2. **頂點預算是 per-asset**:`evaluate_mesh` 預設 budget=64 是 main_draw 粗網格校準的;
   Award 藝術家自己就用 78~98v → AC3 對這批不是通用 fail,適當預算 ≈ 藝術家密度(~100)。

## 評估器可信度先驗(校準,關鍵前置)

延續一貫教訓「判好壞前先驗評估器」。把**藝術家自己的 uvs** 用 `uvs*(W,H)` 光柵化,量對
atlas 切件 alpha 的自身 IoU:光暈 **0.9795** / 身體 **0.9760** / 左手 **0.9681**。
高自身 IoU 證明「atlas 切件 ↔ 藝術家 uvs」座標映射正確(含 rotate=true 件由 atlas_crop 對齊)。
殘差 ~0.02~0.03 為多邊形 vs 羽化邊的固有覆蓋差 → 以此為**判定基準**,非武斷 0.95。

> 副帶校驗:身體 uv-x 只到 0.759(非 ~1.0),初看疑似座標系錯位;但自身 IoU 0.976 證明
> 只是該件在 atlas region 內未占滿寬度,映射正確。**先校準才不會被表象誤導。**

## ★ 核心發現:dense 件 IoU 由「邊界簡化 epsilon」決定(Delaunay 版)

v1 Delaunay 的 hull 來自 `approxPolyDP(epsilon_frac*peri)`。預設 `epsilon_frac=0.008` 對這批
複雜輪廓太粗(hull 僅 14~21),IoU 差藝術家 0.05(光暈)。epsilon 掃描(對 3 件):

| epsilon_frac | 光暈 hull/IoU | 身體 hull/IoU | 左手 hull/IoU |
|---|---|---|---|
| 0.008(舊預設) | 14 / 0.927 ✗ | 21 / 0.969 ✗ | 18 / 0.960 ✗ |
| 0.004 | 22 / 0.962 ✗ | 29 / 0.986 ✅ | 30 / 0.982 ✅ |
| **0.002** ✅ | **38 / 0.983** | **37 / 0.993** | **43 / 0.991** |
| 0.001 | 58 / 0.992(過密) | 60 / 0.995 | 84 / 0.996 |

- **`epsilon_frac=0.002` 是甜蜜點**:3 件全過藝術家 IoU,hull 37~43 ≈ 藝術家精簡度。
- 這是 v2 strip「IoU 由 rows 決定、cols(內部)不影響覆蓋率」在 **Delaunay 版的對應**:
  **IoU 由邊界取樣密度(strip=rows / delaunay=1/epsilon)決定,內部頂點不影響覆蓋率。**
  驗證:validate_award_static 用預設 interior(較少內部點)時生成僅 67~77v(甚至 < 藝術家),
  IoU 仍 0.983~0.993 全過 → 覆蓋率確實只吃邊界密度。

## 生成器改動(落地此發現)

`generate_mesh_v2.generate(..., epsilon_frac=None, max_interior, min_dist)`:新增把 epsilon 等
參數透傳到 v1 Delaunay 路徑;CLI 加 `--epsilon`。dense/複雜件建議 `0.002`,一般件維持 0.008。
**不改 auto 預設**(避免影響已驗收的 main_draw 4 mesh 與合成件);由呼叫端按件複雜度指定。

## 可重現

```
python3 tools/mesh_gen/validate_award_static.py            # 3 件 all_pass, exit 0
python3 tools/mesh_gen/generate_mesh_v2.py <piece.png> --epsilon 0.002
```

## 下一步候選

- **端到端組裝(SkelToJson)**:把 `PSD名/圖層名` 命名 + size+2px padding + 每件 mesh/region 分配
  + dense 件 epsilon=0.002,固化成「PSD 件 → Spine attachment JSON」寫出工具,產可載入的 spine。
- **weighted mesh 權重生成(BBW)**:目前生成 unweighted;Award 這批是 weighted → 下個能力缺口是
  骨骼綁定 + 權重(S3 路線的 BBW 部分),需骨架(S5)先有骨。
- deform 穩健性:等有 deform timeline 的真實件(或使用者確認可對這批施加參考變形)再驗。
