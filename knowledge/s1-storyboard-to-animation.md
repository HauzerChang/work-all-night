# S1 candidate 0d — 分鏡(storyboard)→ Spine 3.8 animation keyframe

- **結論**:把 analyze_target `#3 動作分鏡`(符號:每 beat × 每件的 role/action **文字**)確定性地
  具體化為**可載入、會動**的 Spine 3.8 `animations`(bone rotate/translate/scale + slot color alpha)。
  對 2 份真實 PSD × 2 種 genre(robot=slot_bigwin 3 beats、Symbol_Ww=slot_reveal 7 beats)
  自我驗收 **4 條 AC 全 PASS + 負對照(AC5)全偵測**。build_spine `--animate` 端到端產出的素材,
  setup-pose round-trip 仍 PASS(動畫不擾動靜態幾何)。
- **信心**:高(幾何量化 + 取樣器對照手算精確吻合 + 負對照)。
- **相關階段**:專案第 2 階段 → S1 端到端「目標圖 → 會動的 Spine 素材」。承接 `build_spine.py`(靜態素材)。
- **誠實界定**:role→運動基元是**先驗手感提案**(deterministic,非學自真值);幅度/相位參數
  達物理合理範圍且自洽,但**主觀手感(緩動曲線是否好看、重量感)仍留待使用者/實機**。
  Award 有 12 支真實動畫可作**未來**動作幅度真值比對(尚未做)。

## 工具

- `tools/analyzer/spine_anim.py` — 純 Python **Spine 3.8 timeline 取樣器**(無瀏覽器/無 CDN)。
  支援 linear / `"stepped"` / 緊湊 bezier 散鍵 `{"curve":cx1,"c2":cy1,"c3":cx2,"c4":cy2}`(雷點 #7)。
  `sample(anim,t)`→每 bone 的 {rotate,x,y,scaleX,scaleY} + 每 slot 的 {alpha};`duration`/`all_finite`。
- `tools/analyzer/gen_animations.py` — 分鏡 → timeline 生成器。
  `beat_category(name)` 先把 genre 相依的 beat 名歸類為 **intro/loop/outro/hold/pulse**(關鍵字,token 優先避免子字串誤判),
  再依 **role→運動基元**產鍵幀。CLI `--inplace` 寫回 skeleton.json。
- `tools/analyzer/validate_anim.py` — 自我驗收閘(AC1–AC4 + `--selftest` 跑 AC5 負對照)。
- `tools/analyzer/build_spine.py --animate` — 端到端:靜態素材 + 動畫一次產出。

## 運動基元(role × category)

| category | body | head | limb | 特效(fx) |
|---|---|---|---|---|
| **loop** | scale ±2% 呼吸 + 上下微浮 | 點頭 ±3° | 末梢擺盪 ±5°,**左右反相** | alpha 脈動 ±22% + scale +3% + 緩轉 ±4° |
| **intro** | scale 0→1.12→1 overshoot、alpha 0→1、徑向歸位 | 同 + 小回正 | 同 + 旋轉甩入 ±20° | scale 0→1.25→1、spin −40→0、alpha 0→1 |
| **outro** | scale 1→0、alpha 1→0 | 同 | 同 + 向外飄 | 同 + spin 收 |
| **hold** | 定格 identity | | | |
| **pulse** | scale 1→peak→1 對稱脈衝(首尾 identity) | | +旋轉脈衝 | scale 1→1.3→1、alpha 閃 |

- **無縫循環**:loop 用**正弦取樣**關鍵幀(12/cycle),端點強制相等 → `value(0)==value(dur)` 精確成立。
- **beat 串接介面 = setup identity**(rotate 0 / translate 0 / scale 1 / alpha 1):
  intro 尾、loop 首尾、outro 首、hold/pulse 首尾**全部落在 identity** → 任意順序串接無跳變。

## AC(自我驗收,量化,不靠肉眼)

| AC | 判準 | robot | Symbol_Ww |
|---|---|---|---|
| AC1 well-formed | 時間嚴格遞增、值皆有限、JSON round-trip、bone/slot 皆存在 | ✅ | ✅ |
| AC2 loop seamless | loop 類別每通道 `value(0)==value(dur)`,max_err ≤ 1e-6 | ✅ (err=0) | ✅ |
| AC3 amplitude/phase | body scale∈[0.5%,8%]、head rot∈[0.5°,8°]、limb **反相**(某 t 異號)、fx alpha range≥5% | ✅ | ✅ |
| AC4 beat chaining | intro 尾==identity、intro 起收合、有 overshoot(scale>1.02);loop 首==identity;outro 首==identity、尾收合 | ✅ | ✅ |
| AC5 負對照 | 蓄意打斷 loop 無縫 / intro 不歸位 → 對應 AC 必 FAIL | ✅ 皆偵測 | ✅ 皆偵測 |

取樣器可信度 spot-check(對照手算):body scale@T/4=1.02、R/L-hand rot@T/4=+5/−5(反相)、
intro 起 scale=0.02、intro 尾=identity — 全部精確吻合。圖:`figures/s1_storyboard_to_anim.png`。

## 標準指令

```
python3 tools/analyzer/build_spine.py assets/robot_parts.psd --out <dir> --animate
python3 tools/analyzer/validate_anim.py <dir>/skeleton.json --selftest      # 期望 overall_pass: true
# 或對既有 skeleton.json 補動畫:
python3 tools/analyzer/gen_animations.py <dir>/skeleton.json --psd <psd> --genre <g> --inplace
```

## 待續

- **對 Award 12 支真實動畫做動作幅度真值比對**(旋轉/位移/縮放範圍分佈),把先驗幅度校準到生產手感。
- mesh **deform** timeline(目前只做 bone TRS + slot color;窗簾式軟體形變未生成)。
- 緩動曲線美感 / 相位細節 → 主觀項,留實機或使用者。
