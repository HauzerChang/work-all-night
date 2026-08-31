# S5 (d') 多跳 weighted 肢體鏈端到端驗收(2026-08-31 session 003)

## 一句話

補上 `--rig × --weighted` 併用先前唯一的 honest-boundary 缺口:**weighted mesh 當作鏈中段肢體**
(既是某件的子、又是另一件的父)在真實資產無樣本。用合成多跳鏈 fixture 端到端驗證
`build_spine --rig --weighted`,**5 AC 全 PASS**,證明遞迴接觸縫 + 控制骨掛關節骨的機制
在 2+ 跳鏈上確實成立。演算法早已支援,本次是**填補驗收覆蓋率**(非新演算法)。

## 為什麼需要合成 fixture(缺口的性質)

真實資產 `robot_parts`(Award 機器人)的可拆肢體(頭/左手/右手)有兩個限制:
1. **都是 region 件**(非 mesh)→ 不會成為 weighted mesh;
2. **都直掛 body**(星形 / 單跳,見 `infer_tree` 對它的真值樹)。

它唯一的 weighted mesh 是 **body(rig 根)+ 光暈(effect,掛 root)**。因此:
- 「**weighted mesh 同時是某件的子件、又是另一件的父件**」這個案例**無真實樣本**;
- session 002(`s5-rig-weighted-combo.md`)的 AC3b 只能用 effect 光暈驗「父→子一跳耦合」,
  無法驗「**結構 weighted 件的多跳遞迴帶動**」。

→ 依 RULES「無真實資產時用合成 fixture 驗 pipeline」,造一條乾淨的運動學鏈補覆蓋率。

## 合成 fixture:`tools/mesh_gen/make_limb_chain_psd.py`

一條 4 件的鏈 `body → arm → forearm → hand`(360×320 canvas,實心銳邊純色塊):

| 件 | 佈局用意 | 分析器判定 |
|---|---|---|
| **body** | 最大面積(25200)→ `infer_tree` 取為 root | struct/body、mesh(coverage 0.55) |
| **arm** | 與 body 右上角重疊、往右上延伸 | struct/limb、**mesh**(coverage 0.39)→ weighted |
| **forearm** | 與 arm 左上重疊、折回左上遠離 body | struct/limb、**mesh**(coverage 0.38)→ weighted |
| **hand** | 與 forearm 左端重疊、更遠;小件 | struct/limb、**region**(coverage 0.08)→ 葉件 |

**幾何刻意安排**:只有相鄰件重疊(接觸距離 0)、非相鄰件分離 → `infer_tree` 的
「接觸距離 Dijkstra 樹」recover 出**鏈**(而非星形)。實測拓樸:
`body → arm → forearm → hand`(鏈深 4)。

**踩雷**:
- **PSD 寫檔用 mac_roman 編碼 pascal string,CJK 圖層名會失敗** → fixture 用 ASCII 名
  (分析器 struct_role 關鍵字亦吃英文:`body→body`、`arm/hand→limb`、`forearm` 含 `arm`→limb)。
- 要讓件被判為 **mesh**(→ weighted),需 `coverage ≥ 0.15` 或 `soft ≥ 0.15`
  (見 `analyze_target.slicing_strategy`)。實心銳邊塊 soft≈0 → 靠 coverage;故肢體須夠大。
  此約束在小畫布上讓「鏈中非相鄰件不重疊」變緊,fixture 用對角折返佈局解決。

## 閘:`tools/analyzer/validate_rig_weighted_chain.py`(5 AC + 內建負對照)

對照組:`rig×weighted` build vs `weighted-only` build(同 PSD)。

- **AC1 鏈結構**:bone 父鏈為拓樸鏈(`b_hand→b_forearm→b_arm→b_body→root`,**鏈深 4 ≥ 3、非星形**);
  每個 weighted 件控制骨 `parent == 該件關節骨 b_{nm}`;骨 index 合法。→ PASS
- **AC2 setup 不位移**:rig×weighted 的 setup 世界頂點 == weighted-only 逐頂點,**max_dev 0.0000px**。→ PASS
- **AC3 遞迴帶動(核心收益)**:對每個驅動關節,**後代(含自身)weighted 件位移 > 門檻、
  祖先/旁支 ≈ 0;weighted-only 全脫鉤 = 0**(內建負對照)。實測(轉 25°,平均位移 px):

  | 驅動關節 \ weighted 件 | arm | body | forearm |
  |---|---|---|---|
  | 轉 **b_body**(rig 根) | 73.7 (D) | 39.3 (D) | **80.4 (D,隔 arm 一跳)** |
  | 轉 **b_arm** | 48.0 (D) | **0.0 (祖先不動)** | 67.6 (D) |
  | 轉 **b_forearm** | 0.0 | 0.0 | 48.2 (D) |
  | 轉 b_hand(葉) | 0.0 | 0.0 | 0.0 |

  weighted-only 版**全欄 = 0.0**(控制骨掛 root → 與關節鏈脫鉤)。**多跳驗證 = True**
  (轉 b_body,離它 2 跳的 forearm 確實隨動 80px 且 weighted-only=0)。→ PASS
- **AC3R region 葉件隨鏈**:追蹤 hand 的 attachment 世界代表點(骨原點 + 旋轉後局部偏移)。
  轉其祖先或自身(body 73.6 / arm 73.4 / forearm 70.4 / hand 自身 17.8px)皆動、旁支不動。→ PASS
  - 雷:**旋轉某骨不移動其自身原點**(只旋轉其子/attachment)→ region 葉件要看
    **attachment 的世界點**(`transform_point(bone_world, local_offset)`),非骨原點。
- **AC4 變形乾淨**:上述關節旋轉逐幀,3 個結構 weighted 件 **si=0 / flip=0**。→ PASS

**OVERALL PASS**(exit 0)。一鍵:`python3 tools/analyzer/validate_rig_weighted_chain.py`。

## 關鍵結論

- **併用機制對多跳鏈天然通用**:setup 下整條父鏈皆純平移 → 控制骨世界位置不變 →
  weighted bind 偏移不用改(setup 逐頂點 0.00px);動起來時,控制骨掛在該件關節骨上,
  沿**任意深度**的關節鏈剛性帶動 → 遞迴耦合免額外處理(同 session 002 的座標論點,深度無關)。
- **內建負對照雙軌**:①weighted-only 全脫鉤(證位移是真接進鏈,非度量假象);
  ②rig 版**非後代(祖先/旁支)不動**(證鏈**方向性**正確,非「全部一起動」)。二者同時成立才 PASS。
- **這不是新演算法,是覆蓋率**:接觸縫遞迴(`infer_tree` 多跳)+ 控制骨掛關節骨
  (session 002)早已實作;缺的只是「結構 weighted 件當鏈中段」的端到端樣本,今補齊。

## Honest boundary / 界定

- fixture 為**合成幾何**(非藝術家真值 rig)→ 驗的是「機制在多跳鏈上端到端成立」,
  **非**「推斷結果貼合某藝術家意圖」。後者仍需**真實多肢體分層素材**(使用者資源,
  同 `spine-rig-pivot` 的 L3 硬缺口:多 rig 真值)。故 `rig_weighted_chain` 定 **L2 GREEN**,
  區塊 `spine-rig-pivot` **仍 HOLD**(防固化,L3 缺口不變)。
- 肢體形變品質(緩動、體積保持)屬美術手感(RULES A 類),不在此客觀閘內。

## 檔案

- fixture:`tools/mesh_gen/make_limb_chain_psd.py`
- 閘:`tools/analyzer/validate_rig_weighted_chain.py`(復用 `validate_rig_weighted_build` 的
  `_load/_weighted_slots/_skin_setup/_pose_rotate` + `weighted_deform_eval` 的 world transform)
- cap:`check_readiness.py` → `spine-rig-pivot` 新增 `rig_weighted_chain` L2 GREEN(pipeline)
