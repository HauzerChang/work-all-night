# S1 大獎序列 → 可載入資產 round-trip — candidate (M)

> 2026-10-05 run 003。補「X 就緒 ≠ 產線成立」在**序列化層**的缺口:candidate (L) 的
> `compose_sequence` docstring 一路宣稱其輸出「可直接塞進 `skeleton["animations"][序列名]`、是一段
> 可**載入/播放**的大獎序列」—— 但在此之前**沒有任何產線路徑**把它寫進真實 `skeleton.json`,也**沒有
> 任何閘**驗過「序列化(json.dump round 到產檔精度)→ 重新載入 後,這支**單一**合成 timeline 仍是
> **結構合法、可被 Spine 3.8 載入、且逐幀還原**的 animation」。`validate_build` 只驗 setup pose 的
> **靜態**幾何/atlas 編碼,**從不碰 animation**。本次把這條 boundary 關掉,並把 compose 從
> 「in-memory 量測對象」推成「真實可載入資產」。直指 north star「產出可載入 Spine 的大獎序列動畫」。

## 補的缺口

- candidate (L) 把跨 beat 串接(`compose_sequence`)顯式做出來,(L-2) 補 shear 通道覆蓋、(L-3) 補
  Loop 重播 N 次 + C0-loopability、(L-4) 補自接點 C1 連續 —— 但**全部**在 **in-memory** 的 clip dict
  上量測(`sample()` / `_state_max_diff` / 速度 gap),**從未**把合成序列**序列化成檔**再**重載**檢驗。
- `compose_sequence` docstring:「composed = ... 可直接塞進 skeleton["animations"][序列名]」。這是**宣稱**,
  不是已驗事實。真實產線 `build_spine` 只把**各獨立 beat**(`build_animations` 產物)寫進 `skeleton.json`,
  **從未**寫過合成序列。`grep compose_sequence tools/analyzer/` → 只出現在 **validators**,無產線引用。

## 選題理由(延續 L / L-2 / L-3 / L-4,刻意不加參數軸)

近期連續整合 / 組合閘。M 的客觀新不變量 = **序列化 round-trip 保真 + Spine 3.8 結構合法性**,是把
compose 從量測對象推成**可載入資產**的最後一哩;同時補上**產線路徑**(emit + `build_spine --sequence`),
讓大獎序列真的成為 `skeleton.json` 裡一支具名 animation。

## 做了什麼(全 additive)

1. **`gen_animations.forward_sequence_order(anims)`** → list:由 anims 中**存在**的 beat 組出正向播放順序
   PROPOSAL `["In", <主秀節拍 hit/combo/charge/cascade 依序>, "Loop", "Out"]`(只納入實際存在者;不納
   `{beat}__{tier}` 檔位變體)。純函式。
2. **`gen_animations.emit_sequence_animation(skeleton, anims, order, name="BigWin", gap, merge_tol)`** →
   segments:呼叫 `compose_sequence` 後把合成序列**就地加進** `skeleton["animations"][name]`(additive);
   **拒絕覆蓋**既有同名 animation(`ValueError`,避免清掉某 beat)。order=None → `forward_sequence_order`。
3. **`build_spine --sequence`**(`build(sequence=True|order_list)`):`--animate` 時把各 beat 組成單一
   `"BigWin"` 序列 animation,與各獨立 beat **並存**寫進 `skeleton.json`;summary 回報 `sequence` 段落結構。
   不給 `--sequence` → 逐位元同舊行為(emission 以 `if sequence is not None` 全守住)。
4. **新閘 `validate_sequence_build.py`(M,5 AC)**:從**先驗庫 → 真實 build_spine robot 骨架 →
   build_animations → emit → json.dump(與 build_spine 同參數)→ 重載**端到端。

## 5 AC(全 PASS)

- **M1 present + emission additive**:`emit_sequence_animation` 就地加入 "BigWin";與各獨立 beat **並存**
  且各既有 beat **逐位元不變**(emission 純 additive);BigWin 非空、用到的 bone 皆在 skeleton;segments
  覆蓋 order;總時長 == 末段 start+dur(6.4s)。
- **M2 crux — round-trip fidelity(max diff == 0)**:整份 skeleton 以 build_spine 同參數
  (`ensure_ascii=False, indent=1`)`json.dump` → 重載;重載的 "BigWin" 在 [0,dur] 密集取樣(400 點)+
  各段邊界取樣,與 in-memory 合成 `sample()` **max diff == 0.0**(嚴格相等,非 <tol)→ 證 Python json 以
  repr 寫浮點對合成 timeline **逐位元無損**(可載入資產逐幀 == 設計)。
- **M3 crux — Spine 3.8 結構合法**:重載的 "BigWin" 每條 (bone/slot, channel) timeline **時間嚴格遞增**
  (Spine `SkeletonJson` 的硬性要求;合成/去重 + `_shift_frames` 的 6 位 round 第一次在**序列化形態**被
  檢驗,**0 non-strict 通道**)、全部 time/value finite、**28 個緊湊 bezier 散鍵** `{"curve":..,c2,c3,c4}`
  存活 + **52 個 color 8-hex** 存活(非空驗:序列真帶緩動與 alpha timeline)。
- **M4 faithful concat(reloaded)**:從**重載的** "BigWin" 逐段回切(時間減 offset),每段逐幀還原**孤立
  beat** 的 `sample()`(殘差全 **0.0** ≤ 1e-4)→ 證序列化 + compose 平移/去重對各段**無損**;每內部接點
  **C0 在 clip 端點層量**(前 beat sample(dur) vs 後 beat sample(0),殘差全 ≤ 1e-3);重載 duration ==
  in-mem == 末段。
- **M5 neg-control + guards**:(a) **crux** 把重載序列某通道注入非嚴格遞增幀(等時間 / 遞減)→ 結構檢查器
  `_nonstrict_channels` 回報 non-strict(證 M3 **非空驗**、真能擋下 Spine 載不進的 timeline);對照合法序列
  0 non-strict。(b) emit 覆蓋既有 beat 名("Loop")→ `ValueError`;order 含未知 beat → `KeyError`。
  (c) 擾動重載序列某一值 +5 → round-trip max diff = 5.0 > 0(證 M2 的 0 是有意義的、比較器有鑑別力)。

## 迭代踩雷(預算內自修)

- **初版 M4 內部接點 C0 從 composed 時間軸以 `sample(bt−ε)` vs `sample(bt+ε)` 量 → 假 FAIL**(殘差
  0.004–0.019):這正是 candidate **L / L-4 已記載兩次**的量測 artifact —— ① `compose_sequence` 的接點
  **去重**把前後幀抹成**單一幀**,composed 取樣在接點恆連續;② 若硬取 bt±ε 兩側,捕捉的是接點附近**真實
  非零速度** × ε(velocity×ε ≈ 0.01),**非不連續**。修法 = 回到 **clip 端點層**量(孤立 prev beat
  sample(dur) vs 孤立 next beat sample(0),同 L 的 L2 接點閘),非空驗(In 尾 identity vs hit 首
  identity → 0;burst 首 collapsed ≠ identity 會非 0,見 L5),並經 M4 concat 已證重載逐段 == 孤立 beat
  而綁回重載資產。**同一個「量在哪一層」教訓第三次出現 → 寫死在閘註解裡避免第四次重犯。**
- **初版 gate run() 未把 anims 裝進 `skel["animations"]` 就查 M1 的 additive → KeyError**:真實產線
  `build_spine` 是 `skeleton["animations"] = build_animations(...)` **再** emit;gate 須鏡像此序(先裝各
  beat、再 emit 序列),兩者才並存於同一 skeleton。

## 關鍵發現

1. **「docstring 宣稱可載入」≠「真的序列化成可載入資產且逐幀還原」有 AC** —— 這是「X 就緒 ≠ 產線成立」
   通則在**序列化層**的實例(同 (E) 模板就緒≠產線會用、(0i) 幾何就緒≠生成器接上、(G-2) apply_pivots
   掃過≠主秀下真繞關節)。compose 在 in-memory 被量了四代(L~L-4),序列化/重載這一哩**從未**被驗。
2. **合成/去重的單一 timeline 的「嚴格遞增時間」要在序列化形態驗** —— `compose_sequence` 的接點去重
   (`merge_tol=1e-6`)+ `_shift_frames` 的 6 位 round 是否恆產出 Spine `SkeletonJson` 能載入
   (每通道嚴格遞增)的 timeline,只有**寫檔再重載**才算驗到;in-memory 的 `sample()` 不檢查這條硬約束。
   本 fixture 實測全通過(0 non-strict),M5a 證檢查器**真能抓**違規(非空驗)。
3. **round-trip 保真要證「嚴格相等(==0)」而非「<tol」** —— Python json 以 `repr()` 寫浮點是**可逐位元
   還原**的(shortest round-trip repr),故對不改值的純平移序列應**精確** 0;以 M5c 擾動對照證「0 不是因為
   比較器空轉」。這比「< 容忍值」更強、更誠實。

## honest boundary(仍在)

- **正向播放順序屬美術手感(A 類)**:identity-介面 beat 可自由排序(見 L5c),`forward_sequence_order`
  只給一個**確定性、可播放**的預設 PROPOSAL;預設**不納** burst(collapse 登場 → 放序列中段會製造
  identity→collapsed 不連續接點)與 shear 節拍 wobble/squash/twist(與 L 驗過的無 shear 正向序列一致,
  保持預設序列乾淨;要含 shear 請自訂 order 走 `compose_sequence`,已由 L-2 覆蓋)。
- 本閘驗「**可載入性 / round-trip 保真 / 結構合法**」,**不**驗「序列好不好看」(手感,A 類)。
- 「可載入」以**純 Python 的 spine_anim.sample 重載 + Spine 3.8 timeline 結構約束**為真值代理;**實機
  spine-webgl round-trip** 仍需瀏覽器自動化(CDN 被網路政策擋,見 STATE 未解項),為後續。
- 無改任何 beat 的生成 / 產線值(`compose_sequence` 純時間平移 + 去重;emit 純加鍵)。
- 單一真值資產(robot)。cap `sequence_build_roundtrip` L2 併入 `spine-anim-forge`(仍 HOLD)。

## 檔案

- `tools/analyzer/gen_animations.py` — 新增 `forward_sequence_order` + `emit_sequence_animation`(全 additive)。
- `tools/analyzer/build_spine.py` — `build(sequence=)` + `--sequence` CLI + summary 回報(opt-in,預設 byte-identical)。
- `tools/analyzer/validate_sequence_build.py` — M 閘(5 AC)。
- `tools/check_readiness.py` — 新增 cap `sequence_build_roundtrip`。
