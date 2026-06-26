# S4 真實驗收 — 兩份生產 PSD + 機器人對應 spine(Award)

- **結論**:使用者提供 2 份真實生產 PSD(`Symbol_Ww` symbol、`robot_parts`=「機器人拆件」big win 主角)
  與機器人對應的真實 spine(`Award.json/atlas`)。`psd_slice.py` 對兩份 PSD **切圖無損驗收通過**;
  並與生產 spine **逐件對應吻合(size 全 +2px atlas padding)**,證明切圖 pipeline 對真實檔可用。
- **信心**:高(對真實生產檔驗證 + spine ground truth 交叉比對 + 閘校正後正/負對照)。
- **階段**:第 2 階段 / S4(里程碑:從合成驗證 → 真實驗收)。

## 真實檔(已收進 assets/)

- `assets/Symbol_Ww.psd`(180×180,18 leaf 圖層,0 群組,扁平)。
- `assets/robot_parts.psd`(「機器人拆件」713×693,5 leaf 圖層,扁平)。
- `assets/Award.json` + `assets/Award.atlas`(big win spine:77 bones/47 slots/1 skin/12 anims;
  Award.png 貼圖在使用者端,未提供 → 只做幾何/命名分析)。

## ★ PSD 圖層 → spine slot/attachment 對應(機器人拆件,ground truth)

| PSD 圖層 | PSD size | spine slot | spine type | spine size |
|---|---|---|---|---|
| 光暈 | 706×683 | `機器人拆件/光暈` | **mesh** (78v) | 708×685 |
| 右手 | 595×484 | `機器人拆件/右手` | region (rot 141.79°) | 597×486 |
| 頭 | 120×103 | `機器人拆件/頭` | region (rot -97°) | 122×105 |
| 身體 | 379×425 | `機器人拆件/身體` | **mesh** (98v/154t/hull40) | 381×427 |
| 左手 | 257×215 | `機器人拆件/左手` | **mesh** (80v/116t/hull42) | 259×217 |

**揭示的真實慣例(可直接寫進契約)**:
1. **slot 命名 = `<PSD檔名>/<圖層名>`**(用 PSD 名當前綴 namespace;Award 把多個來源 PSD 的件混在一個 spine,
   靠前綴區分。其他 slot 如 `劍粒子/…`、`OMG角色` 亦然)。
2. **一圖層 ⇄ 一 slot**,size 完全對應(+2px = atlas packer 各邊 1px padding)→ 切件尺寸正確。
3. **mesh vs region 由美術依需求分配**:會 warp/柔性變形的件(光暈、身體、左手)做 mesh;
   剛體件(右手、頭)用 region + 旋轉。**這 5 件在 Award 無 deform timeline** → mesh 靠骨骼/權重變形,非逐頂點 deform。
4. 圖層名為**中文**、無群組(扁平)、全可見。Symbol_Ww 有 opacity<255 的層(臉部陰影 153)。

## ⚠️ 閘校正(又一次 evaluator miscalibration,記取教訓)

初版 `psd_slice` 重組閘直接比 RGBA → 真實 PSD MAE 30(Symbol)/99.99(機器人),**假性失敗**。
查因:`PSDImage.composite()` 對 RGB PSD 的**透明區填白(255)**,我的重組填黑(0);兩者 alpha=0、
視覺無差,但在無意義的透明 RGB 上比對被拉爆。

**修正**:
- 改用 **premultiplied-alpha 比對**(RGB×alpha/255):透明區自動歸零、半透明正確加權。
- reassemble **套用圖層 opacity**(切件本身不烤 opacity,僅驗證時還原 composite)。

校正後:合成 0.014 / Symbol 0.009 / 機器人 0.031(premult_rgb),alpha_mae 全 0 → **三檔全 PASS**。
負對照(漏件)premult_rgb 11–20(仍抓到)→ 校正未過頭。
**教訓(第三次)**:評估器要先校準/負對照才可信(前有 stress_field、composite 白底)。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/Symbol_Ww.psd --eval     # PASS
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd --eval   # PASS
```

## 下一步

- 用機器人 5 件當輸入,跑 S3 `generate_mesh_v2` 生成 mesh,**對照 Award 真實 mesh**(光暈/身體/左手)
  做 IoU/deform 比較 → 端到端「PSD→件→mesh」對真實標的驗收。
- 把對應慣例(`PSD名/圖層名`、mesh/region 分配)固化進切圖→Spine JSON 組裝工具。
