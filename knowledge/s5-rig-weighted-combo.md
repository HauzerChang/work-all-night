# S5 (d) — `--rig` × `--weighted` 併用(weighted mesh 接進關節鏈)

> 里程碑 2026-08-31(session 002)。此前 `build_spine` 的 `--rig`(pivot→bone 關節鏈)與
> `--weighted`(骨綁 mesh + 自動控制骨)**互斥**(併用直接 `SystemExit`)。本次移除該限制,
> 讓 weighted mesh 的控制骨**接進 rig 關節鏈**,產出「能被關節articulate、又能局部 weighted 變形」的素材。
> 工具:`build_spine.py --rig --weighted`、閘 `tools/analyzer/validate_rig_weighted_build.py`(exit 0 = PASS)。

## 結論

- **併用是乾淨的座標問題,非演算法衝突**:weighted 的控制骨原本掛 `root`(絕對世界座標);
  rig 併用後改掛**該件的關節骨 `b_{nm}`**,座標轉為**相對關節骨的局部座標**(local = 控制骨世界 − 關節骨世界)。
- **setup pose 完全不變(逐頂點 0.00px)**:setup 下整條父鏈皆純平移 → 控制骨的世界位置不變 →
  weighted bind 偏移**完全不用改**(partition-of-unity 重建仍精確)。只有骨的父子關係與局部座標變了。
- **收益 = weighted 件真正接進關節鏈**:關節骨(或其祖先)旋轉時,控制骨連同整片 weighted mesh
  沿鏈**剛性帶動**;同時控制骨自身仍可局部變形 mesh。兩種能力疊加,互不犧牲。
- **信心**:高(對唯一真實可拆肢體 rig 4 AC 全 PASS + 內建負對照 weighted-only 版位移=0 具鑑別力)。相關階段:S5 / S3。

## 實作(`build_spine.py`)

1. 移除 `if rig and weighted: SystemExit` 互斥守則。
2. `_weighted_attachment(...)` 新增 `parent_bone`(預設 "root")+ `parent_world`(預設 None):
   - 控制骨 `parent = parent_bone`;座標 `x,y = 控制骨世界 − parent_world`(None 時退化為絕對世界=原行為)。
   - **weighted bind 偏移不動**(仍 = 世界頂點 − 控制骨世界)→ setup 精確。
3. 主組裝迴圈:`use_mesh and weighted` 時,若 `rig` 則以 `parent_bone=b_{nm}, parent_world=wo[nm]`
   (該件關節骨世界原點)呼叫;否則沿用舊行為(掛 root)。
4. 非 mesh 結構件仍走 rig 的 delta 位移路徑(不受影響);region/unweighted-mesh/effect 全兼容。

## 為何 setup 不位移(數學)

Spine `computeWorldVertices`:`worldVertex = Σ_j w_j · boneWorld_j.transform(bind_j)`。
setup 下父鏈無旋轉/縮放 → `boneWorld_ctrl_j` 只是把控制骨平移到其世界原點 `P_j`。
- 掛 root:控制骨局部 = `P_j`(絕對);world 原點 = `P_j`。
- 掛 `b_{nm}`(世界原點 `J`):控制骨局部 = `P_j − J`;world 原點 = `J + (P_j − J) = P_j`(不變)。
兩者控制骨世界原點都是 `P_j` → `boneWorld_ctrl_j` 相同 → `bind_j = 頂點世界 − P_j` 不變 → 重建相同。
**故改父子關係只影響「動起來怎麼帶」,不影響 setup。**

## 四道校驗(`validate_rig_weighted_build.py`,對 Award 機器人 PSD `robot_parts`)

以 rig×weighted 版與 weighted-only 版同時 build,逐項比對:

| 校驗 | 內容 | 結果 |
|---|---|---|
| **AC1 結構** | 每個 weighted 件控制骨 parent == 該件關節骨 `b_{nm}`;rig 樹完好(子件掛 body、body 掛 root);骨 index 合法 | **PASS**(光暈控制骨→b_光暈、身體控制骨→b_身體) |
| **AC2 setup 不位移** | rig×weighted 逐頂點世界座標 == weighted-only 版 | **PASS**:max_dev = **0.0000px** |
| **AC3a 自articulate** | 轉件關節骨 `b_{nm}` 25°:rig 版件會動、weighted-only 版件不動(控制骨掛 root,`b_{nm}` 只是 slot 骨) | **PASS**:光暈 rig 72.0 vs flat 0.0px;身體 rig 53.1 vs flat 0.0px |
| **AC3b 鏈帶動** | 轉 rig 根 `b_身體` 25°:rig 版子 weighted 件(光暈)隨父件帶動;weighted-only 版光暈掛 root → 脫鉤不動 | **PASS**:光暈 rig 73.9 vs flat 0.0px |
| **AC4 變形乾淨** | 上述關節旋轉逐幀 si/flip:結構件硬性=0、effect additive 容忍 | **PASS**:身體(structural) si=0/flip=0、光暈(effect) si=0 |

- **內建負對照 = weighted-only 版**:同一 weighted mesh 掛 root 時,轉關節骨/根骨對它**完全無效(位移=0)**
  → 證 rig 版的位移是「真的接進了關節鏈」,非度量假象。這也是 AC3 的鑑別力來源。
- **真相來源**:build_spine 確定性組裝 + Spine 3.8 bone world transform(`weighted_deform_eval`,已對 Award 真值重現)。純 CPU、無瀏覽器。

## 界定 / 下一步

- **honest boundary — 此資產的 weighted 結構子件是空集**:robot_parts 的 weighted mesh 只有 `身體`(rig 根)
  與 `光暈`(effect);結構肢體子件(頭/左手/右手)是 **region 件**(非 mesh)→ 沒有「weighted mesh 當結構肢體
  中段」的真實案例。故 AC3b 的「鏈帶動」以 effect 光暈(掛 body 下)驗證父→子耦合;更深的多跳 weighted 肢體鏈
  需**新的分層素材**(使用者資源,同 pivot_end2end 的多 rig 缺口)。
- **多跳關節鏈**:演算法(控制骨掛任意深度關節骨)天然支援 2+ 跳;`infer_tree` 也已驗多跳拓樸(見
  `s5-limb-tree-inference.md` AC4 合成鏈)。缺口純為「真實多跳 weighted 肢體鏈真值」。
- `spine-rig-pivot` 區塊**仍 HOLD**:新增 cap `rig_weighted_combo` L2 GREEN,但 L3 硬缺口(多 rig 真值)不變。
  併用能力補齊了「rig 與 weighted 兩條線的整合」,但未新增真值 rig,遵守防固化。
- 軸向精修 / 緩動手感仍屬美術(RULES A 類)。
