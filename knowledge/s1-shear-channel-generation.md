# S1 生成器產出 shear 通道端到端(斜拉 wobble beat,G-4')

> 里程碑 2026-09-08 session 002(candidate G-4')。補 G-4 的 **honest boundary**:G-4 補齊了
> 「件繞關節 pivot 的**一般仿射**(含 shear/非均勻 scale)」的**公式 + 閘**,但當時**沒有任何 beat
> 生成器產出 shear 通道**(產線主秀只用 rotate/scale,AC7 只用合成 shear 驗管路)。本次讓某節拍
> **實際產出 shear 通道**,`build_spine --shear-pivot` 帶 `include_shear=True` 端到端補償 —— 把
> 「公式/閘就緒 ≠ 生成器接上」這最後一段接上。
> 工具:`beat_templates.gen_wobble`、`build_spine --shear-pivot`、`validate_shear_gen.py`、
> 圖 `figures/s1_shear_gen.png`。

## 動機(接 G-4 的最後一塊)

G-4(`s1-shear-pivot-affine.md`)證明:同一條補償公式 `Δ=(M−I)(O−P)`(M=真實 Spine local 含 shear)
讓件繞關節 pivot 做**一般仿射**變換而 pivot 精確不動。但那是**幾何/公式 + 閘**;它的 honest boundary #5
明言:「目前 `gen_animations` 尚未產出 `shear` 通道…當某節拍需要 shear(如斜拉 squash)時,只需讓 beat
產 shear 通道、build 帶 `include_shear=True` 即接上(管路已通,見 AC7)。」本 candidate 就是做這一步。

這是本專案反覆出現的 **「宣告/公式/模板就緒 ≠ 生成器接上」** 模式的又一實例(同 (E)/(H)/(I)/(J)/(J-2)):
能力的**判準與管路**先就緒,**生成器實際使用它**才是把價值兌現的最後一段。

## 運動基元:斜拉 jelly wobble(阻尼 shearX 擺動)

`gen_wobble(role, side_sign, radial)`(`beat_templates.py`)—— **第一個產出 `shear` 通道的生成器**。
純 shearX 斜拉(shearY≡0),幅度**遞減**收回 identity:

```
shearX 包絡(τ, r=WOBBLE_DAMP=0.5):
  0 → +A(0.16)→ −rA(0.38)→ +r²A(0.60)→ −r³A(0.80)→ 0(1.00)
role 峰 A(度):特效 16 / body 14 / limb 12 / head 10   ；side_sign 決定首推方向(左右反相)
```

- **結構簽章**(客觀、可量化,與天真 shear 負對照乾淨分離):
  1. **首尾 shearX == 0** → setup identity 介面,可插在 Loop 循環間(同其他主秀 beat)。
  2. **阻尼振盪**:shearX 序列**繞 0 變號 ≥3**(4 次:+,−,+,−)且**相繼極值幅度嚴格遞減**
     (A>rA>r²A>r³A → 16,8,4,2)。
- **純 shear(不帶 scale/rotate)** → shear 通道**孤立可辨**:全 storyboard 僅 wobble 帶 shear,
  其餘 beat 皆無 → `apply_pivots(include_shear=True)` 的補償對象明確。

Spine shear timeline 格式同 translate:`{"time", "x"(shearX), "y"(shearY)}`。

## 接進產線(additive,直出)

- `beat_templates.py`:加 `gen_wobble` + `WOBBLE_KEYWORDS` + `DUR["wobble"]=0.8`。
- `gen_animations.py`:註冊 `_DISPATCH["wobble"]=gen_wobble`、`_CAT_KEYWORDS` 置前(exact 命中優先)。
- `genre_priors.py`:`slot_bigwin` 加 `wobble` beat(PROPOSAL);Award 真值僅 In/Loop/Out →
  `validate_priors` 列 `prior_beats_unused`(誠實,覆蓋率仍 1.0)。
- `build_spine.py`:`--shear-pivot`(`shear_pivot=True`)→ `apply_pivots(..., include_scale=True,
  include_shear=True)`;**含 `--scale-pivot`/`--pivot-rotate` 語意**。並在 summary 回報
  `pivot_centers`(O)/`pivot_joints`(P)供閘端到端驗殘差(同 rig 的 `rig_joints` 可觀測性)。

`build_spine --animate --shear-pivot`(非 rig)即**直出**:wobble beat 產 shear,件繞關節 pivot 做一般仿射。

## 驗收 `validate_shear_gen.py`(先驗庫→真實 build_spine robot 骨架→build_animations,5 AC 全 PASS)

| AC | 內容 | 實測 |
|---|---|---|
| W1 | **present + shear 產出(crux)** wobble 直出/finite/有 bone,≥1 bone 帶 shear 且峰 ≥5° | 峰 **16°**(5 bone 全帶 shear) |
| W2 | **阻尼振盪簽章** 首尾 0、繞 0 變號 ≥3、相繼極值嚴格遞減 | 變號 4、極值 [16,8,4,2]↓ |
| W3 | **identity 介面** sample(0)/sample(dur) 各 bone identity + shear 首尾 0 | PASS(可插 Loop 間) |
| W4 | **端到端 pivot 不動** `build_spine --shear-pivot` 有關節的 bone pivot 殘差 < 0.5px | 右手 0.009 / 頭 0.004 / 左手 0.013px（arm 50–164px；負對照 8–24px） |
| W5 | **負對照/隔離** (a)天真單調 shear 簽章 FALSE (b)僅 wobble 帶 shear (c)移除 wobble 其餘 beat 逐位元不變 | 全 PASS |

**W4 是端到端的關鍵**:pivot 殘差 <0.02px vs 未補償(繞件中心)8–24px 位移,arm(|O−P|)達 164px,
比值 >1000× → 生成的 shear **確實繞關節 pivot** 做仿射變換(接上 G-4 的 AC7,但用**真實生成的 wobble
beat + 真實 robot 骨架**而非合成 anim)。有關節 pivot 的 bone(右手/頭/左手)被補償,pivot≈件中心的
bone(光暈/身體)正確略過。

## 關鍵發現 / 踩雷

1. **honest boundary 的價值**:G-4 誠實標記「公式就緒 ≠ 生成器接上」,本次正是照著那條邊界把它接上;
   若當初含糊帶過(宣稱「shear 已支援」),就不會有這個明確、可驗收的下一步。
2. **阻尼簽章需「振盪 + 遞減」兩條件並立**:天真單調 shear(0→A→hold)有 shear 值但 0 次變號、無遞減
   → W5(a) 負對照證閘測的是**阻尼振盪**非「有 shear 通道即可」(否則簽章形同虛設)。
3. **shear 隔離讓補償對象明確**:wobble 純 shear、其餘 beat 無 shear → `include_shear=True` 只補償
   wobble 的 shear bone,對既有節拍零回歸(W5c 逐位元不變)。
4. **加性 opt-in**:`--shear-pivot` 預設關;`include_shear` 只影響有 shear 通道的 bone;把 wobble 加進
   先驗庫不擾動其他 beat(build_animations 逐 beat 獨立)。0i/G-3/G-4 路徑逐位元不變。

## honest boundary(仍在)

- 斜拉 wobble 的形狀(阻尼比 0.5、role 峰值)是 **PROPOSAL**(結構簽章客觀,手感留使用者 A 類)。
- 目前只產 **shearX**(shearY≡0);tier(檔位)變體尚未接 wobble(wobble ∉ `MAIN_SHOW_CATS`)——
  可比照 (J) 把 wobble 加進 tier 幅度差異化(shear 峰隨檔位遞增)為後續。
- 單一真值資產(robot);`spine-anim-forge` 仍 **HOLD**(運動基元先驗、未達 L3 端到端真值)。

## 回歸(全綠)

`validate_priors`(cov 1.0)、`priors_beats`(E)、`more_beats`(0g)、`beat_templates`(0f)、`cascade`(0h)、
`priors_combo_charge`(H)、`priors_cascade`(I)、`tier_variants`(J)、`tier_combo_count`(J-2)、
`pivot_rotation`(0i)、`scale_pivot`(G-3)、`shear_pivot`(G-4)、`deform_gen`(0e)、`anim`(+selftest)、
round-trip `validate_build` 對 `--shear-pivot` build(overall_pass、premult MAE 0.031、setup 不變)全 PASS。

## cap / skill

新增 cap `shear_channel_generation` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
