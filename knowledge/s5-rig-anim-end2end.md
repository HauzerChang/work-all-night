# S1×S5 端到端:分鏡生成 keyframe × 推得接觸縫關節(`--rig --animate`)

> 里程碑 2026-09-02(session 001)。閘 `tools/analyzer/validate_rig_anim.py`,一鍵 `python3 tools/analyzer/validate_rig_anim.py`(exit 0 = PASS)。

## 缺口(為何需要這條閘)

兩條已完成的線第一次被當作**一個單元**驗證:

- **S1 (candidate 0d)** `gen_animations`:分鏡 role×beat → bone `rotate/translate/scale` keyframe(`validate_anim` 已驗)。
- **S5** `build_spine --rig`:把「關節=父子件接觸縫」寫成子骨世界原點(pivot→bone 樹,`validate_rig_build` 已驗)。

`build_spine --rig --animate` 早就能一起跑(旗標非互斥),但**沒人證過**:生成的動畫幀是否真的讓肢體
**繞「推得的關節」**旋轉,而非件中心。這是「動畫掛在哪根骨、骨原點是不是關節、取樣器與骨變換一不一致」
的整合正確性 —— 純幾何的 `validate_rig_build`(手設 25°、解析式點旋轉)抓不到。

## 與 `validate_rig_build` 的差異(不是重複)

| | validate_rig_build (AC4) | **validate_rig_anim (本閘)** |
|---|---|---|
| 旋轉來源 | 手設常數 `THETA=25°` | **gen_animations 生成的真實 keyframe**(經 `spine_anim` 取樣) |
| 幾何 | 解析式 `|p−pivot|·2sin(θ/2)` | **完整 Spine bone world transform 組合**(`weighted_deform_eval`) |
| 抓得到的 bug | pivot 幾何位置 | **整合**:動畫掛錯骨 / 骨原點≠關節 / 取樣器與骨變換不一致 |

## 核心量測:關節撕裂(seam tear)

用「Loop peak-rotate 幀」—— Loop 的肢體是**純 rotate 通道**(無 translate/scale 混淆,見 `gen_animations.gen_loop`
role==limb 只設 `b["rotate"]`),是最乾淨的探針。追蹤**關節材質點 J**:

- 忠實參考 `J_body` = J 隨 **body 骨**剛性帶動的世界位置(接觸縫應該在的地方)。
- `rig`:limb 骨原點就在 J、掛 body → 繞自身原點轉不移原點 → `J_rig == J_body`,**撕裂 ≡ 0**(數值精確 0)。
- `flat`(非 rig 對照):limb 骨在**件中心 C**、掛 root → 繞 C 轉時 J 甩離 → 撕裂大。

`rig_tear = |J_rig − J_body|`、`flat_tear = |J_flat − J_body|`。這是「**肢體的接觸縫在動畫下有沒有黏住父件**」的物理量。

### 為何不能用 region bounding-box 角當 seam(踩雷)

第一版用「region 4 角中離關節最近者」當 seam,ratio 只有 1.2(不過)。原因:**bounding-box 角不是接觸縫** ——
角離關節質心約半條邊、離件中心約半條對角線,兩者可比 → ratio≈1。region 的接觸縫是**輪廓上的一段**,不是角。
正解是追蹤「關節材質點」相對 body 的撕裂(見上),它直接對應「件繞哪裡轉」,與件形狀/取點無關。

## 4 條 AC(對 Award `robot_parts`,結構肢體=右手/左手/頭,皆 region+joint)

1. **AC1 動畫驅動關節肢體**:`--rig --animate` 產出有限、well-formed animations,每結構肢體骨某 beat 有非零
   rotate(peak |θ|≥3°;實測 右手 20°/頭 8°/左手 −20°,皆 In beat 甩入)。→ 生成器確有讓 rig 上的關節肢體轉。
2. **AC2 無縫介面在 rig build 上保持(回歸)**:每 beat 的 setup 介面時刻(In 尾/Loop 首尾/Out 首)組合世界點
   ≈ setup(實測 **0.0000px**)→ rig 沒破壞可無縫串接。
3. **AC3 關節樞紐語意(核心)**:Loop peak-rotate 純 rotate 幀,`rig_tear=0.0000px`(<0.5)、`flat_tear`=5.4~19.9px
   (>2)、ratio(flat/rig)>1e6。
4. **AC4 鑑別力/歸因**:(a) 零旋轉介面幀(Loop t=0,θ=0)rig/flat 撕裂皆 0px → 撕裂確由 keyframe 旋轉造成、
   非固定偏移;(b)「若改用件中心 C 當 pivot」解析撕裂 2.6~14.3px ≫ rig_tear≈0 → 量化證 rig 恰繞推得關節轉。

## 關鍵結論

- **rig_tear ≡ 0 是「定義性精確」但非平凡**:它精確為 0 正是因為 build_spine 把骨原點放在了 `infer_pivots` 推得的
  關節、gen_animations 把 rotate 掛對了骨、且 body 是其父。任一環節壞掉 `rig_tear` 就非 0。`flat_tear>0`(同一
  metric 對非 rig 版非零)證 metric 有鑑別力;AC4a(θ=0 時歸零)證訊號來自旋轉本身。
- **併用不是新演算法,是覆蓋率 + 整合正確性**:`--rig` 移動骨原點、`--animate` 疊 local rotate,兩者座標上正交
  (rotate 疊在 local 不動原點)。本閘把「S1 生成 → S5 rig 骨 → 世界姿勢」整條管線鎖成綠。
- **honest boundary(同 pivot_end2end)**:仍 L2,只驗單一 robot rig(Award 僅機器人可拆肢體;OMG/SUP/MEG 為
  單圖+特效無接觸縫)→ 達 L3 的多 rig 真值屬**使用者資源**。緩動幅度/手感留使用者(A 類)。

新增 cap `rig_anim_end2end` L2 併入 `spine-rig-pivot` 區塊(**仍 HOLD**:硬缺口=多 rig 真值不變,防固化)。
