# S4 切圖/補圖都要在 PSD 內編輯,建立同一套座標系(2026-08-28,使用者要求)

> 使用者指出:「無論是切圖還是補圖,都是在 PSD 檔中編輯,如此才能建立相同座標系。」
> 這節記錄為什麼這樣做、技術上怎麼做、以及過程中踩到並修正的兩個真實 psd-tools 陷阱。

## 為什麼(問題)

之前的補圖工具(`inpaint_eval.py`)是對**已經匯出的裁切 PNG**(如 `psd_slice.py` 產出的
`03_身體.png`)做挖洞/補圖測試——這張 PNG 是**局部座標**(裁到該層 bbox,原點在該層左上角),
不是 PSD 的全域畫布座標。如果真的拿補好的 PNG 去「修正」角色,還要自己把結果貼回
`(該層 offset.x + 局部x, 該層 offset.y + 局部y)` 這組全域座標——這正是這條排程前幾輪
(`log/s4-2026-08-28-003.md`)踩過的同一類 bug:**offset 換算一旦手動做,就有算錯的空間**。

**解法**:直接在 PSD 檔內編輯。讀某圖層原本的 `(layer.left, layer.top)` 當唯一的座標基準,
patch 完的圖直接用同一組座標寫回 PSD——座標系一致性由 psd-tools 的 API(`create_pixel_layer`
的 `top`/`left` 參數本來就是全域座標)保證,不必自己算,從結構上排除這類 offset bug。

切圖跟補圖因此共用同一套流程:`psd_slice.py` 讀 PSD 產出各件的全域 offset;補圖時用同一個
`layer.left/top` 寫回同一個 PSD;之後不管什麼時候再跑 `psd_slice.py` 切圖,兩者的座標系
永遠一致。

## 實作:`tools/mesh_gen/psd_inplace_patch.py`

- `patch_layer_with_image(psd_path, layer_name, patched_local_rgba, out_path)`:通用函式。
  找到同名圖層 → 讀 `layer.left/top`(全域)+ `psd.index(layer)`(z 序)→ 移除舊圖層 →
  用 `create_pixel_layer(im, name, top=g_top, left=g_left)` 建新圖層(同尺寸、同座標)→
  移回原本 z 序位置 → 存檔。
- `demo_hole_patch(...)`:自我測試/示範用,重用 `inpaint_eval.py` 的 `punch_hole`/`METHODS`
  (挖洞 → 用既有 baseline 補)接上面那個通用函式,不重新發明補圖邏輯。
- CLI:`python3 psd_inplace_patch.py <psd> <圖層名> --mode --method -o out.psd [--eval]`,
  `--eval` 會直接呼叫 `psd_slice.evaluate()` 自驗座標系/重組是否一致。

## 過程中踩到的兩個真實 psd-tools 陷阱(已修正)

### 陷阱 1:寫入中文圖層名會 crash

`create_pixel_layer(name="身體", ...)` 存檔時丟 `UnicodeEncodeError`——psd-tools 預設用
`macroman`(單位元組編碼)寫 legacy Pascal-string 圖層名欄位,中文字元編不進去。

**真相**:檢查真實生產 PSD(`robot_parts.psd`,Photoshop 存的)才發現,Photoshop 自己也不是
把中文寫進這個 legacy 欄位——那個欄位裡是亂碼(`'®≠≈È'`),真正的名稱存在
`Tag.UNICODE_LAYER_NAME`(`'luni'`)這個 tagged block 裡,`psd-tools` 的 `.name` 屬性讀取時
本來就優先吃 `luni`。**修法**:比照這個慣例——legacy 欄位放 ASCII 佔位字串,手動呼叫
`layer._record.tagged_blocks.set_data(Tag.UNICODE_LAYER_NAME, name)` 寫入真正名稱。
這樣存出的 PSD 不只我方工具讀得對,**真正的 Photoshop 也讀得對**(因為完全比照它自己的慣例)。

### 陷阱 2:重存後的 PSD,預設 `composite()` 會拿到壞掉的合併預覽圖(無 alpha)

第一次 patch 完存檔、重開驗證時,`psd_slice.py --eval` 從 `overall_pass: true` 掉到
**orphan_ratio=0.55、premult_rgb_mae=143**——看起來像整張圖對不上,但視覺上重組結果明明
是對的。

**排查**:比對 `psd.composite()`(預設)vs `psd.composite(force=True)`——預設回傳的圖是
**`mode="RGB"`(完全沒有 alpha 通道!)**,而 `force=True` 正確回傳 `RGBA`。`.convert("RGBA")`
對一張純 RGB 圖做轉換時,PIL 會把 alpha 全填 255(全不透明),導致 `evaluate()` 把**整個
713×693 畫布**都當成「有內容」的參照區域(而非只有角色實際輪廓範圍),重組出來的部分自然
「蓋不滿」→ orphan 暴增。

**根因**:psd-tools 存檔時內嵌的「合併預覽圖」(給不完整解析圖層的舊版工具用的相容性資料)
在**我方工具程式化重存**的檔案裡,沒有正確帶出 alpha 通道;`composite()` 預設會先嘗試吃這張
內嵌預覽(`ignore_preview=False`),吃到就直接回傳,不會重新從圖層堆疊算。`force=True` 強制
跳過預覽、直接從實際圖層重新合成,結果永遠正確。**對原生 Photoshop 存的檔案也完全安全**——
兩種模式的差異只有 <1(premult MAE)的捨入誤差,純屬保險。

**修法**:`psd_slice.py` 的兩處 `psd.composite()` 呼叫(`slice_psd()` 存 `composite.png` 那處、
`evaluate()` 算參照圖那處)都加上 `force=True`。回歸測試:`robot_parts.psd`/`Symbol_Ww.psd`
兩份原生 PSD 重跑後數字不變(`overall_pass: true`,MAE 完全一致)。

## 驗證(端到端)

`psd_inplace_patch.py` 對 `robot_parts.psd` 的「身體」「左手」兩層分別跑合成挖洞→補
(cv2_ns / nearest)→ 寫回 → `--eval` 自驗,兩次 `overall_pass: true`(`premult_rgb_mae≈0.01`,
跟原始未修改檔案幾乎一致,只反映補丁本身不完美帶來的極小差異,不是座標系問題)。並確認
`build_spine.py` + `validate_build.py` 全流程對原始 `robot_parts.psd` 重跑無回歸。

## 對 S4 後續工作的影響

- **往後所有補圖產出都應該用 `psd_inplace_patch.py`(或同一套模式)寫回 PSD**,不要再對
  獨立匯出的裁切 PNG 做完就結束——那樣的結果無法安全地放回原 PSD 的座標系。
- 這也連帶表示:`inpaint_eval.py` 的角色維持「合成挖洞測試 + 量化評估器」(它本來就是用於
  校準/評分,不是生產補圖的最終落地點),真正要「修好一個角色」時,最後一步永遠是透過
  `psd_inplace_patch.py` 寫回 PSD。
- 任何未來會呼叫 `PSDImage.composite()` 的新工具,**預設都要用 `force=True`**,除非明確知道
  該 PSD 從未被程式化重存過。
