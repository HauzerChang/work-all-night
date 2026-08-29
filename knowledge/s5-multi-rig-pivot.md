# S5 — 多 rig pivot 泛化:推斷方法必須對應資產表徵

> 里程碑 2026-08-29(承接同日「rig pivot 首個能力」)。把「pivot 推斷只在單一 rig(Award 機器人)
> 驗過」的 L3 阻塞拆掉。工具:`tools/rig/multi_rig.py`、`tools/rig/validate_multi_rig.py`。
> 圖:`figures/s5_multi_rig_pivot.png`。一鍵:`python3 tools/rig/validate_multi_rig.py`(exit 0 = PASS)。

## 動機

`infer_pivots.py` 的接觸縫演算法只在 Award **機器人 rig**(`機器人拆件/*`,拆件式:每骨一個 slot、
件之間有真實幾何空隙)驗過 3 關節。要脫離 HOLD 需多 rig 真值。Award 另有三個角色可用:
OMG(`1_OMG`)、SUPERWIN(`2_SUP`)、MEGAWIN(`3_MEG`,兩張圖 `megawin角色1/2`)。

**但它們不是拆件式**:各自是**單一 weighted mesh**,由一條骨鏈以權重變形,沒有「每件一個 slot」。
要在其上驗證 pivot 推斷,必須先把「每根骨控制的隱含件」從 weighted mesh 還原出來。這一步逼出本session
的核心發現。

## 核心發現:一個演算法不通吃兩種資產表徵

| 資產表徵 | 幾何特徵 | 關節資訊在哪 | 正確方法 | 實測 |
|---|---|---|---|---|
| **拆件式**(separated parts;PSD 分層 / robot slot-per-part) | 件之間有真實空隙 | 子件 ⇄ 父件**幾何接觸縫** | `contact_seam_joint`(幾何法) | robot 3 關節 err 2–5% 軀幹尺度 ✅ |
| **單一 weighted mesh**(連續網格,骨以權重共享頂點) | 件之間**無**幾何縫 | **權重混合**(子骨近端邊) | `proximal_joint`(權重法) | 3 角色 19 關節 pooled 中位 0.034、84% <0.10 ✅ |

**為什麼幾何法在連續 mesh 上會爆(手臂實測 95–113px)**:對單一 mesh 做 dominant-weight 硬切,肩部頂點
會被分給手臂骨(權重較高),父骨(軀幹)的隱含件只剩下腹部核心。於是「子件(手臂)最靠近父件(腹部)的點」
落在**手肘/手掌**(幾何最近),而非**肩關節**——關節被錯放到末梢。連續 mesh 的件邊界是模糊的權重過渡,
不是幾何空隙,幾何最近點失去意義。

**權重法(proximal_joint)**:關節落在**子骨的近端邊**——子骨自有頂點中「父骨影響最強」處。取
`s = w_child² · w_parent` 的頂點加權質心:`w_child²` 讓估計留在子件側(=近端邊,不被父件本體拉走)、
`× w_parent` 拉向與父件相鄰的接合緣。純幾何質心(baseline)反而被子件遠端(末梢)拉偏。

> 這是專案反覆出現的教訓「**方法要配合輸入表徵**」在 rig 階段的第三次再現
> (前兩次:S3「靜態 IoU ≠ 變形穩健」、S5 首版「pivot 準度 = 件輪廓保真」)。

## 四道 AC(對 Award 3 weighted 角色 + 合計 robot)

尺度正規化 = 各角色 mesh bbox 對角線;TAU=0.10。細節骨(dominant 頂點 <3,如 `2_SUP10/11/12`)如實排除。

| AC | 內容 | 結果 |
|---|---|---|
| **AC1 準度** | proximal 誤差/尺度 中位 <0.05 且 ≥80% <0.10 | **PASS**:中位 **0.034**、**84%**(16/19)<0.10 |
| **AC2 勝 baseline** | proximal 中位 < 子件 dominant 質心 baseline 中位 | **PASS**:0.034 < 0.069 |
| **AC3 負對照** | 隨機 pivot、swap(估計配到別關節真值)皆爆閘 | **PASS**:random 中位 0.33(0% <0.10)、swap 中位 0.26(≤11% <0.10) |
| **AC4 泛化** | robot 拆件式幾何法全過 + 4 weighted rig 皆有通過關節 + pooled ≥80% | **PASS**:**5 rig** 泛化(robot max 0.051 + 每角色 ≥1 過 + pooled 0.84) |

## 誠實限制(仍 HOLD,未達 L3 skill 化)

- **硬案例 = 連續網格上的外張肢體**:3 個 fail(`OMG/1_OMG4` 0.114、`OMG/1_OMG5` 0.122、`MEG1/3_MEG7`
  0.169)全是「從軀幹向外張開的手臂」。權重過渡在這類拓樸較寬、且近端頂點稀疏,`w_child²·w_parent` 質心
  被子件本體略微下拉。緊湊軀幹/串接鏈(SUP 8/8、MEG2 3/3)幾乎全準(多在 1–5% 尺度)。屬**已知限制,不硬性 fail**;
  軸向精修本就是美術(RULES A 類)。
- **權重法需要 rig 權重**:對「已是 weighted mesh」的資產,關節其實已存在(骨本身)——權重法是**獨立交叉驗證**,
  證明「若只給 mesh+權重也能還原藝術家關節」;真正的生產缺口(從**無骨的拆件**推 pivot)仍走幾何法(拆件式)。
- **端到端未接**:`pivot_end2end`(pivot→bone 父子樹寫入 `build_spine`)仍 L0 → `spine-rig-pivot` 區塊
  維持 **L2 HOLD**(check_readiness 實跑確認:多 rig 已 GREEN,但無 ≥1 L3)。達 L3 = 接 build_spine 寫骨樹。

## 下一步(通往 L3 → 脫 HOLD)

1. **pivot→bone 父子樹寫入 `build_spine`**:目前 build_spine 把每件綁 root(無關節鏈)。用推斷的 pivot
   把件重新 parent 成骨鏈、設 bone `x/y` = pivot,產出真正「可依關節旋轉」的 rig。這是最後一哩、達 L3 的關鍵。
2. 肢體父子樹**自動推斷**(目前 tree 取自 `genre_priors`/分析器);外張肢體硬案例可加「近端邊 + 骨鏈方向先驗」修正。
