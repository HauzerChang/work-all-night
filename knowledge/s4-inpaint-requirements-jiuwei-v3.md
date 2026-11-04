# S4 補圖需求清單 — 九尾狐 PSD v3 (chunk 297, 2026-11-04)

來源:`tools/mesh_gen/s4_data/chunk60/cut_sam/`(19 件 SAM 輪廓)。像素遮罩兩兩交集(alpha>128,>30px)結果如下。
分類依 `s4-inpaint-taxonomy.md`(1a 需表演 / 1b 防穿幫 / 2 視角外推)。

## A. 實測遮罩重疊(切圖品質問題,先於補圖處理)
| 件 A | 件 B | 重疊 px | 解讀 |
|---|---|---|---|
| sleeve_left | tails_mass | 10630 (A 的 96%) | tails_mass 吞掉整個左袖 → 尾巴件須把袖子區域挖掉(補圖 1b) |
| sash_train | tails_mass | 21481 (A 的 88%) | 同上,披帛區須從尾巴件挖掉並補尾巴背景 |
| boot_left | boot_right | 5459 (A 的 73%) | 左靴 mask 大半落在右靴內 → 疑 SAM 選錯/框重疊,**需重切而非補圖** |
| hand_left | sleeve_left | 593 | 手/袖邊界,1b 小補 |
| hair_front_right | earrings | 189 (耳環 43%) | 前髮與耳環交界,可接受或加負點 |
| leg_left | leg_right | 234 | 大腿交界,1b 小補 |
其餘 <150px,忽略。

## B. 補圖任務(依優先序)
| # | 件 | 被誰遮 | 類別 | 難度 | 建議路線 |
|---|---|---|---|---|---|
| 1 | tails_mass | sleeve_left、sash_train、hand_left | 1b | 高(蓬鬆毛紋理、面積大 ~3 萬 px) | GPT/codex bridge |
| 2 | hair_main | head、hair_front_*、choker(頭後/頸後髮) | 1b | 中 | bridge;或邊緣外擴+cv2 先試 |
| 3 | head | 前髮束、耳環、choker | 1b | 低 | cv2.inpaint |
| 4 | skirt | belt、sash_train、hand | 1b | 中 | bridge |
| 5 | leg_left/leg_right | 靴口、裙擺、交界 | 1b | 低 | cv2.inpaint |
| 6 | sleeve_left | hand_left | 1b | 低 | cv2.inpaint |
| 7 | boot_left | boot_right | **先重切** | — | 修 SAM 點後再評估 |

類別 2(視角外推)目前無動畫規格驅動,暫不列。1a 無(眼睛等不需單獨表演,依既有決策)。

## C. 前置阻塞
- boot_left 需先重切(負點落在右靴上)。
- tails_mass 須先決定是否保留為整塊(使用者先前標「無法個別拆分」);若保留,補圖只需讓它「在袖/披帛移動時不露洞」(1b 寬鬆閘)。
- bridge 協定仍未知(缺 codex_bridge.ps1),任務單走方案 C 手動搬運;00_style.md 不適用。
