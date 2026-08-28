# S5 關節 pivot 推斷器（rig pivot inference）— 首個原型 + Award 真值閘

> 里程碑 2026-08-28。路線圖 S5「骨架半自動」的第一個純 CPU、可自主收斂的塊。
> 對應 STATE「下一步」候選 0(e):關節 pivot 推斷(件→相鄰件關節)，供 S5。
> 工具:`tools/analyzer/infer_pivots.py`(推斷器)、`tools/analyzer/validate_pivots.py`(真值閘)。
> 圖:`knowledge/figures/s5_pivot_inference.png`。

## 問題

S1/S4 把角色切成「件」後，要組成可動骨架，最卡的一步是**每個關節的 pivot 該放哪**
(RULES 把「骨架 pivot 放哪」列為 A 類人類決策，PLAN 稱之路線圖唯一卡死環節)。
本塊不追求「完美自動」，而是先做出**確定性 baseline 推斷器 + 可信真值閘**——把主觀微調前的
客觀部分自動化，並量化它離真實美術骨架有多近。

## 方法（確定性，非 ML）

輸入抽象：`parts = { name: [poly, ...] }`，poly 為世界座標多邊形（mesh 三角面或 alpha 輪廓）。

1. **rasterize**：把各件多邊形填成共用網格 mask。
2. **overlap graph**：兩件 overlap 像素 / 較小件面積 = `frac_of_smaller`。
3. **特效層剔除**：對「≥半數其他件、各以 frac≥0.9 覆蓋」者標 `effect`（如全幅光暈），
   不納入結構樹（對齊 `build_meta` 的 effect/structural 語意）。
4. **樹 = 由 root(最大結構件=軀幹) 做 BFS**：每件 parent = BFS 最先觸及它的已入樹件；
   同件多候選父取 overlap 最大者。
5. **關節 pivot = parent∩child overlap 區域的世界形心**。

### 為何 BFS 而非「最大 overlap MST」

四肢彼此可能有**假交疊**：Award 右手是大張 region 貼圖，其 alpha 甚至蓋到頭附近
（頭-右手 overlap 2994px > 身體-頭 902px、身體-右手 1974px）。純「最大 overlap」MST 會把
**頭誤掛到右手**。由軀幹 BFS 則頭/左手/右手都先被軀幹觸及（同層、皆軀幹之子），
假邊自然消解。→ **root 選對(最大結構件) + BFS 分層** 是穩健關鍵。

## 真值閘（`validate_pivots.py` 對 Award）

**真值來源**:Spine 中**子骨的世界原點 = 它相對父件的關節 pivot**。Award 機器人 4_LEG* 骨鏈:
身體=4_LEG3(root)、頭=4_LEG4、左手=4_LEG5、右手=4_LEG6（皆 4_LEG3 之子）→
真值關節 = world(4_LEG4/5/6)。

**件 silhouette 全在同一 Spine 世界座標系取得**（免跨座標對齊，這是評估乾淨的關鍵設計）:
- mesh 件(身體98v/左手80v/光暈78v):setup pose weighted skinning 世界頂點三角面。
- region 件(頭/右手):**atlas 真實 alpha 輪廓** → 經 region attachment(x,y,w,h,rot)+骨變換置入世界。

### 結果(全 PASS)

| 關節 | 推斷 pivot | 真值 | 誤差(px) | baseline(子件形心) |
|---|---|---|---|---|
| 身體↔頭 | (−9.7,452.0) | (−10.7,453.0) | **1.4** | 30.1 |
| 身體↔左手 | (87.8,400.7) | (103.6,410.7) | **18.6** | 92.8 |
| 身體↔右手 | (−94.4,404.0) | (−118.3,411.6) | **25.1** | 67.4 |

軀幹對角線 495px；中位誤差 推斷 **18.6** vs baseline 67.4。

- **AC1 階層正確**:root=身體、頭/左手/右手 皆掛身體、無假邊(頭-右手 不成邊) → PASS。
- **AC2 精度**:max 誤差 25.1 ≤ 10%×495=49.5 → PASS。
- **AC3 勝過 baseline**:中位 18.6 < 67.4 → PASS。
- **AC4 特效剔除**:光暈 被標 effect、不獲關節 → PASS。
- **負對照(`--selftest`,用子件形心當推斷)**:AC2/AC3 皆 FAIL → **閘有鑑別力**。

## 關鍵發現 / 誠實界定

1. **pivot 精度相依 silhouette 緊緻度**（本塊最重要的可轉移結論）。
   先用**鬆散 bounding-quad**當右手 silhouette 時，overlap 形心被拉向件中心，
   誤差 **132px**；換成 atlas **真實 alpha 輪廓**後降到 **25px**。
   → 推 pivot **必須**餵真實 alpha 輪廓(mesh 頂點 / atlas/PSD alpha)，**不可**餵 bbox。
2. 頭誤差最小(1.4px):頭是小件、與軀幹的 overlap 乾淨局部；四肢誤差稍大但仍 <5% 對角線。
3. **只推「關節中心」**，不推子件初始旋轉/骨長度（那由骨鏈幾何另算，屬後續）。
4. 本器輸入是「已切件的世界輪廓」;切件本身由 S1/S4 產出。端到端串接
   (analyze/psd_slice 切件 → 世界置放 → 本器出 pivot → 寫回 Spine bones) 屬下一塊。
5. 樣本數小(單一機器人、3 關節)。**推廣需更多真值角色**（人形/多關節鏈）才能升 L3。

## 成熟度

- 評估器:對 Award 真值 + 負對照雙向驗證可信 → **就緒**。
- 生成/推斷能力:單資產 3 關節 PASS → **L2**（尚缺跨角色推廣與端到端串接 → 未達 L3、未 skill 化）。
- 下一步:(a) 端到端接 build_spine（件世界置放 → 推 pivot → 寫 bones 樹 + 子件 local 座標）；
  (b) 多角色真值推廣（人形鏈,可用 main_draw 骨架反推自身件做二號真值）；
  (c) pivot→骨鏈(每子骨 local x,y = pivot 相對父骨、rotation 由件主軸)。
