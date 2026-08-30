# S5 — rig pivot 推斷器(第一版:關節=父子件接觸縫)

> 里程碑 2026-08-29。S5(骨架半自動,路線圖標記的「唯一卡死環節」)的**首個能力**。
> 工具:`tools/rig/infer_pivots.py`(推斷器 + Award 真值 loader)、`tools/rig/validate_pivots.py`(自我品質閘)。
> 圖:`figures/s5_pivot_inference.png`。一鍵驗證:`python3 tools/rig/validate_pivots.py`(exit 0 = PASS)。

## 問題界定(把「卡死環節」切出可客觀化的一塊)

S5 整體(運動 → 骨架 + 每骨 pivot)含**美術決定**,PLAN 標為唯一真正卡死處。但其中有一塊
**可客觀驗證**:給定已拆件幾何(各件 mask/polygon,置於同一 composite 世界座標)+ 運動學父子樹
(誰是誰的子件,由 S1 分析器 / `genre_priors` 提供),**推斷每根子骨的關節 pivot 落點**。

本器只解這塊,並明確界定**不解**的部分:
- ✅ 可客觀:**關節位於「子件與父件的接觸縫」**(shoulder / neck / hip 皆在此)。
- ❌ 屬美術微調(RULES A 類,留使用者):pivot 沿肢體軸的精確落點、為手感刻意偏離接觸縫幾像素。
  → 本器輸出接觸縫質心作為**草案 pivot**,人再微調。

## 演算法(deterministic contact-seam,純 CPU 無 ML)

對每個 (parent, child) 部位對:
1. 取兩件世界點雲(mesh → hull 世界頂點;region → 由 atlas alpha 取真實輪廓,見下)。
2. 對每個 child 點,算到 parent 點雲的最近距離 d。
3. **接觸縫** = d 落在最小 q 分位(預設 q=0.2)的 child 點集合。
4. **joint = 接觸縫質心**。重疊件(child 點落在 parent 內,d=0)自然給出「肩內」pivot,仍合理。

## 真值 + 四道校驗(對 Award 機器人 rig)

真值 = Award.json 機器人子 rig 的骨世界位置(藝術家親手放的 pivot):
身體=`4_LEG3`(子 rig 根)、頭=`4_LEG4`、左手=`4_LEG5`、右手=`4_LEG6`。
以軀幹(父件)bounding box 對角線 **494.6px** 作尺度正規化,TAU=0.10。

| 校驗 | 內容 | 結果 |
|---|---|---|
| **AC1 準度** | 每關節 err/軀幹尺度 < 0.10 | **PASS**：頭 0.044(22px)、左手 0.021(11px)、右手 0.051(25px);max 0.051 |
| **AC2 勝 baseline** | contact-seam 中位誤差 < 「用子件質心當 pivot」中位 | **PASS**：21.6px < 43.0px(左手尤甚:11px vs 110px) |
| **AC3 負對照** | (a) 隨機 pivot、(b) 關節互換 皆爆閘 | **PASS**：random 0.476、swap 0.276(皆 >> 0.10) |
| **AC4 輸入保真依賴** | 用粗略 bounding-rect 代理應爆閘 | **PASS**：rect max 0.820 vs alpha 0.051 |

## 關鍵發現:pivot 推斷品質 = 件輪廓保真(PSD-first 論點在 rig 階段再現)

- Award 的 5 件中,身體/左手/光暈是 **mesh**(真實 hull),頭/右手是 **region**(只有 bounding rect)。
- **只用 region 4 角 → 右手誤差 406px(0.82 軀幹尺度)慘爆**:右手 region 是 597×486 大框但 alpha 僅
  16% 填滿(機器人手+劍外伸),bounding rect 質心/角點嚴重偏離真實肩點。
- 改從 **atlas 頁裁真實 alpha 輪廓**(`infer_pivots._region_world_silhouette`,套 0.70 打包縮放 + region
  rotation + bone world)後,右手 **406→25px**、頭 **66→22px**。
- 結論:**接觸縫演算法本身是對的(左手 mesh 直接 11px);失敗全來自輸入輪廓粗糙**。
  這正是專案反覆出現的教訓「改輸入契約(要 mask/分層 PSD)比硬攻演算法划算」在 **rig 階段的再現**。
  → 生產時各件輪廓應來自 PSD mask / mesh hull,而非 atlas bounding rect。

## 誠實限制 / 下一步(仍 HOLD,未達 skill 化)

- 只在**單一 rig(robot,3 關節)** 驗過;`check_readiness` 中 `spine-rig-pivot` 區塊
  **L2 → HOLD**(端到端 cap 仍 L0)。達 L3 需:(a) 多個 rig 真值(如 Award 其他角色 `1_OMG`/`2_SUP`/`3_MEG` 鏈);
  (b) 把 pivot→bone 父子樹**寫入 `build_spine`**(目前 build_spine 把每件綁 root,無關節鏈)。
- 父子樹目前**取自分析器/先驗**(非本器推;肢體拓樸推斷是另一子問題)。
- 軸向精修 / 手感 = 美術(A 類),不在此閘。
- 對非人形 / 無 mesh 真值的件,接觸縫仍需輪廓保真(同上)。

---

## 里程碑 2 (2026-08-30):接觸縫 pivot 寫入 `build_spine` 骨鏈(整合閘 L2)

延續里程碑 1(pivot 推斷器對 Award 真值 4 AC 全 PASS),本次把**推斷出的關節真正嵌進可載入的 Spine 骨階層**——
S5 從「算得出 pivot」進到「素材的骨鏈就綁在關節上」,通往 L3 的關鍵整合步。

### 做了什麼

- **`build_spine.py --rig`**:結構件不再全部平掛 `root`。改為:
  1. `infer_rig_tree`:結構件中**不透明像素面積最大者為 root**(通常軀幹);其餘結構件為其子(star 先驗)。
     ⚠️ 用 alpha 像素面積(非 bbox)—— 否則「大框但稀疏」的件(如機器人右手 597×486 但僅 16% 填滿)會被誤判為最大。
  2. 對每個結構子件,以 `contact_seam_joint`(里程碑 1 的算法)算關節,把**子骨掛到父件骨下、pivot 設在關節**。
  3. **attachment 偏移補償**:pivot 從件中心搬到關節後,region 用 `att.x/att.y`、unweighted mesh 平移頂點,
     使靜態外觀(件影像中心世界座標)**完全不變**。
  4. rig 重親後 z 序可能讓子骨排在父骨前 → **拓樸排序** bones 陣列(Spine 要求 parent 先於 child)。
  - weighted mesh 走控制骨,不套 rig 關節(已由 weighted-forge 處理);effect 件(光暈)維持平掛 root。

- **`tools/rig/validate_rig_build.py`**:整合閘,4 AC(對 `robot_parts.psd`,star 先驗:身體=root,頭/左手/右手=子):

| AC | 內容 | robot 結果 |
|---|---|---|
| **AC1 素材不位移** | rig build 每 slot 解算影像中心 == flat build 件中心 | **PASS** max 0.0px(完全不動) |
| **AC2 pivot 落關節** | 每子骨世界位置 == 重算接觸縫關節、父子掛接正確 | **PASS** max 0.005px |
| **AC3 繞關節旋轉** | 旋轉子骨 25°:接觸縫位移 rig(繞關節)<< centroid(繞件中心),且末梢確有位移 | **PASS** seam_ratio 0.31–0.47、末梢動 0.09–0.47 |
| **AC4 負對照** | centroid pivot 偏離關節 >10% 尺度、關節互換偏離自身真值 → 皆爆閘 | **PASS** centroid 0.33、swap 破 |

一鍵驗證:`python3 tools/rig/validate_rig_build.py`(exit 0 = PASS)。

圖 `figures/s5_rig_build.png`:左=接觸縫關節作骨階層(● pivot 落在 × 重算縫上,■ root=身體);右=旋轉左手 25°,rig 繞關節(綠,縫錨在關節、肢體從肩甩出)vs flat 繞件中心(紅,整件連縫一起甩、脫離身體)。

### 關鍵發現:整合閘有鑑別力 —— 拒絕非關節式角色(Symbol_Ww)

同一 `--rig` + 閘跑 `Symbol_Ww.psd`(18 層裝飾符號:文字/光暈/鬢角/耳機…):
**AC1/AC2/AC4 PASS,但 AC3 FAIL(16 子件僅 6 過)**。這是**正確**行為,非 bug:
- Symbol_Ww 不是**有關節的角色**,是裝飾件拼盤;star 先驗硬把 16 件掛到「頭」下,但它們彼此重疊/各自獨立,
  **沒有真正的肢體接觸縫**,繞「星狀關節」旋轉不像關節在轉(seam_ratio 0.62–0.93,遠高於 robot 的 0.3–0.47)。
- → 閘沒有橡皮圖章:它只在**真的有接觸縫的 articulated rig** 上放行。
- **能力界定**:`build_spine --rig` + 接觸縫 pivot 適用於**單角色 articulated rig**(robot ✅),
  不適用於裝飾符號拼盤。star 先驗本身的適用性也被閘量化把關(AC3)。

### 誠實界定 / 為何仍 L2 HOLD(未達 L3)

- ✅ 完成子問題 (b)「pivot→bone 父子樹寫入 build_spine」——`pivot_end2end` L0 → **L2**(pipeline 已接 + 單 rig 整合閘 GREEN)。
- ❌ 子問題 (a)「多個 articulated rig 真值」**被素材阻擋**:Award 中**只有 robot 一組已拆多件 rig**;
  `1_OMG`/`2_SUP`/`3_MEG` 經查為**單 slot 角色**(子骨只驅動小燈/光暈特效,無 per-part 美術件)→ 無接觸縫真值。
  → 達 L3 需**更多已拆件的 articulated rig 素材**(使用者資源決策,RULES A/資源),**非演算法問題**。
- 父子樹仍取自 star 先驗(非幾何推肢體樹);完整肢體拓樸推斷是另一子問題。
- 軸向精修 / 手感 = 美術(A 類),不在此閘。
