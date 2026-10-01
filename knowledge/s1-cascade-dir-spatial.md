# S1 (J-5) cascade 跨件波方向由空間位置決定 — 第四條正交軸:相位來源(空間 vs 件序)

> candidate J-5 · 2026-10-01 run 002 · cap `cascade_dir_spatial` L2(併入 `spine-anim-forge`,仍 HOLD)
> 閘:`tools/analyzer/validate_cascade_dir.py`(5 AC 全 PASS)

## 補的 honest boundary

至 (J-4) 為止,cascade 跨件波的每件相位恆為**件序** `pi/(nvalid−1)`(第一件最先 pop、最後一件最後)。
這表示波的**方向**等於「作者把件寫進 storyboard parts 的**列表順序**」—— 一個任意/排版決定的順序,
**沒有物理意義**。本次把相位的**排序鍵**從件序換成**空間座標**,讓波的方向變成**幾何**:

| 方向 | 排序鍵(升序給 rank 0→最先 pop) | 體感 |
|---|---|---|
| `lr` | `bd.x`(最左件先) | 波由左掃到右 |
| `rl` | `−bd.x`(最右件先) | 波由右掃到左 |
| `co` | 距畫布中心 `hypot(x−cx,y−cy)`(最內件先) | 從中心向外爆開 |
| `oc` | `−`徑向距(最外件先) | 從外向中心收攏 |

相位值仍 `rank/(nvalid−1) ∈ [0,1]`,只是 rank 的**排序鍵**改變;
**波形(SPAN / nrip / 深度)分毫不動** → 只重排「哪件何時 pop」。

跨件時序通道至此有**三條正交軸**:結構(nrip,J-3)× 幅度(span,J-4)× **方向 / 相位來源(J-5)**。

## crux:這不是新幅度/段數軸,是「同一道波的方向來源」從件序換成幾何(honest distinction)

J / J-3 / J-4 都在問「波**多深 / 幾道 / 多開**」(波的形狀與強度)。J-5 問的是完全正交的問題:
「波**朝哪個方向掃**」。機制上它既不重生成關鍵幀(不像 count / span 軸),也不做值增益(不像深度軸),
而是**只重排各件既有相位的指派**——同一組相位值 `{0, 1/(n−1), …, 1}` 被**排列**到不同的件上。

要證「真的由空間決定、不是換個名字的件序」,必須在 **件序 ≠ 空間序** 的真實資產上,證峰序**跟空間走、
不跟件序走**。robot fixture 恰好件序 `[光暈, 右手, 頭, 身體, 左手]`(x = 359, 320, 361, 394, 558)
**不是** x 排序(x 最小的右手排在件序第 2),故這是天然的鑑別資產:

- 件序相位(None / `po`):光暈(件序 index 0)最先 pop @ 0.192,右手次之 @ 0.354。
- `lr`(左→右):**右手**(x 最小,件序 index 1)最先 pop @ 0.192,光暈退到 @ 0.354 ——
  **件序相位下不可能發生**(index 1 不會比 index 0 早)。

閘的 **Z5(b)** 固化此鑑別:`lr` 下各件峰時刻的排序 == 件按 x 的排序 **且 ≠ 件序**。

> 註:`co`(中心外擴)在此 fixture 上**恰好**與件序重合(光暈徑向 5.6 ≈ 畫布中心,件序本就近似中心外擴),
> 故 `co` 在此非鑑別方向——它仍**空間正確**(峰時刻依徑向單調),只是巧合等於件序。鑑別用 `lr`/`rl`/`oc`。
> 這是本資產的 honest note:此 storyboard 的件序本就近似中心外擴排列,`co` 的「新意」在別的資產才顯現。

## 三軸正交如何量測(Z4,各軸互不干擾)

- **(a) dir ⟂ 深度**:同一件的 scale 峰 overshoot 在所有方向下**相同**(方向只時移峰,不動值)。
  **踩雷**:以 N=240 離散 argmax 量深度時,各方向把該件峰中心挪到不同絕對 τ → 離散幀落在距連續峰
  不同偏移 → 量到的 max 有 ~0.008 的**混疊** artifact(非真深度變化)。此混疊隨取樣 n **二次收斂**
  (n=240→0.0079、n=2400→0.00088、n=9600→0.00029),故以 **HIRES=9600** 取樣量深度,殘差 3e-4 << 容忍 1e-3。
- **(b) dir ⟂ nrip**:帶 `tier_cascade_ripples` 時,各件 pop 次數 == nrip 在所有方向下皆成立(方向不碰波掃道數)。
- **(c) dir ⟂ span**:帶 `tier_cascade_span` 時,各檔位跨件散佈(max−min 峰時刻)在所有方向下**恆相同** ==
  span。原因優雅:相位集合 `{0 … 1}` 在任一方向下只是被**排列**,其 min(=0→峰落 LEAD)與 max(=1→峰落
  LEAD+span)不變 → 散佈 = span,與方向**無關**。

## 關鍵發現

1. **波的方向本是一個隱含假設**:在 J-5 之前,「跨件波依件序掃」是寫死的——件序即波向。J-5 揭示這假設,
   把波向從「作者排版順序」解放成「可由幾何指定的物理方向」。這是**把隱含預設顯式化成一條可控軸**的例子。
2. **正交軸有三種機制**:深度 = post-hoc 值增益;幾道波 / 一道多開 = gen 當下重生成關鍵幀;
   **方向 = 既有相位的重新指派(排列)**——第三種機制,既非值增益也非重生成,最輕量(O(n log n) 排序)。
3. **離散取樣的混疊會假扮成「軸不正交」**:Z4(a) 一開始 FAIL,根因是 N=240 量深度的混疊(時移把峰挪到
   不同幀相位),非真的深度隨方向變。證法 = 加密取樣看殘差是否**二次收斂到 0**(收斂 → artifact;
   不收斂 → 真效應)。這是量化閘的一般教訓:**量「不變量」時先確認量測本身對無關變數(此處相位時移)不敏感**。

## honest boundary(仍在)

- 方向選擇(slot_bigwin → `co`)是 **PROPOSAL**(手感 A 類);`build_spine` 預設 `cascade_dir=None`(件序,
  byte-identical),方向為 **opt-in**(`--cascade-dir` 或 `cascade_dir_for` 被顯式查用)→ 對既有 golden 零回歸。
- `co` 在本 fixture 與件序重合(見上註);真正展現 `co` 新意需件序 ≠ 徑向序的資產。
- 單一真值資產(robot)。`spine-anim-forge` 仍 HOLD(運動基元先驗、單一真值,防固化)。

## 產出

- `tools/analyzer/gen_animations.py`:`_cascade_phase_of()`(依方向空間鍵給 rank)+ `_build_beat(cascade_dir=)` +
  `build_animations(cascade_dir=)`;`_CASCADE_DIRS` 白名單,未知方向拋 `ValueError`。
- `tools/analyzer/tier_variants.py`:`TIER_CASCADE_DIR` + `cascade_dir_for(genre)`(slot_bigwin→co,opt-in 建議)。
- `tools/analyzer/build_spine.py`:`--cascade-dir {lr,rl,co,oc,auto}`(auto → 查 genre 建議)。
- `tools/analyzer/validate_cascade_dir.py`(新,5 AC)+ `tools/check_readiness.py` 新增 cap `cascade_dir_spatial`。
