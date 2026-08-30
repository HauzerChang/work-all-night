# S4 補圖候選 10 — 光暈材質 1a 邊界再校準(2026-08-30)

- **結論**:候選 1(`real_occlusion_eval.py`)觀察到光暈(放射漸層)材質的 1a `seam_grad_diff`
  判定**非單調**於洞面積(35.8% pass、20.5%/16.8% fail)。本次用新增的
  `punch_hole(shape="ellipse", center=...)` 做**控制變因**實驗(固定位置只變形狀、固定形狀
  只變位置),量化排除「形狀狹長度」與「單獨的位置」兩個簡單假設——**都不足以解釋**真實
  觀察到的非單調現象,誠實結論是：**光暈這類材質的 1a 邊界不能化約成單一合成洞參數
  (面積/長寬比/位置擇一),必須用真實遮擋洞的實際大小+形狀+位置一起看**(呼應候選 1
  已有的結論,這次是用受控實驗正面排除另兩個候選解釋,而非停在「不確定」)。過程中
  **意外揪出一個真實的 `estimate_alpha_taper` bug**(見下方,獨立於本次問題,已記錄未修)。
- **信心**:高(受控實驗直接量測,兩條假設檢驗皆有清楚的反例數據;bug 已直接除錯到
  pixel 層級確認根因)。
- **階段**:S4 / 補圖閘迭代(候選 10,見 `STATE_S4.md`)。

## 方法:延伸 `punch_hole` 支援可控形狀/位置

`inpaint_eval.py::punch_hole` 新增(向後相容,`shape` 預設 `"circle"`,既有呼叫端行為
逐位元不變,已用回歸驗證):

- `shape="ellipse"`:半長軸/半短軸比 `aspect`(面積固定,獨立控制狹長度)、`angle`(弧度,
  長軸朝向)。margin 檢查用半長軸(旋轉不變的最保守外接半徑),確保任何朝向都不碰邊界。
- `center=(oy,ox)`(選填):固定洞心。**沒有這個參數就無法做控制變因實驗**——不同
  aspect/frac 下 margin 檢查的合格候選點集合大小不同,同一個 `seed` 用
  `rng.randint(len(cand))` 會選到不同位置,「形狀」的效應會被「位置隨機换了」混進去,
  兩個變數無法分離(第一版沒加這個就踩到過,見下方「除錯過程」)。

新增 `tools/mesh_gen/s4_1a_shape_boundary.py`:對光暈(`assets/robot_parts.psd`,PSD 全畫布
座標,與 `real_occlusion_eval.py` 用同一份資料/座標系)做三組實驗:

1. **形狀掃描**(固定洞心 = 內容 distance-transform 的 argmax 點,margin 預算 169px):
   `frac ∈ {0.06,0.08,0.10,0.12} × aspect ∈ {1.0,1.5,2.0,2.5,3.0}`(angle=0),
   另加朝向子掃描(固定 frac=0.08,aspect=2.0,`angle ∈ {0°,45°,90°,135°}`)。
2. **位置掃描**(固定形狀 = 圓形,frac=0.08):沿著「光暈核心 → 各真實遮擋案例(身體/
   右手/左手)質心」的方向線,取 5 個內插點(t=0/0.25/0.5/0.75/1.0),超出 margin 的點
   自動 skip。同時量測 `local_grad_mag`:gt 材質本身(非 recon)在該處環狀帶的
   premultiplied 灰階 Sobel 梯度強度均值——這是「材質在該處多陡」的**材質固有屬性**,
   跟任何補圖結果無關,獨立於「洞形狀多狹長」。
3. **真實遮擋洞對照組**:重跑候選 1 的 3 組光暈案例當基準(數字須與既有紀錄一致)。

## 結果與假設檢驗

### 假設 A(形狀狹長度決定 1a 邊界)—— 在可行範圍內不成立

固定洞心後,`aspect` 從 1.0 掃到 3.0(受 margin 限制,更大 aspect 在此位置裝不下)、
`frac` 從 0.06 到 0.12,`seam_grad_diff`(cv2_ns)幾乎全部落在 **0.1~0.4** 這種極低量級
(遠低於門檻 12),與 aspect 幾乎無關(aspect 3.0 甚至比 aspect 1.0 更低)。朝向子掃描
(0°/45°/90°/135°)同一 aspect/frac 下也幾乎都是低值(0.17~0.28)——**除了兩個異常值**
(見下方 bug 說明,那是量測工具本身的問題,不是材質/形狀的真實效應)。

**結論**:排除掉工具 bug 造成的異常值後,狹長度(在本檔測過的 1~3 倍範圍)對
`seam_grad_diff` 幾乎沒有影響——這個固定核心位置的材質本身太平滑,region 太大塊都補得動,
不足以觸發候選 1 觀察到的失敗。

### 假設 B(位置決定 1a 邊界,與形狀無關)—— 同樣不足以解釋

固定形狀(圓形,frac=0.08,遠小於真實遮擋案例的 17~36%)沿三個真實方向線掃描,
`seam_grad_diff` 全部維持在 **0.05~5.2**(遠低於門檻 12),即使推到 t=1.0(真實遮擋案例
質心本身的位置)也是如此(左手方向最高只到 1.25~5.2)。`local_grad_mag`(材質固有梯度)
確實隨位置變化(左手方向從 1.6 升到 4.1~6.0,約 3~4 倍),但這個变化量級**還不足以讓小洞
的 seam_grad_diff 超標**。

**結論**:光是「位置」(在小洞尺寸下)也不能重現真實案例的失敗——真實遮擋案例
(17~36% 面積、真實不規則形狀)比本次位置掃描用的合成小圓洞(8%)大得多、形狀也
不是規則橢圓。

### 綜合結論:1a 邊界無法化約成單一合成洞參數

形狀(可控範圍內)與位置(小洞尺寸下)個別都不能重現候選 1 觀察到的非單調 pass/fail。
最合理的解釋是**真實遮擋洞的「大面積 + 真實不規則形狀 + 特定位置」三者的組合效應**——
這已經是 `real_occlusion_eval.py`(候選 1)在測的東西,沒有比它更簡單、仍然誠實的合成
替代品。**誠實界定**:候選 0/1a 用小圓合成洞校準出的「光暈 CPU 補得動」結論,其適用邊界
本來就該用真實遮擋形狀量,不该試圖再找一個更複雜的合成參數化模型去逼近——這樣做的
邊際投入產出比低,且候選 1 的方法論(遮擋真值法)已經是更貼近實戰、成本更低的驗證方式。
呼應候選 8/候選 1 已有的結論方向:**1b(防穿幫)才是本專案該用的實戰驗收線**,1a 的
「像不像真值」嚴格標準本來就對這類大面積真實遮擋不適用,不需要再修一個「更精確的 1a
邊界公式」。

## 意外發現:`estimate_alpha_taper` 的真實 bug(獨立於候選 10,未修,列入候選)

形狀掃描中兩組(`frac=0.12,aspect=2.0,angle=0°` 與 `frac=0.08,aspect=2.0,angle=135°`)
`seam_grad_diff` 從 <1 暴衝到 **157.6 / 139.3**(`ssim` 崩到 0.67/0.70,`premult_mae`
崩到 92/80)——遠超其他所有掃描點。

**除錯過程**(直接量測像素,不是猜的):

1. 比對洞內 argmax-diff 像素:`recon` 的 **RGB 與 `gt` 完全一致**(255,174,93 == 255,174,93),
   只有 `alpha` 錯得離譜(recon=60.3,真值=255——這個材質區域是內容深處,alpha 該接近滿)。
2. 追進 `estimate_alpha_taper()`:該像素的 `d_bg`(到已知背景的距離場)算出剛好等於
   輸出的 alpha 值(60.3),代表 `ell`(局部漸縮寬度)被算成 **255**(`alpha=clip(255*d_bg/ell,...)`,
   `ell=255` 時 `alpha≈d_bg`,對深內部像素而言嚴重低估——正常應該 `ell` 很小,讓 `d_bg`
   稍微離背景一段距離後就飽和到 255)。
3. 查 `ell` 的來源:`ring = binary_dilation(mask, 15) & fringe_known`(洞周圍 15px 內的
   已知 AA 邊緣像素)算出來的樣本數只有 **7 個**(通過現有的 `< 5` 個才 fallback 的檢查,
   但 n=7 仍是極小樣本)——這個小樣本剛好抽到材質某處**不具代表性**的柔緩梯度,把
   `local_grad` 中位數壓得很低,`ell = 255/local_grad` 因此暴衝到 255。

**根因**:`estimate_alpha_taper` 用**一個 scalar `ell`** 代表整個洞的漸縮寬度,樣本來源
是洞周圍 15px 環內、且要同時滿足「是已知 AA 邊緣(8<alpha<250)」的像素——對**大面積/
非圓形的 interior 洞**,這個環可能只在洞邊界的少數幾個點附近意外挨到材質其他地方的軟邊
特徵(對光暈這種本身就有多層次漸層結構的材質尤其容易),樣本數極少(n=7)還是被現有
`<5` 的門檻放行,导致整個洞(不論深淺)都套用這個被局部污染的單一 `ell`。

**範圍**:目前**只在本次刻意構造的橢圓 interior 洞觸發**——`inpaint_eval.py`/
`real_occlusion_eval.py` 既有的圓形 interior 洞與所有已測真實遮擋洞,回歸驗證數字
與候選 1/8/9 記錄完全一致(見下方回歸驗證),代表這批既有測試案例都沒踩到這個 n=7
小樣本陷阱——但這是運氣,不是這個函式本身穩健。**未修**(維持本次工作塊範圍聚焦在
候選 10 本身;修正需要重新設計 `ell` 的估計方式,例如提高樣本數下限、或對大洞改用
`estimate_alpha_taper` 一節提到的「距離場」搭配**空間變化**而非單一 scalar 的漸縮寬度,
需要獨立的驗證預算,不應在本次順手改)——**列為新候選,見 `STATE_S4.md`**。

## 回歸驗證(AC:不能動到既有已校準結論)

`punch_hole` 新增參數皆有預設值、`shape="circle"` 路徑完全沒有被本次改動觸碰(新分支
`if shape=="ellipse"` 提前 return,原本的 circle/edge 邏輯逐行不變)——用下列命令驗證
數字與既有紀錄逐位元一致:

```
python3 tools/mesh_gen/inpaint_eval.py /tmp/robot_slices/{00_光暈,03_身體,04_左手}.png --modes interior edge
# calibration.pass=true;光暈/身體/左手 interior+edge 的 seam_grad_diff 與 session 008/010 一致
python3 tools/mesh_gen/real_occlusion_eval.py assets/robot_parts.psd
# calibration.pass=true;光暈←身體/右手/左手 cv2_ns seam_grad_diff = 10.596/21.307/19.314
#(與 s4-inpaint-real-occlusion.md 逐位元一致)
python3 tools/mesh_gen/inpaint_eval.py /tmp/symbol_slices/{05_框,08_臉部陰影}.png --modes interior
# calibration.pass=false(既知限制,候選 8);tone_gap = 32.838 / 57.296,與 session 009 一致
python3 tools/mesh_gen/psd_inplace_patch.py assets/robot_parts.psd 左手 --auto --mode edge -o <out> --eval
# chosen_method=nearest,chosen_reason=pass_1b,reveal_1a_score.seam_grad_diff=150.099,
# 與 session 009/010 doc 記錄的 150.099 一致
```

## 可重現

```
python3 tools/mesh_gen/s4_1a_shape_boundary.py --psd assets/robot_parts.psd -o /tmp/shape_out
```

## 下一步

- `estimate_alpha_taper` 的 n=7 小樣本 bug 列入候選(見上)——修正前建議先擴大觸發樣本
  (對更多材質/洞形狀跑一輪,量化多常發生),避免只憑這次的意外案例就重寫核心估計邏輯。
- 其餘既有候選(4:探測 LaMa、6:擴大 Symbol_Ww 樣本、7:1b 閾值反向校準)仍待推進。
