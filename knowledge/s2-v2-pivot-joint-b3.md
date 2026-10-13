# 2.0 (B3) 繞關節 pivot 變換入口:pivot_about_joint(零結構改動)→ 幾何不動點 + validator_v1 雙真值

> MERGE_PLAN_2.0 Phase **B3**(承 B1/B2)。2026-10-13 run 004。
> cap `b3_pivot_joint` L2 併入 `spine-anim-forge`(仍 HOLD)。

## 這個 chunk 解決什麼

repo 有一支紮實的確定性「繞任意點變換」模組 `tools/analyzer/pivot_rotation.py`:讓件繞**關節 pivot P**
轉/縮放/仿射,而非繞**件中心 O**(非 rig 下 bone 原點落件中心 → limb 的 `rotate` 會讓手臂繞自身中心轉,
不物理)。核心式 `Δ=(M−I)(O−P)`(M = bone local 2×2 = R·scale·shear),把 Δ 當補償 translate 疊上去 →
pivot P 成**不動點**(對任意 M 成立)。repo `validate_pivot_rotation.py` 已對這套數學證了 **7 AC**
(真實 Award 肩 pivot 殘差 < 0.5px、剛性、bezier 容忍、端到端)。

但這能力**還沒成為 2.0 skill 的對外介面**,也**沒驗過「併進結構軸後會不會破壞 editor 匯入」**。B3 補這兩層:

1. **包成 skill 公開 API**:`skills/spine-ai-editor/assets/gen_lib/pivot_about_joint.py :: pivot_about_joint(anim, bone_origin, pivot_of, mode)`
   —— 成為 `references/structural_expansion.md` 的 **SOP E:繞關節 pivot 的 keyframe 級解法(零結構改動)**,
   與 SOP A–D 的「移 bone(結構改動,Cocos 須完整重 import)」**互補**。mode = `rotate`(0i)/`scale`(R·S)/`affine`(含 shear)。
2. **editor 雙真值(G2)**:pivot 補償會**新增一條 dense translate 通道**(Δ 對 θ 非線性 → 須密網格重取樣,
   `dt=1/60` 下 31 鍵)。B3 機械化證明補償後的動畫**仍過 v1.3.0 `validator_v1`**(editor 可匯入、loop 閉合)——
   這正是 repo 7AC **沒驗**的那層,也是「把 pivot 併進結構軸」的真正風險面(同 B1/B2 的 G2 雙真值紀律)。

## 做了什麼(純新增 + 文件,無改任何生成/產線值)

- **`skills/spine-ai-editor/assets/gen_lib/pivot_about_joint.py`**(新):`pivot_about_joint()` 薄包 repo
  `pr.apply_pivots`(mode→include_scale/include_shear 對映)+ 輸出過 **G1**(`strip_last_frame_curves`;
  補償通道本為線性鍵,通常拔 0 條,但保留這一關使入口與 B1/B2 的 G 護欄一致)。附 `demo_limb_loop`(合成肩/臂,
  無需真實資產)+ CLI `--self-test`。過渡期 import repo tools(E1 bundle),同 make_beat。
- **`gen_lib/__init__.py`**:export `pivot_about_joint` / `demo_limb_loop` / `SUPPORTED_MODES`。
- **`references/structural_expansion.md`**:新增 **SOP E**(數學、密網格重取樣、移 bone vs 補償的取捨表、API 用法、5AC 摘要、
  Cocos 差異=不需完整重 import)。
- **`tools/analyzer/validate_b3_pivot.py`**(新,5 AC)+ cap `b3_pivot_joint` 併入 `check_readiness`。

## 驗收(`validate_b3_pivot.py`,**5 AC 全 PASS**,truth=real-Award)

- **B3-1 entrypoint**:公開 API 把 demo limb Loop 就地轉繞 pivot 版 → converts `b_arm_L`;通道有限、時間嚴格遞增、
  加密(3→31 鍵)、translate 與 rotate 同長。
- **B3-2 pivot-fixed(核心,移植 repo AC1 到 skill 路徑)**:真實 Award 左手繞肩 pivot,補償後不動點殘差
  **0.0115px**(< 0.5)。
- **B3-3 neg-control**:不補償(繞件中心)漂 **48.83px**(比值 **4247×**);補償版件最遠點仍動 **94.33px**(非凍住)→ 閘非恆真。
- **B3-4 identity/loop seamless**:θ=0 Δ=0;Loop 首尾 rotate/translate 端點相等 → 繞 pivot 補償**保持無縫 Loop 介面**
  (B1/B2 的 loop 閉合性質不被破壞)。
- **B3-5 editor double-truth**:補償後完整 skeleton 過 `validator_v1` **0 error**(editor 可匯入)+ loop 閉合 0;
  **負對照**補償後注入末鍵 curve → validator_v1 抓到 AIOOBE editor-crash;入口 G1 wired(預設輸出乾淨)。

## 關鍵發現

1. **pivot 補償的真正風險面是 editor 相容性,不是幾何**:幾何(不動點/剛性)repo 7AC 早證。B3 的增量價值在證明
   「補償新增的 dense translate 通道」不會引入末鍵 curve 或破壞 loop 閉合 → **過 G2 雙真值**。這是把任何 repo
   能力「併進 skill」的通用檢查點(同 B1/B2)。
2. **結構軸有兩條互補解**:移 bone(結構,SOP A–D,Cocos 須重 import)vs 繞 pivot 補償(keyframe,SOP E,零結構、
   可 diff/回滾)。文件化這個取捨,讓使用者按「是否要進美術主檔 / 是否能接受重 import」選路。
3. **密網格重取樣是正確性前提**:Δ 對 θ 非線性,只在原 keyframe 放 Δ 會幀間漏 pivot;加密成均勻線性網格後
   幀間殘差 ~ `(1/8)|O−P|·dθ²` << 0.1px。這也順帶讓輸出**天然無末鍵 curve**(全線性鍵)。

## honest boundary

- 底層繞 pivot 的完整 7 AC(剛性/bezier 容忍/多模式 scale+shear)見 `validate_pivot_rotation` /
  `validate_scale_pivot` / `validate_shear_pivot`;B3 專注 skill 入口 + editor 雙真值,B3-2 只取 rotate 模式做代表。
- **pivot 放哪(關節定位)仍屬 S5 / 美術(A 類)**:`infer_pivots` 提供接觸縫 pivot,但軸向精修是手感。
- Cocos 實機 round-trip / 視覺確認 = 使用者端(排程 scope 邊界,用 validator_v1 無頭等價替代)。
- 過渡期相依 repo `tools/`(E1 self-contained bundle);cap L2、區塊仍 HOLD。

## 下一步

MERGE_PLAN Phase **B4**(序列 compose/crossfade/loop,C1 連續):接 v1.3.0 idle-loop 與多 beat 大獎序列。
⚠️ B1 已釘住:**地雷 #12 末鍵 curve 的真正戰場在 B4/D1(序列接點),不在單 beat** → B4 的 G1 驗收是重點。
