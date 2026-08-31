# S4 候選 19:上下文假設重測(CPU baseline 加大輸入上下文,能否改變 1a 判定)

## 背景 / 動機

`inpaint_eval.py` 從頭到尾只吃 `psd_slice.py` 切出的、緊裁到單一圖層 bbox 的孤立 PNG——
零周圍上下文。使用者自製 Photoshop `GPT Fill` 插件(見 `s4-gptfill-plugin-knowledge.md`)
給生成模型的重建上下文下限是 **512px**。貫穿 S4 的核心結論「機械紋理材質(`身體`/`左手`)
1a 全 fail」是在「只看單層、零上下文」條件下量出來的,尚未驗證過是不是「裁太緊」的人工
產物——這是候選 19 要回答的問題。

## 方法

新增 `tools/mesh_gen/s4_context_window.py`。核心做法:把同一顆隨機挖洞(`punch_hole`,
與孤立版共用同一個 seed,確保是同一顆洞)分別套進兩種輸入:

- **條件 A(孤立裁切,既有做法)**:`inpaint_eval.py` 原本的孤立層 PNG。
- **條件 B(大畫布視窗)**:以圖層 bbox 為中心、每邊擴到至少 512px(比照插件下限)、裁到
  PSD 畫布範圍內的視窗,視窗內容 = 真實 PSD 場景(其他圖層)當周圍背景。

對兩種輸入各跑 `inpaint_eval.py` 既有三個 CANDIDATE_METHODS(`nearest`/`cv2_telea`/
`cv2_ns`),用同一套 `score()`(premult_mae/alpha_mae/seam_grad_diff/ssim)在洞區配對比較。

## 踩到的兩個坑(方法論本身,校準階段抓到,未信任任何結果就先修正)

1. **第一版直接用 `psd.composite()` 當上下文畫布——錯**:composite 是全部圖層依 z-order
   疊完的最終結果,目標層若被**後畫(z 更高)的圖層局部蓋住**(如 `光暈` 幾乎整個畫布範圍
   內都有其他部件疊在它上面),composite 在那些像素顯示的是蓋在上面那層的顏色,不是目標層
   自己的內容。第一次全跑(6 案例)`calibration.ok` 全部 `False`(`光暈` premult_mae 高達
   87.7)。**改法**:context canvas 只疊「z 序排在目標層之前(較底層)」的圖層。
2. **第二版改用「底層 + `Image.alpha_composite` 貼回目標層」——仍不完全過**:`身體`/`左手`
   殘留 alpha_mae ~2.4~3.2(未達 <2.0 門檻)。診斷發現誤差 100% 集中在目標層自身抗鋸齒的
   半透明邊緣像素(僅 <2% 面積,`opaque_mae`≈0.003,`fringe_mae`≈70~124)——原因是
   `alpha_composite` 對半透明像素疊在不透明背景上時,**輸出 alpha 會被推高**
   (`a_out = a1 + a2*(1-a1)`,背景不透明時 →255)。這是「場景最終呈現」的正確物理結果,
   但語意上不等於「這個圖層自己的 alpha」,兩者本不該逐位元相等——是我的校準檢查本身的
   期望錯了,不是資料有問題。**改法**:bbox 內部不需要疊圖運算,直接硬覆蓋
   (`context_arr[bbox] = gt`,不經過 alpha 混合公式)。第三版:全部 6 案例
   `calibration.ok=True`,premult_mae/alpha_mae 皆為 `0.0`(逐位元相同)。

先校準才能信判定——這是本專案第三次(見 `s4-inpaint-real-occlusion.md`、
`s4-inpaint-1b-edge-gate.md`)在同一個「先驗證假設再信結果」的坑類型上受益。

## 結果(6 案例:`身體`/`左手` 已知 1a 全 fail 材質 × interior/edge;`光暈` 已知 1a pass 當回歸檢查)

| 材質 | 模式 | window_bbox | 三個 baseline 的 ssim delta(windowed − isolated) |
|---|---|---|---|
| 身體 | interior | 512×483(vs bbox 379×425) | **恰好 0.0000**(nearest/cv2_telea/cv2_ns 全部逐位元相同) |
| 左手 | interior | 411×512(vs bbox 257×215) | **恰好 0.0000**(同上) |
| 光暈 | interior | 706×683(= bbox,已 ≥512 無法再擴) | 0.0000(退化案例,bbox 已大於 pad_to,無意義) |
| 身體 | edge | 同上 | nearest −0.038(變差,seam_grad_diff 43.6→107.6 惡化);cv2_telea −0.043;cv2_ns −0.030 |
| 左手 | edge | 同上 | nearest +0.008;cv2_telea +0.004;cv2_ns +0.003(小幅改善,seam_grad_diff 略降) |
| 光暈 | edge | 同上 | 0.0000(同上,退化案例) |

**interior 模式:三個 baseline 在 `身體`/`左手` 上的輸出與孤立裁切版逐位元相同(delta 恰好
0.0000,不是「差很小」而是真的零)。**edge 模式效果小且方向不一致:`nearest` 明顯變差,
`cv2_telea`/`cv2_ns` 小幅改善或小幅變差,量級遠不足以讓 ssim 跨過 1a 門檻(`>0.75`)——
windowed 條件下最高也只到 0.44(`身體::interior`,與孤立版完全相同的數字)。

## 為什麼(機制解釋,已用結果驗證而非事後猜測)

- `fill_nearest`:用 distance-transform 找每個洞內像素「最近的有效(alpha>8 & 非洞)像素」。
  interior 模式的洞完全落在材質內部、四周不遠處就有真實內容像素環繞,视窗擴大不會讓任何
  更遠的『視窗外新增』像素變成更近——結果不變。**edge 模式**洞貼著真實輪廓,擴大視窗後,
  沿輪廓外側原本是「不存在」(孤立版裁掉了)的區域,现在出現了視窗裡其他圖層/背景的有效
  像素——`nearest` 會把這些**不相干材質**的顏色當成「最近有效值」誤用進洞裡,seam_grad_diff
  反而爆增(43.6→107.6)。這正是候選 19 提出時沒預料到的反效果:context 不是免費的,對
  「取最近有效值」這種演算法,錯誤語意的鄰居內容是負貢獻。
- `cv2.inpaint`(Telea/NS):FMM(fast marching method),`radius` 參數(本檔預設 3px)
  限制了每次填值只看邊界法線方向極小鄰域內的已知像素做加權外插,與洞邊界之外幾百 px 的
  視窗內容完全無關——interior/edge 皆理論上應與視窗大小無關,實測 interior 確實零差異;
  edge 的小幅波動(±0.03~0.04)可能來自視窗邊界改變了 telea/ns 演算法內部隊列處理的邊界
  條件(如 `mask` 陣列尺寸不同導致的浮點路徑差異),量級遠低於任何實務意義。

## 結論(直接回答候選 19 提出的問題)

**「1a 機械紋理材質全 fail」不是「只看單層、零上下文」造成的人工產物。** 給 CPU baseline
(`nearest`/`cv2_telea`/`cv2_ns`)喂進比照插件下限(512px)的真實 PSD 場景上下文,在 interior
模式下(S4 大多數評測案例的主要模式)完全沒有效果(逐位元相同輸出);edge 模式下效果小、
方向不一致,且 `nearest` 反而因誤用鄰近圖層像素而變差——沒有任何一個 windowed 案例讓
1a 判定翻盤。

**這收窄了候選 19 原本的假設**:GPT-Fill 插件的「512px 上下文」概念,對它自己的生成式模型
(需要語意理解「這個區域附近有什麼、材質怎麼延續」)是有意義的,但對本專案現有的 CPU 局部
演算法(nearest-fill 的最近有效值、cv2.inpaint 的極小半徑 FMM 外插)完全不適用——它們的
輸入視野本來就被演算法自身的局部性限制死,不是被裁圖裁掉的。**「生成式路徑能不能解 1a」
仍然只能由候選 17(headless `gpt-image-2` baseline,需使用者授權)回答**,候選 4(LaMa
可行性探測)量化過的「通用預訓練權重不足以解 1a」結論也不受本次影響(LaMa 是深度網路,
不在本次測試範圍內,但同樣的「512px 語意上下文只對生成式模型有意義」邏輯適用)。

## 誠實限制

- 只測了 `robot_parts.psd` 的 `身體`/`左手` 兩個材質(候選清單裡「1a 全 fail」的代表案例);
  未擴大到 `Symbol_Ww.psd` 的 icon 類材質(候選 6 測過的 11 層)——理論機制(演算法局部性)
  與材質無關,預期結論可攜,但沒有實測驗證這批新材質。
- `光暈` 的視窗擴大測試是退化案例(bbox 本身已 ≥512,pad_to=512 擴不出更大視窗),沒有
  真正測到「已 pass 案例會不會被 context 拖累」——若要補這個回歸檢查,需要用更大的
  `--pad-to`(如全畫布)或換一個 bbox 較小的已知 pass 材質。
- edge 模式的小幅波動(±0.03~0.04 ssim)只做了機制推測(演算法內部路徑差異),未逐行
  debug telea/ns 原始碼證實,量級太小、不影響結論,未進一步深究。
