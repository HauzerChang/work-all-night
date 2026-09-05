# S4 拆解流程:修正 tag_pendant 決策檔框位置錯誤,複核 skirt(chunk 52)

> 承接 chunk 51 留下的候選項「對 `bodice`/`sleeve_right`/`tag_pendant`/`skirt` 這 4 個
> 裁圖後有跟鄰近部件重疊跡象的部件做進一步定位判定」。本次排程開始無活人裁決,依既有慣例
> (chunk 26/49/50/51)先處理其中零成本、不需授權的兩項——`bodice`/`sleeve_right` 已是
> chunk 48 確認過的「真正演算法歧異,點提示測試過仍解不了」案例,本次不重複；聚焦在
> `tag_pendant`/`skirt` 這兩個 chunk 51 才新觀察到、還沒深入定位的疑慮。

## 背景與方法

延續 chunk 49-51 的方法論:bash+PIL 把可疑部件的 `bbox_pct` 換算成像素裁圖檢視,對定位
不確定的再疊網格座標圖反覆核對實際內容位置。

## `tag_pendant`:確認是同類「框完全落錯」錯誤

原框 `bbox_pct [57,44,69,59]` → 像素 `(262,395,317,530)`。裁圖檢視發現框內是**紅色胸衣
衣料+金色刺繡紋樣**,完全沒有標籤(垂墜符紙/木牌)的任何一部分——跟 chunk 51 找到的
`head`/`fox_ears`/`hair_front`/`earrings`/`choker` 是同一種「框壓根沒對到內容」錯誤,
不是鄰居內容混淆的邊界歧義。

用網格疊圖工具在 x:280-400, y:370-540 範圍定位,確認實際的標籤(豎排文字木牌,頂端有
綁繩結,懸吊在腰間偏右側)位置在 x≈336-377, y≈413-530,比原框整體偏右約 74px、偏下
約 18px。改框:

| 項目 | 舊值 | 新值 |
|---|---|---|
| `bbox_pct` | `[57,44,69,59]`(錯) | `[73,46,82,59]` |
| `bbox_px`(460×898) | `(262,395,317,530)` | `(336,413,377,530)` |
| `confidence` | `high` | `medium` |

## `skirt`:複核後判定框正確,不修改

原框 `bbox_pct [34,40,71,61]` → 像素 `(156,359,327,548)`。裁圖檢視框內容**確實是裙擺
紅色衣料主體**(含金色滾邊、蝴蝶結繫帶),左緣夾帶部分左手/前臂、下緣夾帶部分大腿膚色與
黑靴——但這是矩形框裁切非矩形、彼此重疊人形素材時的**正常 bleed**(裙擺本身斜插在手臂
與大腿之間,任何合理的裙擺矩形框都會夾到鄰居一部分),跟 `tag_pendant`/chunk51 五個部件
「框完全沒碰到目標內容」是不同性質的問題。**判定:不需修正**,`notes` 記錄複核結論以便
後續 chunk 不重複判斷。

## 自我驗證

從修正後的 `suggestions.json` 重建 20 部件 `bbox_px` 決策檔
(`tools/mesh_gen/s4_data/chunk52/decision_reconstructed.json`),跑 `s4_decompose_cut.py
--contour rect --eval`:

- `AC1_parts_produced`:20/20 部件全部產出,`overall_pass: true`。
- 從實際 pipeline 輸出(非我自己的 ad-hoc 裁圖腳本)複核兩張裁圖
  (`tools/mesh_gen/s4_data/chunk52/cut_rect/`):
  - `13_tag_pendant.png`:乾淨完整的標籤(木牌+豎排文字+頂端綁繩結),邊緣只帶極少量
    背景/鄰近衣料,不再是紅色衣料紋樣。
  - `12_skirt.png`:裙擺紅色衣料主體清楚可見,確認 bleed 屬正常範圍,維持原框判定。

## 誠實限制

- `bodice`/`sleeve_right` 本次仍未處理,維持 chunk 48 的既有結論(需人工處理或測試完整版
  SAM,兩者皆需使用者先裁決)。
- 驗證用的 20 部件決策檔延續 chunk 49-51 做法,從 `suggestions.json` 重新換算,不是
  chunk 46-48 使用者手動調整過的那份真實決策檔,不能延續其統計數字。
- 沒有重跑 `--contour sam`(容器未持久化 MobileSAM 權重),矩形裁切的視覺驗證已足以證明
  `tag_pendant` 框位置本身修好、`skirt` 框位置本身無需修改。
- 至此 chunk 47-52 累計已對 `suggestions.json` 全部 20 個部件都做過至少一次裁圖複核
  (`bodice`/`sleeve_right` 兩個除外,兩者是已知案例、非「未檢視」),「框完全落錯」這類
  問題目前已無新的未檢視候選;剩餘懸而未決的只有 `bodice`/`sleeve_right`(需使用者裁決
  處理方式)與 `hair_front` 的精確語意邊界(需使用者用 assist viewer 確認)。

## 檔案

- 修改 `assets/jiuwei_yanlian_char_crop.suggestions.json`:`tag_pendant` 的
  `bbox_pct`/`confidence`/`notes`;`skirt` 的 `notes`(複核結論,`bbox_pct` 不變)。
- 新增 `tools/mesh_gen/s4_data/chunk52/decision_reconstructed.json`(20 部件 `bbox_px`
  決策檔,供重現本次驗證)。
- 新增 `tools/mesh_gen/s4_data/chunk52/cut_rect/`(僅保留 `12_skirt.png`/
  `13_tag_pendant.png` + `manifest.json` 作證據)、`grid_waist_region.png`/
  `grid_tag_closeup2.png`(定位過程疊圖)、`crop_tag_pendant.png`(原框錯誤內容證據)、
  `verify_tag_pendant_pipeline.png`/`verify_skirt_pipeline.png`(pipeline 輸出複核截圖)。
- 新增本篇 `knowledge/s4-decompose-box-fix-tag-pendant.md`。
- 未修改 `s4_decompose_cut.py`/`s4_sam_segment.py`/`s4_decompose_assist.html` 等任何
  production 代碼。
