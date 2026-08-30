# S4 `estimate_alpha_taper` 穩健性量化(候選 13,2026-08-30)

## 背景

候選 10(`s4-inpaint-1a-shape-boundary.md`)的控制實驗中意外撞見一次真實 bug:特定橢圓
interior 洞下,`estimate_alpha_taper` 把洞深處一個 RGB 補對、alpha 本該接近 255 的像素估成
60。追查是 15px 環內只有 `n=7` 個「已知 AA 邊緣」樣本,`local_grad` 的中位數估計被小樣本
污染。既有測試案例(3 機器人材質 interior/edge + 2 Symbol_Ww 材質 + 8 組真實遮擋洞)都沒
觸發,STATE_S4.md 建議先量化「多常發生」再決定怎麼修,不要只憑一次意外案例重寫核心邏輯。

## 方法

`tools/mesh_gen/s4_alpha_taper_robustness.py`:跨 12 個材質(機器人拆件 5 層全部:光暈/右手/
頭/身體/左手;Symbol_Ww 7 層,含之前沒測過的 底/頭/身體/墨鏡/wild)、多種洞形狀
(`punch_hole` circle 6 種 frac × interior/edge、ellipse 4 種 aspect × 3 種 frac × 3 種
angle,ellipse 只支援 interior)、3 個 seed,共 1233 次取樣。每次呼叫 `estimate_alpha_taper`
時用新增的 `debug` 參數記錄 `ring_count`(15px 環內樣本數)、`used_fallback`,並直接量測
洞區域 alpha 估計值 vs 真值的 `alpha_mae`。

## 發現 1:候選 13 的假設成立,但只解釋一部分案例

按 `ring_count` 分桶看 `alpha_mae`:

| ring_count 區間 | n | mae 平均 | mae 最大 | mae>20 個數 |
|---|---|---|---|---|
| [0,5) | 424 | 0.0 | 0.008 | 0 |
| [5,10) | 31 | 12.167 | 139.88 | 7 |
| [10,20) | 47 | 4.329 | 90.384 | 4 |
| [20,30) | 115 | 4.167 | 48.743 | 5 |
| [30,50) | 206 | 2.667 | 39.039 | 2 |
| [50,∞) | 410 | 5.515 | 116.595 | 32 |

`[0,5)` 這桶(舊門檻 `min_ring=5` 本來就會退回全域 fringe)误差近乎 0——退回全域對這批材質
一直是安全的。真正出問題的是 `[5,20)` 這個「剛好卡在舊門檻之上、樣本數仍不足以讓中位數穩定」
的縫隙,和候選 10 撞見的 n=7 案例是同一種失敗模式。

## 修法與驗證

用同一批 1233 筆資料,對每個候選 `min_ring` 門檻,重跑「原本因樣本數落在新舊門檻之間而改變
路徑」的案例,量測退回全域 fringe 後 mae 是變好、變壞、還是不變(不是用單一案例猜門檻):

| 候選 min_ring | 切換到 fallback 案例數 | 變好 | 變壞 | 不變 |
|---|---|---|---|---|
| 10 | 31 | 8 | 0 | 23 |
| 15 | 53 | 11 | 0 | 42 |
| 20 | 78 | 12 | 0 | 66 |
| 22 | 98 | 15 | 0 | 83 |
| 25 | 125 | 18 | **2** | 105 |
| 28 | 164 | 22 | **12** | 130 |

25 開始出現「誤傷本來有效局部樣本」的反向案例,28 惡化更明顯。20~22 是最後的零負面安全帶。
**採用 `min_ring=20`**(留安全餘裕,不頂著剛好翻盤的邊界),`[5,10)` 與 `[10,20)` 桶的
`mae_max` 從 139.88/90.384 全部壓到 0.008(全部改用全域 fringe,對這批材質仍然安全)。
39/1233 案例(原本 50/1233)仍有 mae>20,全部落在新門檻之上的 `[20,∞)` 桶——這是候選 14
(見下)的範圍,不是本次修的問題。

## 回歸驗證(修改前後同一份程式碼分別跑,逐位元比對)

```
python3 tools/mesh_gen/inpaint_eval.py /tmp/robot_slices/{00_光暈,03_身體,04_左手}.png --modes interior edge
# 修改前後 alpha_mae/seam_grad_diff/pass 逐位元相同(光暈/身體/左手 edge alpha_mae 仍 8.571/2.265/2.978)
python3 tools/mesh_gen/real_occlusion_eval.py assets/robot_parts.psd
# 完整 JSON diff 為空
python3 tools/mesh_gen/inpaint_eval.py /tmp/symbol_slices/{05_框,08_臉部陰影}.png --modes interior
# 完整 JSON diff 為空(既有 tone_gap 限制,candidate 8,不受本次修改影響)
python3 tools/mesh_gen/psd_inplace_patch.py assets/robot_parts.psd 左手 --auto --mode edge -o <out> --eval
# 除輸出檔名外,JSON diff 為空(chosen_method=nearest,reveal seam_grad_diff=150.099 不變)
```

這三個既有回歸案例的 `ring_count` 全部落在 `[0,5)` 或 `[50,∞)` 這兩個不受門檻調整影響的桶,
所以逐位元不變並非巧合,而是這次改動的影響範圍本來就精準卡在 `[5,20)` 這個縫隙(用資料驗證,
非只是「跑過就好」)。

## 候選 14(新發現,誠實範圍界定,本次未修):大樣本數下的獨立失敗模式

同一批量化資料也發現了跟候選 13(小樣本統計不穩)完全不同根因的失敗:`ring_count` 很大
(50~700+,樣本數本身完全足夠)照樣 `alpha_mae` 崩壞到 90~140。例如:

- `右手`(硬邊機械材質)edge 模式、`frac=0.06` 小洞:`ring_count=271`,`alpha_mae=115.572`。
  診斷:真值該處幾乎全 255(硬邊實心),但 `local_grad` 中位數估成 9.3(對應 `ell≈27.4`,
  是軟邊材質才該有的漸縮寬度),導致洞深處被錯誤地插值成 alpha≈135 而非該有的 255。
- `光暈`(軟邊材質)特定橢圓 interior 洞(`aspect=2.0`,特定 frac/angle 組合):
  `ring_count=87~377`,`alpha_mae=55~117`。

`min_ring` 對這批案例完全無效(樣本數遠超任何合理門檻)——這代表「15px 環內 AA 邊緣像素的
局部梯度中位數」這個估計量本身,在某些幾何配置下會系統性抓到不具代表性的邊緣段落(可能是
洞的形狀/朝向恰好讓 15px 環主要覆蓋材質邊界中一段局部特別平緩或特別陡峭的區域,不代表洞
深處真正該用的漸縮尺度)。**這是一個獨立於候選 13 的新問題,需要另外的診斷/修法**(例如:
改用洞邊界周長上均勻取樣而非距離環、或用洞邊界本身的局部曲率/走向做加權),本次不展開修,
留給後續 chunk。

## 檔案

- 修改:`tools/mesh_gen/inpaint_eval.py`(`estimate_alpha_taper` 新增 `min_ring`(預設從
  5 提高到 20)與 `debug` 診斷參數,向後相容——不傳這兩個參數的既有呼叫端行為完全不變,
  只有預設值改變的效果,已用上方回歸驗證確認)。
- 新增:`tools/mesh_gen/s4_alpha_taper_robustness.py`(量化實驗腳本,可重跑驗證任何未來
  對 `estimate_alpha_taper` 的修改)。
