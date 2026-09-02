# S5×S1 組合:rig 關節樹 × 生成主秀動畫 —— 關節接合閘(2026-09-02)

> 里程碑:證明 `build_spine --rig --animate` 把 **S5 關節樹**(接觸縫 pivot→bone 父子樹)與
> **S1 生成 timeline**(0d keyframe / 0f 主秀 beat)**組起來後,肢體真的繞關節擺、且黏在父件身上**。
> 並修一個潛伏的組合 bug(rig 下 In/Out 徑向方向算錯)。
> 工具:`tools/analyzer/validate_rig_anim.py`;圖 `knowledge/figures/s5_rig_anim_articulation.png`。

## 為什麼需要這個閘(補的缺口)

- `validate_rig_build`:只驗**單一固定角 θ=25°** 的接觸縫語意(靜態解析式 `|seam−pivot|·2sin(θ/2)`)。
- `validate_anim`:只驗**非 rig 扁平骨架**的動畫良構(In/Loop/Out 介面、無縫)。
- **都沒證明「兩者組起來」成立**:把 S5 骨樹 + S1 生成 timeline 疊在同一份 `skeleton.json` 後,
  整支生成動畫逐幀下,子件是否**繞關節**擺(非件中心)、且**黏在父件插槽**上(非各自飛)。

## 組合機制(rig 接合 vs 非 rig 散架)

`build_animations`(gen_animations.py)把 rotate/translate timeline 掛在件骨 `b_{件名}`。
**同一支生成 timeline**,套在兩種骨架結構上結果天差地別:

| | 結構子件骨 parent | 骨原點 | 子件自轉繞 | 隨父件(body) |
|---|---|---|---|---|
| **`--rig`** | `b_身體`(body) | **接觸縫關節** | 關節 | ✅ 繼承 body 剛體移動 |
| **非 rig(對照)** | `root` | **件中心** | 件中心 | ❌ 不隨 body |

→ rig 版:子件接縫**黏在父件插槽**上;非 rig 版:同動畫但接縫**漂離父件**(散架)。
**負對照 = 完全相同動畫、只差 rig 結構**,是乾淨的鑑別對照。

## 量測(純 CPU,無瀏覽器)

`spine_anim`/`weighted_deform_eval` 逐幀取樣生成 timeline → bone world transform →
量 **「子件接縫點在父件(body)移動座標系中相對 setup 的偏移」= 接縫脫離插槽的距離**。
- 用 **Loop** beat 量接縫(僅旋轉、無平移;body 僅 ±2% 呼吸,**無 scale-from-0** 假影 —— In beat body scale 0.02→1
  會讓「投回 body 座標系」除以 ~0.02 爆數,故不用於接縫量測)。
- 接縫點 = 子件輪廓最靠近父件的前 25%(與 `infer_pivots`/`validate_rig_build` 同基底,用真實 art 輪廓)。

## AC(5 條全 PASS,`python3 tools/analyzer/validate_rig_anim.py` exit 0)

| AC | 內容 | 結果 |
|---|---|---|
| AC1 | 組合良構+機制:rig+animate 可載入;關節子件 Loop 有 rotate;三 beat all_finite;rig 子件掛 body、非 rig 掛 root | ✅ |
| AC2 | rig 接縫黏連:每關節脫槽 ≤ 12px(右手6.3/頭1.0/左手6.1) | ✅ |
| AC3 | 負對照(非 rig 散架):脫槽 右手21.1/頭6.4/左手7.0;**單調 rig<flat**;總和比 2.56(≥1.8);最大比 6.2(≥3.0) | ✅ |
| AC4 | 逐幀有限/乾淨:三 beat 全程 mesh 件(body/光暈)si=0/flip=0/degen=0、world 非退化 | ✅ |
| AC5 | radial 修正+向後相容:非 rig 件骨世界原點==(bone.x,bone.y);rig 修正徑向 cos≈1、舊式對頭/左手翻反(cos −0.74/−0.95) | ✅ |

## 修的 bug:rig 下 In/Out 徑向方向算錯

`build_animations` 舊碼 `dx,dy = bd["x"]-cx, bd["y"]-cy`(件骨 x/y 相對畫布中心)算「件在外側」的徑向,
供 In(由外歸位)/Out(往外飛)/effect 的 translate 方向。
**非 rig 下件骨直掛 root、x/y 即畫布世界座標 → 正確**;
**但 `--rig` 下件骨 x/y 是相對父件的 local 偏移**,舊碼誤把 local 當畫布座標 → 方向錯,
尤其 local 與世界位置**異號**的件(頭 local(17,222) 但世界原點在右上、左手同理)徑向被**翻反**
(頭 cos −0.74、左手 −0.95,近乎反向 → In 時從錯的一側飛入)。

**修法**:新增 `_bone_world_origin(bname, byname)` —— 沿 parent 鏈**累加 local (x,y)** 得 setup 世界原點
(件骨 setup 皆純平移 rotation=0/scale=1,累加即世界原點)。徑向改用世界原點。
**非 rig 退化為 (bone.x,bone.y) → 逐位吻合舊行為(向後相容)**;rig 下修正。回歸:`validate_anim`(非 rig + rig)、
`validate_beat_templates`、`validate_deform_gen` 全 PASS。setup pose 完全不受影響(build_animations 只寫 `animations`)。

## 誠實界定

- **左手鑑別力弱(比值 1.1×)**:幾何上左手**件中心≈關節**(local(44,142) 對其世界位置同號),
  故 flat 版剛好也差不多黏 → 不是 bug,是這件的先天幾何;閘用**單調 + 總和比 + 最大槓桿比**而非
  `min 比值 > 門檻`,誠實涵蓋這種弱件。
- **主秀手感非本閘範疇**:beat 幅度/緩動是先驗手感(A 類,留使用者);本閘只驗**客觀關節接合結構**。
- **仍單一真值資產**(robot_parts / Award 機器人是唯一可拆肢體 rig)→ `spine-rig-pivot` 與
  `spine-anim-forge` 兩區塊**維持 HOLD**(防固化);本閘強化其**組合證據**,非跨 skill 化門檻。

## 一鍵
```
python3 tools/analyzer/validate_rig_anim.py            # 5 AC,exit 0 = PASS
python3 tools/analyzer/validate_rig_anim.py --json     # 附各關節脫槽/比值/cos 明細
```
