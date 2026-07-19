# S3 對照 Award 真實 mesh：weighted 件 + v1 epsilon 校準

> 結論：把 S3 生成器對「第二份真實生產 spine(Award 機器人拆件)」的 3 個 mesh 件驗收。
> 揭示新 regime(weighted、無 deform、面/環狀而非直條),據此(1)修 toolchain 對 weighted+無 deform
> 的崩潰,(2)以真值校準 v1 邊界取樣密度。信心:高(對真實藝術家 mesh 基準量測)。相關:S3 / S2。

## 標的(assets/Award.json，機器人拆件 big win 主角，對應 robot_parts.psd)

| slot/attachment | 藝術家 mesh | weighted | deform | region page |
|---|---|---|---|---|
| 機器人拆件/光暈 | 78v / hull78 / 76tri | ✅ | ❌ 無 | Award2.png |
| 機器人拆件/左手 | 80v / hull42 / 116tri | ✅ | ❌ 無 | Award.png |
| 機器人拆件/身體 | 98v / hull40 / 154tri | ✅ | ❌ 無 | Award2.png |

## 兩個新發現(相對先前 main_draw 4 mesh)

1. **weighted + 無 deform regime**：main_draw 4 mesh 全 unweighted 且每支動畫都有 deform;
   Award 這 3 件相反 —— **weighted(vertices 長度 570/556/738 ≠ uvs×2)、且無任何 deform timeline
   (靠骨骼驅動)**。`光暈` hull=78=verts(純環狀,無內部點)。
   → 位移場轉移閘(`transfer_deform_check`)不適用;硬跑會 shape 崩潰。
2. **v1 邊界取樣過粗**：3 件都不夠高瘦(aspect 0.84~1.12 < 1.2)→ v2 auto 回退 v1 Delaunay。
   v1 舊預設 `epsilon_frac=0.008` 產出 hull 只有 14~21,IoU **低於**藝術家基準(fail)。

## 修正

- **toolchain(weighted/無 deform 不再崩潰)**：
  `deform_eval.real_deform_field` 先偵測 has_deform,無 → 回傳 `field=None`;weighted+有 deform → 明確
  `NotImplementedError`(setup 需 bone 綁定變換,尚未支援)。`validate_against_real` 見 `field is None` →
  `AC_real_deform.applicable=false`(標「bone-driven; deform-transfer N/A」),`overall_pass` 只看 IoU;
  並回報 `artist_mesh`(頂點/hull/tris/weighted)供對照。
- **v1 邊界密度校準**：`generate_mesh.generate` 預設 `epsilon_frac` 0.008 → **0.002**。

## 校準掃描(對藝術家真值 IoU 基準)

| eps | 光暈 IoU/nv/hull | 左手 IoU/nv/hull | 身體 IoU/nv/hull | 判定 |
|---|---|---|---|---|
| 0.008(舊) | 0.926 /74/14 | 0.960 /78/18 | 0.970 /81/21 | 全 fail |
| **0.002(新)** | **0.983 /73/38** | **0.991 /67/43** | **0.993 /77/37** | **全 PASS** |
| 0.001 | 0.992 /118/58 | 0.996 /139/84 | 0.995 /120/60 | 過頭(頂點爆量) |

藝術家基準 IoU:光暈 0.980、左手 0.968、身體 0.976。
**0.002 是甜蜜點**:hull 密度(37~43)≈ 藝術家(40~78)、頂點預算相當、3 件全過基準。
呼應窗簾發現「IoU 由邊界取樣密度決定」—— 面/環狀件同理,只是密度旋鈕在 v1 是 epsilon 而非 rows。

## 迴歸(epsilon 0.008→0.002 無害,且 v1 fallback 更好)

- main_draw 4 mesh(走 v2 strip)全 `overall_pass=True` 不受影響。
- v1 fallback 品質提升:shadow IoU 0.904→0.998、curtain_left 0.980→0.995。
- 切圖閘 `evaluate_slicing` 仍全過。
- 註:`image/shadow2` slot 的 attachment 名為 `image/shadow`(共用 region)→ 驗證要用 `--name image/shadow`。

## 端到端結論(里程碑)

**「PSD 件 → S3 生成 mesh → 對照真實生產 spine 藝術家 mesh」對第二份真實標的(Award 機器人 3 件)
IoU 全過基準**。S3 覆蓋率已在兩種拓樸 regime 驗證:直條(main_draw 窗簾/陰影,v2 strip)與
面/環狀(Award 機器人件,v1 Delaunay@eps0.002)。

## 標準指令

```
python3 tools/mesh_gen/validate_against_real.py \
  --skeleton assets/Award.json --atlas assets/Award.atlas --png assets/Award.png \
  --slot "機器人拆件/身體" --name "機器人拆件/身體" --gen v2
```

## 待續

- weighted mesh 的 deform 轉移(需 bone 綁定變換還原 setup)—— 目前無「weighted 且有 deform」的資產,
  出現時再做。
- S3 目前產 **unweighted** mesh;Award 件是 weighted(綁骨)。若要端到端產「可綁骨的件」,S5 骨架 +
  BBW 權重是下一槓桿(仍為計畫中最卡的 pivot 環節)。
