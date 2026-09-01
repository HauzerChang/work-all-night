# S1 candidate 0e — mesh deform timeline 生成器(讓軟件 mesh 本身會動)

> 里程碑 2026-09-01。補 candidate 0d(`gen_animations.py`)的缺口:0d 只產 **bone TRS + slot alpha**,
> mesh 本身不變形(窗簾/光暈/陰影只被控制骨剛性搬動,不會飄、不會脹縮)。本器生成 Spine 3.8 mesh
> `deform` timeline,讓這些軟件/特效 mesh 真的逐頂點變形。

## 檔案

- `tools/analyzer/gen_deform.py` — 生成器(library + CLI)。
- `tools/analyzer/validate_deform_gen.py` — 7 AC 自我品質閘(gate = `deform_eval`,真實位移場、已驗可信)。
- `tools/analyzer/build_spine.py --animate --deform` — 端到端整合(mesh 件產 deform timeline)。

## 核心設計(RULES:確定性演算法 + 評估器;變形**用真實位移場轉移**不用未校準 stress_field)

1. **運動來源 = 真實藝術家 deform 場**。由 `deform_eval.real_deform_field` 從真實 `main_draw` 的窗簾/陰影
   mesh 抽出「總位移最大幀」的逐頂點位移場(以 **UV** 為座標 → 可轉移到任一拓樸)。這是「柔性布料律動」模板。
   *不是憑空捏造的空間波形(那正是 `stress_field` 被標為不可當閘的教訓)。*
2. **轉移**:UV 內插(griddata linear + nearest 補 hull 外洞)把來源場套到目標 mesh 頂點 → 目標位移場。
3. **時間包絡(beat 相依,首尾強制回 setup)**:
   - `loop` :`ucos` 0→peak→0 正弦包絡,端點強制相等 → **無縫**,且與 bone loop 同 setup 介面。
   - `intro`:swell 0→peak(0.6T)→0(settle to setup),ease-out bezier。
   - `pulse`:對稱 0→peak→0。
   - `outro`/`hold`:mesh **不變形**(不寫 deform key;靜態交給 bone scale/alpha)。
4. **幅度校準**:peak 為真實場的**分數**(loop 0.5 / intro 0.7 / pulse 0.6)→ 位移必 ≤ 真實 deform 幅度。

Spine 3.8 格式寫回 `animations[beat]["deform"] = {skinName:{slot:{att:[{time,offset,vertices,curve..}]}}}`;
deform vertices 為 attachment-local、y-up(與 mesh setup 同空間,逐頂點相加,見 `deform_eval.apply_deform`)。

## 驗收(`validate_deform_gen.py` 7 AC 全 PASS,exit 0)

| AC | 內容 | 結果 |
|---|---|---|
| AC1 | 結構/有限(time 遞增、offset int、vertices 長==2·nv、值有限、bezier 鍵有限) | ✅ |
| AC2 | 逐幀乾淨(sample_poses 展開含相鄰幀內插 → 每 pose si=0/flip=0/degen=0) | ✅ |
| AC3 | loop 無縫(首 frame vertices == 末 frame vertices,皆 0) | ✅ |
| AC4 | setup 介面(intro/loop/pulse 首尾位移==0 → beat 間可無縫串接) | ✅ |
| AC5 | 幅度校準(4 mesh gen_peak ≤ real_max:窗簾 220≤315 / 陰影 71≤102) | ✅ |
| AC6 | 負對照鑑別力 | ✅ |
| AC7 | 端到端(`build_spine --animate --deform` robot_parts → 生成 mesh 光暈/身體 deform 逐幀乾淨) | ✅ |

## 關鍵發現:閘抓的是「拓樸損壞」不是「幅度大」

負對照(AC6)量了兩種壞場:

- **不連貫(scramble)位移場 × 3** → **4/4 mesh 全破**(窗簾 si+flip 28/62、稀疏 12v 陰影也 4/4)。
  這是壞生成器的真實失敗模式(不尊重空間平滑)。
- **連貫真實場等比放大 × 4** → **4/4 mesh 仍乾淨**。合法運動方向只是變大,拓樸不壞。

⇒ 校準應沿**連貫場**做(我方生成器正是如此,peak≤0.7× 有裕度),而非怕「幅度」。稀疏拓樸(12v 陰影)對
同幅度 scramble 較耐(頂點太少難自交),需 ×3 才穩定破 → 負對照要夠強才有鑑別力(單純同幅度 scramble 只破細網 21v)。

## 誠實邊界 / 下一步

- **件 role → 律動場來源為先驗映射**:目前預設「軟布料模板 = main_draw 窗簾場」;哪種件配哪種律動
  (布料/火焰/彈跳/呼吸)屬手感先驗,非學自真值。緩動美感留使用者(A 類)。
- **單一真值資產**:律動模板取自 main_draw(唯一含 mesh deform 的真實資產);多樣律動庫需更多真實 deform 樣本(資源類)。
- `spine-anim-forge` 區塊(0d keyframe + 0e deform)定 **L2 → HOLD**:運動基元是先驗手感,達 L3 前不打包成 skill(防固化,同 rig 區塊策略)。
- 後續候選:(A) S1 keyframe 補主秀 beat 模板(hit/open/reveal);(B) 律動場庫擴充(需更多真實 deform 樣本)。
