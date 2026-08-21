# S3 — weighted mesh **骨骼驅動**變形評估器(補上唯一未驗維度)

- **結論**:新增 `tools/mesh_gen/weighted_deform_eval.py` —— 對 Spine **weighted** mesh 做**真實骨動**
  前向 skinning + 拓樸品質閘。對 Award 機器人 3 個美術 weighted mesh(光暈/左手/身體)驗收:
  **setup + 所有穩態(`*_Loop`)可見幀 0 自交 / 0 翻面**(`_checker_validated=True`),
  且負對照雙向抓得到(bind 打亂 6804 自交、glow In 未遮罩真實骨動 71 自交)→ **閘可信且有鑑別力**。
- **信心**:高(對真實生產骨架 + 美術權重 + 動畫;skinning 數學經 setup 自洽 + bezier 校準)。
- **階段**:第 2 階段 / S3。補上 `s3-robot-mesh-vs-award.md` 標記的**唯一未驗維度**
  「weighted mesh 骨骼變形平滑度(靜態 IoU 不涵蓋)」。

## 標準指令

```
python3 tools/mesh_gen/weighted_deform_eval.py            # 硬閘:_checker_validated → exit 0
python3 tools/mesh_gen/weighted_deform_eval.py --negctrl  # 鑑別力:discriminative → exit 0
```

## ⭐ 關鍵更正(本 session,2026-08-21)

STATE 與 `s3-robot-mesh-vs-award.md` 曾記「**目前資產未含這 3 件的變形動畫**」→ **錯**。
實測:這 3 件綁的骨 `4_LEG3..4_LEG9`(idx 60~66)在 `Award_Legend_In` / `Award_Legend_Loop`
**有 bone timeline**(rotate/translate/scale)。故可建**真實** bone-driven deform 閘(非合成壓力場,
符合 RULES「變形閘用真實位移場、不要用未校準 stress」)。
(旁註:僅 **Legend** 家族拉這些腿骨;Mega/Omg/Super 未動到 → 機器人腿部僅在最高階 Legend 演出。)

## 技術要點(Spine 3.8 skinning,已實作並驗證)

1. **骨 world affine**(normal transform、無 shear):`a=cos(rot)·sx, b=-sin(rot)·sy,
   c=sin(rot)·sx, d=cos(rot)·sy`,平移 `(x,y)`;`world = parentWorld ∘ local`(root parent=identity)。
   Award 全 77 骨皆 normal / 無 shearX/Y → 組合可閉式。
2. **weighted 頂點**:`worldV = Σ_j w_j·(boneWorld_j 施於 bind 局部 (bx,by))`(Spine `computeWorldVertices`)。
   weighted `vertices` 格式:每頂點 `[n, (boneIdx,bindX,bindY,weight)×n]`;bind 是相對該骨的 setup 局部座標。
3. **timeline 套用**:rotate `rotation=data+angle`、translate `x=data+x`、scale `scaleX=data·x`(乘法,預設 x=y=1)。
4. **緊湊 bezier easing**(CLAUDE.md 雷點 #7):`{curve:cx1,c2:cy1,c3:cx2,c4:cy2}`,控制點 P1/P2、
   P0=(0,0)/P3=(1,1);給時間分數 a 二分解 s 使 X(s)=a → 回 Y(s)=percent;`stepped`→持值、缺省→linear。
   **一個 keyframe 的 percent 同套到該 channel 全分量**(Spine 慣例)。

## ⭐⭐ 最重要發現:weighted 變形閘**必須做可見度(alpha)遮罩**

又一次「同一 lesson 換 weighted 版」的踩雷(CLAUDE.md 雷點 #2/#3 attachment/可見度 gating):

- glow 的 `Award_Legend_In` **全幀** si 高達 **71**、area_ratio 衝到 1.98 → 看似美術 mesh 會壞。
- 但該 slot 的 **color timeline alpha = 00(全透明)於 t=0~0.5**,`t=0.6333` 才淡到 `ff`。
  逐幀對照:mesh 的自交**全發生在 alpha≈0 的進場段**(t≤0.467),alpha 一開(t≥0.5)立刻乾淨。
  → 進場的折疊是**看不見的編排**(fly-in / 組裝 / 擠壓),不是拓樸缺陷。
- **修正**:評估器解析 slot color alpha,**只在可見幀(alpha≥0.03)判定**(`slot_alpha()`)。
  glow In 可見自交 71→(遮罩後)剩 1 個瞬時微觀折疊。

## 相位分閘:Loop=硬閘、In/Out=診斷

- **穩態 `*_Loop`**(mesh 完整顯示、休息呼吸)= 真正的變形平滑度判準 → **硬閘**:3 件全 0 自交/0 翻面。
- **進退場 `*_In/*_Out`** 常在 **alpha 淡入 + 擠壓極端**出現**極短(~1 幀)微觀折疊**:
  glow 在 t≈0.63(squash 到 area 0.883、alpha≈1)有 **4 條交叉**,前後幀(0.62/0.64)皆 0。
  bezier 校準**後**仍在 → 非內插假象,是**美術半透明 glow 的真實微折**(視覺可忽略)。列為 `_transient`,不作 pass/fail。

視覺證據:`knowledge/figures/s3_weighted_deform_glow.png`(左=setup / 中=Loop 穩態乾淨 / 右=In t=0.63 擠壓微折,紅線=交叉邊)。

## 量化結果(Award 3 weighted mesh × Legend)

| 件 | nv | tris | driving bones | setup | Loop 穩態(硬閘) | In 可見瞬時 |
|---|---|---|---|---|---|---|
| 光暈 | 78 | 76 | 4_LEG3/4/5/6 | clean | **0 自交**(area 0.997~1.003) | 4 自交@t0.63(squash) |
| 左手 | 80 | 116 | 4_LEG5/9 | clean | **0 自交**(area 0.975~1.0) | 0(area 低至 0.807) |
| 身體 | 98 | 154 | 4_LEG3/7/8 | clean | **0 自交**(area 1.0~1.001) | (Legend_In 未拉其骨) |

`_steady_state_worst_visible = {si:0, flip:0}` / `_transient_worst_visible = {si:4}` / `_all_setup_clean=True`。

## 鑑別力(負對照,`--negctrl`)

- **A. bind-shuffle**(決定性重排各頂點 bind 座標)→ setup **6804 自交** → `setup_clean` 抓到。
- **B. glow 真實 In 不遮罩**(含 alpha=0 幀)→ **71 自交** → 證明閘對「真實骨動下折疊」不盲。
- `discriminative=True`(兩方向皆偵測)。

## 誠實界定 / 下一步

- 本閘驗的是**美術 weighted mesh 在真實骨動下的拓樸合法性**(自交/翻面/退化/面積),
  以美術真值自洽 + 負對照建立可信度。**尚未**做的是:**我方生成 weighted mesh** 的對照
  —— 需 (1) 內部取樣密度控制、(2) BBW 骨綁權重生成,再用本閘量「我方 mesh vs 美術 mesh」變形品質。
  即:**評估器(本次)已就位;生成器(BBW)是下一個 bounded chunk**(RULES:每能力先配評估器 ✔)。
- Loop 動作幅度小(呼吸,area 0.97~1.0),對「密內部頂點是否讓變形更平滑」的區辨力有限;
  未來若拿到大幅骨動的真實 Loop(或用 In 的可見段)可加「變形平滑度(法向/面積梯度)連續性」量度。
