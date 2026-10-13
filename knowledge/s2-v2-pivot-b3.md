# 2.0 (B3) — pivot_rig 結構軸:繞關節 pivot 變換 → 7AC 移植 + `validator_v1` 雙真值

> 排程主線 = **產出 spine-ai-editor 2.0**(2026-10-12 使用者拍板)。路線圖 `skills/spine-ai-editor/MERGE_PLAN_2.0.md`。
> 本篇 = **Phase B3**(承 B2 生成庫入口)。入口:`skills/spine-ai-editor/assets/gen_lib/pivot_rig.py`;閘:`tools/analyzer/validate_b3_pivot.py`。

## 這個 chunk 在解什麼問題

`gen_animations`(B2 的生成引擎)產的 `rotate`/`scale` 是「bone 繞**自身原點**動」。非 `--rig` 組裝時 bone 原點
落**件中心 O** → 手臂繞手臂中心轉、頭繞頭中心轉,**對肢體不物理**(手臂該繞肩、頭該繞頸)。
`references/structural_expansion.md` 的 SOP A/B 是**結構面**解法(加 bone / reparent 把 bone 搬到關節)。
B3 把 repo 的 `pivot_rotation.py` 包成**結構軸 skill 入口**,提供**互補的 keyframe 面**解法:
bone 留在件中心,額外疊一條補償 `translate`,使淨效果 = 件**繞關節 pivot P** 動,**完全不動骨架結構**。

## 數學(確定性、無 ML)

設 bone setup 原點 O(parent 座標)、該幀 local 2×2 仿射 **M**(=R·scale·shear,Spine TRS 序)。
要讓 pivot P 的附著局部點 ℓ_P=P−O 世界座標固定在 P,疊平移:

  **Δ = (M − I)(O − P)**

驗:world(ℓ_P) = (O+Δ) + M·(P−O) = O + (M−I)(O−P) + M(P−O) = O + (P−O) = P，∀M(純代數,M 不必是旋轉)。
- θ=0 且 scale=1、shear=0 時 M=I → Δ=0 → **setup / loop 端點 / In-Out 介面全保持 identity**(無縫不被破壞)。
- Δ 對角度/scale/shear **非線性** → 把通道**加密重取樣**成均勻密網格(dt=1/60),rotate/scale/shear/translate
  同格線性 → 幀間殘差 ~ (1/8)|O−P|·(dθ)² << 0.1px(閘實測 0.01px)。

## 做了什麼(純新增,無改任何既有生成/產線值)

1. **`assets/gen_lib/pivot_rig.py`**(結構軸 skill 入口):
   - 公開 API **`apply_joint_pivots(skel, pivot_of, dt, mode, anims, apply_g1)`**:讀 skeleton bones 的 setup 原點
     為 O,對指定 animations 的「有 pivot」bone 就地套補償,回傳 `{anim: [converted bones]}`。
   - helper `bone_origins(skel)`(讀 setup 原點)、`pivot_delta(deg,O,P)`(純旋轉 Δ 直算);CLI `--self-test`(合成肢體鏈)。
   - **三種補償 mode**(對外契約):`"rotate"`(0i,只補 rotate)/`"srt"`(G-3,M=R·diag(sx,sy),+scale)/
     `"affine"`(G-4,真實 Spine local 含 shear,+shear)。
   - `__init__.py` 加匯出 `apply_joint_pivots / bone_origins / pivot_delta`。
2. **G 護欄內建**:輸出前過 **G1**(`strip_last_frame_curves`,地雷 #12);補償本身產的密網格**無 curve 鍵**→
   天生 editor 乾淨,G1 仍 wired 以攔住既有通道末鍵 curve + 保持入口契約一致。**G3** 就地改傳入 dict(呼叫端自行決定 A/B)。
3. **過渡期相依**:`pivot_rig` 透過 `_wire_repo_tools()` import repo `tools/analyzer`(`pivot_rotation` / `spine_anim`)
   與 `assets/curve_tools`;**G5 的 self-contained bundle 留 Phase E1**。
4. **`references/structural_expansion.md` 新增 SOP E**(繞關節 pivot 變換 keyframe 補償:何時用、三 mode、流程、不變式、與 SOP A/B 對照)。
5. **閘** `tools/analyzer/validate_b3_pivot.py`(5 AC,透過**公開 API** 套補償、subprocess 跑真正的 validator_v1)。

## 5 AC(全 PASS,真值 = 真實 Award 左手 + `infer_pivots` 肩 pivot,|O−P|=117.4px)

- **B3-1 entrypoint+fixed-point**:經 `apply_joint_pivots` 公開 API,左手繞肩 pivot → 補償版 pivot 附著點殘差 **0.011px**(<0.5,移植 AC1)。
- **B3-2 negative-control**:**不補償**(繞件中心 O)→ pivot 位移 **48.8px**(>>補償版,≥10,移植 AC2)→ 閘非恆真。
- **B3-3 moves+rigid**:件最遠點位移 **94.3px**(≥8,移植 AC3)且所有件點到 P 距離逐幀偏差 **0.011px**(剛性/等距 <0.5,移植 AC5)。
- **B3-4 identity+curve**:θ=0 幀 Δ=0(移植 AC4,loop 端點無縫)且 bezier 緩動下殘差 **0.060px**(<0.5,移植 AC7,加密重取樣正確處理 curve)。
- **B3-5 end2end+double-truth**:經入口在**可載入** skeleton(Loop limb rotate,帶 slot/attachment 占位)套補償 →
  (a) 有限 + loop 端點無縫(移植 AC6 a,b);(b) 生成 loop pivot 殘差 **0.0003px**(<0.5,AC6 c);(c) 內建負對照未套用版位移 9.75px(AC6 d);
  (d) **`validator_v1` 0 error(editor 可匯入)+ loop 閉合 0 問題**(MERGE_PLAN §1 **G2** 雙真值);(e) **G1 wired**:apply_g1=False 生成後注入末鍵 curve →
  validator_v1 抓到 editor-crash(`b_身體.scale 最後一鍵帶 curve` AIOOBE)。

回歸:`check_readiness` 新增 cap `b3_pivot`(L2,pipeline,併入 `spine-anim-forge` 仍 HOLD);既有閘不受影響(純新增檔 + 純新增 pivot_rig 模組)。

## 決策 / 關鍵發現

- **結構軸有兩面:結構面(SOP A/B 加 bone/reparent)與 keyframe 面(SOP E 繞 pivot 補償)**。前者改骨架、適合永久性結構缺陷;
  後者不動骨架、適合「生成動畫後一次補好肢體物理」,可直接接 B2 生成的大獎 skeleton。B3 補的是後者,與既有 SOP A/B 互補不取代。
- **補償後輸出仍過 editor 雙真值(G2)是本 chunk 的增量**:不只證「繞 pivot 數學對」(repo 7AC 早已證),更證**透過 skill 入口套補償後、
  含新增密網格 translate 通道的 skeleton 仍能被 editor 匯入 + loop 閉合**——這是 2.0 對外契約(遊戲能播且編輯器能匯入)的要求。
- **補償的密網格重取樣天生 editor 乾淨**:rotate/translate 逐幀線性、無 curve 鍵 → G1 在補償通道上拔 0 條(呼應 B1/B2「單 beat G1 拔 0 條」);
  末鍵 curve 的真正風險仍在序列 compose/crossfade(B4)。
- **Δ 公式對任意仿射 M 成立**:`pivot_delta_affine` 的不動點是純代數,不需 M 是旋轉/相似 → mode=rotate/srt/affine 共用同一補償骨幹,
  差別只在每幀 M 怎麼組(R / R·scale / 真實 Spine local)。srt/affine 的 scale/shear 繞 pivot 由 repo 既有 G-3/G-4 閘覆蓋,B3 閘以 rotate 為主路徑驗入口。

## honest boundary

- **pivot 來自 `infer_pivots`(S5 接觸縫推斷,單真值資產 Award robot)**;「哪些件該繞哪個關節」在真實新資產上仍需 rig 真值或人微調(A 類 / 使用者資源,S5→L3 硬缺口)。
- 本 B3 閘主路徑驗 `mode="rotate"`;`srt`/`affine`(scale/shear 繞 pivot)的正確性靠 repo 既有 `validate_scale_pivot.py`/`validate_shear_pivot.py`(G-3/G-4)覆蓋,入口只是把它們包成對外 API。
- viewer / Cocos 實機載入 = 使用者端(排程 scope 邊界);本閘用 `validator_v1`(spine-webgl 無頭等價)替代。
- 過渡期相依 repo `tools/`(E1 self-contained bundle 後才純使用者端 standalone);單一真值資產。

## 下一步

Phase **B4**(序列 compose/crossfade/loop,C1 連續):接 v1.3.0 的 idle-loop 與多 beat 大獎序列。
**AC**:相異 beat 接點 C1 連續閘通過;首尾可接 Loop;stiffness 不升。**B4 是 G1 末鍵 curve 的真正戰場**
(前段尾幀 outgoing curve 可能變某 timeline 末鍵 → B1/B2/B3 單 beat 皆拔 0 條,B4 才會真的拔到)。見 MERGE_PLAN_2.0 Phase B4。
