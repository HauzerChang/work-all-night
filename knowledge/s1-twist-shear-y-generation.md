# S1 生成器產出 shearY 通道(雙軸 shear,twist beat,G-4'''''')

- **結論**:`beat_templates.gen_twist`(斜拉「扭轉」)是**第一個產出 `shearY≠0` 通道的生成器**,補上 wobble(G-4')/squash(G-4'''')一路留到現在的**最後一條 shear 通道 honest boundary** —— 兩者皆 `shearY≡0`。twist 讓兩個 skew 軸(shearX、shearY)**同時且獨立**擺動 → 平行四邊形的**兩條邊各自傾斜**(單軸 shear 只斜一條邊)→ 塞滿真實 Spine local 2×2 一般仿射 M 的**最後一個自由度**。`build_spine --shear-pivot` 端到端把含 shearY 的一般仿射繞關節 pivot 補償而 pivot 精確不動(`pivot_channels_affine` 第一次被生成器產的 shearY≠0 驅動)。
- **依據**:`validate_twist_gen.py`(先驗庫 slot_bigwin → **真實 build_spine robot 骨架** → build_animations)**6 AC 全 PASS**;20 回歸閘全綠(19 既有 + 新 twist_gen);`build_spine --animate --tier-variants --shear-pivot` + `validate_build` round-trip overall_pass。
- **信心**:高(客觀結構簽章 + 端到端不動點 + 三路負對照;主秀手感屬 A 類留使用者)。
- **相關階段**:第 2 階段 S1(反推分析器 → 動畫生成),`spine-anim-forge` 區塊(仍 HOLD)。

## 為什麼是「最後一條 shear 邊界」

真實 Spine 3.8 bone local 2×2(`transform_matrix_full`,TransformMode.Normal):

```
a = cos(rot + shearX)·sx      b = cos(rot + 90 + shearY)·sy
c = sin(rot + shearX)·sx      d = sin(rot + 90 + shearY)·sy
```

- 第一個基向量 `(a,c)` 由 **shearX** 傾斜;第二個基向量 `(b,d)` 由 **shearY** 傾斜。兩者**各自獨立**。
- wobble(G-4')只擺 shearX(第一條邊傾斜),squash(G-4'''')在 shearX 上再加體積守恆非均勻 scale,但**都 `shearY≡0`** —— 第二條邊始終只由 rotate 帶著轉,不能獨立傾斜。
- twist 讓 shearY 也非零 → M 的四個元素全部由**獨立通道**驅動(rotate/scaleX/scaleY/shearX/shearY),一般仿射的所有自由度到齊。

矩陣行列式印證雙軸的獨立性:`det(M) = sx·sy·cos(shearX − shearY)`(sx=sy=1 時 `det=cos(shearX−shearY)`)—— 只有**兩軸之差**進入 det;單軸(shearY≡0)退化回 G-4 的 `det=cos(shearX)`。

## 運動基元:雙軸阻尼 shear(正交解耦)

`_twist_env(A, nosc)` 產兩條包絡(共用阻尼 r=WOBBLE_DAMP=0.5、同幅 A、同窗 [WOBBLE_LEAD,WOBBLE_TAIL]):

- **shearX(τ)**:逐位元同 `_wobble_env` —— 極值落 τ_i、符號 (−1)^i、幅度 A·rⁱ。
- **shearY(τ)**:同幅同阻尼,但每個極值時刻**偏移半個極值間距**(= 四分之一週期,正交)。故 shearY 峰落在 shearX 過零附近 → **shear 方向隨時間旋轉**(螺旋/對角晃),兩通道解耦。

Spine 的 shear 通道每個 keyframe 同時含 x,y,故 `gen_twist` 在兩軸極值時刻的**聯集網格**上線性取樣合併成單一 shear timeline(x,y 各自的極值都被保留)。

## 客觀結構簽章(可量化、負對照乾淨分離)

- **V1 present + shearY 產出(crux)**:twist beat 直出、finite、有 bone;峰 |shearX| **且**峰 |shearY| ≥ MIN_SHEAR(5°;實測皆 16°)—— shearY 必須非零 = 接上最後一條邊界。
- **V2 雙軸阻尼振盪**:shearX **與** shearY 各自(合併網格上取**轉折點**還原真實極值 [16,−8,4,−2])—— 首尾 0、繞 0 變號 ≥3、相繼極值嚴格遞減(阻尼)。
  - **踩雷**:合併網格讓單軸值序列含線性段上的內插點(如 shearX 在 shearY 極值時刻的中間值),直接套「相繼幅度遞減」會 FALSE。解法=先取**轉折點**(內部點 i 若 (v[i]−v[i−1]) 與 (v[i+1]−v[i]) 異號)還原該軸真實阻尼極值,再套既有 `_sign_changes_zero`/`_extrema_mags_decreasing`。
- **V3 雙軸獨立(crux)**:(a) **非比例** —— 最小平方比例擬合 `y≈k·x` 的殘差比 ≥ MIN_RESID(0.3;實測 0.82);(b) **正交** —— 乘積 `shearX·shearY` 於密網格繞 0 變號 ≥ MIN_PRODSC(4;實測 6)。
  - 兩個判準皆**免受共同衰減包絡污染**(相關係數會被兩軸共用的阻尼包絡拉高到 ~0.5,不可靠;殘差比與乘積變號對幅度縮放不變)。
- **V4 identity 介面**:sample(0)/sample(dur) 各 bone identity、shear 首尾 x==y==0 → 可插 Loop 間。
- **V5 端到端 pivot 不動**:`build_spine --shear-pivot` 產 twist 帶補償,關節 bone pivot 殘差 **fixed <0.011px** vs 未補償(繞件中心含 shearY)**negctrl 8–29px**(arm 50–164px、peak shearY 10–12°)—— shearY 首次驅動 `pivot_channels_affine` 而不動點精確保持。
- **V6 負對照/隔離**:(a) 單軸(shearY≡0,=wobble)→ V1 shearY 產出 FALSE、V3 正交(乘積恆 0)FALSE;(b) 比例(shy=k·shx,只是旋轉過的單軸 shear)→ V3 殘差 0、乘積 0 次變號 → 獨立 FALSE(**證第二軸是獨立 DOF,非把單軸換方向**);(c) shear 隔離:非 `SHEAR_CATS` beat 皆 0 bone 帶 shear;(d) 加性:移除 twist storyboard → 其餘 beat 逐位元不變。

## 實作 / 整合

- `beat_templates.py`:`gen_twist(role, side_sign, radial, nosc=4)` + `_twist_env` + `_TWIST_SHEAR`(role→幅度)+ `DUR["twist"]=0.8` + `TWIST_KEYWORDS`。
- `gen_animations.py`:`_DISPATCH["twist"]=gen_twist`;`_CAT_KEYWORDS` 置前(避免與 wobble 關鍵字爭用)。
- `genre_priors.py`:slot_bigwin 加 `twist` beat(additive)+ `_BIGWIN_ROLES["twist"]`(coverage 仍 1.0、Award 無命名→列 prior_beats_unused,誠實 PROPOSAL)。
- `tier_variants.py`:`twist` 併入 **SHEAR_CATS**(shear-isolation 閘 shear_gen W5b / wobble_tier T4 認得,零回歸)。
- `validate_twist_gen.py`:新閘(6 AC)。復用 `_shear_x`/`_sign_changes_zero`/`_extrema_mags_decreasing`(shear_gen)、`_world`(shear_pivot)。
- `check_readiness.py`:cap `twist_shear_y_generation` L2(pipeline)。

## honest boundary(仍在)

- twist **未接 tier 幅度 / count-aware**:shear 峰、雙軸振盪段數隨檔位遞增為後續(比照 G-4''/G-4''';twist ∉ MAIN_SHOW_CATS/COUNT_AWARE_CATS,故不產 `twist__{tier}` 變體)。
- shearX = shearY **同幅同源**(共用 A/r/窗,只差相位):獨立幅度階梯 / 獨立段數為後續。
- 扭轉形狀為 PROPOSAL(結構簽章客觀:雙軸阻尼 + 正交獨立;手感留使用者 A 類)。
- 單一真值資產(robot_parts);`spine-anim-forge` 區塊仍 HOLD(運動基元先驗、單一真值,防固化)。

## 關鍵發現

- **一般仿射 M 的所有自由度已由獨立通道到齊**:rotate、scaleX/scaleY(G-3/G-4'''' 非均勻+體積守恆)、shearX(G-4')、shearY(本次)—— shear 通道 honest boundary 系列(G-4→G-4'''''')到此收束。
- **免受包絡污染的獨立性判準**:兩個阻尼同源通道的相關係數會被共用衰減包絡拉高(~0.5),不足以判獨立;改用**比例殘差比 + 乘積繞 0 變號**兩個對幅度縮放不變的判準,對「正交 vs 比例(旋轉過的單軸)vs 單軸」三態乾淨鑑別。
