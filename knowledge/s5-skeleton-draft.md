# S5 起步 — 骨架草案產生器(件鄰接分析),對照 Award 藝術家骨架全 PASS

- **結論**:`skeleton_draft.py` 從件的重疊/鄰接自動產出骨階層 + pivot 草案;
  `skel_to_json.py --draft` 組成帶階層的 Spine skeleton(佈局仍 == PSD,位置 0.001px/光柵 MAE 0.031);
  對 Award 藝術家真實骨架驗證:**拓樸完全一致、可比 pivot 全部在藝術家選點的 6.9% 件對角線內**
  (頭 4.3px!)。骨架草案第一次「生成→過閘→對真值」閉環。
- **信心**:高(藝術家 ground truth 對照 + 三閘自驗);但啟發式只在**一個** GT 上校準,
  換資產(多層鏈式肢體、非人形)需再驗。
- **階段**:第 2 階段 / S5 起步(骨架設計從 ⬜ → 草案能力已建)。
- **工具**:`skeleton_draft.py` / `skel_to_json.py --draft` / `validate_draft_vs_award.py`。

## Award 藝術家骨架真值(從 assets/Award.json 讀出)

```
4_LEG(全域錨 (0,0),持光暈)→ 4_LEG2(髖)→ 4_LEG3(身體,腰部,rot 87.8° 朝上,len 137)
                                              ├─ 4_LEG4(頭,頸部)
                                              ├─ 4_LEG5(左手,肩)  ├─ 4_LEG6(右手,肩)
```
藝術家 pivot 換算到件影像座標(仿射反解,殘差 0):頭=頸底 (0.47,0.87)、
雙手=肩側、身體=腰 (0.36,0.44)、光暈=**場景錨(在件影像外 y=1.07)**。

## 草案啟發式(v1,以此 GT 歸納+校準)

1. **角色**:bbox 覆蓋畫布 ≥85% 且與過半件重疊 → effect(掛 root 層);
   其餘中 alpha 面積最大 → trunk;剩下 limb。
2. **階層(trunk 優先)**:與 trunk 重疊者直掛 trunk(淺樹);不接觸 trunk 者以最大重疊鏈式入樹。
3. **pivot**:limb = 與 parent 的重疊區質心(關節在相接處);trunk/effect = 自身質心。

## 驗證結果(robot_parts,exit 0)

| AC | 結果 |
|---|---|
| 拓樸(trunk/parents/root-level) | **與藝術家完全一致** |
| pivot 距離(/件對角線) | 頭 **0.027**(4.3px)、右手 0.039、左手 0.054、身體 0.069;tol 0.15 全過 |
| 組裝(--draft)位置/光柵 | 0.001px / MAE 0.031(階層化後佈局不變) |
| 骨架閘(evaluate_skeleton) | structure+pivot 100% |

## ★ 兩個關鍵設計決策(v1 的失敗驅動)

1. **「最大重疊」會被 z 交叉假邊騙**:劍(右手件)從臉前橫過 → 頭↔右手重疊 > 頭↔身體(頸部)
   → 頭被誤掛到手上。修正 = **trunk 優先規則**(觸 trunk 就掛 trunk;slot rig 慣例本就是淺樹)。
   誤掛版本會被 `validate_draft_vs_award` AC1 抓 → 對照器有鑑別力(天然負對照)。
2. **重疊矩陣 key 順序 bug**:存用 names 序、查用字典序 → 左手↔身體被 miss 誤判孤島。
   教訓:無序 pair 的 dict key 一律 `tuple(sorted(...))`。

## 不可自決項(A 類,留人)

- **effect 件(光暈)的錨點**:藝術家綁在場景全域錨(件外),是「這特效跟著整隻怪物還是跟著身體」
  的全域擺位決策,單件幾何推不出來 → 草案用自身質心,人審時改。
- pivot 微調手感(頸底 vs 頸中、肩窩深淺)仍留人;但草案已把人的工作從「從零擺骨」降為「微調」。

## 已知局限
- 啟發式對「多節肢體鏈」(上臂→前臂→手)只驗過理論路徑(不觸 trunk → 鏈式),無 GT 實測。
- trunk=最大面積件:對「背景板比角色大」的 PSD 會誤判(需先靠 effect/backdrop 分類擋掉)。
- Award 真值拓樸寫死在 validate 工具內(單資產);多資產後應外部化。

## 可重現
```
python3 tools/mesh_gen/skeleton_draft.py -o /tmp/robot_draft.json
python3 tools/mesh_gen/skel_to_json.py --draft /tmp/robot_draft.json --out r.json --eval   # 0.001px
python3 tools/mesh_gen/evaluate_skeleton.py r.json                                          # 過閘
python3 tools/mesh_gen/validate_draft_vs_award.py                                           # 對真值 exit 0
```
