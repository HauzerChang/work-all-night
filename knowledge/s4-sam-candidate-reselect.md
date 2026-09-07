# S4 chunk 59:候選重選策略(fragmented 時自動改選 largest_component_frac 最高的候選)

> 承接 chunk58 誠實限制清單提出、未實作的候選:「遇到 `low_confidence: fragmented` 時,
> 自動改選 SAM 回傳 3 個候選裡 `largest_component_frac` 最高的那個,不需人工點提示」,
> 樣本僅 2 案(`head`/`sash_train`)。本次擴大測試到 5 個已知案例(涵蓋兩種已知失敗病因),
> 量化+視覺雙重確認後**落地進 production**(`s4_sam_segment.py`)。

## 結果總覽:策略有明確適用邊界,不是萬用修法

用 box-only(不加點)對 5 個部件測試「選 argmax(scores)」vs「選 3 候選裡
argmax(largest_component_frac)」:

| 部件 | 已知病因類型 | 兩策略選中候選是否不同 | 重選後内容正確? |
|---|---|---|---|
| `head` | fragmented(乾淨候選存在,未被 argmax(scores) 選中) | 是 | ✅ 完整臉部(largest_frac 0.56→0.92) |
| `sash_train` | fragmented(同上) | 是 | ✅ 完整紅布飄帶(largest_frac 0.50→0.999) |
| `skirt` | 內容選錯但乾淨(未觸發 fragmented 旗標) | **否**(兩策略選中同一候選) | ❌ 三個候選視覺複核皆為皮膚,無一是裙擺布料 |
| `bodice` | 內容選錯(argmax(scores) 候選 largest_frac=0.629,剛好在 0.6 門檻之上而不觸發 fragmented) | 是,但無幫助 | ❌ largest_frac 最高候選(0.998)視覺複核是**手臂皮膚**,比原選中的髮絲候選更乾淨但內容更離題 |
| `sleeve_right` | 內容選錯(argmax(scores) 候選已經 largest_frac=0.999,未觸發 fragmented) | 是,但無幫助 | ❌ 三個候選視覺複核**全部是同一件胸衣/皮甲**,沒有一個是袖子 |

**結論**:這個策略只解決「乾淨候選存在、只是分數排序不可靠」這一種失效模式(chunk58 定義
的第三種病因,`head`/`sash_train` 型)。對「所有候選內容都選錯」的失效模式
(`bodice`/`sleeve_right`/`skirt` 型)完全無效,`bodice` 案例甚至證實 chunk58 的疑慮成立
——**選 largest_frac 最高的候選有時反而是內容更錯、只是形狀更乾淨的候選**(手臂皮膚
largest_frac=0.998 > 髮絲候選的 0.629)。

## 為何落地是安全的(零回歸設計)

策略**只在原選擇已經被判定 `fragmented`(`n>1 且 largest_frac<0.6`)時才嘗試重選**,
且只在找到「本身不會被判定 fragmented/too_much_fg」的替代候選時才真的換選。這個 gate
本身保證:

- `skirt`/`bodice`/`sleeve_right` 的 argmax(scores) 選中候選本來就**不是** fragmented
  (largest_frac 分別 1.0 / 0.629(剛好壓線在門檻之上) / 0.999)——三者從未觸發重選邏輯,
  行為與修改前逐位元相同,不可能被這次改動弄得更差。
- 真正驗證:對 chunk58 `decision_final.json` 拿掉 `head`/`sash_train` 的 `points` 欄位
  (回復純 box-only)重跑完整 `s4_decompose_cut.py --contour sam --eval`(20 部件真實
  pipeline,非 ad-hoc 腳本)——**`head`/`sash_train` 這次不需要任何點提示就自動修正**
  (`auto_reselected: true`,`low_confidence: false`,largest_frac 0.9237/0.9987,跟
  chunk58 人工點提示版本同等乾淨甚至更高),**其餘 18 個部件的 `sam_info` 除了多一個
  `auto_reselected: false` 欄位外,逐位元與 chunk58 基準完全相同**(已用程式逐欄位比對,
  0 處數值差異)。

## 誠實限制

- 樣本仍只涵蓋這份九尾焰蓮素材的 20 個部件、5 個測試案例(2 正面+3 確認不適用)。策略的
  gate 條件(`fragmented` 判準本身)是既有經驗閾值,非普適常數(見 `s4_sam_segment.py`
  檔頭既有警語),換一批美術風格素材時 gate 是否還能準確區分「可救」與「不可救」案例
  未知。
- `bodice`/`sleeve_right`(A 類岔路,已測 4 次點提示 + 本次候選重選皆無效)、`hair_front`
  (語意邊界待使用者確認)三者狀態未變,仍待使用者裁決/確認。
- 未產生新的「官方」決策檔/PSD——chunk58 的 `decision_final.json`(`head`/`sash_train`
  帶手動點提示)已是有效的第三份 production PSD 基礎,功能上與「拿掉點、靠自動重選」
  等價(兩條路徑此刻收斂到同樣乾淨的 mask),故不重複產出第四份僅內容相同的 PSD;此次
  改動的價值是**未來新素材遇到同類 fragmented 案例時,不再需要人工用格線疊圖+反覆測點
  才能解決**,是工具鏈本身的能力提升,非本次素材的新產出。
- 只測了「總是嘗試重選、挑 largest_frac 最高的乾淨候選」這一種重選規則;未測試其他候選
  規則(如優先原始分數次高、或加權分數與 largest_frac)。

## 檔案

- 改動 `tools/mesh_gen/s4_sam_segment.py`:`segment()` 新增自動重選邏輯 + `info` 新增
  `auto_reselected` 欄位(向後相容,舊呼叫端未讀此欄位不受影響)。
- 新增 `tools/mesh_gen/s4_data/chunk59/candidate_reselect_test.py`(5 案例 ad-hoc 驗證
  腳本)、`candidate_reselect_results.json`、各候選疊圖 PNG。
- 新增 `tools/mesh_gen/s4_data/chunk59/decision_no_headtrain_points.json`(chunk58 基準
  拿掉 head/sash_train 的 points,用於驗證自動重選)、`cut_sam_reselect/`(20 部件真實
  pipeline 輸出,`--eval` `overall_pass: true`)。
