# S1 (G-4''''''-tier) twist 反相雙軸 shear 峰隨檔位遞增(兩軸同比 → φ 保形、scale-invariant 雙軸幾何)

- **結論**:把 (G-4'''''') 新生成的 `twist`(反相雙軸阻尼 shear,產線第一個驅動 shearY 的節拍)接上**檔位幅度差異化** ——
  twist 併入 `MAIN_SHOW_CATS`,`build_spine --animate --tier-variants` 每檔位直出 `twist__{Super,Mega,Omg,Legend}`,
  兩條 shear 軸的峰隨檔位嚴格遞增(shearX [16,21.6,27.2,33.6]°、shearY [11.2,15.12,19.04,23.52]°),
  而 shearY/shearX ≡ −`TWIST_PHI`(0.7)**逐檔不變**、反相耦合與阻尼振盪簽章逐檔保形。
- **信心**:高(端到端經 `build_animations`/真實 build_spine robot 骨架量測,6 AC + 負對照全 PASS,21 回歸閘全綠,無 GREEN→RED)。
- **相關階段**:專案第 2 階段(S1 反推分析器 / anim-forge)。cap `twist_tier_amplitude` L2 併入 `spine-anim-forge`(仍 HOLD,防固化)。

## 為什麼是這個 bounded chunk

(G-4'''''') 讓 `gen_twist` 產出雙軸 shear(shearX 純 wobble 阻尼擺、shearY 反相且幅度 ×φ),但其 honest boundary
明列:**twist 未接 tier 幅度 / count-aware**(`gen_twist(nosc=)` 已備參數未接;比照 wobble G-4''、squash G-4''''')。
twist 是主秀節拍,強度理應隨大獎檔位遞增,幅度軸在**兩條** shear 軸 —— 又一「檔位機制就緒 ≠ 每個新通道接上」缺口。
本次補**幅度**軸(tier 幅度),與 wobble/squash 的推進順序一致(先 tier 幅度,count-aware 為後續)。

## 實作(極小改動,重點在驗證)

- `tools/analyzer/tier_variants.py`:`MAIN_SHOW_CATS` 加入 `twist`。**關鍵:twist 純 shear(無 scale 通道,故不在
  `COUPLED_SCALE_CATS`)** → `amplify_bone_tl` 的 shear 迴圈(`v'=g*v`,對 0 對稱)以**同一 g** 同時放大 shearX 與 shearY,
  無需任何新增放大邏輯。twist 亦不在 `COUNT_AWARE_CATS`(`_count_maps` 無 twist entry → 走 amplify base anim,非重生成)。
- 無須改 `gen_animations`:`build_animations` 早已依 `MAIN_SHOW_CATS` 路由檔位變體。base(Super,g=1.0)逐位元 == 無檔位輸出。
- `tools/analyzer/validate_twist_tier.py`:新閘(6 AC)。復用 `validate_shear_gen` 的阻尼簽章判準與 `validate_twist_gen`
  的雙軸讀取(`_shear_y`/`_shear_xy`/`_interior_shear`/`_tw3_eval`/`_has_shear_y`),確保與既有 shear/twist 閘完全一致。
- `tools/check_readiness.py`:註冊 cap `twist_tier_amplitude` L2(pipeline)。

## crux(與 wobble tier 的差異 → 閘的鑑別力來源)

wobble tier 只有**一條** shear 軸;twist 有**兩條**。檔位放大要保住「反相雙軸 shear」簽章,兩軸必須**同比**縮放:
- 每關鍵幀 shearY = −φ·shearX;amplify 後 shearX' = g·shearX、shearY' = g·shearY = −φ·(g·shearX) = −φ·shearX'
  ⇒ **shearY/shearX = −φ 逐檔恆定**、反相(乘積符號)不變、阻尼比 r=0.5 同比放大 → 符號序列與遞減比不變。
- 若兩軸**各自獨立增益**(例如只放大 shearX、shearY 不動),φ 會漂移、甚至可能翻掉反相 → 就不再是同一種雙軸扭轉。
- 本機制用**單一 g** 對兩軸(shear 通道 `v'=g*v`)⇒ **反相雙軸幾何 scale-invariant**(強度變、幾何種類不變:
  愈高檔位擰愈狠,仍是同一種雙軸 shear 扭轉,非別種運動)。TT6(b) 用「獨立軸增益負對照破 φ」證此單一-g 是 φ 保形的關鍵。

## AC(`validate_twist_tier.py` 6 條全 PASS)

- **TT1 present + backward-compat**:base twist 帶雙軸 shear(shearX/shearY 峰皆 ≥5°);每檔位 `twist__{tier}` 產出、
  finite、有 bone、≥1 bone 帶 shear、名經 `beat_category` 仍路由回 twist;**base(含 In/Loop/Out + base twist)帶/不帶
  tier_gains 逐位元不變**。
- **TT2 crux — dual-axis peak monotone**:各檔位峰 |shearX| **與** 峰 |shearY| 皆 Super<Mega<Omg<Legend 嚴格遞增
  (端到端量:shearX [16,21.6,27.2,33.6]°、shearY [11.2,15.12,19.04,23.52]°),且首檔(Super,g=1)兩軸峰 == base。
- **TT3 crux — φ 比值 tier-invariant**:每個 twist bone 每檔位 shearY 峰 / shearX 峰 ≈ TWIST_PHI(0.7,誤差 ≤2e-3)
  → 單一 g 對兩軸同比 → 反相雙軸耦合 scale-invariant。
- **TT4 兩軸阻尼簽章逐檔保形**:每檔位每 twist bone 的 shearX **與** shearY 各自 (a)首尾 0 (b)繞 0 變號 ≥3
  (c)相繼極值嚴格遞減(阻尼)。
- **TT5 反相逐檔保形 + 偏離峰遞增**:每檔位每內部極值幀 shearX·shearY<0(反相保形);且反相夾角偏離峰
  |shearY−shearX| 隨檔位嚴格遞增([27.2,36.72,46.24,57.12]°)。
- **TT6 neg-control / isolation**:(a)平增益守衛(全 1.0)→ TT2 兩軸遞增 FALSE 且各檔位逐位元 == base twist;
  (b)單一-g 兩軸同比單元測(`amplify_bone_tl` 對雙軸 shear-only bone → shearX、shearY 皆 ×g、比值不變、不生 scale 鍵;
  **獨立軸增益負對照**只放大 shearX → 比值改變,證單一-g 是 φ 保形關鍵、閘測比值不變非恆真);
  (c)shear 隔離到 `SHEAR_CATS`(wobble/squash/twist)及其 `__tier` 變體,不外洩非-shear 主秀 beat。

## 端到端

`build_spine --animate --tier-variants --shear-pivot` 直出 `twist__{Super,Mega,Omg,Legend}`,shearY 經關節 pivot 補償
仍存活且隨檔位遞增(11.2→23.52°);`validate_build` round-trip overall_pass(premult MAE 0.031)。

## honest boundary(仍在)

- twist 未接 **count-aware**(扭轉段數隨檔位,`gen_twist(nosc=)` 已備參數未接;比照 wobble G-4'''、squash G-4'''''-c)—— 下一步候選。
- 反相雙軸未接**體積守恆**耦合 scale(`det=cos(shearY−shearX)≠1` → 擰轉變面積;volume-conserving twist = shear+scale+rotate
  三通道同時且守恆,為後續)。
- 幅度增益階梯與 φ 皆為 **PROPOSAL**(結構簽章客觀、手感留使用者 A 類);單一真值資產(robot_parts);anim-forge 仍 HOLD。
