# S4 chunk 58:`head`/`sash_train` 點提示測試 —— 正面結果,並發現第三種失敗病因

> 承接 chunk57 誠實限制清單:`head`/`sash_train` 是 chunk47/54 起就被 heuristic 正確標記
> `low_confidence`(fragmented)的兩個部件,`bodice`/`sleeve_right` 已測 4 次點提示無效
> (A 類岔路)、`skirt` 已測點提示有效並落地(chunk55-57),但 `head`/`sash_train` 從未
> 測過點提示——本次補上,並把它們正式落地進第三份 production PSD。

## 結果總覽

**點提示對 `head`/`sash_train` 都有效**,且本次額外發現：這兩者的失敗病因跟 `skirt`
也不同——**不是「候選物件選錯」,而是「正確的乾淨候選其實已經存在於 SAM 回傳的 3 個
候選遮罩裡,只是不是分數最高的那個」**。

| 部件 | box-only(baseline) | 最佳點提示版本 |
|---|---|---|
| `head` | `fg_ratio=0.4117, n=4, largest_frac=0.5612`(❌ fragmented,人臉被髮絲分成碎片) | `pos_face_neg_hair`: `fg_ratio=0.2447, n=3, largest_frac=0.8169`(✅ 單一完整人臉) |
| `sash_train` | `fg_ratio=0.4204, n=7, largest_frac=0.5035`(❌ fragmented,紅布+黑靴混在一起) | `pos_fabric_neg_neighbor`: `fg_ratio=0.3013, n=8, largest_frac=0.998`(✅ 單一完整紅布飄帶) |

baseline 數字跟 chunk47/54 記錄的 `low_confidence: fragmented` 完全重現(見下方
「baseline 重現」)。

## 關鍵發現:第三種「框正確、SAM選錯」病因

chunk48/55 已知兩種病因：

- **`bodice`/`sleeve_right` 型**:候選物件在特徵空間離目標很近(髮絲/胸衣;胸衣/袖子),
  點提示救不了。
- **`skirt` 型**:候選物件特徵空間差異夠大(皮膚 vs 布料),純 box prompt 缺方向性,
  加一點就能扭轉整個選擇。

本次對 `head`/`sash_train` 逐一檢視 SAM box-only 回傳的 **3 個候選遮罩各自的分數與
連通度**(而不是只看被 `argmax(scores)` 選中的那個),發現：

- `head` box-only 三候選:`cand0 score=0.7336 largest_frac=0.9237`(乾淨完整臉部,
  未被選中)、`cand1 score=0.7488 largest_frac=0.5612`(fragmented,被 argmax 選中)、
  `cand2 score=0.7038 largest_frac=0.5878`。
- `sash_train` box-only 三候選:`cand0 score=0.7526 largest_frac=0.9897`、
  `cand1 score=0.8626 largest_frac=0.9987`(乾淨完整紅布飄帶,未被選中)、
  `cand2 score=0.9308 largest_frac=0.5035`(fragmented,混入黑靴,被 argmax 選中)。

**兩案例中,乾淨/單一連通的候選都已經存在於 SAM 的 3 個輸出裡,只是恰好不是
`argmax(scores)` 選中的那個**——這是第三種病因:**SAM 自身的分數排序不可靠,不是
「所有候選都選錯內容」,也不是「純 box prompt 缺方向性」,而是「候選選擇策略
(`argmax(scores)`)本身有時挑到品質較差的候選」。點提示的作用在這裡不是「重新指向
正確物件」,而是**改變 3 個候選各自的分數,把原本分數較低的乾淨候選推到最高分**
(`head`:加點後 `cand0` 分數從 `0.7336→0.9078` 躍居第一;`sash_train`:加點後仍是
`cand2`原型的鄰居分數下降、`largest_frac` 從 0.5035 提升到 0.998,細節見下方逐格結果)。

**方法論意義**:除了「逐案實測點提示是否有效」(chunk55 已建立的結論)之外,這次額外
建議——**遇到 `low_confidence: fragmented` 的案例,除了測點提示,也該先看一眼 box-only
的 3 個候選裡有沒有已經乾淨的**(這是免費的診斷步驟,不需要任何點提示或使用者輸入,
只是目前 `s4_sam_segment.py` 的 `segment()` 只回傳 argmax 選中的那個,沒有暴露其餘
兩個候選讓呼叫端檢視)。這意味著除了「加點提示」,理論上還有一個更便宜的候選修法:
**遇到 fragmented 時,自動改選 3 個候選裡 `largest_component_frac` 最高的那個**,完全
不需要人工點提示。本次**未實作**這個候選修法(屬於 production 代碼異動,且只驗證了
2 個案例、樣本太小不足以確認是普遍規律),留給後續作為新候選。

## Baseline 重現

用 chunk57 `decision_final.json` 的框(`head=[184,90,359,216]`,
`sash_train=[129,494,350,862]`)重跑純 box-prompted SAM(不加點):

- `head`:`fg_ratio_in_box=0.4117, n_components=4, largest_component_frac=0.5612` →
  `low_confidence=True, reason=fragmented`。跟 chunk54 記錄的攔截結果一致。
- `sash_train`:`fg_ratio_in_box=0.4204, n_components=7, largest_component_frac=0.5035`
  → `low_confidence=True, reason=fragmented`。跟 chunk47/54 記錄一致。

視覺複核 baseline mask(見 `tools/mesh_gen/s4_data/chunk58/head_box_only.png`、
`sash_train_box_only.png`):`head` 的 mask 大致覆蓋整張臉+頸部但明顯碎裂(髮絲穿過
臉部造成不連通);`sash_train` 的 mask 把紅布飄帶跟旁邊黑色皮靴的紋理混在一起,呈現
斑駁交錯的雜訊狀。

## 方法:比照 chunk55,先放大格線疊圖確認座標再選點

- `head`:格線疊圖(`grid_head.png`,`step=20px`)確認額頭花鈿約 `(272,120)`、鼻樑
  約 `(277,158)`、嘴唇約 `(270,178)`、下巴約 `(270,198)`;負向點放在左右兩側灰髮
  髮絲 `(210,110)`/`(335,110)`。
- `sash_train`:格線疊圖(`grid_sash_train.png`,`step=30px`)確認紅布飄帶主體沿飄動
  方向約 `(210,600)`/`(220,680)`/`(210,750)`;負向點放在黑色皮靴 `(450,650)` 與
  露出膚色大腿 `(370,540)`。

## 逐格測試結果

| 部件 | case | 點 | scores | chosen | fg_ratio | n | largest_frac | 視覺 |
|---|---|---|---|---|---|---|---|---|
| head | box_only | 無 | [0.734,0.749,0.704] | 1 | 0.412 | 4 | 0.561 | ❌ 臉部碎裂 |
| head | pos_face | 4 正向(額/鼻/唇/下巴) | [0.897,0.739,0.788] | 0 | 0.241 | 3 | 0.837 | ✅ 完整臉部 |
| head | pos_face_neg_hair | 上述4正向+2負向(兩側髮絲) | [0.908,0.741,0.796] | 0 | 0.245 | 3 | 0.817 | ✅ 完整臉部(已存疊圖確認) |
| sash_train | box_only | 無 | [0.753,0.863,0.931] | 2 | 0.420 | 7 | 0.504 | ❌ 混入黑靴紋理 |
| sash_train | pos_fabric | 3 正向(布料主體) | [0.740,0.877,0.933] | 2 | 0.303 | 27 | 0.979 | 大致乾淨(仍有多個極小碎片) |
| sash_train | pos_fabric_neg_neighbor | 上述3正向+2負向(靴/腿) | [0.788,0.875,0.909] | 2 | 0.301 | 8 | 0.998 | ✅ 完整紅布飄帶(已存疊圖確認) |

`head` 和 `sash_train` 各自最佳版本 `largest_component_frac`(0.817、0.998)都遠高於
`LOW_CONFIDENCE_LARGEST_COMPONENT_FRAC=0.6` 門檻,`fg_ratio`(0.245、0.301)也遠低於
`LOW_CONFIDENCE_FG_RATIO=0.75` 門檻——兩者用真正的 `SamSegmenter.segment()`(見下方
「落地驗證」)確認 `low_confidence: false`。

## 落地驗證:第三份 production PSD

不同於 chunk55(純驗證,未落地),這次因為點提示的 production 接線(schema/
`s4_sam_segment.py`/`s4_decompose_cut.py`/`s4_decompose_assist.html`)在 chunk56 已經
做好,本次直接把 `head.points`(`pos_face_neg_hair` 版)與 `sash_train.points`
(`pos_fabric_neg_neighbor` 版)疊加進 chunk57 `decision_final.json` 的基準,存成
`tools/mesh_gen/s4_data/chunk58/decision_final.json`,程式驗證**除了這兩個部件多了
`points` 欄位,其餘 18 個部件跟 chunk57 基準位元級相同**,跑完整
`s4_decompose_cut.py --contour sam --eval` → `manifest_to_psd.js`,產出
`jiuwei_yanlian_decompose_sam_v2.psd`(20 圖層)——**第三份 production PSD**。

- **AC1**:20/20 部件產出,`overall_pass: true`。
- **`head`/`sash_train` sam_info(真正 production pipeline,非 ad-hoc 腳本)**:
  `head`:`fg_ratio_in_box=0.2447, n_components=3, largest_component_frac=0.8169,
  low_confidence=false`;`sash_train`:`fg_ratio_in_box=0.3013, n_components=8,
  largest_component_frac=0.998, low_confidence=false`——跟 ad-hoc 驗證腳本數字完全
  一致。
- **其餘 18 部件無回歸**:逐欄位比對本次 `manifest.json` 的 `sam_info` 跟 chunk57
  `cut_sam/manifest.json`——**完全相同,0 處差異**。
- **AC2**(PSD 圖層幾何 round-trip):psd-tools 重開 PSD,逐圖層比對
  `name`/`offset`/`size`——20/20 完全相符。
- **AC3**(PSD 圖層像素 round-trip,沿用 chunk57 教訓改用 premultiplied-alpha 比對,
  不用 straight RGBA):20/20 `premult_max_diff=0` 且 `alpha_max_diff=0`,位元級無損。
- **視覺複核**:`00_head.png`、`14_sash_train.png` 皆為單一乾淨形狀(人臉/紅布飄帶),
  無碎片破圖;`06_bodice.png` 複查維持 chunk54/57 記錄的失敗模式(選到深色髮絲非紅色
  胸衣),確認無新回歸。

## 誠實限制 / 未做的事

- **候選修法「fragmented 時自動改選最高 largest_frac 的候選」未實作**:本次只是在
  `head`/`sash_train` 兩案發現這個現象並記錄,樣本太小,且需要修改
  `s4_sam_segment.py` 的 `segment()` 回傳邏輯(目前寫死 `argmax(scores)`),屬於
  production 代碼異動,留給後續評估是否投入(潛在好處:比點提示更便宜,不需要人工
  互動;風險:未驗證這個策略在其餘已知案例——尤其 `bodice`/`sleeve_right`——是否
  同樣有效或反而更差,`bodice`/`sleeve_right` 目前每個候選可能全部都選錯內容,不是
  單純連通度問題,選最高 `largest_frac` 的候選未必是對的)。
- `bodice`/`sleeve_right`(A 類岔路,已測 4 次點提示無效)、`hair_front`(需使用者用
  assist viewer 確認語意邊界)三者在這份 PSD 裡原樣未解,跟 chunk53/57 一致。
- `sash_train` 最佳版本 `n_components=8`(仍有小碎片,`largest_frac=0.998`),不是
  完美單一連通,但碎片極小(視覺確認為背景雜訊點,不影響部件可用性)。
- 未測試更大規模的座標敏感度掃描(比照 chunk55 的做法,單組座標 + 1 組加負向點的變體
  即視為已驗證,邊際報酬遞減)。
- torch/timm/MobileSAM 原始碼與權重、`npm` node_modules 皆為本次容器內暫存,不預期
  持久化,下次排程需重裝(指令已記錄於 `knowledge/s4-sam-segment.md`)。
- 未修改任何既有 production 代碼(`s4_sam_segment.py`/`s4_decompose_cut.py`/
  `manifest_to_psd.js` 沿用 chunk56/57 版本,零改動,本次純資料/產出)。

## 對候選清單的更新

- ~~`head`/`sash_train` 需要測點提示~~ → **已解**:兩者點提示皆有效,已落地進第三份
  production PSD。
- 新增候選:**候選選擇策略改進**(fragmented 時改選 3 個候選裡 `largest_component_frac`
  最高者,可能不需點提示就解決問題)——樣本僅 2 案,價值待更多案例驗證後評估是否投入。
- `bodice`/`sleeve_right`(A 類岔路)、`hair_front`(語意邊界待使用者確認)維持既有
  狀態,未產生新的懸而未決項。

## 檔案

- 新增 `tools/mesh_gen/s4_data/chunk58/point_prompt_test.py`(一次性驗證腳本)、
  `grid_head.png`/`grid_sash_train.png`(格線疊圖)、`head_*.png`/`sash_train_*.png`
  (各候選/測試案例疊圖)、`point_prompt_results.json`。
- 新增 `tools/mesh_gen/s4_data/chunk58/decision_final.json`(chunk57 基準 +
  head/sash_train 點提示)、`cut_sam/`(20 張部件 PNG + composite.png + manifest.json)、
  `jiuwei_yanlian_decompose_sam_v2.psd`(第三份 production PSD)。
