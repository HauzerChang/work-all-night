# S1 (J-6) cascade 跨件波方向推廣成任意直線方向向量投影 — 對角/垂直(投影族),徑向仍另一族

> candidate J-6 · 2026-10-02 run 001 · cap `cascade_dir_vector` L2(併入 `spine-anim-forge`,仍 HOLD)
> 閘:`tools/analyzer/validate_cascade_dir_vector.py`(6 AC 全 PASS)

## 補的 honest boundary(J-5 的推廣)

(J-5) 把 cascade 波的**相位來源**從件序換成空間,但只給了 **4 個離散名鍵**:`lr`/`rl`(軸向)+ `co`/`oc`(徑向)。
換言之,波方向只能是「左右兩軸」或「中心徑向」—— **對角、垂直、任意斜角都到不了**。

本次把相位的**排序鍵**改由件中心沿**任意單位向量 `(ux, uy)` 的投影**決定:

```
k_i = (x_i − cx)·ux + (y_i − cy)·uy      # 件 i 沿方向 u 的投影;rank 升序 → 先 pop
```

波方向變成可沿**任一角度**(對角 45°、垂直 90°……)連續鋪開。相位值仍 `rank/(nvalid−1) ∈ [0,1]`,
**波形(SPAN / nrip / 深度)分毫不動** → 只重排「哪件何時 pop」(與 J-5 同機制=相位的重新指派/排列)。

跨件時序通道的**方向軸**至此由「4 個離散名鍵」推廣成「連續角度(投影族)」。

## crux:投影族只推廣「直線/軸向」方向;徑向(co/oc)仍是另一族(honest distinction)

這是 J-6 的核心誠實分野,**不是**「現在能到任何方向了」,而是**精確地**:

1. **`lr`/`rl` 是投影族的特例**(軸向投影)。`lr ≡ 投影到 (1,0)`、`rl ≡ 投影到 (−1,0)`。
   閘 **V1** 證 `cascade_dir=(1,0)` 的輸出與 `cascade_dir="lr"` **逐位元相同**、`(−1,0)` 與 `"rl"` 相同。
   (證法:投影鍵 `(x−cx)·1 = x−cx`,對 x 嚴格單調 → 與 `lr` 的 `k=x` 排序完全一致 → 峰時刻、anim 全同。)

2. **對角(45°)/ 垂直(90°)是 J-5 四名鍵到不了的新方向**。robot fixture 上 45° 對角的峰序
   `[身體, 光暈, 右手, 頭, 左手]`(投影鍵 ∝ x+y),與 `lr`/`rl`/`co`/`oc` **四者皆不同**、也 ≠ 件序。
   閘 **V3(a)** 固化:對角峰序與四名鍵峰序無一相撞、且 ≠ 件序 → 真的解鎖了新的波朝向。

3. **但 `co`/`oc`(徑向)不是任何單一投影**。徑向鍵是**距中心的距離** `hypot(x−cx, y−cy)`,
   是**非線性**的(等值線是圓,不是直線);投影鍵的等值線是**直線**。故徑向排序一般**不在**投影族裡。
   閘 **V3(b)** 直接證明:密格掃 360° 得 **20 個相異投影排序**,`co`、`oc`、件序**皆不在**其中,
   而對角**在**其中且 ≠ 兩軸向序。→ 誠實標出投影族的邊界:它涵蓋所有**直線**方向,但**不涵蓋徑向**。

> 一句話:J-6 把方向從「2 軸 + 2 徑向」的 4 個點,推廣成「所有直線方向」的連續族;
> 軸向(lr/rl)收進來成特例,徑向(co/oc)仍是另一條獨立的族 —— 不假裝「包了一切方向」。

## 三軸正交如何量測(V5,沿用 J-5 的量測機制)

方向(含對角)只重排相位指派,不碰波形,故與深度/span/nrip 三軸正交:

- **(a) dir ⟂ 深度**:同一件 scale 峰 overshoot 在所有向量方向下 == base。沿用 J-5 的 **HIRES=9600** 取樣
  消除「相位時移把峰中心挪到不同幀相位」造成的離散混疊(該混疊隨 n 二次收斂 → 非真深度變化)。
- **(b) dir ⟂ span**:帶 `tier_cascade_span` 時各檔位跨件散佈在所有向量方向下 == span
  (相位集合 `{0…1}` 只被排列 → min/max 不變 → 散佈 = span,與方向無關)。
- **(c) dir ⟂ nrip**:帶 `tier_cascade_ripples` 時各件 pop 次數 == nrip 在所有向量方向下成立。

## 負對照(V6,證閘有鑑別力)

- **(a) crux 反向**:角度 θ 的峰序 == θ+180° 峰序的**逆序**(反方向把同一道波倒過來掃)。對 0/45/90/135° 皆成立。
- **(b) 零向量守衛**:`cascade_dir=(0,0)` → `ValueError`(無方向可投影)。
- **(c) parse 守衛**:`parse_cascade_dir("zzz")`(亂字串)、`"v1"`(殘缺向量)→ `ValueError`;
  正常路徑 `"a0"` 解為軸向單位向量 `(1,0)`(≡ lr)。
- **(d) 方向只作用 cascade**:非 cascade 主秀 beat 在任一向量方向下逐位元同 base(不外洩)。

## 關鍵發現

1. **把「4 個離散選項」推廣成「連續參數族」時,誠實的工作是標清楚『族邊界』** —— 不是宣稱「現在什麼都能做」,
   而是精確說:投影族 = 所有**直線**方向(軸向是其特例),**不含**徑向。V3(b) 用「徑向序不在 360° 投影集合裡」
   把這條邊界變成**可機讀的否證**(不是嘴上說說)。
2. **特例要用逐位元等價去證,不是用「看起來像」**:V1 證 `(1,0)` 的輸出 byte-identical 於 `"lr"`,
   才算真的「lr 是投影特例」。這同時保證了零回歸(named 分支不動 + 向量分支對軸向重現 named)。
3. **線性(投影)vs 非線性(徑向)的可達性差異是幾何事實,不是實作選擇** —— 投影等值線是直線、徑向是圓,
   點集沿圓的排序一般不是任何直線掃出的排序。這解釋了為何 co/oc 無法被收進投影族(不是沒實作,是幾何上不同族)。

## honest boundary(仍在)

- 方向/角度選擇是 **PROPOSAL**(手感 A 類);`build_spine` 預設 `cascade_dir=None`(件序,byte-identical),
  向量/角度為 **opt-in**(`--cascade-dir a45` / `v1,1`)→ 對既有 golden 零回歸。
- 徑向(co/oc)刻意**不**併入投影族(幾何上不同族);若未來要「任意徑向中心」可另開一條,不混進方向向量軸。
- 單一真值資產(robot)。`spine-anim-forge` 仍 HOLD(運動基元先驗、單一真值,防固化)。

## 產出

- `tools/analyzer/gen_animations.py`:
  - `_dir_vector(cascade_dir)`:把 `(ux,uy)` 正規化成單位方向;named 字串/None → None;零向量 → `ValueError`。
  - `parse_cascade_dir(spec)`:CLI/字串 → build_animations 值。`"a<deg>"`/純數字 → 角度(度,自 +x 逆時針,
    Spine y-up)→ `(cos,sin)`;`"v<ux>,<uy>"` → 向量;named/auto 原樣;`""`/None → None;其餘 → `ValueError`。
  - `_cascade_phase_of`:多一條向量投影分支(`vec = _dir_vector(...)`);named 分支完全不動 → 零回歸。
- `tools/analyzer/build_spine.py`:`--cascade-dir` 去掉 `choices`,改經 `parse_cascade_dir`(named / `a<deg>` / `v<ux>,<uy>`)。
- `tools/analyzer/validate_cascade_dir_vector.py`(新,6 AC;複用 `validate_cascade_dir` 的 helper 保同源可信)。
- `tools/check_readiness.py`:新增 cap `cascade_dir_vector` L2(併入 `spine-anim-forge`,仍 HOLD)。回歸 **50 GREEN / 0 RED**。

## 端到端

```
python3 tools/analyzer/build_spine.py assets/robot_parts.psd --out specs/robot_spine \
    --genre slot_bigwin --animate --cascade-dir a45      # 45° 對角波
python3 tools/analyzer/build_spine.py assets/robot_parts.psd --out specs/robot_spine \
    --genre slot_bigwin --animate --cascade-dir v1,1     # 等價:方向向量 (1,1)
```
