# S1 (L-6) 跨 beat crossfade / mix 序列組合:以 C1 斜坡消接點 C1 kink

> candidate **L-6**(2026-10-06 run 002)。承 L-5:把序列接點 C1 從「量化 / 攤開」推到「修正」。
> 程式:`tools/analyzer/gen_animations.py`(crossfade 段)・閘 `tools/analyzer/validate_sequence_crossfade.py`。

## 補的缺口(L-5 的「下一步」/ STATE 的 crossfade 軸)

candidate (L) 的 `compose_sequence` 只做**純時間平移 + 接點去重**,相鄰 beat 在接點**瞬間切換**。L-5 證實
正向大獎序列 `In→hit→combo→charge→cascade→Loop→Out` 每個相異接點雖 **C0 無縫**(值連續、可串接播放),卻
**C1 不連續**(接點速度突變 15~114):各 beat 是離散節拍,端點切線互不相同。**純平移去重做不到平滑接點 ——
需真正的 mix 機制**(STATE line 1210-1211:「compose 的純平移+去重做不到,需真正的 mix 機制」)。

本次新增 **crossfade**:相鄰 beat 時間**重疊** `xf` 秒,重疊區以權重斜坡 `w(s)`(s∈[0,1])**混合**兩 beat 的
姿勢,並以閘把關「crossfade + C1 斜坡」能把 L-5 攤開的接點 kink 消掉。直指 north star「產出可**平順**播放的
大獎序列」。全 additive、純函式、不改任何生成/產線值。

## crux:crossfade 能否消接點 C1 kink,取決於斜坡本身是否 C1(w'(0)=w'(1)=0),而非 crossfade 本身

重疊區 composed 姿勢 `P(T) = (1−w(s))·A(ta) + w(s)·B(tb)`(A=前 beat,B=後 beat,s=(T−T0)/xf,
ta/tb 為兩 clip 的 local 時間,dta/dT=dtb/dT=1)。微分:

```
P'(T) = (w'(s)/xf)·(B(tb)−A(ta)) + (1−w)·A'(ta) + w·B'(tb)
```

- 重疊**左界** T0(s=0):`P'(T0⁺) = (w'(0)/xf)·(B_start−A(d_before−xf)) + A'(d_before−xf)`;左界之外(純 A)
  `P'(T0⁻) = A'(d_before−xf)`。相減 → **接點引入的速度不連續 = (w'(0)/xf)·(B_start−A(d_before−xf))**。
- 重疊**右界** T0+xf(s=1):同理 = `(w'(1)/xf)·(B(xf)−A_end)`。

⇒ **斜坡 w'(0)=w'(1)=0(smoothstep 3s²−2s³ / smootherstep 6s⁵−15s⁴+10s³)時,接點引入的 kink 恆為 0
(閉式精確)**:離散瞬切被換成 xf 秒的平滑過渡(過渡內速度為 A'/B' 的平滑混合,無新 kink)。**線性斜坡
w'≡1 則兩界 kink≠0**(= 兩 clip 在重疊界的值差 / xf)→ crossfade 本身**不足以** C1,**C1 的斜坡**才是鑑別子。

此 kink 是**閉式**(乘 `w'(0)/w'(1)` 導數),**與有限差分步長、與 clip 內部關鍵幀位置皆無關** —— 不會把 beat
自身的內部節拍 kink 誤計為接點 artifact(L-5 的 `seam_velocity_gap` 是 `xf→0` 的瞬切極限,本函式量 crossfade
**後**殘餘的接點 kink)。實測踩雷:`xf=0.2`(=最短 beat Out=0.4 的一半)時重疊界落在 clip 內部節拍 kink 上,
有限差分探針量到假 kink 134~167;閉式乘 `w'` 完全不受影響(smoothstep 恆 0)—— 證**必須用閉式、以導數鎖接點引入量**。

## 做了什麼(全 additive)

`gen_animations.py` 新增(純函式,不改任何既有值;`xf=0` 一律退化回 `compose_sequence` 逐位元相容):
- `crossfade_ramp(name)` → `(w, w')`:smoothstep / smootherstep(C2)/ linear。
- `crossfade_pose_at(anims, order, xf, T, ramp)` → 解析混合姿勢(真正的 mix;compose 的純平移**做不到**)。
- `crossfade_seam_kink(clip_before, clip_after, xf, ramp)` → **閉式**接點 C1 kink `{left,right,max}`
  (= 上面兩界公式)。
- `crossfade_junction_kinks(anims, order, xf, ramp)` → 序列逐接點閉式 kink。
- `is_c1_crossfade_sequence(anims, order, xf, ramp, vel_tol)` → crossfade 後全程 C1 判準(與 L-5
  `is_c1_continuous_sequence` 對照:純接續恆 False,crossfade+smoothstep → True)。
- `crossfade_sequence(anims, order, xf, nsamp, ramp)` → 把序列重取樣成**單一可載入** animation
  `(composed, segments)`:body 區與重疊區以統一時間解析度 `dt=xf/nsamp` 重取樣解析姿勢成線性關鍵幀
  (body 回純 clip 姿勢=忠實,重疊回混合);`segments` 相鄰段區間**相交 xf**(與 compose 無交疊不同)。

## 閘 `validate_sequence_crossfade.py`(5 AC 全 PASS,真實 robot 骨架)

從**先驗庫 → 真實 build_spine robot 骨架 → build_animations** 端到端(與 L/L-3/L-4/L-5 同一 fixture);
`xf=0.15`、`nsamp=16`。

- **X1 present+well-formed+忠實+backward-compat**:合法 Spine timeline(時間嚴格遞增/finite);總時長
  `5.5 == Σdur − 6·xf`;**body 區忠實**(emitted vs 孤立 clip 平移 max 0.0019 ≤ 0.05);**`xf=0` 逐位元 ==
  `compose_sequence`**;segments 相鄰相交 xf。
- **X2 crux — smoothstep 消接點 kink**:smoothstep crossfade 每接點閉式 kink **全 0**(≤1e-6)**對照**純接續
  (L-5)每接點 15~114(In→hit 114/hit→combo 87/combo→charge 109/charge→cascade 78/cascade→Loop 15/
  Loop→Out 15)→ crossfade 消 kink;`is_c1_crossfade_sequence`(smoothstep)=**True** 而
  `is_c1_continuous_sequence`(純接續)=**False**。
- **X3 真混合 + 非空驗**:重疊中點(s=0.5)姿勢與**前 beat 單獨**、**後 beat 單獨**皆不同(各 ≥0.3,實測最小
  0.577)→ 真在混合非瞬切;重疊**真縮短**總時長 6·xf=0.9;接點兩側端點速度 ≥1(非空驗,否則 kink=0 空驗)。
- **X4 crux — C1 斜坡才是鑑別子(負對照)**:**線性**斜坡 crossfade 每接點閉式 kink 15~120(crossfade 本身
  不足以 C1)、`is_c1_crossfade_sequence`(linear)=**False** → 證**斜坡的 C1 性**(w'兩端=0)才是消 kink 的
  原因,非 crossfade 本身;**smootherstep**(C2)亦每接點 =0 → 證關鍵 = `w'(0)=w'(1)=0` 的**共性**,非特定 smoothstep。
- **X5 metric 良定義 + 守衛 + 空驗**:(a) **閉式==數值**:合成 clean clip 對(無內部關鍵幀干擾)線性斜坡的
  閉式 `crossfade_seam_kink`(left 10 / right 40)== `crossfade_pose_at` 數值有限差分(10.0006/39.9994,
  rel<1e-3);(b) **emitted 重疊忠實**:emitted 在重疊 vs 解析 `pose_at` nsamp=16 誤差 0.191、nsamp=64 降至
  0.0028(**隨 nsamp 收斂**→線性重取樣 artifact 非 bug);(c) **輸入守衛**:xf<0 與 xf>min_dur/2 → ValueError、
  xf=0 委派不報錯;(d) **空驗守衛**:兩**靜止** clip crossfade → smoothstep **與**線性 kink 皆 0(靜止 → 無論
  斜坡皆無 kink)**但**無運動 → 證「kink=0」須配非靜止才有意義(smoothstep 在**會動**的真 beat 上 kink=0 才是
  實質結果;呼應 L-5 空驗)。

## 迭代踩雷(預算內自修)

初版 `crossfade_sequence` 的 body 區用**固定 nsamp** 細分 → 長 beat(Loop body 1.7s)細分間距 ~0.1s 太粗,
bezier 弧線性近似誤差 0.063 > FAITH_TOL 0.05(X1 假失敗)。改用**統一時間解析度** `dt=xf/nsamp` 決定 body
細分數(`nbody=round((hi−lo)/dt)`)→ body 忠實度與重疊同步、隨 nsamp 收斂,誤差降到 0.0019。
(初版還殘留一條 sparse-channel bug:只保留 body 內部原關鍵幀 → 關鍵幀只在 t=0/dur 兩端的 sparse 通道在 body
無幀 → 退化成 identity 直線,誤差 5.4;改為「逐通道重取樣解析姿勢(body 命中原關鍵幀角點 + dt 細分)」一併修掉。)

## 關鍵發現

1. **crossfade 消接點 C1 kink 的充要是「斜坡本身 C1」(w'(0)=w'(1)=0),非「有無 crossfade」** —— 線性斜坡
   crossfade 兩界 kink 猶存(15~120),smoothstep/smootherstep 恆 0。很多天真 crossfade 用線性斜坡故仍頓挫;
   把「重疊混合」與「斜坡連續性」分成兩獨立條件,**後者才是消 kink 的鑑別子**(呼應本 repo 通則「真簽章常需
   兩獨立條件並立」:L-3 無縫+非靜止、L-4/L-5 C0+C1)。
2. **接點引入的 kink 要用閉式(乘 w' 導數)量,不可用有限差分探純值** —— 閉式與取樣步長、與 clip 內部關鍵幀
   位置皆無關;有限差分在重疊界落到 clip 內部節拍 kink 上會量到假 kink(xf=0.2 探針 134~167 而閉式恆 0)。
   L-5 的 `seam_velocity_gap` 是本量的 `xf→0` 瞬切極限。
3. **「量化 / 攤開」可推到「修正」,但修正觸及美術手感要界清楚** —— 接點該不該平滑、xf 多長、哪些撞擊感該
   保留,屬 A 類;本 run 只把**機制**(crossfade + C1 斜坡能消 kink)客觀化並以閘證成,**不替使用者決定**要不要
   套、套哪些接點。
4. **統一時間解析度(body 與重疊同 dt)讓重取樣忠實度單調隨 nsamp 收斂** —— 固定段數對不等長 body 會給出
   不均勻解析度(長 beat 粗、短 beat 細),改以時間步 dt 定段數即一致可收斂。

## honest boundary(仍在)

- **哪些接點該平滑、xf 多長**屬美術手感(A 類):離散節拍的撞擊感可能該保留(大獎的「撞擊感」本是設計);
  本 run 只客觀化機制,不替使用者決定套用策略。
- `vel_tol=1.0` / `xf=0.15` 為量級選擇;正向序列無 shear(與 L 同採 hit/combo/charge/cascade,但 crossfade
  機制本身通道無關、含 shear);單一真值資產(robot)。
- 無改任何 beat 生成/產線值(全新純函式;`xf=0` 委派後逐位元不變)。cap `sequence_crossfade` L2 併入
  `spine-anim-forge`(仍 HOLD)。

## 下一步(候選,皆自主)

- **接點平滑的選擇性套用**(把 crossfade 從「全序列同一 xf」推到「per-接點 xf / 只平滑特定接點」)—— 但
  **哪些接點、xf 多長**觸美術手感 A 類,屬 PROPOSAL,需謹慎界定。
- 或 **crossfade × tier**(高檔位序列更緊湊的接點 xf)/ **非對稱 crossfade**(不同進出速率);或回主秀生成軸 /
  S5 rig 真值(C/資源類,仍阻塞 L3)。
- 詳見 `STATE.md` 的「下一步動作」。
