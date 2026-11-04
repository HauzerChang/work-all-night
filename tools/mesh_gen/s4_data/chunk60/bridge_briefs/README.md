# bridge 任務單草稿 (方案 C:手動複製到 bridge\briefs\todo\,參考圖到 ref\)
**00_style.md 不適用本專案,請忽略。**

## 任務 1:tails_mass 被遮區補圖 (類別 1b 防穿幫)
- 參考:`cut_sam/18_tails_mass.png`(RGBA,460x898 座標系 offset 0,0)、`cut_sam/composite.png`
- 需補區:與 `07_sleeve_left.png`、`13_sash_train.png`、`08_hand_left.png` alpha 交集區域(約 3 萬 px,見 knowledge/s4-inpaint-requirements-jiuwei-v3.md)。
- 要求:延續毛絨狐尾的色調/紋理,輸出與原圖同尺寸 RGBA PNG,僅補遮罩區、其餘像素不變、邊緣 alpha 不留硬切。
- 驗收:只要動態下不露洞,不需逐像素還原(寬鬆閘)。

## 任務 2:hair_main 頭後/頸後髮補圖 (1b)
- 參考:`04_hair_main.png`;補被 head/hair_front/choker 蓋住的髮區,延續髮絲方向與色調。

## 任務 3:skirt 被腰帶/披帛/手遮區補圖 (1b)
- 參考:`11_skirt.png`;補紅裙布料紋理。

輸出命名:`<part_id>_filled.png`,放回 bridge 結果資料夾後由使用者搬回 repo `chunk60/filled/`。
