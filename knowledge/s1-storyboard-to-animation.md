# S1 分鏡 → 動畫 keyframe(讓產出素材「會動」)

- **結論**:把 analyze_target 的 `3_motion_storyboard`(role-based beats)**確定性**轉成 Spine 3.8
  `animations`(bone TRS + slot color/alpha),不靠 ML。三支 beat **In / Loop / Out** 自動生成,
  已整合進 `build_spine.py`(原本 `animations: {}` → 現在自動填)。對 2 份真實 PSD(robot 5 件 /
  Symbol_Ww 18 件)量化 AC **全 PASS**,round-trip setup pose 不受影響(仍 MAE 0.031)。
- **信心**:高(結構/無縫/有界/軌跡皆機讀驗;負對照 5 種缺陷全部觸發對應 AC)。
- **相關階段**:第 2 階段 S1(承接 build_spine「規格→可載入素材」,補上「會動」維度)。

## 工具

- `tools/analyzer/storyboard_to_anim.py` — `build_animations(spec, part_bone, part_slot)` → animations dict。
- `tools/analyzer/validate_anim.py` — 5 條 AC 自我驗收閘(+ 簡易 FK 軌跡)。
- 兩者已被 `build_spine.py` 串起(build 即產動畫)。

## 角色 → 運動模板(role motion templates)

| role | In(入場,0.5s) | Loop(待機,2.0s,seamless) | Out(退場,0.35s) |
|---|---|---|---|
| 特效 | spin-in(−90→0)+ scale 0.3→1.2→1.0 + alpha 0→1 | **緩轉一圈 0→360**(等速線性無縫)+ scale 脈動 1.0↔1.03 + alpha 0.8↔1.0 | scale→0 + alpha→0 |
| body | 彈入 scale 0.2→1.1→1.0 + translate y −30→0 + alpha | 呼吸 scale y 1.0↔1.025 + bob translate y 0↔4 | scale→0 + alpha→0 |
| head | 同 body 彈入 | 微點頭 rotate 0↔−2° + 隨身 bob y 0↔3 | scale→0 + alpha→0 |
| limb | 甩入 rotate −40→6→0 + scale 0.5→1.08→1.0 | 末梢擺盪 rotate ±3° 正弦(左右**相位錯開** 0 / 0.5) | scale→0 + alpha→0 |

- 未在分鏡列出的件:用 `2_effects.is_effect` 補判「特效」,否則 body。
- limb 相位:依出現序交替 0 / 0.5,達到「左右錯開」的錯落感。

## 量化 AC(validate_anim.py)

- **AC1 結構合法**:bone/slot 名存在;timeline 鍵合法(rotate/translate/scale);time 單調≥0。
- **AC2 Loop 無縫**:Loop 每條 timeline 首尾 keyframe 值相等(rotate 容許 0↔360 同餘)。
- **AC3 有動作**:每 beat 至少 1 件有非零值域(非 no-op)。
- **AC4 Loop 有界**:待機 rotate ≤8°(特效 spin 360 例外)、scale ∈[0.9,1.1]、translate ≤12px。
- **AC5 FK 軌跡**:root-child 前向運動學取件中心世界軌跡,無 NaN;Loop 首尾閉合(<0.5px)。

負對照(證鑑別力):打破無縫(首尾差 0.05)→AC2 fail;Loop rotate 25°→AC4 fail;未知 bone→AC1 fail;
全 no-op→AC3 fail;time 非單調→AC1 fail。**5 種缺陷各觸發對應 AC,baseline PASS**。

## Spine 3.8 動畫格式(實測自 `assets/main_draw.json`)

- rotate:`{"time":t,"angle":deg}`;translate:`{"time":t,"x":,"y":}`;scale:`{"time":t,"x":,"y":}`。
- slot alpha:`slots.<name>.color = [{"time":t,"color":"rrggbbaa"}]`(hex,此處 RGB 恆白只調 aa)。
- `time==0` 的 keyframe **省略 time 鍵**(對齊真實匯出)。
- 緊湊 bezier 散鍵 `{"curve":cx1,"c2":cy1,"c3":cx2,"c4":cy2}`;本工具用 ease-in-out=(0.25,0,0.75,1)。

## 誠實界定 / 限制(下一步線索)

- **bone 原點在件中心(非關節 pivot)** → limb 旋轉繞中心而非肩點。待機微擺盪視覺 OK,
  但大幅甩動會「整塊繞中心轉」不自然。**關節 pivot 推斷 = S5**,尚未做(路線圖唯一卡死環節)。
- FK/AC 用**線性內插**量值域與首尾(Spine bezier 只改時序、不改端點值),故值域/無縫判定與實機一致;
  **緩動手感(緩急、重量感)屬主觀**,留給使用者在 spine_inspector 目視(客觀/主觀分工符合 SOP)。
- beat 時長/幅度為**類型先驗**(slot_bigwin),非對真值影片校準;有 benchmark 影片後可回歸校準。
- mesh 件(光暈/身體)目前只受 bone TRS 驅動,**未加 deform timeline**(mesh 自身頂點變形);
  可作後續(與 S3 deform 評估器接軌)。
