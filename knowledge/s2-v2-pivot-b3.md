# 2.0 (B3) — 結構軸:繞關節 pivot 變換 gen_lib 入口(`apply_pivot_rotation`)+ G2

> 排程主線 = **產出 spine-ai-editor 2.0**(2026-10-12 使用者拍板)。路線圖 `skills/spine-ai-editor/MERGE_PLAN_2.0.md`。
> 本篇 = **Phase B3**(承 B2)。入口:`skills/spine-ai-editor/assets/gen_lib/make_beat.py :: apply_pivot_rotation`;
> 閘:`tools/analyzer/validate_b3_pivot.py`;文件:`references/structural_expansion.md` SOP E。

## 這個 chunk 在解什麼問題

`references/structural_expansion.md` 原本只有**結構解**(加 bone / reparent / transform mode)——動骨架本身。
但常見情況是「**可動軸已在對的件上、只是轉動中心不對**」:非 `--rig` 組裝時 bone 原點落件中心 O,故件的
`rotate`/`scale`/`shear` 會繞**件中心**動,而物理上手臂該繞**肩**、頭該繞**頸**。repo 半年前做過
`pivot_rotation`(candidate 0i→G-4)給了 **keyframe 級互補解**:bone 留件中心、疊一條補償 `translate`,
使淨效果=件繞關節 pivot P 轉/縮/剪,**完全不動骨架結構**。B3 把它併成 2.0 的**公開結構軸入口**,
並把 repo 既有 7 pivot AC 移植到「經 skill 入口」版 + 外加 **G2 雙真值**(MERGE_PLAN Phase B3)。

## 數學(確定性,無 ML)

設 bone setup 原點 O(parent 座標)、該幀 local 2×2 = `M = R(θ)·shear·diag(sx,sy)`(真實 Spine 3.8 TRS)。
要讓貼該 bone 的幾何做同一 `M`、而 pivot P 為**不動點**,只需加平移

```
Δ = (M − I)(O − P)
```

驗證:`ℓ_P = P − O`,套用後世界座標 `(O+Δ) + M·ℓ_P = O + (M−I)(O−P) + M(P−O) = P`(∀ M,純代數)。
`θ=0 且 scale=1、shear=0` 時 `M=I → Δ=0` → **setup/loop 端點/In-Out 介面保持 identity**(無縫不破)。
`Δ` 對 θ/s/shear **非線性** → 把通道**加密重取樣**成均勻密網格(`dt=1/60`)、各通道同格線性 → 幀間一致,
殘差 <<0.1px;既有 translate(如徑向歸位)被**疊加**,兩種位移語意共存。

## 做了什麼(純新增,無改任何既有生成/產線值)

1. **`gen_lib` 公開入口** `apply_pivot_rotation(skel, pivots, anim_names=None, bone_origin=None,
   include_scale=False, include_shear=False, dt=1/60, apply_g1=True)`(`make_beat.py`):
   - `pivots` 鍵可用**件名 / slot 名 / bone 名**(`_resolve_pivot_bones` 解析);值=關節 pivot(該 bone parent 座標)。
   - `bone_origin` 預設自 `skel["bones"]` 的 (x,y) 推(`_bone_origin_from_skel`;gen_lib skeleton 皆 root-parented)。
   - `include_scale`/`include_shear` 轉交 repo `pivot_rotation.apply_pivots`——讓繞 pivot 的變換也含
     scale(cascade pop 脈衝)/ shear(wobble/twist)。純 rotate 用預設(False,False)。
   - 輸出前過 **G1**(`strip_last_frame_curves`);就地修改並回傳 `(skel, {anim: [converted_bone,...]})`。
   - `__init__.py` 對外匯出。
2. **`references/structural_expansion.md` SOP E**(繞關節 pivot 變換,keyframe 級):數學、skill 入口用法、
   不變式 / honest boundary、與結構解互補的定位。
3. **閘** `validate_b3_pivot.py`(7 AC,透過**公開 API** 套 pivot、subprocess 跑真正的 validator_v1)。

## 7 AC(全 PASS;真值=真實 Award 機器人左手 arm_len 117.4px + `infer_pivots` 推得肩 pivot)

- **B3-1 entrypoint+fixed-point**:`apply_pivot_rotation`(公開 API)使肩 pivot P 的附著點成**不動點**,
  密網格幀間最大殘差 **0.0115px**(< 0.5)。
- **B3-2 neg-ctrl(繞件中心)**:**不補償**(繞件中心 O)時同一 P 位移 **48.83px**(ratio **4247** >> 20)→ 閘非恆真。
- **B3-3 part-moves**:離 P 最遠件點位移 **94.33px**(≥ 8)→ 沒把件凍住。
- **B3-4 identity-interface**:θ=0 幀 Δ=0(< 1e-6)→ setup/loop 端點保持 identity。
- **B3-5 rigidity(等距)**:純旋轉 pivot 下所有件點到 P 距離逐幀絕對偏差 **0.0115px**(< 0.5)→ 真繞 P 旋轉。
- **B3-6 end2end+G2**:`generate_bigwin` cascade beat → `apply_pivot_rotation(include_scale=True)` →
  (a) finite+時間嚴格遞增;(b) loop 端點相等(無縫);(c) 生成 beat 上 pivot 不動 **0.0007px**;
  (d) 內建負對照未套用 **27px**;(e) **`validator_v1` 0 error + loop 閉合**(editor 可匯入)。
- **B3-7 curve-tolerance**:rotate 帶緊湊 bezier 緩動時 B3-1 仍成立(殘差 **0.0596px**)→ 加密重取樣正確處理 curve。

## 關鍵發現

1. **pivot 補償與 scale/shear 正交、可共存**:補償只是一條**純平移疊加** + 密網格重取樣,不改原 rotate/scale/shear
   的值,故同一件可同時「繞 pivot」且「做 cascade/wobble/twist 的單件運動」;include_scale/include_shear 用真實
   Spine local `M=R·shear·S`,Δ 公式對**任意仿射 M** 皆成立(含非均勻 scale / shear)。
2. **套在生成 beat 上 editor 真值閘仍乾淨**:B3-6 證「生成大獎 beat → 套結構軸 pivot → validator_v1 乾淨」,
   結構軸 keyframe 解可機械化入 2.0 流程(非只手工 patch)。loop 閉合仍過,因端點 M=I → Δ=0。
3. **結構解與 keyframe 解互補、非互斥**:SOP A/B(動骨架)給**新自由度**(某部位本來沒可動軸);
   SOP E(本篇)修**既有自由度的轉動中心**(可動軸已在對的件上)。發現「某部位該動但沒辦法」用前者;
   發現「動是動了但轉動中心不對」用後者。
4. **pivot 補償對參數非線性 → 密網格是正確性前提**:只在原 keyframe 放 Δ、線性內插 ≠ 真值 → 幀間漂;
   dt=1/60 重取樣後殘差 <<0.1px(bezier 緩動 0.0596px 亦然)。

## honest boundary

- **座標系前提**:pivot P 與 bone 原點 O 必須同在「該 bone 的 parent 座標系」。gen_lib skeleton 皆 parent 到 root,
  故 P 用 root(≈世界)座標;bone 另有非 root parent 時須自備 `bone_origin` 與同系 P。
- **pivot 位置本身來自 S5 `infer_pivots`**(人形接觸縫自動推;人臂繞肩殘差 0.0115px 實測)。**非人形 pivot
  仍需人微調**(A 類岔路,S5 唯一卡死環節;本閘只驗「給定 pivot → 繞它轉的 keyframe 生成正確」,不驗 pivot 來源)。
- **過渡期相依 repo tools**:`apply_pivot_rotation` import repo `pivot_rotation`/`curve_tools`;純使用者端 standalone 須等 **E1** bundle。
- **Cocos / viewer 實機載入 + 視覺手感** = 使用者端(排程 scope 邊界);排程用 validator_v1 無頭等價替代。
- 單一真值資產(Award robot 左手)。

## 回歸

`check_readiness` 新增 cap `b3_pivot`(L2,role=pipeline,併入 `spine-anim-forge` 仍 HOLD);既有閘不受影響
(純新增檔 + gen_lib 純新增函式,未改 gen_animations/pivot_rotation/curve_tools/validator_v1 任何值)。
既有 `validate_pivot_rotation.py`(repo 原 7 AC)仍 PASS(B3 移植版與其量測一致、數值吻合)。
