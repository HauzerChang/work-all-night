# S5 — pivot→bone 父子樹寫入 build_spine(`--rig`)

> 里程碑 2026-08-30。S5 脫離 HOLD → L3 的**第二個要件**(第一件=接觸縫 pivot 準度,見
> `s5-rig-pivot-inference.md`)。把「關節=父子件接觸縫」的推斷**接進 `build_spine`**,
> 讓產出的 Spine 素材帶**真正的骨骼關節鏈**(不再每件綁 root),且關節落在解剖正確的縫上。
> 工具:`tools/analyzer/build_spine.py --rig`、`tools/analyzer/validate_rig_build.py`。
> 圖:`figures/s5_rig_build.png`。一鍵:`python3 tools/analyzer/validate_rig_build.py`(exit 0 = PASS)。

## 做了什麼

`build_spine` 原本把每個件的 bone 都 `parent=root`、置於件中心(無關節、動起來會整片剛體平移)。
新增 `--rig`:

1. **父子樹**(確定性,來自分析器 `note` 先驗):`結構件/body` = rig 根;`結構件/head`、
   `結構件/limb` = body 的子件;`特效件` 掛 body 下但**不視為關節**(原點=件中心)。
   無 body 註記時取最大結構件為 body。
2. **關節落點**:結構子件的 bone 世界原點 = `infer_pivots.contact_seam_joint(body輪廓, 子件輪廓)`
   (子件最靠近 body 的 q=0.2 分位點質心)。特效件原點=件中心。
3. **座標換算**:bone 為相對父骨的局部座標 → `local = 關節世界 − 父骨世界`(setup 下父骨無旋轉/縮放)。
   bone 陣列以**階層序**輸出(body → 關節子件 → 特效件),確保父必先於子。
4. **保 setup pose**:bone 原點從件中心移到關節後,attachment 以 `delta = 件中心 − bone原點`
   位移補回(region 設 `att.x/y=delta`;unweighted mesh 每頂點 `+delta`)→ 畫面完全不動。

`build_meta.json` 每件補 `bone_parent` / `joint` / `role`;summary 回 `rig_root` + `rig_joints`(世界座標)。
⚠️ **`--rig` 暫不與 `--weighted` 併用**(weighted 控制骨父子樹整合列為後續),同下時直接 `SystemExit` 拒絕。

## 四道校驗(`validate_rig_build.py`,對 Award 機器人 PSD `robot_parts`)

以 `--rig` 版與 `--rig` 關掉的**非 rig 版**同時 build,逐項客觀比對:

| 校驗 | 內容 | 結果 |
|---|---|---|
| **AC1 骨樹結構** | 結構子件 bone `parent==b_body`、body `parent==root`、特效件亦掛 body 下 | **PASS** |
| **AC2 setup 不位移** | 每件世界點雲(mesh 頂點/region 4 角)rig vs 非 rig 逐點吻合 | **PASS**:max_dev = **0.0000px** |
| **AC3 pivot 安裝往返** | 子骨世界原點(經 local↔parent 換算後重算)== 推斷的接觸縫 pivot | **PASS**:max_dev = **0.042px**(僅座標四捨五入 2dp 誤差) |
| **AC4 關節語意** | 轉子骨 25° 時「父子接觸縫點集」的位移:rig(繞縫)<< 非 rig(繞件中心) | **PASS**:min ratio **2.1×**(頭 3.2× / 左手 2.8× / 右手 2.1×) |

- **真相來源**:接觸縫 = `infer_pivots`(已對藝術家真值驗過);bone world transform = `weighted_deform_eval`
  (已對 Award 真值重現 Spine 3.8 transform)。純 CPU、無瀏覽器。
- **AC4 用真實 art 輪廓**(非 region bounding-rect):右手 region 是大框但 alpha 僅 16% 填滿,用 4 角當
  縫點會失真(踩過:corner 版右手 ratio 掉到 1.0)→ 改從件 alpha 取真輪廓、取 q=0.2 接觸縫集。
- **AC4 門檻 2.0×(縫運動至少減半)**是原則性上界,非湊數:右手接觸縫**解剖上本就寬**(整條手臂基部貼
  身體),故它的改善 2.1× 天然低於頭/左手的 3×;3 件全部清 2.0×。
- **非 rig 版即 AC4 的負對照**(關節放件中心 → 縫撕裂大);rig 版一致地更好。

## 意義 / 界定

- **S5 第二 L3 要件達成**:pivot→bone 樹已端到端接進 build_spine,產出帶正確關節鏈的可載入 Spine。
  `check_readiness` 中 `spine-rig-pivot` 的 `pivot_end2end` 由 **L0 → L2 GREEN**。
- **區塊仍 HOLD(未 L3)——誠實界定**:L3 需「對**多個**真實標的穩定通過」,但 **Award 只有一個可拆肢體 rig**
  (見下方發現),第二個真值 rig 屬**使用者資源**(A/資源類),故 `pivot_end2end` 定 L2 而非 L3,區塊維持 HOLD。
  這遵守防固化規則(生成器/pipeline 未達 L3 不打包 skill)。
- **父子樹目前取自分析器 note 先驗**(body/head/limb),非本器推;肢體拓樸自動推斷是另一子問題。
- **軸向精修 / 手感**仍屬美術(RULES A 類),不在此閘。

## 關鍵發現:Award 只有一個可拆肢體 rig(recalibrate STATE 的多 rig 建議)

STATE 曾建議用 Award 其他角色鏈 `1_OMG`/`2_SUP`/`3_MEG` 取多 rig 真值。實查 Award 47 slots / 77 bones 後:

| rig | 根骨 | 內容 | 可拆肢體? |
|---|---|---|---|
| `4_LEG`(機器人) | 4_LEG3 | 身體/頭/左手/右手 各綁獨立子骨(4_LEG3/4/5/6)+ 光暈/劍特效 | **✅ 唯一** |
| `1_OMG` | 1_OMG | `OMG角色`單張 + 小燈1..9(特效粒子,各自骨) | ❌ 單圖+特效 |
| `2_SUP` | 2_SUP | `superwin_角色`單張 + 光暈03/04 | ❌ 單圖+特效 |
| `3_MEG` | 3_MEG | `megawin角色1/2`(皆綁 3_MEG,未拆)+ 光暈05/眼睛光暈 | ❌ 單圖+特效 |

- 其餘三角色是**整張角色圖 + 發光/小燈特效**,沒有「肢體父子件 + 接觸縫」結構 → 無法作為接觸縫 pivot 的真值。
- 這也解釋了原始 S5 為何選機器人:它是 Award 中**唯一**被藝術家拆成多肢體並各給 pivot 的件。
- **結論**:多 rig 真值需**新的分層/已 rig 素材**(使用者提供),不在現有 assets 內。→ 已回報為資源類待辦。

## 下一步(要達 L3 / 完全脫離 HOLD)

1. **多 rig 真值**(唯一硬缺口,資源類):第二個含多肢體接觸縫 + 藝術家 pivot 的真實 rig(使用者提供分層/rig 檔)。
2. 肢體父子樹**自動推斷**(目前取自先驗 note):由拆件相鄰圖 + 運動分群推父子關係。
3. `--rig` × `--weighted` 併用:weighted 控制骨的父子樹整併進關節鏈。
4. 多層關節鏈(目前只做 body→子件一層;手→前臂→手掌等 2+ 跳鏈需遞迴接觸縫)。
