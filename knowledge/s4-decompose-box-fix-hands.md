# S4 拆解流程:修正 hand_left/hand_right 決策檔框位置錯誤(chunk 50)

> 承接 chunk 49 的做法(在 `assets/jiuwei_yanlian_char_crop.suggestions.json` 源頭修正錯誤框),
> 本次排程無活人可裁決,依既有慣例(chunk 26/49)獨立檢查 chunk 48 留下的第三個「框有問題」
> 案例 `hand_right`,並在複查過程中**額外發現 `hand_left` 也是同類型的框完全沒對準錯誤**
> (先前未被任何 chunk 標記出來)。兩個都是零成本、視覺可直接確認的框位置修正。

## 背景

- `hand_right`:chunk 48 已在 `knowledge/s4-sam-point-prompt-investigation.md` 記錄「框
  (345,422,409,512)只有右下角一小塊擦到真正的手腕/手掌,大部分框住符紙標籤+白紗」,歸類為
  「框沒對準」問題,但列在 3 個「真正分割語意歧義」案例裡未優先處理,chunk 49 也明確記錄
  「本次沒有修正」。核對 `suggestions.json` 換算出的像素框 `bbox_pct=[75,47,89,57]` →
  `(345,422,409,511)`,跟 chunk 48 報告的錯誤座標幾乎完全吻合(誤差 1px 屬四捨五入),確認
  跟 `leg_left`/`boot_left` 同一種情況:草稿從 chunk 43 就錯,可以在源頭直接修正。
- `hand_left`:chunk 47(`knowledge/s4-sam-segment.md`)用「使用者手動確認過的真實決策檔」
  測試,把 `hand_left` 列在「9 個明確正確」名單裡。但那份真實決策檔跟 chunk 49 已確認的
  `leg_left`/`boot_left` 一樣,**只有部分欄位跟 `suggestions.json` 草稿一致**——本次獨立用
  網格疊圖工具檢視 `suggestions.json` 的 `hand_left` 框(`bbox_pct=[13,50,26,59]`→像素
  `(59,449,119,529)`),發現這個框完全落在**尾巴/翅膀狀白色毛髮紋理**區域,附近完全沒有
  手的內容——跟「明確正確」的回報矛盾。**結論**:使用者當次應該有手動調整過 `hand_left`
  的框才使它在真實決策檔裡是對的,但那次調整沒有被持久化進 repo,所以 `suggestions.json`
  這份草稿裡的 `hand_left` 座標其實一直是錯的,只是之前沒人拿它跟真實決策檔比對過,沒被
  發現。

## 定位過程

用網格疊圖工具(bash+PIL,座標網格疊在放大裁圖上)分別在原框周圍擴大視野搜尋兩隻手的真實
位置:

- **`hand_left`**:原框 `(59,449,119,529)` 落在角色左側九尾狐尾/翅膀狀白色毛髮束上。往右
  擴大搜尋,實際的左手(手腕纏紅色絲帶、五指自然下垂含粉色指甲)位於 `(132,423,218,558)`
  附近,跟原框完全不重疊(原框最右緣 x=119,實際手部從 x=132 開始)。
- **`hand_right`**:原框 `(345,422,409,511)` 大部分落在符紙標籤(木牌)與半透明白紗上,只有
  右下角 `x≈390-409,y≈460-511` 一小塊擦到手腕/紅色絲帶(呼應 chunk 48 原始描述)。實際的
  右手(同樣手腕纏紅色絲帶、五指微彎)完整範圍在 `(378,443,450,588)`,手掌與手指主體在原框
  範圍之外(原框下緣 y=511 就切掉了,實際手指延伸到 y≈588)。

## 修正方式

比照 chunk 49 的允許邊緣夾帶做法(不苛求零 bleed,框住可見主體即可):

| id | 舊 bbox_pct(錯) | 新 bbox_pct | 新 bbox_px(460×898) |
|---|---|---|---|
| `hand_left` | `[13,50,26,59]` | `[29,47,47,62]` | `(132,423,218,558)` |
| `hand_right` | `[75,47,89,57]` | `[82,49,98,65]` | `(378,443,450,588)` |

同時把兩個 part 的 `confidence` 從 `high` 下修為 `medium`,並在 `notes` 記錄修正原因,
`hand_left` 額外記錄「chunk47/48『明確正確』判定用的是未持久化的真實決策檔,跟這份草稿不是
同一份輸入」以避免下游誤解。

## 自我驗證

用修正後的 `suggestions.json` 重建一份 20 部件 `bbox_px` 決策檔
(`tools/mesh_gen/s4_data/chunk50/decision_reconstructed.json`,承接 chunk 49 的重建檔,只
再改 `hand_left`/`hand_right` 兩項座標,其餘 18 項不變),跑 `s4_decompose_cut.py --contour
rect --eval`:

- `AC1_parts_produced`:20/20 部件全部產出,`overall_pass: true`。
- 逐格人工視覺複核修正後的 `09_hand_left.png`/`10_hand_right.png`:
  - `hand_left`:裁出畫面確實是**左手**(手腕紅色纏繞絲帶+完整五指,含粉色指甲),邊緣夾帶
    少量白紗背景,屬允許範圍內的 bleed。
  - `hand_right`:裁出畫面確實是**右手**(手腕紅色纏繞絲帶+完整五指),邊緣夾帶少量白紗與
    符紙標籤邊角,同樣屬允許 bleed。
- 修正前後對照見 `tools/mesh_gen/s4_data/chunk50/cut_rect/`(僅保留
  `09_hand_left.png`/`10_hand_right.png`/`manifest.json` 作證據,其餘 18 個部件的裁圖已
  刪除,避免 repo 堆放跟本次修正無關的檔案)。

## 誠實限制

- 跟 chunk 49 一樣,本次用的 20 部件決策檔是從修正後的 `suggestions.json` 重新換算,**不是**
  chunk 46-48 使用者手動調整過的那份真實決策檔(那份檔案本身沒有持久化進 repo),不能拿來
  延續 chunk 47 的統計數字(9 個明確正確 / 5 個靜默錯誤等)。
- `hand_left` 這次修正代表:**`suggestions.json` 草稿至少有 3 個部件(`leg_left`/
  `boot_left`/`hand_left`)存在「使用者當次手動修好但未持久化」的落差**,只是前兩個先前已
  被 chunk 48 的目視複核發現,`hand_left` 是本次才發現。這提高了一個疑慮:`suggestions.json`
  草稿裡目前「看起來沒被回報過問題」的其餘部件(如 `earrings`/`sash_train`/`tails_mass` 等
  本來就標 `low`/`medium` 信心的項目),**不能因為沒被回報過就假設框是對的**——只是還沒被
  用同樣方法逐一複查。若後續要對這份草稿做更全面的信任度盤點,建議把剩餘部件也逐一跑一次
  網格疊圖複核,而非只等下游回報才修。
- 沒有重跑 `--contour sam`:跟 chunk 49 理由相同(容器未持久化 MobileSAM 權重),矩形裁切的
  視覺驗證已足以證明「框位置本身修好了」,SAM 精修屬於 chunk 48 選項 (c) 的範疇,不在本次
  零成本修正動作內。
- 兩隻手在畫面上本身是分離、可清楚辨識的獨立內容(不像 `leg_left`/`boot_left` 有腿部本身重疊
  不可分的素材限制),修正後的框沒有已知的殘留視覺歧義。

## 檔案

- 修改 `assets/jiuwei_yanlian_char_crop.suggestions.json`:`hand_left`/`hand_right` 兩個
  part 的 `bbox_pct`/`confidence`/`notes`。
- 新增 `tools/mesh_gen/s4_data/chunk50/decision_reconstructed.json`(從修正後
  `suggestions.json` 換算的 20 部件 `bbox_px` 決策檔,供重現本次驗證)。
- 新增 `tools/mesh_gen/s4_data/chunk50/cut_rect/`(`09_hand_left.png`/
  `10_hand_right.png`/`manifest.json`,修正後的裁圖證據)。
- 新增本篇 `knowledge/s4-decompose-box-fix-hands.md`。
- 未修改 `s4_decompose_cut.py`/`s4_sam_segment.py`/`s4_decompose_assist.html` 等任何
  production 代碼。
