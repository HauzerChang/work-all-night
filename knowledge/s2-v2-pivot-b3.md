# 2.0 (B3) — 繞關節 pivot 變換:gen_lib 結構軸入口 `pivot_about_joint` → 幾何真值 + v1.3.0 `validator_v1`

> 排程主線 = **產出 spine-ai-editor 2.0**(2026-10-12 使用者拍板)。路線圖 `skills/spine-ai-editor/MERGE_PLAN_2.0.md`。
> 本篇 = **Phase B3**(承 B1/B2)。入口:`skills/spine-ai-editor/assets/gen_lib/pivot_about_joint.py`;閘:`tools/analyzer/validate_b3_pivot.py`。

## 這個 chunk 在解什麼問題

B1/B2 把「大獎節拍生成」接進 v1.3.0 的編輯器真值閘。但生成出來的 limb `rotate`/`scale`/`shear` 在**非 rig** 組裝下
bone 落在**件中心 O**,於是手臂繞「自己中心」轉/脹縮,對肢體不物理(手臂該繞肩、頭該繞頸)。repo 的**結構性解法**
(`build_spine --rig`)是把 bone 搬到關節(動骨架);B3 把 repo 的**互補 keyframe 級解法** `pivot_rotation.py` 抽成
一條 **skill 結構軸入口**——bone 留件中心、額外加補償 `translate`,使淨效果=件繞**關節 pivot P**,而**骨架結構一位元都不動**。

這屬「**結構軸**」:與 `references/structural_expansion.md` 的加骨/reparent(SOP A–D)並列,同樣是「讓視覺元件取得正確可動軸」,
只是用 keyframe 補償而非改骨樹(新增 **SOP E**)。

## 數學(確定性,無 ML)

設 bone setup 原點 O、local 線性部 `M = R(θ)·shear·diag(sx,sy)`(真實 Spine TRS)。要讓貼在該 bone 的幾何繞 pivot P 變換:

```
Δ = (M − I)(O − P)
```

不動點:`(O+Δ) + M·(P−O) = O + (M−I)(O−P) + M(P−O) = P`,對**任意** M 成立。`M=I`(θ=0,s=1,shear=0)→ Δ=0 → setup/loop 端點 identity 保持。
Δ 對 θ/s 非線性 → 通道**加密重取樣**(dt=1/60)使幀間殘差 << 0.1px。

## 做了什麼(純新增,無改任何既有生成/產線值)

1. **`assets/gen_lib/pivot_about_joint.py`**(skill 結構軸入口):
   - 公開 API `apply_pivot_about_joint(skel, pivot_of, include_scale=, include_shear=)`(整份 skeleton,bone_origin 由 bones (x,y) 推得,回傳 `{anim: [converted bones]}`)
     + `apply_pivot_about_joint_anim(anim, bone_origin, pivot_of, ...)`(單支 anim)+ CLI `--self-test`。
   - 委派 repo `pivot_rotation.apply_pivots`(rotate / `include_scale`=M=R·S / `include_shear`=一般仿射含 shear)。
2. **G 護欄內建**:輸出前跑 **G1**(`strip_last_frame_curves`;本軸皆密網格線性鍵→通常拔 0 條,但統一保險);**G3** 就地改傳入 anim,呼叫端存 A/B。
3. **過渡期相依**(MERGE_PLAN 明列):`_wire_repo_tools()` shim import repo `tools/analyzer`(`pivot_rotation`/`spine_anim`)+ `assets/curve_tools`;**G5 self-contained bundle 留 E1**。
4. **SOP E** 寫進 `references/structural_expansion.md`(何時用 keyframe 繞關節 pivot vs 搬骨、數學、用法、不變式、驗收)。
5. **閘** `validate_b3_pivot.py`(5 AC,透過**公開 API** 套用、真實 Award 幾何真值 + subprocess 跑真正的 validator_v1)。

## 5 AC(全 PASS,真值=真實 Award 左手世界幾何 42 verts + `infer_pivots` 推得肩 pivot |O−P|=117px)

- **B3-1 entrypoint+schema**:`apply_pivot_about_joint` 為公開 callable;對 B2 `generate_bigwin` 產的 cascade beat(include_scale)套關節軸 → 轉 5 bone 且 schema 合法(validator_v1 v0 0 error;非臨時腳本)。
- **B3-2 pivot-fixed(crux)**:經 skill 入口套 24° 擺動 → pivot 附著點殘差 **0.0115px**(AC1)+ 剛性等距 **0.0115px**(AC5)+ 件最遠點位移 **94.33px**(AC3,沒凍住)。
- **B3-3 negctrl+identity**:**不補償**(繞件中心 O)pivot 位移 **48.83px**(AC2),比值 **4247×**(閘非恆真)+ θ=0 幀 Δ=0(AC4 identity 介面)。
- **B3-4 editor-import(G2,B 階段固有維度)**:套用後輸出**仍過編輯器真值閘**——cascade(include_scale,M=R·S)`validator_v1` **0 error** + loop 閉合 0、wobble(include_shear,一般仿射含 shear)**0 error**、bezier 緩動擺動殘差 **0.0596px**(AC7)。
- **B3-5 end2end+non-vacuous**:(a)真實 `build_animations` Loop → skill 入口 → finite/無縫/pivot 不動 **0.0003px** + 內建負對照未套用會動 **9.75px**(AC6);(b)對套用後 beat 注入末鍵 curve → validator_v1 抓到地雷 #12 AIOOBE,預設 apply_g1=True 輸出乾淨 → 證編輯器閘在本軸非恆真。

## 關鍵發現

1. **repo 7AC 只驗 runtime 幾何不動點;B3 把它移植到 skill 入口並加上編輯器雙真值閘(G2)**——這是 B 階段相對 repo 原閘的真升級:繞關節 pivot 的密網格 translate/scale/shear 輸出**仍 editor 可匯入**。
2. **R·S(scale-about-pivot)與含 shear 的一般仿射皆 editor 乾淨**:pivot 補償不會引入末鍵 curve(全密網格線性鍵),故 `M=R·S` 與 `M=R·shear·S` 兩種 beat 都過 validator_v1 0 error——證繞關節軸與 B1/B2 的 editor 相容性一致。
3. **「結構軸」可用 keyframe 達成而不動骨樹**:SOP E 與 SOP A(搬骨)是同一需求(正確可動軸)的兩條互補路徑;keyframe 路徑可 diff/回滾、只影響指定動畫,適合不想動結構的場景。
4. **延續 B1 的 G1 洞見**:單 beat 層級本就無末鍵 curve;本軸的密網格重取樣也不引入,G1 在此通常拔 0 條(統一保險而非必要)。

## honest boundary

- **繞 pivot 是否貼手感的美術微調留使用者**(A 類):閘只驗客觀幾何不動點與 editor 可匯入性。
- **單一 rig 真值**(Award 左手+推得肩 pivot);pivot P 本身是 S5 接觸縫**草案**(其準度另由 `validate_pivots` 把關)。
- **過渡期相依 repo tools**:`pivot_about_joint` 目前 import repo `tools/analyzer`;純使用者端 standalone 須等 **E1** bundle。
- **viewer/Cocos 實機載入 = 使用者端**(排程 scope 邊界,用 validator_v1 無頭等價)。

## 回歸

`check_readiness` 新增 cap `b3_pivot`(L2,role=pipeline,併入 `spine-anim-forge` 仍 HOLD);**0 RED**。
純新增檔(skill 入口 + 閘 + SOP E + cap),未改 `pivot_rotation.py`/`gen_animations`/`curve_tools`/`validator_v1` 任何值;
既有 `validate_pivot_rotation.py` 7AC 仍逐 AC PASS(本閘與之共用真值、同尺度門檻)。
