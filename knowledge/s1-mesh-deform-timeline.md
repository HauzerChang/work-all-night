# S1 candidate 0e — 分鏡 → mesh deform timeline 生成器(讓軟件「會變形」)

> 里程碑 2026-08-31(session 004)。補上 candidate 0d 的缺口:0d 只生成 **bone TRS + slot alpha**,
> mesh 件(窗簾/軟布/光暈/陰影)整片剛性隨骨走、**不會自身變形**。本能力為 skin 內每個 mesh
> attachment 生成逐頂點 `deform` timeline,使軟件真正會「飄/脹/縮」。

## 產出

- `tools/analyzer/gen_mesh_deform.py` — 確定性 mesh deform 生成器。
- `tools/analyzer/validate_mesh_deform.py` — 4 AC 真值閘(對 main_draw 4 個**真實美術 mesh**)。
- `tools/analyzer/build_spine.py --deform`(搭 `--animate`)— 端到端接入產線。
- check_readiness 新區塊 `spine-motion`(0d + 0e),**HOLD**(客觀閘全綠,但動作美感主觀=A 類)。

## 核心設計:仿射保證 + 波幅閘控

deform = 逐頂點 local 位移(y-up,offset=0 全長 `2*nv`),Spine 3.8 格式:
`animations[beat]["deform"][skinName][slot][att] = [{time, vertices:[dx,dy,...]}, ...]`。

mesh role → 位移場族(確定性關鍵字判定 `mesh_role`:含 shadow/glow/光暈/陰影… → radial,其餘 → shear):

- **affine swing**(布料/窗簾):`dx = A·fy·swing(t)`、`dy=0`,`fy=(ymax−y)/h`。fy 對 y 線性 →
  整體為**仿射剪切** → 恆乾淨(見下「關鍵教訓」)。整片左右擺,底邊擺幅大。
- **radial-breathe**(光暈/陰影):`offset_i = s(t)·(p_i − centroid)`。**均勻縮放亦是仿射** →
  s>−1 時恆乾淨。脈動呼吸。
- **可選行進波**(相位隨 fy 變 → 對 y **非線性**,非仿射):較好看但**不保證**乾淨;波幅經
  `deform_eval` 逐幀閘**自動遞減**(`WAVE_FRAC×0.5^k`,≤6 次)至乾淨,最差退化為純仿射(仍乾淨且非平凡)。

beat 類別對映(與 gen_animations 一致):loop 無縫(端點相等)/ intro 收在 identity(deform=0)/
outro 由 identity 起 / pulse 首尾皆 0 / hold 不發。三 beat 皆以 deform=0 為介面 → 與 0d bone
timeline 的 setup identity 無縫串接。**刻意線性內插(不加 bezier curve 鍵)**:讓相鄰 keyframe 間
任一中間幀都是兩個乾淨場的凸組合 → 中間幀也保證乾淨(bezier 可 overshoot 出凸包)。

## ⚠️ 關鍵教訓:「雙射」不等於「mesh 保拓樸」

**踩雷**:原以為「純 y 剪切 `dx=g(y)` 是平面雙射 → 對任意幅度恆保拓樸」。在 main_draw 4 mesh 上過關,
但接 build_spine 的**密集 body mesh(60v/97tri)後爆 si=30/flip=6**。

**根因**:平面雙射只保證**點**不重合,但 mesh 的**直線邊**是在頂點位移後「重畫」的直線,
**不是**原直線邊在映射下的像。只有**仿射**映射(線性剪切、均勻縮放、平移、旋轉)才與線性內插可交換
→ 精確把直線邊映成直線邊。**非線性**位移(相位隨 y 的行進波)下,直線邊會互穿 → 自交。
故:
- **仿射場族(swing/uniform-scale)**才是真正「可證明乾淨」的核心;
- **非仿射行進波**必須靠 `deform_eval` 逐幀閘把關(振幅小 → 邊位移小 → 收斂到乾淨;極限 A→0 為 identity)。

**負對照校準**:一開始用「radial s=−2」當折疊負對照 → 閘顯示 si=0 未抓到。原因:均勻縮放 s=−2 是
繞質心 180° 旋轉(det=(1+s)²=+1),**保拓樸**,不該被抓 —— 這反而印證 radial 場族的安全性。
改用「單一 hull 頂點拽過質心到對側」(非均勻)才是真正撕裂,閘正確抓到 si=8/flip=1。

## AC 結果(全 PASS)

對 main_draw 4 真實美術 mesh(curtain_left/right 21v、shadow/shadow2 12v),生成 5 類 beat:

| AC | 內容 | 結果 |
|---|---|---|
| AC1 | 格式/可載入 + round-trip(deform_frames 讀回一致、vertices 長==2*nv、time 單調自 0) | PASS |
| AC2 | 乾淨閘(每 mesh×beat 全取樣幀 si/flip/degen=0;含線性內插 substep,各 49 幀) | PASS |
| AC3 | 無縫 + identity 介面(loop 首==尾;intro 尾==0、outro 首==0、pulse 首尾==0) | PASS |
| AC4 | 非平凡(loop 位移 16–54px)+ 負對照(折疊 si=8/flip=1 被抓)+ 正對照(極端仿射剪切 5×寬仍乾淨) | PASS |

**端到端接 build_spine**:`--animate --deform` 對 robot_parts(光暈=radial、身體=shear)產 3 beat×2 mesh,
294 取樣幀 **si/flip/degen=0 全乾淨**、位移 22–341px(非平凡);波幅閘讓密集 body 自動收斂到乾淨。
回歸:`validate_build`(round-trip)、`validate_anim`(0d 4AC)在 `--animate --deform` 下**皆仍 PASS**
(deform 與 bone/slot timeline 共存不互擾)。

## 誠實界定

- **動作美感主觀**:role→運動基元、擺幅/波形皆為**先驗手感提案**(非學自真值)。客觀閘只保證
  「合法 / 乾淨 / 無縫 / 非平凡」,不保證「好看」→ 緩動與律動感留使用者(A 類)。故 `spine-motion`
  區塊**刻意不宣告 L3、維持 HOLD**(防把主觀手感固化成 skill)。
- **weighted mesh 的 deform**:本能力對 unweighted 直接加 local 位移(足以判拓樸)。weighted mesh 的
  bone-skinning 變形另有 `weighted_deform_eval`;混合 deform+skinning 的 timeline 生成屬後續。
- 未接影格級「主秀 beat(hit/open/reveal)」的 mesh 專屬爆發模板 —— 可與 S1 (f) 一起做。
