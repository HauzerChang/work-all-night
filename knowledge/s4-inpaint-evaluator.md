# S4 補圖能力 + 補圖閘(occlusion inpainting)

- **結論**:立起補圖能力的**自我品質閘**(樞紐,RULES「每能力必配評估器」)並校準可信。
  工作流依使用者定義:**切圖定出區塊 → 被上層遮住的下層在被遮區補圖**(如 dj_cat「軀幹」被「頭」蓋住)。
  補圖閘 `inpaint_eval.py` 對 **flat(dj 軀幹)+ textured(robot 身體)兩種畫風** 皆 `discriminates=True`:
  telea/ns/extend 三種真實補圖全 PASS、noop/flat/noise 三個負對照全在**對的軸**上 FAIL。
  端到端在真實 `dj_cat_ai_final.psd` 跑通:「頭 蓋 軀幹」2543px 破洞 → telea 補 → 閘 PASS。
- **信心**:高(評估器經正/負對照 + 兩畫風校準;端到端對真實生產 PSD)。
- **階段**:第 2 階段 / S4 補圖(補齊 S2 缺的補圖閘樞紐)。

## 補圖閘判準(對應 PLAN「0 破洞 / 0 明顯接縫」)

| AC | 指標 | 門檻 | 需真值? |
|---|---|---|---|
| AC1 破洞 | hole_fill(補區補完後不透明比例) | ≥ 0.999 | 否(可部署) |
| AC2 接縫 | seam_ratio(補區邊界梯度 ÷ 洞周邊已知窄環的局部紋理梯度,JND 下限 40) | ≤ 1.5 | 否(可部署) |
| AC3 保真 | PSNR(補區 vs 真值) | ≥ 11 | 是(僅校準) |

- **部署時只有 AC1+AC2**(被遮區本就沒真值);AC3 只在「合成遮擋+已知真值」校準時算,
  用來**證明免真值的 AC1/AC2 真能追蹤品質**。

## 校準鑑別表(合成遮擋,兩畫風)

| 方法 | dj 軀幹(flat) seam / psnr | robot 身體(textured) seam / psnr | 判定 |
|---|---|---|---|
| telea | 0.65 / 20.0 | 0.64 / 13.2 | PASS |
| ns | 0.69 / 21.5 | 0.66 / 13.6 | PASS |
| extend(外擴) | 0.67 / 19.8 | 0.76 / 11.2 | PASS |
| noop(留洞) | hole_fill=0 | hole_fill=0 | FAIL(破洞) |
| flat_gray | 5.10 / 10.2 | 2.23 / 8.5 | FAIL(接縫) |
| noise | 6.66 / 7.5 | 2.45 / 6.5 | FAIL(接縫) |

→ 好補圖 seam **0.64~0.76**、硬填 **2.2~6.7**,兩畫風皆 >3× 分離 → 門檻 1.5 有充裕邊際。

## ⚠️ 評估器校準教訓(第 4、5 次 miscalibration)

1. **seam 分母不能用全域紋理中位數**:洞落在**局部平坦區**時,層內他處強邊界會把全域中位數/百分位灌高,
   或平坦層中位數=0 → 除爆(實測 telea seam=2.6e7)。**改用『洞周邊 3~15px 已知窄環』的局部紋理當分母
   + JND_FLOOR(40)下限**:平坦區的好補圖仍低(續平)、硬填仍高(邊界跳變)→ 兩畫風都乾淨分開。
2. **`psd.composite()` 對某些 AI 生成 PSD 回傳『全不透明』**(dj_cat:content px 恰為 772×427 整張):
   使 `psd_slice` 的 AC3 孤兒率把整片空背景誤判為「未覆蓋內容」→ 假性 56% 失敗。
   **但個別圖層切圖是對的**(AC2 premult 重組 MAE 0.50 < 2 通過)。此為 s4「透明區填白」的姊妹坑。
   → 修法留待下一有界塊(見下)。

## 補圖 CPU 降階梯(對應 Spine能力鍛鍊計畫 S4)

① 邊緣外擴(`extend`,distance-transform 最近已知色)② `cv2.inpaint` telea/ns(本檔預設)
③ LaMa(需權重)④ GPU/人工。目前 ①②純 CPU 已足以過閘;複雜紋理大缺口再升 ③④。

## occlusion_mask(真實破洞偵測,啟發式)

`真洞 = 上層不透明 ∩ 下層透明 ∩ 膨脹(下層不透明, grow)`,只標『缺的』像素(不覆寫已畫好內容)。
`grow`(下層內容合理延伸多遠)是**美術決定**,取保守起點。dj_cat 全對掃描的真實補圖熱點:
DJ台體→軀幹(2675)、鏡框→鏡片(2660)、頭→軀幹(2543)、頭→胸部(2115)、左手掌→頭(1748)…
**使用者原例「耳機右罩→軀幹」實測僅 2px 洞**(AI PSD 已把軀幹在耳機下畫全)→ 該對幾乎不需補。

## 工具 / 可重現

```
python3 tools/mesh_gen/inpaint_eval.py --calibrate <完整層.png>   # 校準+負對照,discriminates 應 True
# 部署:import inpaint.complete_layer / occlusion_mask + inpaint_eval.evaluate
```

## 下一步候選

- **硬化 psd_slice AC3**:對「全不透明 composite」PSD,孤兒 content 改由『非背景色 / 圖層 alpha 並集』界定,
  而非直接用 composite alpha(修第 5 坑)。
- **grow 校準**:用 dj_cat 多對真實遮擋,量『補多遠才夠(動畫最大位移下不露洞)』→ 給 grow 建議值。
- 串進 pipeline:切件 → occlusion_mask 標補區 → 補圖 → S3 mesh → SkelToJson。
