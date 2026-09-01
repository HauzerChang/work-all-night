# S1/S3 — mesh deform timeline 生成器(窗簾/軟體形變)

- **結論**:補上 candidate 0d(分鏡→動畫)最後一個缺口——此前 `gen_animations.py` 只生成
  bone TRS + slot color alpha,**mesh 不會變形**。新增**確定性 mesh deform 生成器**
  `gen_deform.py`:把 beat 類別 → 空間位移場 × 時間 shape 具體化為 Spine 3.8 `deform`
  timeline(unweighted mesh 的逐頂點 offset)。對 main_draw **4 個真實藝術家 mesh × 4 beat 類別**
  自我驗收 `validate_deform_gen.py` **AC1–5 全 PASS**;已接進 `build_spine --animate` 與 `gen_animations`。
- **信心**:高。位移場模型**grounded 於藝術家真值**(非臆測)+ 拓樸閘全乾淨 + 隨機場負對照有鑑別力 +
  經 Spine reader(`deform_eval.benchmark_real`,即讀藝術家真實 deform 的同一支)round-trip 全 clean。
- **相關階段**:第 2 階段 → S1「會動的 Spine 素材」產線;讓 `build --animate` 的窗簾/軟件真正 deform。

## 位移場模型(從藝術家真值反推,非臆測)

量測 main_draw 4 個真實 mesh 的 deform(`real_deform_field` 取各 mesh 總位移最大幀):

| mesh | 峰值位移 | 佔長軸長 | 錨定端(|d|=0) | 自由端(|d|=max) | 主方向 |
|---|---|---|---|---|---|
| curtain_left | 314.7px | 58.8% | 頂(rail) | 底 | **水平掃動** |
| curtain_right | 307.2px | 57.4% | 頂 | 底 | 水平 |
| shadow / shadow2 | 101.6px | ~19% | 頂 | 底 | 水平 |

**逐頂點量測**(curtain_left,close 幀):|deform| 幾乎**線性遞增於「距頂的距離」**
(頂 w=1.0 → |d|=0;底 w=0.0 → |d|=315),且**dx 主導**(水平掃)。

⇒ 確定性場: `offset_perp[i] = A · w_i · shape(τ)`,`w_i` = 距錨邊的正規化距離 ∈[0,1]
(錨邊 0、自由端 1),`shape(τ)` 依 beat 類別。**「哪端錨定」單張 mesh 無法得知 → prior**
(預設長軸 max 端 = 頂錨定,`anchor` 參數可覆寫)。

## beat 類別 → 時間 shape

| 類別 | shape(τ) | 端點 | 用途 |
|---|---|---|---|
| **loop** | `sin(2πτ − k·w_i)`(travelling wave) | 首尾=0(無縫) | idle 飄動,可無縫接 TRS loop |
| **pulse** | `sin(πτ)` | 首尾=0 | 對稱陣風(命中) |
| **intro** | `(1−τ)(1+0.3 sin 4πτ)` | 首=掃開、尾=0 | reveal 入場,收在 setup 接 loop |
| **outro** | `τ` | 首=0、尾=掃出 | reveal 退場,由 setup 生長 |
| **hold** | — | 無 deform | 定格 |

## AC(自我驗收,量化,不靠肉眼)

| AC | 判準 | 結果(4 mesh × 4 cat) |
|---|---|---|
| AC1 well-formed | 時間嚴格遞增、值有限、offset 長度==2·nv、JSON round-trip | ✅ |
| AC2 loop seamless | loop 的 `offset(t=0)==offset(t=dur)`,max_err ≤ 1e-6 | ✅ (err=0.0) |
| AC3 topology clean | 全取樣幀(含相鄰內插)self_intersections/flips/degenerate 皆 0 | ✅ |
| AC4 amplitude plausible | 峰值 >0.5px(真的會動)且 ≤ **類別包絡** 0.60·長軸;area_ratio∈[0.5,2.2] | ✅ |
| AC5 negative control | (a) 隨機逐頂點場 → 撕裂(si=62,flip=9);(b) 打斷 loop 端點相等 → seam err>0 | ✅ 皆偵測 |

峰值:loop ~31px / pulse ~54px / intro ~213px / outro ~187px(窗簾級,皆在 321px 包絡內、拓樸乾淨)。

## 關鍵發現 / 決策

- **位移場模型可從藝術家真值反推**:窗簾 = 頂錨定、水平掃、幅度線性於距錨距離。這不是猜的,
  是量 4 個真實 mesh 得到的一致規律 → 確定性演算法有真值依據(符合 RULES「不用 ML 學美術決定」)。
- **平滑 shear 場極耐變形**:loop 幅度**灌爆 6×**(~187px)仍拓樸乾淨——呼應早前「藝術家 315px
  strip 拓樸乾淨」的發現。單向、幅度單調於 w 的剪切場本質上不自交。故 AC3 的鑑別力**不能靠加大幅度**
  demo,改用**隨機非平滑場**(si=62)證閘非空過。
- **類別包絡 vs 該 mesh 自身峰值**:AC4 上限用「跨所有藝術家 mesh 的最大 deform ≈59% 長軸」當**類別物理
  包絡**,而非「該 mesh 自身藝術家峰值」——後者是藝術家對那件的**手感選擇**(如 shadow 只掃 19%),非物理硬限。

## honest boundary / 待續

- **預設幅度是窗簾級**:intro/outro 對 shadow 會掃到 213px(>shadow 藝術家的 102px,但在類別包絡內)。
  「shadow 應比 curtain 掃得少」是**語意知識**(shadow vs curtain),幾何無從得知 →
  caller(分析器/storyboard)應傳 `amp_frac` 給 role-specific 幅度。生成器已開放此參數。
- **reveal intro/outro 為非零端點設計**:窗簾「開/關」的大單向掃動(open 結束在掃開態、非 identity)
  與現有「所有 beat 收在 identity」的 TRS 串接慣例不同;本次 intro=掃開→identity、outro=identity→掃出
  以維持可串接,大單向 reveal sweep(open 停在掃開態的 loop-idle)留後續。
- **weighted mesh 不適用**:此生成器產逐頂點 offset(unweighted);weighted mesh 的 deform 需 vs
  骨變形疊加,屬 deform-of-weighted 後續課題。
- **緩動曲線美感**:主觀項,留使用者/實機。

## 工具 / 標準指令

```
# 生成器(獨立):
python3 tools/mesh_gen/gen_deform.py assets/main_draw.json loop
# 自我驗收閘(期望 overall_pass:true, exit 0):
python3 tools/mesh_gen/validate_deform_gen.py
# 端到端(有 mesh 的資產,build --animate 自動附 deform):
python3 tools/analyzer/build_spine.py <psd> --out <dir> --animate
```

- `tools/mesh_gen/gen_deform.py` — `gen_deform_timeline(setup,category,anchor,amp_frac,sway_sign)`、
  `build_deform_block(skeleton,category,...)`(對 skeleton 所有 unweighted mesh 產一支 anim 的 deform 區塊)。
- `tools/analyzer/spine_anim.py` — 新增 `sample_deform(frames,time)`(取樣 deform offset 向量)、
  `deform_frames_finite(frames)`(well-formedness)。
- `tools/analyzer/gen_animations.py` — `build_animations(...,mesh_deform=True)` 依 beat 類別自動附 deform。
- 圖:`knowledge/figures/s1_mesh_deform_gen.png`(anchor 權重 / 藝術家真值場 / 生成場 / loop 無縫姿態)。
