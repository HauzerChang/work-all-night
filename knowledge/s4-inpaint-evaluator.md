# S4 補圖閘 v1 + CPU baseline 邊界(2026-08-28)

> 分支 `claude/spine-s4-inpainting`。工具:`tools/mesh_gen/inpaint_eval.py`。
> 對應 `handoff_S4.md` §4/§5 chunk 0:補圖閘 v1 + 邊緣外擴/`cv2.inpaint` baseline。

## 方法(合成真值法)

1. 取一個完整件(RGBA PNG,如 PSD 切件)當**真值**。
2. **人工挖洞**(`punch_hole`,模擬動畫露出被遮區後的破洞):
   - `interior`:洞完全落在內容內部(距輪廓 ≥1.15×半徑),模擬「中段被別的件遮住,露出時要內插」。
   - `edge`:洞的圓心取在輪廓邊界上,洞會跨出輪廓,模擬「邊緣被裁掉,補圖要外推」(較難)。
3. 用 baseline 補洞,與真值比對 4 項指標(洞區內):
   - `premult_mae`:premultiplied-RGB 平均絕對誤差(沿用 S2/S4 切圖閘教訓,避免透明區誤判)。
   - `alpha_mae`:alpha 平均絕對誤差。
   - `seam_grad_diff`:洞邊界環狀帶(dilate∧¬erode)的 Sobel 梯度強度差 — 量化補丁接縫是否突兀。
   - `ssim`:窗口化結構相似度(premultiplied 灰階,自實作,環境無 skimage)。

## 校準(正/負對照,先驗證鑑別力再信任判定)

依 `RULES.md` 教訓(S2/S4 已踩 3 次 miscalibration),**先確認指標本身無偏、且能分辨好壞,才信任 baseline 判定**:

- **正對照**(`gt`:直接拿真值填洞):所有測試件 100% `premult_mae=0 / ssim=1.0`,指標無偏。
- **負對照 A**(`none`:洞維持透明):`ssim` 全部 < 0.1、`alpha_mae` ≈ 250+,明顯 fail。
- **負對照 B**(`random`:洞填隨機噪聲):`ssim` 全部 < 0.08、`premult_mae` 90~113,明顯 fail。
- `inpaint_eval.py` 主流程內建 `calibration_check`:兩負對照若意外 pass,整份報告視為不可信(exit 1)。
  本次所有跑過的件校準皆 `pass`。

閾值(`THRESH`):`premult_mae<18`、`ssim>0.75`、`seam_grad_diff<12`。由正/負對照的巨大差距(gt≈完美、
負對照 ssim<0.1)與下方兩類真實件的清楚分野(光暈通過 ssim 0.98~0.99、身體/左手全落在 ssim<0.52)
校準,不是憑空猜的門檻。

## Baseline 實作

- **Level 1 邊緣外擴** `fill_nearest`:`scipy.ndimage.distance_transform_edt(return_indices=True)`
  找洞內每像素最近的有效像素,直接抄過去(nearest-fill,非真的鏡射,但同等級的最省做法)。
- **Level 2** `fill_cv2_inpaint`:`cv2.inpaint`(Telea / Navier-Stokes),洞區補完強制設回不透明。

## 真實件實測結果(robot_parts.psd 切件)

| 件 | 洞類型 | 洞大小 | nearest ssim | cv2_telea ssim | cv2_ns ssim | 結論 |
|---|---|---|---|---|---|---|
| `光暈`(柔和放射漸層) | interior | 26565px(占 12%) | **0.989** ✅ | **0.995** ✅ | **0.998** ✅ | **CPU 補得動** |
| `光暈` | edge(咬邊界) | 27471px | 0.755(壓線 fail,seam/alpha 超標) | 0.709 ❌ | 0.707 ❌ | **邊緣外推明顯更難,即使紋理簡單** |
| `身體`(機械面板/高光/接縫) | interior | 1517~9477px(占 2~12%) | 0.13~0.43 ❌ | 0.19~0.49 ❌ | 0.23~0.51 ❌ | **CPU 補不動,任何測試尺寸皆 fail** |
| `身體` | edge | 6429px | 0.324 ❌ | 0.420 ❌ | 0.401 ❌ | **CPU 補不動** |
| `左手`(同身體材質) | interior/edge | 3222~4293px | 0.03~0.14 ❌ | 0.18~0.19 ❌ | 0.18~0.20 ❌ | **CPU 補不動** |

(完整數據見本次 `log/s4-2026-08-28-001.md` 附的 JSON 輸出。)

## 誠實界定:CPU 補得動 / 補不動的邊界

- **決定因素是局部紋理複雜度,不是洞的大小**:身體件即使洞縮到 1517px(半徑 ~22px,遠小於通過的
  光暈 26565px 洞),SSIM 仍只有 0.43,遠低於通過線。反之光暈用大洞(26565px)仍輕鬆通過。
  → 換句話說,**洞多小都救不了「洞落在高頻細節區」的失敗**;**洞多大都不影響「洞落在平滑漸層區」的成功**。
- **CPU 1–2 級(nearest / cv2.inpaint)能補得動**:純色、柔和放射/線性漸層、無銳利內部邊緣的區域
  (本例:光暈,interior 洞)。這類缺口邊界外推(`edge`)也比內插(`interior`)難一截(0.99→0.76),
  但仍在「有機會靠 baseline 微調通過」的量級。
- **CPU 1–2 級補不動**:含機械面板分割線、高光反射、局部陰影漸層等**結構性內部邊緣**的區域
  (本例:機器人身體/左手,任何洞尺寸皆 fail,SSIM 上限 ~0.5)。這類需要「知道洞裡本來畫了什麼形狀」
  的語意資訊,edge-aware 的 Telea/NS 只能沿既有梯度外插,對「洞內有全新結構」無能為力
  → **需升 Level 3(LaMa 等深度 inpaint)或 Level 4(人工/GPU 生成)**。
- **額外發現(alpha 處理缺陷)**:`edge` 模式(洞跨出輪廓)下,`cv2_inpaint` 把整個洞區強制設為不透明,
  但柔和邊緣的真值 alpha 本應隨半徑衰減 → `alpha_mae` 明顯偏高(28~42)。這是 baseline 實作本身的
  簡化(未對 alpha 做漸層外推),不是 cv2 演算法的鍋;若要在生產用 edge 缺口,alpha 通道需要獨立於
  RGB 的漸縮處理(如對 alpha 也跑 inpaint,或用距離場乘上真值輪廓形狀先驗)。

## 與 S4 契約策略的呼應

這結果**再次印證** `PLAN.md`/`handoff_S4.md` 的核心策略:「改輸入契約比硬攻演算法划算」。
本資產(機器人拆件)分層 PSD 本身**沒有破洞**(美術已畫全),補圖閘目前只能靠**合成挖洞**驗證;
上表證明只要遮擋區落在「機械細節」量級,CPU baseline 就守不住,**PSD-first(要求美術畫全被遮區)
仍是目前唯一能穩定產出「無破圖」部位件的路徑**;CPU inpaint 適合當作 PSD 未覆蓋到的小面積、
低頻缺口的補強手段,而非主力。

## 下一步候選

1. **遮擋真值法**:用 Award/機器人多件疊合 composite,找已知某件被上層遮住、但 PSD 該層本身
   有畫全的區域,當更貼近實戰的真值(目前只有合成挖洞,見 `STATE_S4.md` 未解問題)。
2. **Level 3 評估**:LaMa 等深度 inpaint 是否可裝(權重下載可能被網路政策擋,需先探測)。
3. **alpha 通道獨立補圖**:修正 `fill_cv2_inpaint` 的 edge 模式 alpha 處理(見上「額外發現」)。
4. 用本閘對 Symbol_Ww.psd 的其他層(icon 類,可能有更多平面色塊)跑一輪,擴大「CPU 補得動」樣本。
