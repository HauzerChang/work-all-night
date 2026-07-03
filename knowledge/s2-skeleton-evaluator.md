# S2 骨架閘 — 結構 + pivot 空間關聯(以兩份真實骨架校準)

- **結論**:`evaluate_skeleton.py` 完成。結構閘(單 root/parent 先定義/slot-bone 合法/weight index
  合法)+ pivot 閘(bone↔其控制件的空間關聯,d_norm)。**正對照:main_draw(28 骨,98.6%)、
  Award(77 骨,100%)、我們生成的 robot.json(100%)全過;強負對照(遠位移 rebind/造環/壞 slot)
  三份骨架全抓到**,SELFTEST PASS。
- **信心**:高(兩份真實生產骨架 + 生成骨架正對照;負對照分離度 0.98~1.0 vs 0.0~0.03)。
- **階段**:第 2 階段 / S2(骨架閘 → **S2 四閘齊了**:切圖/mesh/補圖/骨架)。
- **工具**:`tools/mesh_gen/evaluate_skeleton.py`(`--selftest` 一鍵重現)。

## 核心測量

- **setup pose 世界變換**(normal mode、無 shear;兩份真實資產皆只用此):
  world = parent_world ∘ T(x,y)R(rot)S(sx,sy),依定義序遞推。
- attachment 世界頂點:region(角點旋轉平移)、unweighted mesh(bone-local 直接變換)、
  **weighted mesh**(`[n,(boneIdx,bindX,bindY,w)*n]` 逐頂點 Σ w·boneWorld∘bind)。
- **d_norm** = bone 世界位置到 attachment 世界 bbox 的外距 / bbox 對角線。
- 閘:d_norm ≤ 0.5 的比例 ≥ 95%。

## 真實分佈(閾值依據)

| 骨架 | atts | 中位數 | p90 | max(合法離群) |
|---|---|---|---|---|
| main_draw | 73 | 0 | 0 | 2.99(background:bone 掛遠處) |
| Award | 176 | 0 | 0 | 0.326(weighted 角色 mesh) |

→ 真實 rig 的 pivot 幾乎全在件內;0.5/95% 給足合法離群空間,同時讓壞 rig(位移後 0~3%)天差地遠。

## ★ 關鍵發現:負對照必須「rebind」— bone-relative 幾何的不變性

**單純打亂 bone 位置抓不到任何東西**(pivot_frac 完全不變):attachment 是 bone-relative,
骨移美術跟著移,pivot↔件距離是**建構不變量**。壞 rig 的真實樣貌是「**畫面佈局對、骨插錯位置**」
(S5 草案的實際失敗模式)——綁定時產生巨大 local offset。負對照因此要:
打亂/位移骨 → **重算 attachment local 座標保住世界佈局**(region x/y、unweighted 頂點、
weighted 逐骨 bind 座標,全用 inv(newWorld)∘oldWorld 轉換)→ d_norm 才會爆。
**教訓(第 5 次評估器校準):先想清楚「量的東西在壞的情況下真的會變嗎」。**

## 負對照結果

| 負對照 | main_draw | Award | robot(生成) |
|---|---|---|---|
| scramble+rebind(件間互換)| ✅ 0.82 | ✅ 0.68 | ⚠️ 未抓到(見局限)|
| **displace+rebind(位移 1.5×美術範圍)** | ✅ 0.03 | ✅ 0.0 | ✅ 0.0 |
| 造環 / 壞階層 | ✅ 結構 | ✅ 結構 | ✅ 結構 |
| slot 指壞骨 | ✅ 結構 | ✅ 結構 | ✅ 結構 |

## 已知局限(誠實邊界)
1. **件少且互相重疊的小 rig,「件間互換」型壞綁定抓不到**(robot 5 件全在畫布上疊,換中心
   仍在彼此 bbox 內)。空間關聯閘天生只管「骨離件多遠」,不管「綁對哪一件」;selftest 把
   scramble 列 informative、displace 列 strict。
2. 忽略 transform/IK constraint 對 setup 的影響(Award 僅 1 個,實測不影響分佈)、無 shear。
3. **不評「pivot 放關節哪一點」的美術手感** — 那是 PLAN 標記的唯一卡死環節,留人審;
   本閘管的是結構合法 + 空間 sanity,讓 S5 草案能先自主過濾掉垃圾。

## 可重現
```
python3 tools/mesh_gen/evaluate_skeleton.py assets/main_draw.json --selftest   # PASS
python3 tools/mesh_gen/evaluate_skeleton.py assets/Award.json --selftest       # PASS
python3 tools/mesh_gen/evaluate_skeleton.py <any.json>                          # 生產用(exit code)
```
