# S1 (J-7) cascade 波方向由件幾何自動導出 — 把 J-6 方向軸的「取值來源」由手感常數下推成幾何導出

> candidate J-7 · 2026-10-02 run 002 · cap `cascade_dir_geo` L2(併入 `spine-anim-forge`,仍 HOLD)
> 閘:`tools/analyzer/validate_cascade_dir_geo.py`(5 AC 全 PASS)

## 承 (J-5)/(J-6):方向軸的第三次精煉 —— 逐步移除「人手指定」

**同一條方向軸**(cascade 跨件波的相位來源),三次精煉逐步把「用哪個方向」從人手移開:

| candidate | 方向怎麼來 | 誰決定 |
|---|---|---|
| J-5 | 件序 → **空間**(4 個具名 `lr`/`rl`/`co`/`oc`) | 人手選一個具名 |
| J-6 | 具名 → **連續**(任意角 / 向量) | 人手給角度/向量 |
| **J-7** | 連續值 → **由件幾何導出**(質心→最遠件) | **幾何自動導出**(不再人手給) |

J-6 把方向的**值**連續化了,但「用哪個方向」仍是 per-genre **手感常數**
(`tier_variants.TIER_CASCADE_DIR`,如 `slot_bigwin → "co"`)。
J-7 新增 sentinel `cascade_dir="geo"`:方向**向量**由件實際幾何導出,隨資產自適應,不再寫死。

## crux:J-7 **不是**新正交軸(honest distinction,勿誇大)

跨件時序通道的三條正交軸(結構 nrip,J-3 × 幅度 span,J-4 × 方向/相位來源,J-5)**沒有變成四條**。
J-7 導出的方向向量**導出後仍走 J-6 的投影排序**(`k = x·ux + y·uy` → rank → 相位,同機制)。

J-7 改的是方向軸的**取值來源(provenance)**:從「人手給一個值」換成「由幾何導出一個值」。
- J-5 = 方向**空間化**(把隱含的件序假設顯式化成可控軸)
- J-6 = 方向值**連續化**(4 具名 → 任意角/向量)
- J-7 = 方向值**自動化**(手感常數 → 幾何導出)

三者都是**同一條方向軸**的精煉,逐步把人手從迴圈裡拿掉。

## 導出規則 `derive_cascade_dir(centers, source="centroid_farthest")`

- `centroid_farthest`(目前唯一 source):件**質心** → 距質心**最遠件**的單位向量。
  - **確定性、無 PCA ±符號歧義**:PCA 主軸只給一條線(方向正負須另定);最遠件天然定出一個**明確指向**。
  - 語意 = 波沿「叢集中心 → 最外側肢體」軸掃(投影最大的最遠件最後 pop)。
- 呼叫端(`_cascade_phase_of`)給**當前 beat 的有效件中心** → 方向隨實際參與件自適應。
- 退化幾何(所有件重合 → 零方向)、空件、未知 source → `ValueError`(輸入守衛)。

robot fixture 導出結果:質心 (398.3, 371.2),最遠件 = **左手**(距質心 163.5,角度 13.2°),
導出向量 ≈ `(0.974, 0.228)`;geo 波序 = `[右手, 光暈, 身體, 頭, 左手]`(峰時刻 0.158→0.296→0.429→0.567→0.70)。

## 全 additive 的接法

- 新增 `derive_cascade_dir`(純函式,獨立可測)。
- `_normalize_cascade_dir`:`"geo"` / `("geo", source)` → `("geo", source)` marker(置於通用 length-2 向量分支**前**,
  否則 `("geo", src)` 會被誤當 `(ux, uy)` 向量而 `float("geo")` 爆錯)。
- `_cascade_phase_of`:`kind=="geo"` → 用當前件中心 `derive_cascade_dir` 得向量 → `kind="proj"` 落 J-6 投影路徑。
- `build_spine --cascade-dir geo`(或 `geo:SOURCE`);`_parse_cascade_dir` 認 `"geo"`/`"geo:..."`。
- `None`/`"po"`/具名/角度/向量路徑逐位元不變(geo 為全新 sentinel,純加性)。

## 閘:`validate_cascade_dir_geo.py`(5 AC 全 PASS)

從先驗庫 → **真實 build_spine robot 骨架** → `build_animations(cascade_dir="geo")` 端到端量;
geo 向量**由閘自行獨立重算**(不碰生成器私有 `derive_cascade_dir`)以保持獨立驗證。

- **W1 present + backward-compat**:geo 產每 cascade beat 有 bone/finite;非 cascade 主秀 beat 逐位元同 base;`po==None`。
- **W2 derived projection ordering(crux)**:峰時刻依閘獨立導出的質心→最遠件投影鍵嚴格遞增,**最遠件(左手)最後 pop**。
- **W3 still a cascade + interface**:geo 仍一道有序跨件波(散佈 ≥ 0.30)+ 首尾 setup identity + 特效 slot alpha=1。
- **W4 orthogonality**:geo 下仍保 (a) dir⟂深度(geo 峰 overshoot == base,HIRES 量)、(b) dir⟂nrip(帶 ripples 各件 pop 次數==nrip)、(c) dir⟂span(帶 span 散佈==宣告 span)。
- **W5 neg-control(data-derived)**:
  - **(a) crux discriminator**:同一 `cascade_dir="geo"` 套在**兩個不同幾何** —— 真實 robot(vA≈`(0.974,0.228)`,13°)vs 把「頭」沿 +y 推遠 1200 成最遠件的變體(vB≈`(-0.036,0.999)`,92°)—— **導出向量不同**且**波序不同**,各自**吻合自身幾何**的質心→最遠件投影序。若 `derive` 回常數 → 兩幾何同波序 → fail(**實測:常數 bug 會讓 W2 與 W5(a) 同時 FAIL**,見下)。
  - **(b)** 導出向量/波序 == 閘獨立重算(robot),且最遠件最後 pop。
  - **(c)** geo 波序 ≠ 手感常數 `"co"`(現 `cascade_dir_for(slot_bigwin)`)、≠ `oc`、≠ 件序 `po`、≠ `lr`、≠ `rl` → J-7 與所有 J-5 具名 + 現行手感預設皆不同。
  - **(d)** 輸入守衛:未知 geo source、空件、退化幾何(件重合→零方向)→ `ValueError`。

**閘可信(負對照固化)**:把 `derive_cascade_dir` monkeypatch 成回常數 `(1,0)`(忽略幾何)→ **W2 與 W5(a) 皆 FAIL**
(W2:生成器輸出不再對齊獨立導出的幾何方向;W5(a):兩幾何波序變相同)→ 證閘真測「方向由資料導出」,放寬非拆閘。

## 關鍵發現

1. **「離散→連續」(J-6)之後的下一個通用槓桿是「人手給→資料導出」**:凡是「某個軸的值由人手常數提供」的地方,都可問「這個值能不能由資產本身的某個幾何/統計量導出?」—— 把人手從迴圈裡拿掉一層(方向選擇從 per-genre 常數變成 per-asset 幾何函式)。
2. **要證「值是資料導出、非常數」,必須在兩個不同輸入上證輸出跟著變**:單一資產上「導出值==某幾何量」只證了「這次巧合對上」;真正的鑑別是**換一個幾何**(把最遠件搬到別處),看導出方向**是否跟著轉**且波序**跟著自身新幾何**(W5(a))。這與 J-5 的「件序≠空間序才能鑑別空間 vs 件序」同一精神 —— **鑑別 data-derivation 要讓『資料』變，看輸出是否跟著變**。
3. **幾何導出要挑「無符號歧義」的量**:質心→最遠件天然定出**有向**軸(明確指向);PCA 主軸只給一條線、方向正負須另定,反而需要再引入一個人手規則定正負 —— 選確定性量可避免把「移除的人手」又加回來。
4. **反例陷阱(踩雷):質心反射 + 重新導出 = 不變**:最初想用「把件繞質心反射」當鑑別,但反射後重新導出方向也翻號 → 投影鍵 `k'_i = k_i − const`(減常數不改排序)→ 波序**不變**,兩個翻號互相抵消,鑑別力為零。**教訓**:設計 data-derived 鑑別時,若變換同時作用於「資料」與「導出量」且兩者對稱,效果可能相消 —— 要改用**只改資料不自我抵消**的變換(把某件搬到新位置成最遠件,導出方向大幅轉向而非翻號)。

## honest boundary(仍在)

- J-7 **不是新正交軸**,是方向軸**取值來源**的自動化(provenance);跨件時序通道仍三條正交軸。
- `source` 選擇(目前只 `centroid_farthest`)與**最終手感微調**(要不要用質心→最遠件、或別的幾何來源如主秀爆點方向)仍是 **PROPOSAL(A 類)**;J-7 只提供一個幾何有據的**預設導出**。
- 單一真值資產(robot)→ 防固化,cap `cascade_dir_geo` L2 併入 `spine-anim-forge`(**仍 HOLD**)。
- 後續可擴充 `source`(如 PCA 主軸配確定性定號、主秀爆點方向),或讓 genre 先驗庫建議「用 geo 還是手感常數」。
