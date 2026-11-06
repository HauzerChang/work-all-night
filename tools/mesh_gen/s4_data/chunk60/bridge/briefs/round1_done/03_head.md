images: ref/head.png,ref/head_mask.png,ref/head_preview.png,ref/composite.png

# 任務 03:補圖 `head`(Spine 2D 角色部件,1b)

**briefs/00_style.md 不適用本任務,請忽略。**

## 輸入
- `ref/head.png`:要補的部件,RGBA PNG,460x898,透明背景。這是從整張角色圖 `ref/composite.png` 切出的「head」。
- `ref/head_mask.png`:需補區遮罩(白=需要重繪,黑=必須原樣保留),4520 px,範圍約 x232–340 / y95–220。
- `ref/head_preview.png`:整張圖上用紅色標出需補區,幫你理解該區在角色上的位置。

## 要做什麼
角色動起來時,這個部件被 hair_front_left、hair_front_right、earrings、choker 擋住的區域會露出來。請在**遮罩白色區**畫出這個部件在被遮處「本來應該有」的樣子:
- 材質:臉頰兩側皮膚與頸部;前髮束下方應是臉側/耳朵/頸側皮膚,脖子底部延伸到頸鏈下方。
- 只延續 `head` 本身,**不要**畫進遮擋它的件(hair_front_left、hair_front_right、earrings、choker)的內容。
- 顏色、光影、筆觸要與 `ref/head.png` 既有像素無縫銜接,不留硬邊、不留色塊接縫。
- 部件的外輪廓可以在白色區內自然延伸;白色區之外若本來是透明,就保持透明。

## 硬性要求
1. 輸出 RGBA PNG,尺寸必須是 460x898,座標系與輸入完全相同(不要裁切、不要縮放、不要位移)。
2. **遮罩黑色區的像素(含 alpha)必須與 `ref/head.png` 逐像素相同**;只有白色區可以改。
3. 白色區內補出的像素要有合理 alpha(部件邊緣柔和過渡,不要整塊 255 的硬邊)。
4. 不要加背景、不要加文字、不要改變整體色調。

Save the result as `out/head_filled.png`
