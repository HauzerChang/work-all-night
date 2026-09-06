# S4 chunk 55:對 `skirt`(chunk54 新發現的靜默錯誤)測點提示 —— 正面結果

> 承接 chunk 54「下一步候選 1」:`skirt` 是 chunk54 才首度用 SAM 測試出的靜默錯誤
> (選到皮膚而非裙擺紅布),跟 chunk48 已測過 4 次點提示無效的 `bodice`/`sleeve_right`
> 是不同材質/重疊模式,chunk54 明確標註「值得獨立測試而非直接假設無效」。本次結果:
> **點提示對 `skirt` 有效**,跟 `bodice`/`sleeve_right` 的負面結果不同。

## 背景:baseline 先重現失敗

用 chunk53 決策檔的 `skirt` 框(`bbox_px=[156,359,327,548]`)重跑純 box-prompted
SAM(不加點),確認能重現 chunk54 的失敗結果:`fg_ratio_in_box=0.1964`(chunk54 原始
記錄 `fg_ratio=0.20`,一致),選中的是皮膚(大腿)形狀,不是裙擺紅布主體。見
`tools/mesh_gen/s4_data/chunk55/skirt_box_only.png`(紅色疊圖 = mask,可見疊在大腿上)。

## 方法:比照 chunk48,先放大確認座標再選點

用網格疊圖工具(`step=20px`)放大框內容,目視確認紅色裙擺布料主體(含金色刺繡紋樣)在
畫面右上區域(約 x=220~320, y=380~460),皮膚(大腿)在下方(約 y=470~540)。

## 結果:加正向點後乾淨選中裙擺,單點就夠,5/5 組合皆成功

| 測試 | 點 | fg_ratio_in_box | n_components | largest_component_frac | 內容(視覺確認) |
|---|---|---|---|---|---|
| `box_only`(baseline) | 無 | 0.196 | 2 | 0.819 | ❌ 皮膚(大腿) |
| `pos_only` | 2 正向點(裙擺布料) | 0.445 | 1 | 1.0 | ✅ 乾淨裙擺紅布 |
| `pos_neg` | 2 正向 + 2 負向(皮膚/手) | 0.459 | 3 | 0.998 | ✅ 乾淨裙擺紅布(主體同 pos_only,多出微小碎片) |
| `single_pt_A` | 單一正向點 (260,395) | 0.453 | 1 | 1.0 | (僅量化,未存疊圖) |
| `single_pt_B` | 單一正向點 (290,420) | 0.448 | 1 | 1.0 | ✅ 乾淨裙擺紅布(已視覺確認) |
| `single_pt_C` | 單一正向點 (230,410) | 0.457 | 1 | 1.0 | ✅ 乾淨裙擺紅布(已視覺確認) |

**5 種點提示組合(2 正向點、正向+負向、3 種不同座標的單一正向點)全部成功**,選出的形狀
一致是完整裙擺輪廓、單一連通元件、fg_ratio 穩定落在 0.44~0.46 區間——不是巧合單次結果。
不需要負向點,單一正向點就足夠(比 `bodice`/`sleeve_right` 當時測的正負點組合更省)。

## 跟 chunk48(`bodice`/`sleeve_right`)的對比:不是同一種失敗模式

chunk48 對 `bodice`/`sleeve_right` 測了 4 次點提示(正向點、正向+負向點)全部失敗,
結論是「點提示對這兩個案例沒有可靠修正能力」。這次 `skirt` 的點提示卻穩定成功,說明
chunk54 的判斷(「材質/重疊模式不同,值得獨立測試」)是對的——**「框正確、SAM選錯」這個
症狀底下至少有兩種不同的病因**:

- `bodice`/`sleeve_right` 型:候選物件本身在特徵空間離目標很近(髮絲/胸衣;胸衣/袖子),
  點提示不足以扭轉模型對「哪個候選比較顯著」的判斷。
- `skirt` 型:候選物件(皮膚 vs 裙擺布料)特徵空間差異夠大,只是純 box prompt 沒有方向性
  訊息時模型選錯,加一個點就足以扭轉。

**沒有辦法只看「框正確但SAM選錯」這個症狀就預判點提示有沒有用,需要逐案實測**——這是
本次除了「skirt 這個案例本身解決了」以外,更有一般性的方法論結論。

## 誠實限制 / 未做的事

- **未修改任何 production 代碼**(`s4_sam_segment.py` 的 `segment()` 目前只接受
  `bbox_xyxy`,不支援點提示參數)。這次驗證證明點提示對 `skirt` 有價值,但要讓它進
  production pipeline,需要:(1) 決策檔 schema 加「輔助點」欄位、(2)
  `s4_decompose_assist.html` 加互動點選 UI(chunk48 當時把骨架蓋出來又還原,因為那次
  驗證是負面結果;這次是正面結果,補做 UI 有實際意義了)、(3) `s4_decompose_cut.py`
  接線讀取決策檔裡的點資訊傳給 `SamSegmenter`。這些都還沒做,留給下一次排程。
- 未對 `hair_front`(chunk54 已知的框重疊案例,非分割演算法問題)測點提示——那是語意
  邊界問題(需使用者用 assist viewer 裁決瀏海/頭部/狐耳的分界),不是這類「候選選錯」
  問題,測點提示不會有幫助,故意跳過。
- 只測了單一組正向點座標的 3 種變體 + 1 組正負點組合,沒有做更大規模的座標敏感度掃描
  (例如網格化掃描整個框內數十個點各自的成功率)——5/5 全部成功已經是相當一致的訊號,
  邊際報酬遞減,沒有繼續加碼測試。
- 未產出新版 PSD(這次是驗證性質,`bodice`/`sleeve_right` 仍未解,组一份「部分修正」
  的 PSD 意義有限,留到下面的 production 接線完成、能一次處理所有已知案例後再組)。

## 對候選清單的更新

- ~~`skirt` 需要跟 `bodice`/`sleeve_right` 一樣的處理方式決策~~ → **已解:點提示可解
  `skirt`,不需要跟 `bodice`/`sleeve_right` 一樣的「接受/人工/放棄」三選一,可以直接
  规划把點提示功能做進 production pipeline**。
- 新增候選:**把點提示接線進 production**(decision JSON schema + assist viewer UI +
  `s4_decompose_cut.py`),讓 `skirt` 這個案例真正在正式流程裡被修正,而不只是停在
  ad-hoc 驗證腳本。這是目前唯一"已知有效但未落地"的改進動作,優先度高於繼續测試
  `bodice`/`sleeve_right`(那兩個已經 4 次驗證無效,重複测試不會有新資訊)。

## 檔案

- 新增 `tools/mesh_gen/s4_data/chunk55/point_prompt_test.py`(一次性驗證腳本,非
  production 代碼)。
- 新增 `tools/mesh_gen/s4_data/chunk55/point_prompt_results.json`(6 組測試的量化結果)。
- 新增 `tools/mesh_gen/s4_data/chunk55/skirt_*.png`(5 張疊圖:baseline + 4 個點提示
  變體)。
- 未修改任何 production 代碼(`tools/mesh_gen/s4_sam_segment.py`、
  `tools/mesh_gen/s4_decompose_cut.py`、`tools/mesh_gen/s4_decompose_assist.html`
  均維持 chunk 47 版本)。
