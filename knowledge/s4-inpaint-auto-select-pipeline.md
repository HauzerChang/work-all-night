# S4 補圖「評分→採用→落地」自動鏈路(2026-08-28)

> 延續 `s4-psd-inplace-edit.md`(統一座標系)與 `s4-inpaint-1b-lenient-gate.md`(1b 寬鬆閘)。
> 打通 `STATE_S4.md` 下一步候選第 1 項:讓 `inpaint_eval.py` 的評分結果直接驅動
> `psd_inplace_patch.py` 的落地寫回,不再是兩支各自獨立的腳本。

## 問題

之前 `inpaint_eval.py` 只能對「合成挖洞、有真值」的情境評分(校準用途);
`psd_inplace_patch.py` 只能寫回「呼叫端已經手動指定好用哪個 baseline」的結果(`--method`)。
中間缺一段:**真實補圖沒有真值,要怎麼自動選 baseline?**

## 設計:1b 分數盲選

真實補圖沒有 gt 可比,不能用 1a 分數挑。但 1b(防穿幫,自我參照)天生就是為這個情境設計的
——它本來就不看真值洞內內容。所以:

- `inpaint_eval.score_candidates(holed_rgba, mask, methods)`:對候選 baseline(`nearest`/
  `cv2_telea`/`cv2_ns`,不含 `gt`/`none`/`random` 這些只能當對照組的)各跑一次、各算一次 1b 分數。
- `inpaint_eval.select_best(scored, priority, applicable)`:依優先序(便宜的先試,見
  `handoff_S4.md` 的分級 baseline 精神)挑第一個 1b pass 的;全部 fail 就退而求其次選
  `seam_ratio` 最低者,並標記 `no_pass_fallback_lowest_seam_ratio`——**這個標記本身就是
  「這次判定沒有信心」的訊號,呼叫端/後續流程不能把它當 pass 悄悄吞掉**。
- `psd_inplace_patch.patch_layer_auto(psd_path, layer_name, mask, out_path, mode)`:串起來,
  真實情境的入口——呼叫端給 mask,跑完選定的 baseline 直接寫回同一個 PSD(沿用
  `patch_layer_with_image()` 的座標系保證)。

## 關鍵 gotcha:`applicable` 旗標(這次踩到的新坑)

第一版實作漏了一件事:`s4-inpaint-1b-lenient-gate.md` 已經校準出「1b 的自我參照假設只在
`interior` 模式成立,`edge` 模式(洞跨在真實輪廓上)套用會讓正對照自己都被誤判」。但
`score_candidates`/`select_best` 一開始沒有理會這個範圍限制——直接對 edge 洞的候選分數
套用 `THRESH_1B`,會讓 edge 情境被誤標「pass_1b」(有信心的假象)。

用左手 edge 模式重現:三個候選全部 `pass:false`(`tone_gap` 53~72,遠超閾值 28),觸發 fallback,
證實若沒 gating,萬一某個候選僥倖壓線通過閾值,系統會用「pass_1b」的高信心語氣採用一個
1b 假設本來就不適用的判定。**修法**:`select_best` 新增 `applicable` 參數,`patch_layer_auto`/
`demo_auto_patch` 都要求呼叫端明確傳 `mode`(interior/edge)算出這個旗標——**這裡刻意不用
mask 自動偵測是否貼著輪廓**,因為要準確判斷「這個洞是否跨在真實輪廓上」需要知道洞打之前的
完整外形,對真實已存在的破洞不一定拿得到,寧可要求呼叫端明確告知,不猜測(RULES.md:不確定
就明說,不捏造判定)。`applicable=False` 時無論個別分數是否壓線 pass,一律走 fallback,
reason 標成 `1b_not_applicable_edge_mode_fallback_lowest_seam_ratio`,不會出現 `pass_1b`。

## 自我驗證(這條鏈路自己的評估器)

真實情境沒有 gt,沒辦法直接驗「選得對不對」。用合成挖洞模擬「盲選」情境來驗:

`psd_inplace_patch.demo_auto_patch()` —— 選擇邏輯全程只碰 1b 分數(跟真實情境一樣盲），
寫回 PSD 後才**額外**用 gt 算選中結果的 1a 分數「揭曉」(`reveal_1a_score_of_chosen`)。
這個揭曉步驟只存在於自我測試,不會出現在真實情境的 `patch_layer_auto()` 輸出裡。

跑在 `robot_parts.psd` 上的結果(`身體`,interior,seed=0):

| 項目 | 結果 |
|---|---|
| 候選(nearest/cv2_telea/cv2_ns)1b 分數 | 三個皆 pass(`alpha_gap=0`,`seam_ratio` 0.49~0.62,`tone_gap` 0.41~2.09) |
| 盲選結果 | `nearest`(優先序第一個 pass 的),reason=`pass_1b` |
| 揭曉的 1a 分數(選中結果 vs gt) | `ssim=0.33`,`reveal_1a_pass=false` |
| `psd_slice.evaluate()` 寫回後自驗 | `overall_pass: true` |

**符合預期,不是回歸**:呼應 `s4-inpaint-1b-lenient-gate.md` 已驗證的核心結果——機械紋理
案例在 1a 嚴格標準下必然 fail(這是「CPU 補不動 1a」的既有結論),但 1b(防穿幫)標準下
CPU baseline 夠用。這條鏈路的自我驗證目標不是「盲選要 1a 也 pass」(那是 1a 情境的鏈路),
而是「盲選過程誠實地只用 1b 訊號、edge 情境不會偽裝成有信心、寫回後座標系/重組仍然正確」
——三項都驗到了。

edge 模式(`左手`)重跑同一測試:三候選 1b 皆 fail,`chosen_reason` 正確標成
`1b_not_applicable_edge_mode_fallback_lowest_seam_ratio`,沒有出現 `pass_1b`。

## 回歸測試

- 舊的 `--method`(單一手動指定 baseline)路徑不變,`--eval` 仍 `overall_pass: true`。
- `psd_slice.py --eval` 對原始 `robot_parts.psd`(未修改)重跑無回歸(`overall_pass: true`)。
- `inpaint_eval.py` 主流程(合成挖洞校準,`calibration.pass`)對「身體」件重跑仍 `true`。
- 新增 `--mask`(真實情境 CLI 入口,吃一張外部遮罩 PNG)與 `--auto`(合成自測入口)互斥,
  CLI 檢查兩者同時給會報錯。

## 用法

```
# 真實情境:呼叫端已經知道洞在哪(mask PNG,非0=要補的區域),明確指定 interior/edge
python3 psd_inplace_patch.py <psd> <圖層名> --mask hole_mask.png --mode interior -o out.psd --eval

# 自我測試/評估器:合成挖洞模擬盲選情境,驗證選擇邏輯本身
python3 psd_inplace_patch.py <psd> <圖層名> --auto --mode interior --seed 0 -o out.psd
```

## 誠實界定

- `select_best` 的優先序固定「便宜的先試」(nearest → cv2_telea → cv2_ns),不是「分數最好的
  先選」——同一批全 pass 時可能選到 `tone_gap` 較差(但仍在閾值內)的候選(如上面 `身體` 案例
  選中 `nearest` 而非 `tone_gap` 更低的 `cv2_telea`)。這是刻意的分級策略(見
  `handoff_S4.md`),不是 bug;若要優化「同 pass 內選最好」,之後可以把 `select_best` 改成
  「先過濾 pass,再按 seam_ratio/tone_gap 加權排序」,目前還沒做。
- `applicable` 旗標要求呼叫端明確傳入,不是自動偵測——這對「已存在的真實破洞」是合理限制
  (通常美術/上游流程知道這個洞的性質),但如果之後要接一個全自動、無人工標註的管線,這裡
  會是一個需要額外解的子問題。
- 1b 本身的誠實界定(閾值靠正負對照校準、非人工穿幫標註反校準)沿用
  `s4-inpaint-1b-lenient-gate.md`,這裡沒有重新處理。
