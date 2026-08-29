# S4 補圖候選 2 — 1b(防穿幫)edge 模式支援(2026-08-29)

> 延續 `knowledge/s4-inpaint-1b-lenient-gate.md`(1b 只在 interior 模式校準過)與
> `knowledge/s4-inpaint-real-occlusion.md` 候選 9(真實遮擋樣本揭露:小尺寸圖層如「頭」的
> 遮擋洞天生易落在 edge 模式,而 1b 對 edge 完全沒有驗收線,只能退回 1a——1a 對機械紋理
> 材質又全 fail)——這是候選 9 量出來的真實覆蓋率缺口,不是理論延伸,本 chunk 補上。

## 結論

`tools/mesh_gen/inpaint_eval.py::score_1b()` 新增 `mode="edge"` 支援,讓 edge 模式的洞
也能給出有校準依據的 1b pass/fail 判定(不再一律標「不適用」)。核心結果:

- **機械紋理材質(機器人拆件家族:光暈/身體/左手)edge 模式 1b 校準通過**,且與既有
  interior 模式結論同型——1b 三個 CPU baseline(nearest/cv2_telea/cv2_ns)全 pass,呼應
  「CPU 補不動是 1a 嚴格標準的結論,1b 防穿幫標準下這批廉價 baseline 夠用」的既有假設,
  現在 edge 模式也適用了。
- **候選 9 揭露的真實缺口(`頭←右手`,小尺寸圖層 46.5% 遮擋比例、edge 模式)現在有真正
  的判定**:`applicable=True`,gt/none/random 校準全過,3 個 CPU baseline 全 pass——這批
  之前「沒有任何量化閘能判定動態下是否穿幫」的小尺寸機械材質補圖,現在有驗收線了。
- Symbol_Ww 家族的 `框`/`臉部陰影` 在 edge 模式下的 `tone_gap` 不可信,**與候選 8 已經
  記錄的限制(`s4-inpaint-tone-gap-limits.md`:tone_gap 只在機器人拆件材質家族內可信)
  是同一件事延伸到 edge 模式,不是新問題**(見下方「已知限制延續」)。

## 設計:第一版嘗試失敗 → 改用「排除真實輪廓段落,只評內容內部轉接」

**第一版嘗試**(依 STATE_S4.md 候選 2 原始構想):「比對這個材質沿真實輪廓其他段落的天然
tone/alpha 變化範圍」當基準——即拿 `content` 輪廓上遠離這次洞的其他段落,量它的天然梯度/
色調落差,`seam_ratio`/`tone_gap` 都改成比值(reconstructed ÷ 天然範圍)。

**量化後發現失敗**:premultiplied 色彩在背景(alpha≈0)側恆為 0,任何補丁(不管內容補得
對不對,只要 alpha 補對)在真實輪廓交界處量出的落差,量級都跟「材質本身在別處的真實輪廓」
落差相近——鑑別力被稀釋到分不出亂補(random)與正確填補(gt)。實測數字(punch_hole 合成
edge 洞,原始比值版):

| 材質 | gt seam_ratio | random seam_ratio | gt tone_gap(比值) | random tone_gap(比值) |
|---|---|---|---|---|
| 身體 | 0.504 | 1.747 | 0.269 | 1.898 |
| 左手 | 1.237 | 1.292 | 0.676 | 0.779 |
| 框 | 0.858 | 1.123 | 0.648 | 0.643 |

`random`(亂補,理應是最明顯的負對照)與 `gt`(正對照)幾乎糾纏在一起,任何單一門檻都無法
同時讓所有材質的 gt pass、random fail——**這組比值指標本身鑑別力不足**,不是門檻沒調好。

**改法**(採用版):mask 的定義本身就 ⊆ 挖洞前的原始內容(不可能補到真實輪廓之外),所以
洞邊界「貼著真實輪廓」的那段,補對補錯都不影響它本來就會出現的 alpha/色調落差——這段根本
不是補圖行為造成的接縫,不必也不該拿來評分。真正該評的是洞邞界「完全落在內容內部」的那部分
轉接(patch 材質 vs 周圍既有內容像素接得順不順)——這跟 interior 模式的「材質內部紋理」問題
本質相同,**直接複用同一套 `local_ring` baseline,不重新發明,單位維持絕對值(premultiplied
色差、梯度比值),與 interior 完全一致**。

實作:`_exclude_real_silhouette(inside_band, outside_band, content, mask, width)`——把貼近
真實背景(`~(content|mask)` 膨脹 `width` px)的那段邊界帶排除,只留下 `content↔content` 的
轉接部分;`seam_grad`/`tone_gap` 只在這個限縮後的區域算,baseline(`local_ring`)完全沿用
interior 分支的既有邏輯不變。若限縮後樣本太少(< 60px,如小尺寸圖層洞幾乎吃掉整條輪廓的
極端情況)→ `applicable=False`,誠實承認評不了,不硬湊數字。

### 踩到的一個真實 bug:`content` 在兩種呼叫情境下語意不同

`_exclude_real_silhouette` 的背景判定原本直接用 `~content`。但 `content` 在校準流程
(`run_with_mask`)是挖洞前的完整真值輪廓(已含洞的位置);在真實落地情境
(`score_candidates`,呼叫端已經有個現成的洞)則是**已經挖洞後**的 holed_rgba 算出的輪廓
——洞本身在這種 `content` 裡看起來就是「沒有內容」。若直接對這種 `content` 取
`~content` 當背景,洞本身會被誤當成背景,導致緊貼洞的 `outside_band` 幾乎全部落在
`dilate(~content,width)` 內而被排光(因為洞就在正下方)。第一次端到端測試
(`psd_inplace_patch.py --auto --mode edge`)就踩到:所有候選的 1b 分數全部是 0,
`applicable` 恆 `False`,`select_best` 只能走 fallback,完全沒發揮到新支援的 edge 判定。

**修法**:`mask` 定義上永遠 ⊆ 原始真實內容(洞不可能長在背景外),所以 `content | mask`
才是兩種呼叫情境下一致的「完整真實輪廓」(校準流程本來就相等,真實情境下補回洞的部分),
用它算真背景才對。修正後 `patch_layer_auto`/`demo_auto_patch` 的 edge 模式端到端測試
恢復正常(見下方驗證)。

## 校準結果

**機器人拆件家族(光暈/身體/左手,`inpaint_eval.py --modes edge`)**:`calibration.pass=True`。

| 材質(edge) | gt tone_gap | none tone_gap | random tone_gap | 3 baseline pass? |
|---|---|---|---|---|
| 光暈 | 0.234(pass) | 157.968(fail) | 58.281(fail) | 全 pass |
| 身體 | 2.308(pass) | 31.571(fail) | 95.645(fail) | 全 pass |
| 左手 | 19.238(pass) | 113.568(fail) | 27.259(fail) | 全 pass |

閾值(`THRESH_1B_EDGE`,見 `inpaint_eval.py`):`alpha_gap<=0.02`、`seam_ratio<2.2`
(沿用 `THRESH_1B` 同值)、`tone_gap<23.0`(比 interior 的 28 收緊——排除後樣本區域較窄、
統計波動較大,沿用 28 會讓「左手」的負對照 random 以些微差距 27.259<28 誤判 pass;機器人
家族正對照上限 19.238 與負對照下限 27.259 之間,23.0 留有安全邊界)。

**真實遮擋樣本(`real_occlusion_eval.py`,8 組全跑,含 3 組 edge:身體←頭/頭←右手/頭←身體)**:
`calibration.pass=True`,回歸(5 組既有 interior 案例)數字與 session 010/011 逐項一致
(如 `光暈←右手` gt seam_ratio 0.834、`身體←左手` gt seam_ratio 0.842,完全相同)。

**候選 9 揭露的關鍵案例 `頭←右手`(小尺寸圖層,46.5% 遮擋比例,edge)現在有真正判定**:

| method | applicable | pass | tone_gap |
|---|---|---|---|
| gt | True | True | 0.46 |
| none | True | False | 114.972 |
| random | True | False | 31.606 |
| nearest | True | **True** | 2.275 |
| cv2_telea | True | **True** | 3.924 |
| cv2_ns | True | **True** | 1.86 |

之前這個案例(候選 9 發現的覆蓋率缺口)完全沒有量化閘可判定,現在 1b 確認三個 CPU
baseline 全部防穿幫夠用。

## 端到端驗證(`psd_inplace_patch.py --auto --mode edge`)

`assets/robot_parts.psd 左手 --auto --mode edge`:`chosen_method=nearest`,
`chosen_reason=pass_1b`(修正 bug 前是 `1b_not_applicable_fallback_lowest_seam_ratio`,
盲選邏輯完全沒發揮新支援);`candidate_1b_scores` 三個候選皆 `applicable:true,pass:true`;
`reveal_1a_score_of_chosen`(僅自我測試用的揭曉分數)ssim=0.1359——與既有結論一致
(機械紋理 1a 補不動,但 1b 判定它「動態下夠用」),證明盲選挑到一個 1a 嚴格標準下明顯
不完美、但 1b 防穿幫標準下有把握的 baseline,符合這條鏈路的設計初衷。

## 回歸驗證(AC:不能動到既有已校準結論)

- **interior 模式完全不受影響**(`score_1b(mode="interior")` 分支邏輯與呼叫路徑逐行不變):
  機器人 3 材質 + Symbol_Ww `框`/`臉部陰影` 全部重跑,`gt`/`none`/`random` 的 `tone_gap`/
  `seam_ratio` 數值與 session 008/009 記錄完全一致(如 `框` interior gt tone_gap=32.838,
  `臉部陰影` gt tone_gap=57.296,逐位元相同);calibration.pass 維持既有的 `False`
  (原因不變:候選 8 已記錄的 `框`/`臉部陰影` tone_gap 跨材質不可攜)。
- `real_occlusion_eval.py` 既有 5 組 interior 案例(光暈←身體/右手/左手、身體←左手、
  右手←頭)的 gt/none/random 1b 分數與 session 010/011 逐項一致。
- `psd_inplace_patch.py --auto --mode interior`(左手/身體)`chosen_method`/
  `candidate_1b_scores` 與 session 007/010 記錄一致(仍選 `nearest` via `pass_1b`)。
- `select_best()`/`score_candidates()` API 變動(新增 `mode` 參數;`select_best` 的
  `applicable` 現在由呼叫端從 `score_candidates()` 回傳值讀取,不再自己用
  `mode=="interior"` 猜測)——`psd_inplace_patch.py` 兩處呼叫點已同步更新,行為對 interior
  模式完全等價(舊版 `applicable=(mode=="interior")` 對 interior 恆 True,新版從
  `score_1b` 回傳的 `applicable` 對 interior 也恆 True)。

## 已知限制延續(非新問題)

`Symbol_Ww.psd::框`(環形鏤空,厚度極薄)edge 模式的 `tone_gap` 仍不可信(gt=27.234 壓線
超過門檻,而同案例的 random=25.64 竟然更低)——這跟候選 8 已經量化證明的「`tone_gap` 跨
材質家族不可攜,`框`/`臉部陰影` 屬於此限制」是同一件事在 edge 模式下的延續,不是本次改動
引入的新缺陷(該材質在 interior 模式下本來就已經 fail calibration,見上方回歸驗證)。
`臉部陰影` 在 edge 模式下 `applicable=False`(排除真實輪廓段落後剩餘樣本 < 60px 門檻),
誠實跳過判定,不硬湊數字。

## 誠實界定

- `_exclude_real_silhouette` 的 `width`(用來判定「貼近真實輪廓」的距離)與 `min_px`
  門檻是工程參數(沿用既有 `boundary_bands`/`local_ring` 的固定寬度慣例),不是靠人工
  「這樣算貼近輪廓」的標註反推校準的——如同既有 1b 指標,仍是靠正負對照分野訂出的量化
  代理,不是使用者視覺主觀判斷的完全替代。
- `THRESH_1B_EDGE.tone_gap=23.0` 只用機器人拆件家族 3 個材質校準,樣本量不大;若未來
  有更多獨立機械材質家族素材,應比照候選 9 的作法擴大樣本交叉驗證。
- 本次只驗證了 edge 模式在「洞邊界大部分仍落在內容內部,只有一小段貼真實輪廓」的情境;
  「洞幾乎等於整條輪廓」(如遮擋件完整覆蓋掉某層一半以上且該層本身很小)的極端情況目前
  靠 `min_px` 門檻誠實標 `applicable=False`,尚未找到替代判定方式。
