# S1 相異 beat 接點 C1(速度)連續 / 序列全程 C1 — candidate (L-5)

> 2026-10-06 run 001。關掉 candidate (L-4) 誠實列出的 honest boundary:L-4 的
> `loop_seam_velocity_gap` / `is_c1_loopable` **只驗自接點**(同一支 Loop 重播 N 次),並明記
> 序列**全程** C1(含**相異 beat 接點** In→hit / … / Loop→Out 的速度連續)尚未驗。本次把 C1
> 從「自接點」一般化到「相異接點」並以閘把關。**crux 發現**:①真實大獎正向序列每個相異接點都
> **C0 無縫但 C1 不連續**(大獎序列本質是一串離散節拍/撞擊);②**自接點 C1(L-4)與相異接點
> C1(L-5)是兩個獨立不變量**(Loop 可安全重播卻在與鄰 beat 接點頓挫)。這是**組合層的覆蓋補強
> + 三條純量測/純判斷函式**,無改任何 beat 生成 / 產線值。

## 補的缺口(L-4 誠實列出的 honest boundary)

candidate (L-4) 的 `loop_seam_velocity_gap(clip)` 量「一支 clip 平鋪重播時**自接點**(前份尾→後份首)
的速度不連續」,`is_c1_loopable` 判「可**無頓挫**重播」。但 L-4 的「下一步」誠實記著:

> 續整合/組合閘精神:序列**全程** C1 連續(不只自接點,也含**相異 beat 接點** In→Loop / Loop→Out
> 的速度連續 —— 本次只驗自接點,相異接點的 C1 尚未驗)。

`compose_sequence` 把各 beat 串成序列,L 已驗每個相異接點 **C0 無縫**(`state_end(前) == state_start(後)`)。
但即使接點**值**連續,若兩 beat 在接點的**切線速度不同**(`v_end(前) ≠ v_start(後)`),串接後接點仍有
**速度突變(velocity kink)**。本次把這條序列全程 C1 的相異接點版 boundary 關掉。

## 選題理由(延續 L / L-2 / L-3 / L-4 / G-2,刻意不加參數軸)

近期多為整合 / 組合閘而非再加生成軸。L-5 的客觀新不變量 = **相異接點 C1 速度連續(序列全程)**,
L 的 C0 判準與 L-4 的自接點 C1 判準都涵蓋不到。直指 north star「產出可**平順**播放的大獎序列」。

## 做了什麼(全 additive)

1. **`gen_animations.seam_velocity_gap(clip_before, clip_after, h=1e-3)`** → float:相異接點 C1 不連續量 =
   `max |v_end(clip_before) − v_start(clip_after)|`(跨所有 bone 通道 rotate/x/y/scale/shear + 每 slot alpha,
   單側有限差分)。**一般化 L-4 的 `loop_seam_velocity_gap`**:後者是本函式 `clip_before is clip_after`
   (自接點)的特例。
2. **`loop_seam_velocity_gap(clip, h)` 改為委派** `seam_velocity_gap(clip, clip, h)`(自接點 = 相異接點
   的 `before==after` 特例;`max|v_end−v_start|` 對 abs 對稱,**逐位元等價**,零回歸——探針實測 Loop/hit/In
   三者 `seam(x,x) == loop_seam(x)` 皆 True)。
3. **`gen_animations.sequence_seam_gaps(anims, order, h=1e-3)`** → list:序列 `order` 每個相鄰接點的
   `{"i","seam","c0_gap","c1_gap"}`(`c0_gap` = `_state_max_diff(sample(前,dur), sample(後,0))`,`c1_gap` =
   `seam_velocity_gap`)。相鄰同名(如 `Loop,Loop`)自然退化為自接點。序列全程逐接點報告。
4. **`gen_animations.is_c1_continuous_sequence(anims, order, tol=1e-6, vel_tol=1.0, h=1e-3)`** → bool:
   每接點 `c0_gap ≤ tol`(C0 無縫)**AND** `c1_gap ≤ vel_tol`(C1 無頓挫)。C1-continuous ⇒ C0-continuous。
5. **新閘 `validate_sequence_seam_c1.py`(L-5,5 AC)**:從**先驗庫 → 真實 build_spine robot 骨架 →
   build_animations** 端到端(與 L / L-3 / L-4 同一 fixture)。正向序列 `In→hit→combo→charge→cascade→Loop→Out`。

## 5 AC(全 PASS)

- **S1 present + C0 複驗 + 非空驗**:正向序列每個相異接點 `c0_gap ≤ 1e-6`(**全 0**,值無縫可串接播放,
  L 複驗);接點兩側**真有運動**(max 端點速度 ≥ 1,否則 C1 判準空驗);`sequence_seam_gaps` 良構
  (長度 == len(order)-1、每項 finite)。
- **S2 crux — metric 良定義**:相異接點 C1 gap 對 h∈{2e-3,1e-3,5e-4} 穩定(相對差 < 1e-3,最大
  In→hit 5.8e-4)→ 單側差分 = 端點**切線**,非有限差分 artifact;並**確認**須在 clip 端點層量 ——
  composed 時間軸的接點速度是 sampling/dedup 相依 artifact(≥1 接點 composed **低報**真 kick,實測
  hit→combo composed 48.4 vs clip 端點 86.6,低報至 0.56×)。
- **S3 crux — 序列 C0 無縫但非 C1**:正向序列**全程** C0 無縫(每接點 c0_gap ≤ 1e-6)**但每個**相異接點
  `c1_gap ≥ 10`(實測 In→hit 114・hit→combo 87・combo→charge 109・charge→cascade 78・cascade→Loop 15・
  Loop→Out 15)→ `is_c1_continuous_sequence`==**False** 且**非**因 C0(C0 全過)→ 證序列可無跳變播放卻
  仍逐接點頓挫;報告**最大 kick 接點** In→hit 114 定位之。
- **S4 crux — 自接點 C1 ⊬ 序列接點 C1(本 run 核心)**:`Loop` `is_c1_loopable`==True(自接點 gap
  0.188 < 1,L-4)**但** Loop 的兩個序列接點(cascade→Loop、Loop→Out)c1_gap ≈ **14.997 ≥ 10**,且
  min(Loop 序列接點)/Loop 自接點 ≈ **79.7× ≥ 50** → 證自接點 C1 **不蘊含**序列接點 C1(兩獨立不變量;
  肇因:Loop 端點正呼吸擺動 ≈15 而鄰 beat 近靜止到達/離開)。
- **S5 正對照 + 負對照 + 空驗守衛**:
  - (a) **正對照(放行力)**:共線切分 clip(rotate 0→10→20 於 t_m 切兩半)→ 接點 c0_gap≈0 且 c1_gap≈0
    (兩半共享 t_m 切線)→ `is_c1_continuous_sequence`==True → 證閘能**放行**真 C1 接點(非恆判 False 的廢閘)。
  - (b) **crux 負對照**:同前半 + 切線不符的後半(rotate 10→5)→ c0_gap≈0(值仍連續,10==10)**但**
    c1_gap = 15 > 1 且 `is_c1_continuous_sequence`==False → 抓出 C0 看不到的速度 kink。
  - (c) **空驗守衛**:兩靜止 clip → c0_gap==c1_gap==0 trivially「C1」且 is_c1_continuous==True **但**接點
    兩側端點速度 ≈0 < 1(無運動)→ 證「gap≤tol」必要不充分、須配非靜止(呼應 L-4 C1e-b / L-3 LP4)。

## 回歸

`python3 tools/check_readiness.py` → **0 RED**(新增 cap `sequence_seam_c1` L2 併入 `spine-anim-forge`,仍 HOLD;
L-4 等既有閘逐一 GREEN 證三條新純函式 + `loop_seam_velocity_gap` 委派重構零回歸)。

## 關鍵發現

1. **真實大獎序列全程 C0 無縫但每接點 C1 不連續** —— 每個 beat 首尾皆 setup identity → 接點值連續(可無
   跳變串接播放);但各 beat 是**離散節拍/撞擊**,接點速度突變 15~114 → 平順播放需另行設計。這是把「序列
   能播放(C0)」與「序列播得平順(C1)」分成兩個獨立可量測層(呼應 L-3/L-4「真簽章常需兩獨立條件並立」)。
2. **自接點 C1(L-4)與相異接點 C1(L-5)互不蘊含** —— 同一支 Loop 可以「自接點 C1-loopable」(重播 N 次
   無頓挫)卻在「與鄰 beat 的序列接點」C1 失敗(Loop 端點呼吸擺動 ≈15 而鄰 beat 近靜止)。loop 層的無縫
   ≠ 序列層的無縫,**量在哪一層決定看見哪種連續性**(呼應 L-2/L-3/Z4)。
3. **composed 時間軸的接點速度對相異接點是不可靠 proxy** —— 對自接點(L-4)dedup 必抹平恆 C0;對相異接點
   則**視 sampling/dedup 與接點兩側段長而定**(部分接點 composed 低報真 kick、部分巧合吻合),故 C1 的
   principled 量只在**孤立 clip 的端點切線**(本函式所做),不能從 composed 時間軸量。
4. **一般化舊函式要證「特例逐位元等價」** —— `loop_seam_velocity_gap(clip)` 委派 `seam_velocity_gap(clip,
   clip)` 的零回歸,靠「自接點 = before==after 特例且 max|v_end−v_start| 對 abs 對稱」+ 探針實測逐位元相等
   (呼應 J-6「向後相容要證舊值在新路徑下逐位元重現」)。

## honest boundary(仍在)

- 大獎序列**是否該被設計成全程 C1** 屬美術手感(A 類):離散節拍的接點 kick 是設計使然、非 bug;要不要
  讓某些接點平滑(例如進 Loop 前讓 cascade 以 Loop 的起始速度收尾)是後續手感決策,本閘只量化並逐接點攤開。
- `vel_tol=1.0` 為量級選擇(Loop 自接點 0.19 ≪ 1 ≪ 序列接點 ≥15)。
- 無改任何 beat 生成 / 產線值(三新函式純量測 / 純判斷;`loop_seam_velocity_gap` 委派後逐位元不變)。
- 單一真值資產(robot)。cap `sequence_seam_c1` L2 併入 `spine-anim-forge`(仍 HOLD)。
