# S4 拆解流程:修正 leg_left/boot_left 決策檔框位置錯誤(chunk 49)

> 承接 chunk 48 找到的發現:留下的 3 個未執行選項裡,選項 (a)「先修 `leg_left`/
> `boot_left` 兩個錯誤框」是**零成本、唯一已知有效的改進動作**,本次排程無活人可裁決,
> 依既有慣例(chunk 26)執行這個不需授權、不花費的選項。選項 (b)(3 個真正歧義案例接受
> 人工處理)非本次動作項;選項 (c)(測試完整版 SAM)因需使用者先確認投入成本,不執行。

## 背景:錯誤來源追溯

chunk 46/47/48 測試用的「使用者手動確認過的真實決策檔」是在對話當次提供、**沒有被
持久化進 repo**(跟 chunk 41「取檔手法」是同一類環境限制:排程 session 之間不繼承
對話附件)。本次排程重新檢查 repo 裡唯一持久化的來源
`assets/jiuwei_yanlian_char_crop.suggestions.json`(chunk 43 Claude vision 產出的
原始草稿),發現 `leg_left`/`boot_left` 的 `bbox_pct` 換算成像素,跟 chunk 48 報告的
錯誤框座標**完全吻合**:

- `leg_left`:草稿 `bbox_pct=[27,57,46,73]` → 換算 `(124,512,212,656)`,與 chunk 48
  報告的錯誤框座標一致。
- `boot_left`:草稿 `bbox_pct=[27,67,49,99]` → 換算 `(124,602,225,889)`,同樣一致。

**結論:這個錯誤從 chunk 43 我自己第一版 vision 分析就已經存在,使用者手動調整決策檔
時沒有改到這兩個框(可能信任了標籤文字沒有逐一複查內容)。** 因為草稿檔本身有被
commit 進 repo,可以直接在源頭(`suggestions.json`)修正,不需要使用者重新提供那份
未持久化的真實決策檔。

## 修正過程

用網格疊圖工具(bash+PIL,座標網格疊在放大裁圖上)逐段放大檢視 `leg_left`/`boot_left`
一帶的實際內容(`assets/jiuwei_yanlian_char_crop.png`,460×898):

- **裸露大腿膚色區域**:約 x=195~305,y=460(裙擺下緣)~545(靴口),是**一整片連續
  膚色**,兩腿在畫面上緊貼/重疊站立,肉眼看不出兩腿的分界線。
- **靴子區域**:約 x=195~300,y=545~880,同樣是**單一連續黑色靴筒輪廓**,看不出兩隻
  靴子並排的分界——這張圖裡兩腿幾乎完全遮擋彼此,不是左右分開站立的姿勢。
- 對照已驗證正確的 `leg_right`(`bbox_pct=[54,54,73,71]`→像素 `(248,485,336,638)`)/
  `boot_right`(`bbox_pct=[49,67,73,99]`→像素 `(225,602,336,889)`),兩者已經涵蓋了這片
  連續膚色/靴筒的**右半部**。

**修正方式**:比照 `leg_right`/`boot_right` 已驗證可接受的做法(框住可見膚色/靴筒範圍
的一半,允許邊緣夾帶少量鄰接物件,不苛求零 bleed),把 `leg_left`/`boot_left` 改框到
同一片連續膚色/靴筒的**左半部**:

| id | 舊 bbox_pct(錯) | 新 bbox_pct | 新 bbox_px(460×898) |
|---|---|---|---|
| `leg_left` | `[27,57,46,73]` | `[41,51,55,61]` | `(189,458,253,548)` |
| `boot_left` | `[27,67,49,99]` | `[41,61,56,98]` | `(189,548,258,880)` |

同時把這兩個 part 的 `confidence` 從原本的 `high` 下修為 `medium`,並在 `notes` 記錄
修正原因與「兩腿視覺重疊、非分離可辨」這個材質限制,避免下游誤以為這是一個乾淨可信的
標註。

## 自我驗證

用修正後的 `suggestions.json` 重建一份 `bbox_px` 決策檔
(`tools/mesh_gen/s4_data/chunk49/decision_reconstructed.json`,20 部件全轉換,僅
`leg_left`/`boot_left` 座標改變,其餘 18 個原樣保留,**不是** chunk46-48 使用者手動
調整過的那份真實決策檔的等價物,見下方「誠實限制」),跑
`s4_decompose_cut.py --contour rect --eval`:

- `AC1_parts_produced`:20/20 部件全部產出,pass。
- 逐格人工視覺複核修正後的 `15_leg_left.png`/`17_boot_left.png`:
  - `leg_left`:裁出畫面**確實是裸露大腿膚色**(邊緣夾帶少量鄰接布料紋樣,屬允許範圍
    內的 bleed),不再是手+尾巴毛髮。
  - `boot_left`:裁出畫面**確實是黑色靴筒**(含靴口金屬扣飾),邊緣夾帶少量絲帶布料,
    不再是純布料+毛髮。
  - 修正前後對照圖見 `tools/mesh_gen/s4_data/chunk49/cut_rect/`(僅保留
    `leg_left`/`leg_right`/`boot_left`/`boot_right` 四張裁圖 + `manifest.json` 作
    證據,其餘 16 個部件的裁圖已刪除,避免 repo 堆放跟本次修正無關的檔案)。
- 沒有重跑 `--contour sam`:本次容器沒有持久化 MobileSAM 權重(chunk 47 下載的
  `~/models/mobile_sam.pt` 屬於當次 session 本地檔案,不會被下一個排程繼承,重下載
  非零成本),而矩形裁切的視覺驗證已經足以證明「框位置本身修好了」這個本次要解決的
  問題——SAM 精修屬於選項 (c) 的範疇,不在本次零成本修正動作內。

## 誠實限制

- **這片「腿+靴」的視覺內容本身兩腿重疊、不可分**:即使框位置修對了,`leg_left` 跟
  `leg_right`(`boot_left` 跟 `boot_right`)裁出來的內容仍然是**同一團連續膚色/靴筒的
  左右兩半**,不是兩條真正獨立可辨的腿。這是來源美術圖本身的姿勢限制(兩腿站立時互相
  遮擋),不是任何分割演算法能解決的——修正只解決了「框完全沒對到目標」這個更嚴重的
  錯誤,沒有、也不可能解決「這張圖畫的兩腿本來就重疊」這個更根本的素材限制。若之後要
  幫這個角色的左右腿做成 spine 裡真正獨立擺動的兩個 slot,這裡切出來的內容本身就需要
  後續之一:(a) 接受兩腿目前使用同一份/相似的裁切內容(視覺上本來就分不出誰是誰),
  (b) 用生成式補圖把被遮擋的那條腿的隱藏部分畫出來(屬於候選類「遮擋物底下內容生成」
  等級的難度,見 `knowledge/s4-cut-vs-slice-research-split.md`,不是本次任務範圍)。
- **本次用的 20 部件決策檔是從 `suggestions.json` 重新換算的,不是 chunk46-48 使用者
  親手調整過的那份「真實決策檔」**(那份檔案的 `fox_ears` 等欄位曾被使用者手動改動,
  但沒有持久化進 repo)。除了 `leg_left`/`boot_left` 這兩個本次要修的框以外,其餘 18
  個部件用的是未經使用者調整的原始草稿座標,**跟先前 chunk 47 報告的「9 個明確正確」
  等統計數字不是同一份輸入,不能直接拿來延續累計統計**,只能作為「這兩個框修好了」這
  件事本身的獨立證據。
- `hand_right` 框沒對準的問題(chunk48 提到的第三個「框有問題」案例,只有右下角一小塊
  擦到手)**本次沒有修正**——chunk48 原文把它跟「純演算法歧義」歸在同一組未解案例,
  優先度低於已明確定位成因的 `leg_left`/`boot_left`,且本次只處理 chunk48 選項 (a)
  明確點名的兩個框,避免擴大本次工作塊範圍。

## 檔案

- 修改 `assets/jiuwei_yanlian_char_crop.suggestions.json`:`leg_left`/`boot_left`
  兩個 part 的 `bbox_pct`/`confidence`/`notes`。
- 新增 `tools/mesh_gen/s4_data/chunk49/decision_reconstructed.json`(從修正後
  `suggestions.json` 換算的 20 部件 `bbox_px` 決策檔,供重現本次驗證)。
- 新增 `tools/mesh_gen/s4_data/chunk49/cut_rect/`(`15_leg_left.png`/
  `16_leg_right.png`/`17_boot_left.png`/`18_boot_right.png`/`manifest.json`,修正後
  的裁圖證據,僅保留腿/靴四件,其餘裁圖已清除)。
- 新增本篇 `knowledge/s4-decompose-box-fix-legs.md`。
- 未修改 `s4_decompose_cut.py`/`s4_sam_segment.py`/`s4_decompose_assist.html` 等任何
  production 代碼。
