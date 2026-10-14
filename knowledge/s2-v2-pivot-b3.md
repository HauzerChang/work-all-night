# 2.0 (B3) 繞關節 pivot 變換入口(結構軸):pivot_axis → 幾何真值 + validator_v1 雙真值

> MERGE_PLAN_2.0 **Phase B3**(承 B1 橋接閘 / B2 生成庫入口)。排程主線 = **產出 spine-ai-editor 2.0**。
> 本篇把 repo 的 `pivot_rotation.py` 抽成 skill 層級入口,補 `references/structural_expansion.md` 的 SOP E。

## 這個 chunk 是什麼

B1 證明「repo 一支 cascade beat → validator_v1」可機械化;B2 把生成流程抽成 skill 入口 `gen_lib.make_beat`
(`generate_bigwin` 4 種大獎 beat)。B3 補上 **spine-ai-editor 的「結構軸」**:讓件**繞關節 pivot**(肩/頸)轉,
而非繞件中心轉——這是肢體動畫物理正確的前提。

repo 既有 `validate_pivot_rotation.py` 已以 **7 AC** 對真實 Award 幾何證明「件繞關節 pivot 轉」的確定性分解正確
(`Δ=(M−I)(O−P)`);B3 把那能力**抽成可重用的 skill 入口**(作用在 gen_lib 生成的動畫上,不只臨時腳本),
並**新增 B1/B2 的雙真值紀律(G2)**:補償後不只幾何對,還要過 `validator_v1`(editor 可匯入 + loop 閉合)。

## 做了什麼(純新增,`generate_bigwin` 逐位元不變 → B2 零回歸)

1. **`skills/spine-ai-editor/assets/gen_lib/pivot_axis.py`**(結構軸入口):
   - `apply_joint_pivots(skel, anim_name, pivot_of, bone_origin=None, include_scale=False, include_shear=False, apply_g1=True)`
     —— 就地把某動畫內「有 pivot」的 bone 轉成繞關節 pivot 版(**不動骨架結構**,只疊補償 translate);回傳被轉 bone 名。
   - `bone_origins_from_skel(skel)` —— 從 bones 取每根 setup 原點 O(非 rig 下即件中心)。
   - 過渡期透過 make_beat 的 `_wire_repo_tools()` import repo `pivot_rotation` / `spine_anim`(E1 bundle)。
2. **`skills/spine-ai-editor/assets/gen_lib/make_beat.py`** 新增 `generate_idle(parts)` + `IDLE_DEMO_PARTS`
   (**role 用英文** body/head/limb/特效;idle Loop 依 role → limb 走 **rotate** 通道,是繞關節 pivot 的典型來源)。
   `generate_bigwin` / `DEMO_PARTS` / `SUPPORTED_BEATS` **完全不動**(B2 閘逐 AC 續 PASS 證零回歸)。
3. **`references/structural_expansion.md`** 新增 **SOP E**(keyframe 級繞關節,不動骨架):數學推導、密網格重取樣雷點、
   用法、SOP A(動骨架)vs SOP E(動 keyframe)選用表。
4. **`tools/analyzer/validate_b3_pivot.py`**(B3 閘,5 AC;經**公開入口**作用在 gen_lib 動畫 + 真實 Award 幾何 + subprocess validator_v1)。
5. `check_readiness.py` 新增 cap `b3_pivot`(L2,pipeline,併入 `spine-anim-forge`,仍 HOLD)。

## 驗收(自我量化,不靠肉眼)

`python3 tools/analyzer/validate_b3_pivot.py` → **overall_pass,5 AC 全 PASS**(括號內為 repo 7 AC 對映):

- **B3-1 entry+double-truth(G2)**:`apply_joint_pivots` 可呼叫;作用在 gen_lib idle beat(limb rotate → 繞肩)後,
  被轉 bone **恰為** `[b_arm_L, b_arm_R]`(給了 pivot 的 limb),轉後 skel 過 `validator_v1` **0 error**(含末鍵 curve 檢查)。**新增雙真值**。
- **B3-2 fixed-point(repo AC1)**:經入口對真實 Award 左手→肩 pivot(|O−P|=117.4px)補償 → pivot 附著點殘差 **0.0115px** < 0.5。
- **B3-3 negctrl+rigid+moves(repo AC2/AC3/AC5)**:不補償(繞件中心)位移 **48.83px**(ratio **4247×**);件最遠點動 **94.33px**;
  所有件點到 P 距離逐幀偏差 **0.0115px** < 0.5(剛性/等距)。
- **B3-4 identity+loop(repo AC4 + 雙真值)**:θ=0 幀 Δ=0(0.00e+00)→ 無縫;轉後 idle 首尾相等 → `validator_v1` loop 閉合 **0 問題**。
- **B3-5 scale-pivot+curve+guard**:(a) 對 **B2 pop beat** 的 scale bone(b_body)用 include_scale=True → 件繞 pivot 縮放
  (ℓ_P 殘差 **0.0004px** + 非 pivot 點動 **11.2px**)→ **把 B3 接回 B2**;(b) bezier 緩動 rotate 仍 fixed-point **0.0596px**(repo AC7);
  (c) 守衛:pivot≈件原點(<0.5px)/ 未知 bone → 跳過不加多餘 translate。

回歸:`check_readiness` 新增 cap `b3_pivot` GREEN;B2/B1 閘續 PASS;block 驗決不變(`spine-anim-forge` 等仍 HOLD)。

## 關鍵發現

1. **密網格重取樣把補償輸出成純線性鍵 → 地雷 #12 天生不觸發**:繞 pivot 的 Δ 對 θ 非線性,須加密重取樣;
   輸出全是 `{time,angle}`/`{time,x,y}` 線性鍵(無 compact bezier)→ editor 匯入本就安全(收尾仍過 G1 保險)。
   呼應 B1/B2「G1 真正風險在序列 compose/crossfade」——單件 keyframe 補償同樣乾淨。
2. **結構軸有兩條互補解法**:SOP A/B **動骨架**(加 bone 到關節,長期/反覆用最乾淨)vs SOP E **動 keyframe**
   (Δ=(M−I)(O−P),不動骨架、可 diff/回滾、快速試 pivot 候選)。2.0 兩者都備,依情境選。
3. **scale-about-pivot 把 B3 接回 B2**:同一入口 `include_scale=True` 可直接作用在大獎 pop beat 的 scale 通道 →
   手臂從肩伸長(不是自身中心脹縮)→ 結構軸不只服務 idle,也服務大獎 beat。
4. **一條公開入口涵蓋 rotate / scale / shear 繞 pivot**:`include_scale`/`include_shear` 開關對應剛體→相似→一般仿射三層,
   不動點性質對**任意 M** 成立(純代數)。

## honest boundary

- Cocos / viewer 實機載入 = 使用者端(排程 scope 邊界);本閘用 spine-webgl 無頭等價(validator_v1)+ 幾何量化替代。
- **關節 pivot 放哪(肩/頸/肘)屬 S5 rig / 美術決策(A 類岔路)**:`tools/rig/infer_pivots`(父子件接觸縫)給草案,
  軸向精修留美術。本閘用接觸縫真值(左手→肩)+ 合成 pivot 驗機制,非窮舉關節。
- 過渡期相依 repo `tools/analyzer`(E1 self-contained bundle 後純使用者端才 standalone)。單一真值資產(Award / DEMO)。

## 下一步

Phase **B4**(序列 compose/crossfade/loop,C1):接 v1.3.0 的 idle-loop 與多 beat 大獎序列。
**這裡才是 G1 的真正戰場**(B1 洞見:序列自接點的 outgoing curve 可能變某 timeline 末鍵 → 地雷 #12)。
AC=相異 beat 接點 C1 連續閘通過、首尾可接 Loop、stiffness 不升。見 `MERGE_PLAN_2.0.md` Phase B4。
