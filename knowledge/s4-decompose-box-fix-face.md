# S4 拆解流程:修正 head/fox_ears/hair_front/earrings/choker 決策檔框位置錯誤(chunk 51)

> 承接 chunk 50 留下的候選項「對 `suggestions.json` 其餘部件(尤其 `low`/`medium` 信心項目)
> 逐一跑網格疊圖複核,盤點是否還有同類『框完全沒對準但沒被回報』的落差」。本次排程無活人
> 裁決,依既有慣例(chunk 26/49/50)執行零成本、視覺可直接確認的框位置修正。**這次盤點的
> 範圍是角色頭部/頸部一帶(先前 chunk 47-50 只盤點過下半身的手/腿/靴子),結果發現這一帶
> 問題比預期更集中、更嚴重**——5 個部件裡有 5 個框都對不準,而且原始信心大多標 `high`。

## 背景與方法

用 bash+PIL 把 `suggestions.json` 20 個部件的 `bbox_pct` 全部換算成像素、逐一裁出來看過
一輪(不是只挑可疑的看,是全部 20 個都裁圖檢視)。下半身(`leg_left`/`leg_right`/
`boot_left`/`boot_right`/`hand_left`/`hand_right`)已在 chunk 47-50 逐一驗證過,本次
略過;`sash_train`/`hair_main`/`tails_mass` 是已知本來就難的大範圍重疊材質(chunk 43/47
已標低信心且被自動 heuristic 攔截過),本次也不重複處理。剩下沒被任何 chunk 驗證過的
9 個部件全部裁圖檢視,發現其中 **5 個(head/fox_ears/hair_front/earrings/choker)是同一種
「框大部分落在畫面上方的標題文字/引言文字區域,完全或大部分沒框到自己的標籤內容」的錯誤**。

其餘 4 個(`bodice`/`sleeve_right`/`tag_pendant`/`skirt`)裁圖後有跟鄰近部件內容重疊的跡象
(呼應 chunk 47 SAM 測試已記錄的「框跟鄰居重疊」問題),但**這次沒有進一步處理**——這類是
邊界鬆緊的語意歧義(框大致有碰到自己的目標,只是也夾帶了鄰居的一大塊),跟本次要修的「框
完全落在錯誤區域」不是同一種問題,已有 chunk 48 的既有結論(`bodice`/`sleeve_right` 屬於
「真正演算法歧異,點提示測試過仍解不了」,需人工/更貴的方法處理),不重複下判斷。

## 定位過程

用網格疊圖(bash+PIL,座標網格疊在放大裁圖上,标注實際像素座標)在角色頭/頸部區域
(約 x:100-420, y:0-280)反覆定位五官/耳朵/耳環/頸飾的真實位置,確認畫面版面是「圖片上方
1/4 是標題『九尾·焰蓮 JIUWEI·YANLIAN』+ 引言『顛焰生蓮,狐影惑心』文字疊在深色背景上,
角色的臉/耳朵從畫面中段才開始」。

| id | 標籤 | 舊 bbox_pct(錯) | 舊框實際內容 |
|---|---|---|---|
| `head` | 頭部(含五官) | `[25,3,65,18]` | 大部分是標題文字,只有右下角小塊擦到眉毛/耳根,**沒有**鼻子/嘴巴/下巴 |
| `fox_ears` | 狐耳(雙耳) | `[30,0,75,8]` | 大部分是標題文字,只有底部一小條擦到耳尖 |
| `hair_front` | 瀏海/額前髮絲 | `[28,5,62,15]` | 大部分是引言文字+背景,只有右緣擦到少量髮絲 |
| `earrings` | 耳環(雙耳) | `[58,15,70,21]` | 框住的是鼻子/嘴巴/下巴(臉部),**沒有**耳環 |
| `choker` | 頸飾(紅色蝴蝶結+墜飾) | `[46,19,58,25]` | 大部分是裸露肩膀/髮絲,只有右緣擦到頸飾邊緣,**沒有**頸飾主體 |

## 修正方式

比照 chunk 49/50 的允許邊緣夾帶做法(不苛求零 bleed,框住可見主體即可):

| id | 新 bbox_pct | 新 bbox_px(460×898) |
|---|---|---|
| `head` | `[40,10,78,24]` | `(184,90,359,216)` |
| `fox_ears` | `[38,1,78,19]` | `(175,9,359,171)` |
| `hair_front` | `[35,2,80,20]` | `(161,18,368,180)` |
| `earrings` | `[68,16,73,21]` | `(313,144,336,189)` |
| `choker` | `[48,19,72,26]` | `(221,171,331,233)` |

五個 part 的 `confidence` 都從 `high`(`hair_front` 原本已是 `medium`)下修為 `medium`,
`notes` 記錄修正原因。

## 自我驗證

從修正後的 `suggestions.json` 重建 20 部件 `bbox_px` 決策檔
(`tools/mesh_gen/s4_data/chunk51/decision_reconstructed.json`),跑 `s4_decompose_cut.py
--contour rect --eval`:

- `AC1_parts_produced`:20/20 部件全部產出,`overall_pass: true`。
- 逐格人工視覺複核修正後的 5 張裁圖(`tools/mesh_gen/s4_data/chunk51/cut_rect/`):
  - `head`:完整臉部(額頭紅色印記、雙眼、鼻子、嘴唇、下巴),邊緣夾帶少量髮絲/耳朵,屬允許
    bleed。
  - `fox_ears`:兩隻完整狐耳(尖端到耳根),邊緣夾帶部分臉部,屬允許 bleed。
  - `hair_front`:確實是頭髮內容(雙耳之間、額頭上方的髮絲),不再是文字;但跟 `head`/
    `fox_ears` 新框有大幅重疊(見下方誠實限制)。
  - `earrings`:清楚可見金色墜飾+紅色流蘇耳環。
  - `choker`:清楚可見紅色蝴蝶結+金色墜飾頸飾。

## 誠實限制

- **`hair_front` 的精確語意邊界沒有解**:「瀏海」跟「頭部」「狐耳」在這個髮型(長直髮,雙耳
  外露,沒有明顯瀏海瀏海分界)下本身就沒有清楚的分割線,這次新框只保證「框內是頭髮而非
  文字」,不代表這是語意上最貼切的「瀏海專屬」範圍——跟 `sash_train`/`hair_main` 一樣是
  需要人用 assist viewer 手動確認的主觀切分,不強行用演算法解。
- **`earrings` 只框到單耳**:畫面上只有 character 右耳的耳環清楚可見(金色墜飾+紅色流蘇),
  左耳完全被長髮遮住,看不到第二個耳環。標籤寫「雙耳」但這個框只能反映看得到的那一只,
  若後續需要真正雙耳都有 slot,這個限制需要另外處理(可能是遮擋恢復,不是框選問題)。
- **本次盤點仍不是全部 20 個部件的完整驗證**:`bodice`/`sleeve_right`/`tag_pendant`/`skirt`
  這 4 個裁圖後有跟鄰近部件重疊的跡象,但沒有像本次 5 個一樣做「框完全對錯」的判定,留給
  後續 chunk(`bodice`/`sleeve_right` 已知是 chunk 48 的演算法歧異案例,`tag_pendant`/
  `skirt` 是本次新觀察到、還沒深入定位的疑慮)。
- 驗證用的 20 部件決策檔延續 chunk 49/50 做法,從 `suggestions.json` 重新換算,不是
  chunk 46-48 使用者手動調整過的那份真實決策檔,不能延續其統計數字。
- 沒有重跑 `--contour sam`(容器未持久化 MobileSAM 權重),矩形裁切的視覺驗證已足以證明
  框位置本身修好。

## 檔案

- 修改 `assets/jiuwei_yanlian_char_crop.suggestions.json`:`head`/`fox_ears`/`hair_front`/
  `earrings`/`choker` 五個 part 的 `bbox_pct`/`confidence`/`notes`。
- 新增 `tools/mesh_gen/s4_data/chunk51/decision_reconstructed.json`(20 部件 `bbox_px`
  決策檔,供重現本次驗證)。
- 新增 `tools/mesh_gen/s4_data/chunk51/cut_rect/`(僅保留本次修正的 5 張裁圖 +
  `manifest.json` 作證據)。
- 新增本篇 `knowledge/s4-decompose-box-fix-face.md`。
- 未修改 `s4_decompose_cut.py`/`s4_sam_segment.py`/`s4_decompose_assist.html` 等任何
  production 代碼。
