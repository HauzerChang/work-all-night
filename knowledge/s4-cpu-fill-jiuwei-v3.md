# S4 九尾狐 v3 低難度件 CPU 補圖批次 (chunk 305, 2026-11-06)
工具:`tools/mesh_gen/s4_cpu_fill_batch.py`;輸出 `s4_data/chunk60/cpu_fill/`(holed/filled/report.json)。
對象:head、leg_left、leg_right、sleeve_left、hair_main。洞=件被遮擋件覆蓋的區域;候選 nearest/cv2_telea/cv2_ns,1b 自我參照盲選。

## 結果(誠實版)
- **v1(洞外擴 17px 含輪廓外)**:5 件全 `pass_1b`,但目測 head、leg 在輪廓外長出條紋/髮色拖尾 → **1b 閘在「洞咬輪廓外緣」時鑑別力不足,pass 不可信**(第 4 次 miscalibration 類教訓:閘判定要配目測/真值,不可單信)。
- **v2(洞限輪廓內)**:洞只剩 head 333px、leg_right 286px、sleeve_left 779px、hair_main 77px、leg_left 0px。表示**切件本身大多沒被遮擋色污染,真正缺的是「輪廓外、被擋住而從未存在」的區域**(外推,非內插)——CPU 的 1–2 級對這種外推只會產生條紋,屬 `s4-inpaint-taxonomy` 的 1b 外推,難度比清單估的高。
- **hair_main 切件本身錯誤**:內容是含「JIUWEI」字樣的背景髮暗區碎片,不是長髮主體 → 需先重切(同 boot_left),補圖無意義。
- z 欄位只是切件順序,非前後層;遮擋關係須顯式指定(OCCLUDERS)。

## 結論 / 建議
1. 真正需要補的是輪廓外延伸區 → 低難度件也建議走 bridge(GPT)或加「額外延伸遮罩」規格,CPU 只作 fallback。
2. 待重切:boot_left、hair_main(二者都需使用者給 SAM 點)。
3. 想讓閘可信:加「輪廓外溢」指標(補圖後 alpha 超出原 closing 輪廓的比例)。
