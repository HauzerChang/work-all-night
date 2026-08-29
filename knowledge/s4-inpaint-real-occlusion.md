# S4 補圖候選 1 — 遮擋真值法(比合成挖洞更貼近實戰)

- **結論**:新增 `tools/mesh_gen/real_occlusion_eval.py`,用機器人拆件 PSD 5 個真實圖層兩兩疊合,
  取「圖層 A 的內容 ∩ 蓋在它上面的圖層 B 的內容」當**真實形狀**的洞(A 自己的原始像素就是真值,
  因為 PSD 分層本就每層畫全)。跑過程中**揪出並修正 1b `seam_ratio` 的一個真實全域基準 miscalibration**,
  修正後對 4 組真實遮擋案例全部校準通過;並量化出「真實遮擋形狀 vs 合成圓形挖洞」判定的
  **一致與不一致之處**——與候選 8(tone_gap 跨材質不可攜)是同一類「自我參照指標的隱含假設在
  什麼條件下破功」的發現,但這次是**同一材質、不同洞形狀/位置**就會破功,比候選 8 更根本。
- **信心**:高(真實 PSD 圖層資料 + 完整正負對照校準 + 對照既有 6 個材質×模式的回歸測試零反向)。
- **階段**:S4 / 補圖閘迭代(候選 1,見 `STATE_S4.md`)。

## 方法

`real_occlusion_eval.py`:
1. 用 `psd_slice.leaf_layers()` 讀 `robot_parts.psd` 的 5 個 leaf 圖層,各自貼回**整張 PSD 畫布座標**
   (不是切件裁到的 bbox 局部座標——兩層要在同一座標系才能算真實重疊)。
2. 對每一對 `(target, occluder)`:`mask = target.alpha>8 & occluder.alpha>8`,即「occluder 疊在
   target 上面時,target 會被蓋住的真實形狀」。`gt = target` 自己的圖層像素(該區域本來就有真值,
   因為 PSD 圖層各自獨立畫全,不因被蓋住而缺角)。
3. `classify_mode()`:量測洞跟 target 自己內容邊界的重疊比例,決定當 interior 或 edge(1b 只在
   interior 校準過,見 `s4-inpaint-1b-lenient-gate.md`)——真實遮擋洞不像 `punch_hole` 保證落在
   哪一種,得實測分類。
4. 重用 `inpaint_eval.py` 抽出的共用核心 `run_with_mask(gt, mask, mode, base, out_dir)`(見下方
   重構說明),跑跟合成挖洞閘**完全同一套** baseline/指標/門檻/校準邏輯——確保兩邊可比較。

**測試的 4 組真實遮擋對**(機器人拆件 5 層兩兩重疊分析,見下方量測全表):

| target ← occluder | 洞面積/target 內容 | 洞形狀 | mode |
|---|---|---|---|
| 光暈 ← 身體 | 35.8% | 單一連通、圓潤 | interior |
| 光暈 ← 右手 | 20.5% | 單一連通(+1 個 2px 雜點)、狹長不規則 | interior |
| 光暈 ← 左手 | 16.8% | 單一連通 | interior |
| 身體 ← 左手 | 3.2% | 單一連通,10.7% 邊界沾黏 | interior(沾黏比例仍在門檻內) |

其餘配對(右手/頭/身體 等小面積重疊,<13%)因面積太小或本身尺寸太小未列入(見下方全表)。

## 全部真實重疊量測(5 層 C(5,2)=10 對,供後續延伸取用)

```
光暈(z0) occluded_by 右手(z1): overlap_px=46050 frac_of_光暈=0.205
光暈(z0) occluded_by 頭(z2):   overlap_px=6405  frac_of_光暈=0.029
光暈(z0) occluded_by 身體(z3): overlap_px=80169 frac_of_光暈=0.357
光暈(z0) occluded_by 左手(z4): overlap_px=37748 frac_of_光暈=0.168
右手(z1) occluded_by 頭(z2):   overlap_px=2978  frac_of_右手=0.065
右手(z1) occluded_by 身體(z3): overlap_px=1956  frac_of_右手=0.042
右手(z1) occluded_by 左手(z4): overlap_px=0
頭(z2)  occluded_by 身體(z3):  overlap_px=829   frac_of_頭=0.129
頭(z2)  occluded_by 左手(z4):  overlap_px=0
身體(z3) occluded_by 左手(z4): overlap_px=2538  frac_of_身體=0.032
```

## ⚠️ 揪出並修正:1b `seam_ratio` 全域基準 miscalibration

**第一次跑 `光暈←右手` 就抓到正對照(gt)本身 1b fail**:`seam_ratio=2.723`(門檻 2.2)。
gt = 洞內填真值本身,**理論上不該有任何接縫**,fail 代表指標本身有偏,不能信。

**查因**:`score_1b()` 原本的 `baseline_grad`(「材質本來的邊緣強度」基準)是用
**整件扣掉洞的全域平均梯度**。光暈是放射狀漸層——核心附近陡、外圈平緩——全域平均被
大面積外圈平緩區稀釋成很低的基準。右手的遮擋範圍剛好跨過光暈核心陡峭區(量測:洞邊界帶
局部平均梯度 49.8,全域平均只有 16.6,前者是後者 3 倍),用被稀釋的全域基準去除,連正對照
自己都被誤判成「比正常區域突兀」。

對照組(排除混淆因子):`光暈←身體`(洞邊界帶梯度 10.6,低於全域 16.6)、`光暈←左手`
(30.3,略高於全域但沒到跨核心的程度)兩案例 gt 1b 均正常 pass——證實問題不是「光暈這個材質
不能用 1b」,而是**基準本身抽樣位置不對(全域 vs 局部)**,恰好被右手的遮擋位置撞到。

**修正**(`inpaint_eval.py::score_1b`):`baseline_grad` 改成只採**洞周圍局部環狀帶**
(洞外緣往外固定 12px 的環,呼應 `estimate_alpha_taper()` 同樣用固定寬度環的設計慣例,
不隨洞尺寸縮放);樣本太少(<200px,洞太小/太薄擠不出局部環)才退回原本的全域平均。

**修正效果量化**(`光暈←右手` gt 案例,ring_out 掃描驗證選對環寬):

| 環寬(band 外緣起算) | baseline_grad | seam_ratio |
|---|---|---|
| 全域(原本) | 61.0(全域稀釋值,見上) | **2.723(fail)** |
| +6px | 72.22 | 0.69 |
| +12px(採用) | 67.47→(用 width+12=15 iter) | **0.834(pass)** |
| +20px | 54.05 | 0.922 |
| +30px | 47.11 | 1.057 |

修正後 4 組真實遮擋案例的 gt 1b 全數 pass(`光暈←身體` seam_ratio 0.41→0.258,
`光暈←右手` 2.723→0.834,`光暈←左手` 1.589→0.635,`身體←左手` 0.382→0.842),
兩個負對照(none/random)1b 依然全數 fail(鑑別力沒被削弱)。`calibration.pass` 從
`False`→`True`。

**回歸驗證(AC:不能動到既有已校準結論)**:
- 機器人 3 材質(光暈/身體/左手)× interior/edge 合成挖洞閘重跑:`calibration.pass=True`,
  每個 baseline 的 1a/1b pass/fail 結果與候選 8(session 009)完全一致(光暈 interior 三個
  baseline 1a/1b 全 pass;身體/左手 interior 1a 全 fail、1b 全 pass;edge 模式 1b 全部
  `applicable=False` 不受影響)。
- `Symbol_Ww.psd::框/臉部陰影`:`calibration.pass` 仍 `False`,但失敗原因**仍是** `tone_gap`
  超標(框 32.838、臉部陰影 57.296,與候選 8 session 009 記錄的數字一致)——`seam_ratio` 本身
  兩案例都在門檻內(1.011 / 0.549),證實這次修正沒有引入新的失敗模式,`tone_gap` 跨材質不可攜
  是候選 8 已誠實界定、獨立於本次修正的既有限制(見 `s4-inpaint-tone-gap-limits.md`)。
- `psd_inplace_patch.py assets/robot_parts.psd 身體 --method cv2_ns --mode interior --eval`:
  `overall_pass:true`,`AC2_recon`/`AC3_no_orphan` 數字不變。
- `psd_inplace_patch.py assets/robot_parts.psd 左手 --auto --mode edge --eval`:
  `chosen_method` 仍是 `cv2_telea`(fallback 排序不變,因為 edge 模式的 `select_best` 走
  seam_ratio 排名 fallback、不看絕對 pass/fail 門檻),`reveal_1a_score_of_chosen.alpha_mae=2.978`
  與 log 009 記錄的數字完全一致。

## 重構:抽出 `run_with_mask()` 共用核心

`inpaint_eval.py` 原本的 `run_one()` 把「讀檔案→挖洞→跑全部 baseline+指標+校準」黏在一起,
洞的來源被寫死成 `punch_hole()`。抽出 `run_with_mask(gt, mask, mode, base, out_dir)` 當共用核心
(`run_one()` 改為呼叫它),讓 `real_occlusion_eval.py` 可以帶真實遮擋 mask 進來,跑**完全同一套**
baseline/指標/門檻/校準邏輯——這是候選 1 的核心要求(「對照合成挖洞閘的判定是否一致」),兩邊
判定邏輯不共用就無法比較。純函式抽取,`run_one()` 對外行為不變(已用上面的回歸驗證確認)。

## 真實遮擋 vs 合成挖洞:判定是否一致?

**`身體←左手`(機械紋理,3.2% 面積)——完全一致**:1a 三個 CPU baseline 全 fail
(ssim 0.52~0.60),1b 全 pass——與合成挖洞閘的既有結論(候選 0/1b 閘)逐項相符。
真實遮擋面積雖遠小於合成挖洞測試過的 2%~12% 範圍(更小),結論方向不變。

**`光暈`(放射漸層)——部分不一致,揭露既有結論的隱藏前提**:合成挖洞閘(12% 面積、圓形)
下 3 個 CPU baseline 對光暈 1a **全 pass**(ssim 0.99+,`seam_grad_diff` ≤5.1)。換成真實
遮擋形狀後:

| 案例 | 面積 | ssim(cv2_ns) | seam_grad_diff(cv2_ns) | 1a pass? |
|---|---|---|---|---|
| 光暈←身體 | 35.8% | 0.983 | 10.6 | **True**(< 12 門檻) |
| 光暈←右手 | 20.5% | 0.924 | 21.3 | **False**(> 12 門檻) |
| 光暈←左手 | 16.8% | 0.944 | 19.3 | **False**(> 12 門檻) |

三案例 ssim/`premult_mae` 都仍在門檻內,**唯獨 `seam_grad_diff` 在右手/左手兩案例超標**
(合成挖洞從未量到 >5.1,真實形狀量到 17~21)。1b(防穿幫寬鬆閘)三案例仍全數 pass。

**誠實結論**:「光暈(平滑漸層材質)CPU 補得動」這個候選 0 的結論,是用**小面積
(12%)、圓形、隨機位置**的合成洞校準出來的,對**大面積(17~36%)、不規則形狀、位置固定
的真實遮擋**不完全成立——嚴格的 1a 標準會因接縫可見度(而非色差本身)被真實不規則洞形/
較大洞面積放大而 fail。但**1b(這批 CPU baseline 動態下不穿幫)在全部 4 組真實遮擋案例
都成立**,呼應候選 8 已經驗證過的分類法(taxonomy):1a 是「補得像不像」的嚴格標準,
1b 是「動不動下會不會露餡」的實戰標準,兩者本來就該給出不同結論,這次用真實遮擋形狀
再次確認 1b 才是本專案實際要用的驗收線。

## 可重現

```
python3 tools/mesh_gen/real_occlusion_eval.py assets/robot_parts.psd -o /tmp/real_occ_out
# calibration.pass == true;4 組案例 gt 1a/1b 皆 pass,none/random 皆 fail
python3 tools/mesh_gen/inpaint_eval.py /tmp/robot_slices/{00_光暈,03_身體,04_左手}.png --modes interior edge
python3 tools/mesh_gen/inpaint_eval.py /tmp/symbol_slices/{05_框,08_臉部陰影}.png --modes interior
```

## 下一步

- 其餘候選(2:1b edge 模式支援、4:探測 LaMa、6:擴大 Symbol_Ww 樣本、7:1b 閾值反向校準)仍待推進。
- 若要繼續深挖候選 1:可再測 `右手←頭`/`身體←頭` 等小面積配對(<13%),或把「真實遮擋洞」
  這個更貼近實戰的洞來源,拿去覆核候選 8 遺留的 `框`/`臉部陰影` 材質(Symbol_Ww 沒有多層
  互相遮擋的真實案例可用,若要延伸需另找/另造有真實重疊的分層素材)。
