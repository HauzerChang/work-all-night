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
- **額外發現(alpha 處理缺陷,已修正,見下方「`fill_cv2_inpaint` edge 模式 alpha 修正」節)**:
  `edge` 模式(洞跨出輪廓)下,`cv2_inpaint` 原本把整個洞區強制設為不透明,但柔和邊緣的真值
  alpha 本應隨半徑衰減 → `alpha_mae` 明顯偏高(28~42)。

## `fill_cv2_inpaint` edge 模式 alpha 修正(2026-08-28,見 `log/s4-2026-08-28-008.md`)

延續上面的發現,實測了三種替代「洞內強制拉滿不透明」的做法,**前兩種直覺解法反而更差**:

| 做法 | 光暈 edge alpha_mae | 身體 edge alpha_mae | 左手 edge alpha_mae | 判定 |
|---|---|---|---|---|
| 原本:強制 255 | 41.8 | 4.18 | 5.55 | baseline |
| ① 對 alpha 整顆跑 `cv2.inpaint` | 72.5(更差) | 136.5(更差) | 122.6(更差) | ❌ 洞外背景的 0 值被大範圍擴散進洞內,連該不透明的洞中段都被拉低 |
| ② alpha 單點最近鄰外推(`fill_nearest` 原本作法) | 28.9(較好) | 21.9(更差) | 5.37(打平) | ❌ 硬邊材質會抓到緊貼輪廓的極薄 AA 邊緣像素(alpha 9~30)當最近值,把洞中段該有的高 alpha 拉低 |
| ③ **距離場×局部量測漸縮寬度**(`estimate_alpha_taper`,採用) | **8.6** | **2.27** | **2.98** | ✅ 全面改善,無一惡化 |

**③ 的方法**(`tools/mesh_gen/inpaint_eval.py::estimate_alpha_taper`):
1. 洞外「已知背景」(alpha≤8)當 0 端錨點,算洞內每像素到最近已知背景的距離 `d_bg`。
2. 局部漸縮寬度 `ell` 用洞周圍**看得到的**真實 AA 邊緣像素(8<alpha<250)量出來,不是猜的常數:
   `ell = 255 / median(這些像素的 alpha 梯度幅值)`。材質邊緣硬(身體/左手)量出 `ell≈2px`,
   邊緣軟(光暈放射漸層)量出 `ell≈32px`,是量測值而非固定假設。
3. `alpha_est = clip(255 * d_bg / ell, 0, 255)` — 深入內部飽和到 255,貼近背景線性衰減到 0。

**驗證範圍**:3 真實件(robot_parts.psd:光暈/身體/左手)+ 4 個新獨立件(`Symbol_Ww.psd`:頭/框/
臉部陰影/底)、interior+edge 兩模式全跑;`interior` 模式全面持平(alpha_mae 仍 0,無回歸);`edge`
模式跨全部 7 件 alpha_mae 一致改善,**1a `pass` 判定翻盤 6 處、全部方向正確(False→True,原本
壓線/略差的案例變 PASS,無一從 True 翻成 False)**——光暈 edge(原 FAIL)、臉部陰影 interior
(原 FAIL)、底 edge(原 FAIL)現在 PASS;身體/左手/框/頭仍正確 FAIL(這些案例的失敗原因是
RGB 結構本身補不出來,不是 alpha)。校準(`calibration_check`)前後皆 PASS/FAIL 一致(見下方
已知限制),改動不影響鑑別力。

**刻意不動 `fill_nearest`(Level 1)**:同一顆 `estimate_alpha_taper` 若也套在 `fill_nearest`,
會讓它的 RGB(仍用最近鄰)與新算出的 alpha 來自不同來源像素;在複雜拓樸件(`Symbol_Ww.psd::框`,
環形鏤空)上實測讓 `ssim` 從 0.775(PASS)掉到 0.452(FAIL)——真實判定翻盤,故 revert,
Level 1 保留原本「RGB/alpha 同一個最近鄰索引」的作法不動。`fill_cv2_inpaint` 沒有這個顧慮,
因為它的 RGB 本就走獨立的 `cv2.inpaint` 通道,不存在「同源」可保留。

**順帶發現(超出本次範圍,留待未來)**:對 `Symbol_Ww.psd` 新測的 `框`/`臉部陰影` 兩件,
`calibration_check` 的 1b 正對照(`gt` 本身的 1b 分數)竟然 `tone_gap` 過高判定 fail
(`框` interior `tone_gap=81.75`、`臉部陰影` interior `tone_gap=57.3`,皆遠高於
`THRESH_1B["tone_gap"]=28.0`)——這與本次的 1a alpha 改動**無關**(改動前後數值完全相同,
純粹是這兩個新材質本身內部色調變化大,1b 的「洞周圍本來沒有接縫」假設對它們不成立)。1b 目前
只在原本測過的 robot_parts.psd 三件上校準過(見 `s4-inpaint-1b-lenient-gate.md`);要在更多材質
類型上用 1b,需要先把這個 `tone_gap` 誤判抓出來重新校準,列為新候選,見 `STATE_S4.md`。

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
