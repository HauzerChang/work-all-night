# S1 跨 beat 混場(crossfade / overlap-mix)接點機制 — candidate (M)

> 2026-10-05 run 003。補 candidate (L-4) 誠實列出的 honest boundary:`compose_sequence`(L)用**純時間
> 平移 + 接點去重**串序列 —— 任一時刻輸出**恰等於某一支 clip**(平移後),**從不產生兩支 clip 的混合**。
> 本次新增**真正的 mix 機制** `crossfade_pair`:在**時間重疊窗**內同步取樣兩支 clip 做**凸組合**
> `out=(1-w)·A+w·B`,w 於窗內 0→1。這是**組合層的新軸**(非再加生成參數),全 additive。

## 補的缺口(L-4 / L-3 誠實列出的 honest boundary)

candidate (L) 的 `compose_sequence(anims, order)` 把 beat 的 keyframe **時間平移** `offset_i=Σ_{j<i}dur_j`
後**合併**,接點時間重合則**去重**(保留後者)。這是**無損拼接**——但**前提是接點值相等**(C0 無縫);
L-3 已發現:值**不**相等的接點會被時間去重**抹成陡坡**(composed 恆 C0,但那是 artifact)。所以 compose
的本質限制是:

> **compose 任一時刻的輸出 = 某一支 clip 的值(平移後);它無法讓兩支 clip『同時作用』。**

但真實大獎序列常需「前一拍還沒收完、後一拍已經起」:兩拍在一段**時間重疊窗**內**同時**以權重交叉淡入
淡出(這正是 Spine runtime 的 track mix / animation state 混場)。純平移 + 去重做不到,**需要真正的
mix 機制**。L-4 把這條列為「下一個組合層軸」。

## 選題理由(延續 L / L-2 / L-3 / L-4,刻意不加參數軸)

近期多為整合 / 組合閘而非再加生成軸。M 的客觀新能力 = **重疊窗凸組合**,compose 的接點閘涵蓋不到(且
compose **做不到**此機制,見 crux M3)。從**先驗庫 → 真實 build_spine robot 骨架 → build_animations**
端到端,與 L / L-3 / L-4 同一 fixture(hit × combo)。

## 做了什麼(全 additive)

1. **`gen_animations.crossfade_pair(clipA, clipB, window, dt=1/120, weight="smooth")`** → `(composed, info)`:
   把 A 的尾段 `window` 秒與 B 的首段 `window` 秒**時間重疊**,窗內 `out=(1-w)·A+w·B` 凸組合。
   - 時間軸:B 整體右移 `offsetB = durA − window`;總長 `total = durA + durB − window`。
   - 窗前 `[0, offsetB)` → 純 A(**原幀逐位元**,保留 bezier 緩動);窗後 `(durA, total]` → 純 B(原幀右移);
     重疊 `[offsetB, durA]` → dt 重取樣的線性橋接混合幀。
   - slot color 在本資產恆 `ffffffAA`(僅 alpha 動)→ 混合後 alpha 由 `_alpha_to_hex` 重建,忠實。
2. **`_crossfade_weight(u, mode)`**:`linear`=u;`smooth`=smoothstep `3u²−2u³`(端點 w'=0 → 進/出純段
   速度亦連續,C1 更順)。兩者 w(0)=0、w(1)=1、w(0.5)=0.5(混場深度鑑別與 mode 無關)。
3. **`crossfade_sequence(anims, order, window, dt, weight)`**:fold-left 兩兩 crossfade 折疊多拍(結果 clip
   本身仍是 clip,可再與下一支混場 → **機制深度無關**);回傳 `(composed, infos)`。
4. **新閘 `validate_sequence_crossfade.py`(M,5 AC)**:端到端同 fixture。

## 機制的客觀不變量(閘把關)

- **端點精確**:窗首 w=0 ⇒ 輸出==A(offsetB);窗尾 w=1 ⇒ 輸出==B(window)。銜接「A 當下在做什麼」→
  「B 當下在做什麼」。
- **單位分解(partition of unity)**:(1-w)+w≡1 ⇒ 窗內若 A==B 則輸出==A(兩拍一致時**不引入失真**)。
- **凸性 / 有界**:輸出恆為兩輸入的凸組合 ⇒ 每通道值落在 `[min(A,B), max(A,B)]`,**無 overshoot**。
- **混場深度**:窗內可達「兩支 clip 當下**都不在**」的中間態(≈0.5A+0.5B)——compose **永遠做不到**。
- **退化**:window→0 ⇒ **連續**退化回 compose 的 C0 拼接(concat = 零窗 crossfade)。

## 5 AC(全 PASS)

- **M1 present + structure**:`crossfade_pair(hit,combo,0.3)` 產單一可載入 clip;`total==durA+durB−W=1.1`、
  `overlap==[0.2,0.5]`、`all_finite`、bones 齊。
- **M2 crux — 端點精確 + 非空驗**:窗首 `cf(0.2)==hit(0.2)`、窗尾 `cf(0.5)==combo(0.3)`(bone 殘差
  **4e-7** < 1e-4;含 alpha 的 full diff < 0.01 的 8-bit 量化容忍);**中點** `cf==0.5·A+0.5·B`(bone
  殘差 4e-7 → 混場公式忠實烘進 keyframe);非空驗:中點 `|A−B|≈8.33 ≥ 1`(確實在混、非兩拍恰好重合)。
- **M3 crux — 混場深度 compose 做不到**:重疊窗格點上,crossfade 對「{A(t), B(t−offsetB)}」的最小距離
  (mix depth)**max = 4.20 ≥ 1**(達兩拍都不在的中間態);而 `compose_sequence([hit,combo])` 在**同一
  絕對時間**的 mix depth **= 0**(恆等於某一支 clip)→ 證本機制是 compose **做不到**的新組合層軸。
- **M4 faithful outside overlap**:窗外逐位元沿用原幀 → A 內部 knot(time<offsetB)`cf==A`、B 內部 knot
  (B-time>window,右移 offsetB)`cf==B`,殘差 **< 1e-6**(bone 與 full 皆是)→ 只動重疊窗。
- **M5 neg-control + 守衛**:
  - (a) **crux window→0 連續退化**:cf(W) vs `compose_sequence([hit,combo])` 的 sup-dist **線性於 W**
    (窗外純-B 段較 concat 右移恰 W → sup = 接點速度·W);W∈{0.04,0.02,0.01} 的 `sup/W = 212.96`
    **三者恆定**、sup 隨 W 遞減 → W→0 時 →0,concat = 零窗 crossfade。
  - (b) **partition-of-unity 守衛**:兩支**相同靜止 hold**(恆 P=20°)混場 → 窗內 `cf==P` 殘差 **0**。
    (若權重非和=1,例如相加,會得 2P=40°)→ 證真凸組合。
  - (c) **凸性守衛**:窗內逐 knot 每通道 `cf∈[min(A,B),max(A,B)]`,越界數 **0**。

## 關鍵發現

1. **compose(平移+去重)與 crossfade(重疊+凸組合)是兩種本質不同的接點**:compose 任一時刻輸出 = 某一
   支 clip 的值,**狀態空間只走兩支 clip 各自的軌跡**;crossfade 在重疊窗內走**兩軌跡的凸包內部**——能
   到達**兩支 clip 誰都不經過**的中間態(M3 以同一絕對時間的 mix depth 4.2 vs 0 把這條差異量化)。這是
   「為什麼 L-3 發現 compose 的去重會把不等值接點抹成陡坡」的正面解:要讓不等值接點**平順過渡**,不能靠
   平移去重,得靠**時間重疊 + 權重混合**。
2. **crossfade 是 concat 的連續推廣**:window→0 時逐點退化回 compose(M5a 的 sup/W 恆定 = 線性退化證據)。
   故兩者不是對立選項,而是**同一族接點的兩端**(零重疊 = C0 拼接;正重疊 = 混場)。
3. **凸組合的三條代數性質(端點精確 / partition-of-unity / 凸有界)一次把機制的正確性釘死**:端點精確證
   「接得上」、partition-of-unity 證「不失真」(A==B ⇒ 原樣)、凸有界證「不 overshoot」。這比只驗一條
   「看起來平滑」穩健得多——它們是**可被負對照否證**的代數不變量(相加會破 partition-of-unity、權重>1 會
   破凸有界)。

## honest boundary(仍在)

- **重疊窗長 `window` 與權重曲線(linear / smooth)屬美術手感(A 類)**:本閘只驗「給定 W 與權重,混場的
  代數性質正確」,**不**主張某個 W / 曲線最好看(那要人/參考影片拍板)。
- beat 排序(哪兩拍該 crossfade、重疊多少)仍是 PROPOSAL(A 類)。
- 混合在**值空間**(相對 setup 的 local 通道)做凸組合,近似 Spine runtime 的 track mix;對 rotate 大角度
  的「最短弧」混合、或 weighted-mesh 的 deform 混場未涵蓋(本資產 beat 為 unweighted bone 通道)。
- 單一真值資產(robot)。cap `sequence_crossfade` L2 併入 `spine-anim-forge`(仍 HOLD)。

## 下一步候選(接本軸)

- **(M-2) crossfade 的 C1 / 速度連續性**:smooth 權重讓混場**進 / 出純段**速度連續(端點 w'=0),可比照
  L-4 的 `loop_seam_velocity_gap` 量「混場邊界的速度跳變」,證 smooth 比 linear 無頓挫(linear 在窗邊
  有速度折點)。
- **(M-3) crossfade × loopability**:把 Loop 用 crossfade 首尾自混成**完美無縫無頓挫**的循環(接 L-3/L-4)。
- **(M-4) 多拍 fold 的接點不變量**:`crossfade_sequence` 在**每個**接點複驗 M2–M5(現已能跑,未加閘)。

## 檔案

- `tools/analyzer/gen_animations.py` — 新增 `crossfade_pair` / `crossfade_sequence` / `_crossfade_weight` /
  `_alpha_to_hex`(全 additive,不改既有函式)。
- `tools/analyzer/validate_sequence_crossfade.py` — M 閘(5 AC)。
- `tools/check_readiness.py` — 新增 cap `sequence_crossfade`。
