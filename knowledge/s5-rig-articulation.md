# S5 — 接觸縫 pivot 寫入 build_spine 的關節鏈(端到端 articulated rig)

> 里程碑 2026-08-29(續 `s5-rig-pivot-inference.md`)。把 S5 首個能力(接觸縫 pivot 推斷)
> 從「孤立推斷」推進到「**寫進實際產出的可載入 Spine rig**」——路線圖 L3 要求的其中一半(接 build_spine)。
> 工具:`tools/analyzer/build_spine.py --rig`、閘 `tools/rig/validate_rig.py`。圖 `figures/s5_rig_articulation.png`。
> 一鍵驗證:`python3 tools/rig/validate_rig.py`(exit 0 = PASS)。

## 做了什麼

`build_spine` 原本把**每件都綁 root、骨放件中心**(無關節鏈,旋轉任一件都繞件中心轉,關節會散開)。
新增 `--rig`:依分析器 `#2` 的 `struct_role` 建**運動學父子樹**,並把 S5 接觸縫 pivot 寫成骨原點:

- **樹**:`body` = 子 rig 根(掛 root);`head`/`limb` = 掛 `body`;特效件/其他 = 掛 root(不 articulate)。
- **關節 pivot**:對每個 (parent, child) 用 `infer_pivots.contact_seam_joint`(父子件世界輪廓的接觸縫質心)。
- **骨**:子骨 `parent = 父件骨`,位置 = `關節 − 父骨世界位置`(骨原點落在關節)。
- **attachment 補償**:骨從件中心移到關節後,region 加 `(x,y)=件中心−關節` 偏移、unweighted mesh 頂點整體平移同量
  → **setup pose 世界位置完全不變**(只改 rig 結構,不改外觀)。
- 產物多一份 `rig_meta.json`(每關節:parent_bone / role / joint_world)。

座標關鍵:所有骨 rotation=0、無 scale,故「世界位移 == 局部偏移」,補償是單純平移。父骨世界位置在
topo 序(父先於子)逐一算出;body 為根時父世界位置 = body 件中心。

## 自我品質閘 `validate_rig.py`(4 AC,以 plain build 當負對照)

| AC | 內容 | 結果(robot) |
|---|---|---|
| **R0 可載入/topo** | JSON 可解析、每骨 parent 排在其前(Spine 可安全逐骨算 world) | **PASS** |
| **R1 setup 不變** | 每件 articulated 世界中心 == plain 世界中心 < 0.5px | **PASS**:max **0.000px**(Symbol_Ww 跨 genre 亦 0.005px) |
| **R2 pivot=關節** | 子骨旋轉 θ=35°(閘用 30°)時關節點位移:articulated≈0、plain 甩開 | **PASS**:rig **0.000px** vs 負對照 **25.9~85.0px** |
| **R3 樹符語意** | head/limb 掛 body、body/特效 掛 root,與 struct_role 一致;且 ≥2 關節 | **PASS**:3 關節(頭/左手/右手→身體),光暈/身體→root |

R2 是核心:**關節是否為旋轉不動點**,直接證明 pivot 放對——與 plain(骨在件中心 → 旋轉繞件中心 →
關節被甩離身體 26–85px)形成內建負對照,鑑別力乾淨。準度 vs 藝術家真值由姊妹閘 `validate_pivots`
(同一 `contact_seam_joint`、11~25px)保證,本閘不重複。

## 關鍵性質:`--rig` 永不破壞 setup pose(跨 genre 穩健)

setup 不變是**構造保證**(偏移補償),非湊出來:robot max 0.000px、Symbol_Ww(slot_reveal,16 件)max
0.005px(僅四捨五入)。故 `--rig` 是安全的可選升級——即使 genre 的 `struct_role` 語意鬆散(如 symbol
把裝飾件判成 limb,建出 16 條「關節」),也只改 rig 結構、素材外觀分毫不動;是否 articulate 是使用者選擇。
`validate_build`(舊靜態 round-trip 閘)**不適用** articulated rig(它用骨位當件中心、忽略 attachment
偏移)——articulated 一律用 `validate_rig`。

## 誠實界定 / 仍缺(區塊維持 HOLD,未達 skill 化)

- **`spine-rig-pivot` 區塊仍 HOLD**:`rig_end2end` 已達 **L2 GREEN**(端到端串成 + 一鍵閘),但 L3 需
  「對**多個真實標的**穩定通過」,目前僅 **robot 一條 rig**。
- **多 rig 真值阻塞(資產結構)**:Award 只有 robot 被拆件(`機器人拆件/*` 5 slot 對 5 骨);其他角色
  `OMG`/`superwin`/`megawin` 皆為**整圖單 slot 掛在角色根骨**(骨鏈 `1_OMG2..5` 等雖在,但無分件
  attachment)→ **無 part-to-part 接觸縫可推**。達 L3 需外部提供多角色**拆件** PSD/spine。
- 父子樹目前取自 `struct_role` 先驗(非本器推肢體拓樸);weighted mesh 件當關節子件尚未支援(robot
  的 head/hand 皆 region;body 為根,不受影響)。
- 軸向精修 / 手感偏移 = 美術(RULES A 類),不在此閘。
