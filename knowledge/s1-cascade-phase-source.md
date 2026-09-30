# S1 (J-5) cascade 波方向由空間位置決定 — 跨件時序通道的「方向(相位來源)」軸

> candidate J-5 · 2026-09-30 run 002 · cap `cascade_phase_source` L2(併入 `spine-anim-forge`,仍 HOLD)
> 閘:`tools/analyzer/validate_cascade_phase.py`(5 AC 全 PASS)

## 補的 honest boundary

cascade 跨件時序通道此前已有兩條軸:**結構**(nrip,J-3:掃幾道波)× **幅度**(span,J-4:一道多開)。
但各件的**相位**(phase∈[0,1],決定誰先誰後)一律由**件序**(storyboard `parts` 的位置)決定:
`phase = pi/(n−1)`。也就是波的**方向**永遠等於「件在規格清單裡的排列順序」,與件在畫面上的**空間位置**無關。

本次補上 cascade 的**第三條正交軸 = 方向(相位來源)**:相位改由**空間位置排名**決定波的方向。

| mode | 相位排名鍵 | 波方向 |
|---|---|---|
| `order`(預設) | 件序(parts 位置) | 舊行為(逐位元相容) |
| `x` | 件中心 `bd.x` 升序 | **左 → 右**(x 小者先亮) |
| `radial` | 件中心到畫布中心距離升序 | **中心 → 外擴**(近者先亮) |

相位仍以**排名** `rank/(n−1)` 均勻映到 [0,1] → span(散佈)/nrip(波掃次數)/幅度(深度)語意**全部不變**。
平手(同鍵)以**件序**打破 → 完全確定性穩定排序。

## crux:「方向」= 排名的重新指派(permutation),不動時刻集合

相位來源軸與前兩條軸(nrip 結構、span 幅度)的**機制分野**:它既不重生成關鍵幀窗(不像 nrip/span),
也不做值增益(不像 J 深度)——它只是把**同一組峰時刻**重新**指派**給不同的件(a permutation of who-peaks-when)。

由此得兩個強斷言(閘的核心鑑別點):

1. **峰時刻多重集合三模式相同**(P4a):order/x/radial 三模式下,所有件的峰時刻**集合**完全一致
   (真實骨架 {0.158, 0.296, 0.429, 0.567, 0.70}),只是**指派給不同件**。→ 證相位來源與 span/nrip/深度**正交**
   (它動不了「有幾道波 / 一道多開 / pop 多深」,只動「哪件在哪個時刻」)。
2. **真實 robot 骨架上件序 ≠ x 序 → 波方向真的改變**(P2/P5a):真實 cascade 件序
   `[光暈, 右手, 頭, 身體, 左手]`,但 `右手 x=320.5 < 光暈 x=359.0` → **x 模式下右手與光暈 who-peaks-first 互換**
   (order 模式光暈先 pop τ=0.158,x 模式右手先 pop τ=0.158)。同一骨架、同一切,只換相位來源 → 觀察得到的方向改變。

（真實骨架上 **radial 序恰 == 件序**,因該清單本就依徑向排好 → radial 模式在此骨架逐位元同 order,是個乾淨的
backward-compat 錨點;要證 radial 模式真跟著徑向,用合成 fixture。)

## 生成:相位排名映到 [0,1](gen_animations._phase_ranks)

```
_phase_ranks(valid, bone_of, cx, cy, mode):
    order  → rank == 件序(list 位置)               # 逐位元同舊行為
    x      → 依 bd.x 升序排名                        # 左→右
    radial → 依 hypot(x−cx, y−cy) 升序排名           # 中心外擴
    平手 → 以件序打破(stable、確定性)
呼叫端:phase = rank/(n−1)                          # 均勻散佈 → span/nrip 語意不變
```

因為相位仍是 [0,1] 均勻排名,`gen_cascade` 的窗中心 `c_k = (k + LEAD + p·span)/nrip` 完全照舊吃這個 `p`,
故 span/nrip **不受干擾**(P4b/c);值增益只放大深度 → 深度軸也不受干擾(P4d)。**三軸(nrip × span × 深度)全與方向正交**。

## 全 additive · 向後相容

- 新增 `CASCADE_PHASE_MODES = ("order","x","radial")` + `_phase_ranks`(gen_animations)。
- `_build_beat(..., cascade_phase="order")` / `build_animations(..., cascade_phase="order")` /
  `build_spine --cascade-phase {order,x,radial}` 透傳;**對 cascade base 與所有檔位變體一致套用**(波方向不隨檔位變)。
- `order`(預設)→ rank == pi → **逐位元同無參數呼叫**(base + 所有 tier 變體)。非-cascade beat 完全不受影響。
- 非法 mode → `ValueError`(輸入守衛)。

## 閘 `validate_cascade_phase.py`(真實 robot 骨架 + 合成 3-排列 fixture)

從**先驗庫**經 `analyze_target`→**真實 build_spine robot 骨架**→`build_animations(..., cascade_phase=...)`
端到端量(與 J/J-3/J-4 同一真實 fixture);另加**合成 3-排列 fixture**(件序 / x 序 / 徑向序**兩兩皆異**)做乾淨鍵隔離。

- **P1 present + backward-compat**:`order` 對 base 與**所有檔位變體**逐位元同無參數呼叫;非-cascade 主秀 beat
  三模式逐位元不變(相位來源只作用 cascade,不外洩)。
- **P2 spatial drives wave(crux)**:真實骨架 x 模式峰時刻在 **bd.x 升序**下嚴格遞增 + 右手/光暈 who-first **互換**;
  radial 模式峰時刻在**徑向升序**下嚴格遞增;合成 fixture 每模式峰時刻在**自己的鍵序**下嚴格遞增。
- **P3 signature + interface**:三模式仍是**合法 cascade**(在自己鍵序下跨件峰遞增 + 散佈 ≥0.30);首尾 setup identity、
  特效 slot alpha 首尾=1(可插 Loop 間)。
- **P4 orthogonality**:(a) 峰時刻**多重集合**三模式相同(permutation);(b) x+span → 各檔位散佈(x 序量)== 宣告 span;
  (c) x+nrip → 每件 pop 次數==nrip;(d) x+gains → 峰**深度**隨檔位遞增。
- **P5 neg-control**:(a) 真實 x 模式峰在**件序**下**不**遞增(真跟著 x、非恆真);(b) 合成每模式在**另兩鍵**序下**不**遞增
  (鍵隔離);(c) 退化:所有件同 x → x 模式平手以件序打破 → 逐位元==order;(d) 非法 mode→ValueError。

## 關鍵發現

- **跨件時序通道至此有三條正交軸:結構(nrip)× 幅度(span)× 方向(相位來源)**。三者機制各異:
  nrip/span 重生成關鍵幀窗、深度用值增益、**方向只是排名的重新指派(permutation)**。
- **permutation 軸的簽章 = 「時刻集合不變、指派改變」**:與重生成/值增益軸乾淨區分的判準是「峰時刻多重集合在各
  模式下相同」(P4a)——這是一個比「某量遞增」更結構化的正交性斷言。

## honest boundary(仍在)

- 方向的**選擇**(order / x / radial,以及未來可加的右→左、外→內、沿任意向量)是 **PROPOSAL**(手感 A 類,留使用者);
  閘只驗「所選方向被正確、確定性地實現且與其他軸正交」。
- 相位用**排名**(均勻散佈)而非**原始座標值**(等比散佈):排名保 span/nrip 語意不變、最小改動;若要「按實際間距
  拉開波」(近的件擠、遠的件散)是另一個**連續相位**變體(可加 `phase_metric="rank"|"value"`),為後續。
- 單一真值資產(防固化);cap `cascade_phase_source` L2 併入 `spine-anim-forge`,**仍 HOLD**(運動基元先驗)。
