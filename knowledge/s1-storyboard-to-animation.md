# S1 分鏡 → 動畫 keyframe(storyboard → Spine animations)

**結論**:`build_spine.py` 產出的素材原本 `animations:{}`(不會動)。本次補上
`animate_spine.py`(分鏡→timeline)+ `validate_animation.py`(6-AC 幾何自我閘),
讓端到端產出的素材**會動**且動作品質可機讀驗收。robot(slot_bigwin)/ Symbol_Ww(slot_symbol)
兩資產、兩 genre **overall_pass=True**;評估器經真值錨 + 5 個負對照雙向確認可信。
**信心:高(客觀幾何項)**。手感(緩動曲線、重量感)屬主觀,留給使用者(L2)。
**相關階段:S1 端到端 pipeline / 專案第 2 階段(骨架設計 × 動畫)。**

## 做了什麼

- `tools/analyzer/animate_spine.py`:讀 `analyze_target` 的 #3 動作分鏡(每件 role→action)+
  `build_spine` 的 `skeleton.json`,**確定性**生成 Spine 3.8 `animations` timeline。
- `tools/analyzer/validate_animation.py`:對產出的 animations 做幾何量化 6-AC pass/fail + 差距。

指令:
```
python3 tools/analyzer/build_spine.py assets/robot_parts.psd --out /tmp/robot_spine
python3 tools/analyzer/animate_spine.py assets/robot_parts.psd /tmp/robot_spine/skeleton.json --out /tmp/robot_spine/skeleton_anim.json
python3 tools/analyzer/validate_animation.py /tmp/robot_spine/skeleton_anim.json --psd assets/robot_parts.psd
```

## 動作原型(role × beat,全確定性,無 ML)

角色由分鏡取得:`effect / body / head / limb`。beat key 先經**語意類**正規化,
讓不同 genre 都對映到 4 個原型(不再只認 In/Loop/Out):

| beat key(先驗) | 語意類 | builder |
|---|---|---|
| in / comeout / land / static | enter | `build_in`(off-pose→neutral,彈入 overshoot) |
| loop / idle | loop | `build_loop`(**無縫**待機呼吸) |
| out / close | exit | `build_out`(neutral→off-pose,縮出淡出) |
| open / hit / win / accent | accent | `build_accent`(pop→回 neutral 強調) |

**Loop(待機)動作原型**:

- **body 呼吸**:`scaleY = 1 + 0.03·raisedcos(u)`、`scaleX = 1 − 0.015·raisedcos(u)`(體積守恆感)、
  `transY = 4·raisedcos(u)` px。`raisedcos(u)=0.5−0.5cos(2πu)`,u=t/T,首末=0(無縫)。
- **head 微擺**:`rot = 3°·(sin(2πu)−sin0)`。
- **limb 末梢擺盪(相位錯開)**:`rot = 5°·(sin(2πu+φᵢ)−sin φᵢ)`,φᵢ=2π·i/n_limb;
  **平移 −sin φᵢ 讓首末仍=0**(錨在 neutral、無縫、且峰值時間隨 φ 分散)。
- **effect 脈動**:bone `rot = 7°·(sin(2πu)−sin0)`(峰對峰 14°,落在真值 band)+
  slot alpha `= 1 − 0.22·raisedcos(u)`(ff→cc→ff 脈動)。

**設計不變式**:錨點 = neutral setup pose → **In.末 == Loop.首 == Out.首**(轉場連續);
Loop 每 channel **首 keyframe 值 == 末 keyframe 值**(嚴格無縫)。

## 幅度校準(真實生產動畫,`main_draw` / `Award`)

觀測(見驗證腳本):
- **Loop 無縫真值錨**:`main_draw_loop`、`main_idle`、`main_idle3` 的 bone timeline
  **首末差 = 0.0000**(嚴格無縫)。→ 定為 A2 不變式。⚠️ `Award_*_Loop` 首末差達 22°
  (tier 間用 crossfade,非 bone 級無縫),故無縫真值錨取 `main_draw`,不取 Award。
- **幅度 band**(真實中位/極值 → 保守上界):rotate range ≤ **15°**(真實 median ~5–6°、
  max ~22° 為少數大件)、scale range ≤ **0.15**、translate range ≤ **35px**、alpha∈[0,1]。

## 評估器 6-AC(`validate_animation.py`)

| AC | 判準 | 真值/依據 |
|---|---|---|
| A1 結構 | 參照 bone/slot 存在;數值有限 | — |
| A2 Loop 無縫 | 每 channel 首值==末值(eps 1e-4) | main_draw 首末差=0 |
| A3 有動作 | 每個出現的 role 都有非零 Loop 振幅 | 分鏡要求「都會動」 |
| A4 幅度有界 | rotate≤15° / scale≤0.15 / trans≤35px / alpha∈[0,1] | 真實幅度 band |
| A5 相位錯開 | ≥2 limb:峰值時間 spread≥0.05T **或** 兩兩相關<0.99 | 末梢錯相位手感 |
| A6 轉場連續 | enter.末 / exit.首 ≈ loop.首(tol 0.01);enter/exit 本身非無縫 | 錨點設計 |

**評估器可信度(雙向確認,per RULES「每能力必配可信評估器」)**:
- 真值自一致:真實 `main_draw` 3 支 loop A2 首末差 = 0.0000。
- 負對照 5/5 全被抓:非無縫 Loop→A2 fail、超幅(180°)→A4 fail、同相位 limb→A5 fail、
  In 末不回 neutral→A6 fail、參照鬼 bone→A1 fail。

## 驗收結果

- **robot(slot_bigwin,5 件)**:loop_beat=`Loop`,A1–A6 全 pass。
  Loop 振幅:effect 14° / limb 10° / head 6° / body scale 0.03、transY 4px;A2 首末差 0.0。
- **Symbol_Ww(slot_symbol,18 件)**:loop_beat=`idle`(land→enter/win→accent),A1–A6 全 pass。

## 誠實界定 / 限制(留待後續)

- **緩動曲線目前為線性取樣**(每 channel 9 點近似正弦);未輸出 Spine 緊湊 bezier。
  讀起來已是平滑呼吸,但要「藝術家級手感」需 bezier easing(可續作,評估器對線性/bezier 皆適用)。
- **未做實機渲染對照**:spine_inspector 走 CDN(jsDelivr)被網路政策擋(既有 blocker);
  本次以幾何量化 + 軌跡取樣自驗,未跑瀏覽器 round-trip。
- **動作是類型先驗提案(PROPOSAL)**,非逐件美術設計;pivot 仍用件中心(b_<件>@root),
  關節 pivot 推斷(S5)未做 → limb 是繞件中心轉,非繞肩/肘關節。
- accent(open/hit/win)僅 scale pop,未做粒子/位移爆發。
