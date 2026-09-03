# S1×S5 整合:生成的分鏡動畫讓肢體繞關節擺(candidate 0g)

> 里程碑 2026-09-03。閘:`tools/analyzer/validate_anim_rig.py`(一鍵 exit 0 = PASS)。
> 圖:`knowledge/figures/s1_anim_rig.png`。cap:`anim_rig_articulation` L2(併入 `spine-rig-pivot` 區塊,仍 HOLD)。

## 補的缺口(為什麼需要這個閘)

`build_spine --rig --animate` 把兩個已完成能力組合起來,但**沒有任何閘驗過這個組合的運動**:

- **S1 keyframe**(`gen_animations`,0d):給每個肢體件一條 `rotate` timeline。Spine 的 rotate = 「繞該件 **bone 原點**旋轉」。
- **S5 rig**(`--rig`,2026-08-30):把結構子件的 bone 原點從**件中心**移到**與父件的接觸縫**(關節)。
- 既有閘的盲點:
  - `validate_anim.py` 只驗動畫**良構/無縫**,且跑在**非 rig** build(骨在件中心)上 → 不涉及關節。
  - `validate_rig_build.py` AC4 只驗**手動** `THETA=25°` 硬寫旋轉的縫撕裂,**不是** `gen_animations` 生成的 keyframe。

→ 「gen_animations 生成的動畫,施加在 rig 骨上,到底有沒有繞關節?」**過去無人驗**。本閘補這條 S1×S5 接縫。

## 關鍵洞察:機制本已組合,缺的是「生成端」的證明

結構上組合**本就成立**:build_spine 先跑 rig_layout(把 `b_{nm}` 移到關節),再跑 `gen_animations`(rotate 落在**已移到關節的**骨)。實測 Loop 生成的 rotate 確實掛在關節骨上:`b_右手`=+5° `b_頭`=+3° `b_左手`=−5°(rig 與非 rig 的 timeline **逐鍵相同**,只差骨原點位置)。所以這是**整合/回歸閘**,不是新演算法——但它是唯一量化證明「生成動畫 × rig = 真關節運動」的東西。

## 方法(純 CPU,無瀏覽器)

對每個結構子件(`joint=True`:頭/左手/右手):
1. 取件的**稠密外輪廓**世界點(`_dense_world_contour`,`CHAIN_APPROX_NONE` + 等距下採樣到 ~80 點)。
2. **以已驗關節 `J`(rig 骨世界原點)錨定** seam/distal:seam = 離 J 最近 K=6 點、distal = 離 J 最遠 K=6 點。
   —— ⚠️ **踩雷**:一開始用「件輪廓最靠近 body 的點」自行猜縫,對大件/重疊件(左手縫域寬 24→182px)量測極不穩,三件結果互相矛盾。
   改用 **J 當真值錨點**(J 已由 validate_rig_build AC3 證『安裝在真縫上,往返 0.04px』)→ 穩定。
3. 取生成 Loop 該件骨的 rotate **峰值角**,把件當**剛體**綁其單一 bone(`local = inverse(setup world)·p`),
   施「只轉該骨峰值角」pose → posed world → 量每點位移。rig(繞關節 J)/ 非 rig(繞件中心 Cf)各做一次(同一組 seam/distal 索引)。

## 驗收(4AC 全 PASS)+ 內建負對照

| AC | 內容 | 結果 |
|---|---|---|
| **G1 生成即接關節** | 動畫良構(all_finite)+ 每結構子件骨在 Loop 有非平凡 rotate(峰\|角\|>0.5°) | PASS(5°/3°/5°) |
| **G2 生成動畫繞關節** | seam 位移 rig<<非rig,`seam_flat/seam_rig>2` | PASS(右手 5.0×/頭 4.7×/左手 8.0×;rig seam 0.6–2.7px、非rig 2.7–13.6px) |
| **G3 真關節簽章** | rig 末梢/縫位移比>3 且>2×非rig | PASS(rig 16.7/10.1/15.0 vs 非rig 2.3/1.2/1.0) |
| **G4 負對照** | 峰值角=0 → rig 殘餘位移<1e-2px | PASS(0.0px,證位移來自動畫非數值) |

- **內建主負對照 = 非 rig build**(骨在件中心):同一生成動畫,繞件中心轉 → 縫與末梢**對稱擺**(G3 比≈1),縫撕裂(G2 位移大)。
- **鑑別力來源**:G2/G3 的 seam/distal 錨在 rig 關節 J,天然偏向 rig(繞 J 轉時近 J 的點少動)——但這**正是物理主張**(縫錨在關節);
  而非 rig 用**同一組點**仍顯示大位移 + 對稱比(≈1),證差異真實非量測人工。

## 誠實界定(honest boundary)

- 仍 **L2 非 L3**:同 `pivot_end2end`,只驗過**單一 robot rig**(Award 僅機器人一件可拆肢體 rig;OMG/SUP/MEG 為單圖+特效無接觸縫)。
  多 rig 真值屬**使用者資源**,`spine-rig-pivot` 區塊維持 **HOLD**。
- 本閘驗**客觀關節運動結構**(縫錨定 + 末梢甩開),**非美感**;擺幅/緩動手感仍留使用者(A 類)。
- 用 Loop(肢體只有純 rotate,最乾淨的關節測試)。In/Out 另有 translate,未納入本閘(良構性由 validate_anim 覆蓋)。

## 檔案

- `tools/analyzer/validate_anim_rig.py` — 閘本體(`_dense_world_contour` / `_pose_only` / `_rigid_pose_disp` / `evaluate` / `_make_figure`)。
- `knowledge/figures/s1_anim_rig.png` — rig vs 非rig 對照:實線=setup 虛線=posed 圓點=bone原點。
  rig 圓點落在縫(限位)、posed 縫錨住末梢甩開;非rig 圓點在件中心、posed 整件連縫一起盪開(縫撕裂)。
