# S1 分鏡 → 動畫 keyframe(讓產出素材「會動」)

> 結論:把 analyze_target 的 **#3 storyboard** 轉成 Spine 3.8 `animations`(In/Loop/Out)timeline,
> 純 CPU、確定性、幅度校準自真實 Award。附**量化自驗閘 + 負對照**,8 條 AC 全 PASS,閘有鑑別力。
> 信心:高(對 slot_bigwin In/Loop/Out;跨資產結構穩健)。相關階段:S1 端到端 pipeline 的「會動」缺口。

## 動機

`build_spine.py` 先前只產 setup pose,`animations` 為空(素材是靜態的)。本步補上「運動」——
依反推框架「**運動決定一切**」,由每件的 **role**(特效 / body / head / limb)決定其運動,
組出 bigwin 三段式 In/Loop/Out。

## 工具

- `tools/analyzer/gen_animation.py`
  - `build_animations(skeleton, spec)` → `{In, Loop, Out}`(Spine 3.8 bones/slots timeline)。
  - `add_animations(skeleton, spec)` → 就地寫回 skeleton;`build_spine.py --animate` 已串接。
  - 同檔導出取樣器 `sample_bone / sample_slot_alpha`(含緊湊 bezier 解算)——**單一真相**,validator 直接用。
- `tools/analyzer/validate_animation.py` —— 量化 AC 閘 + `--selfcheck`(負對照)+ `--award`(真值 sanity)。

## 運動設計(role → timeline)

| beat | body | head | limb | 特效(光暈) |
|---|---|---|---|---|
| **Loop**(1.0s,無縫) | scale 呼吸 1.0→1.05→1.0(上行) | rotate ±2° | rotate ±3°,**兩手反相**(sin/−sin) | scale 脈動 +4% + slot alpha 1.0→0.78→1.0 |
| **In**(0.5s,收斂 setup) | scale 0.2→1.08→1.0 彈入 + translate 上移歸零 | rotate −15°→0 | rotate ±40°→0(左右反向甩入)+ translate 歸零 | scale 0.5→1.15→1.0 + rotate −30°→0 + alpha 0→1 |
| **Out**(0.4s) | scale→0.01 | scale→0.01 | scale→0.01 | scale→0.01 + alpha→0 |

- **無縫關鍵**:Loop 每條 timeline 首尾 == setup(呼吸走「上行」形狀 `[{},{t:.5,1.05},{t:1}]`,
  與 Award `大標` Loop 實測形狀一致);In 收斂到 setup → **In 尾 == Loop 頭**,兩段可無縫串接。
- **相位錯開**:兩 limb 用 `sin(2πt)` / `sin(2πt+π)` 取樣 → rot 序列相關係數 = −1.0(避免全身同步的紙板感)。

## 幅度校準(真值:Award 12 支 *_Loop 實測)

- Award Loop **scale ppk ∈ [0.05, 3.75]**(中位 0.40),**rotate ppk ∈ [0.44°, 22.4°]**(中位 6.3°)。
- 我方選 body 呼吸 ppk=0.05(== `大標`)、limb ppk=6°(≈ 中位)、head ppk=4° → **全落在真實區間**。
- ⚠️ 真值另發現:Award Loop timeline **只有 82/120 首尾嚴格相等**(68%),即真實生產也常靠 mix/setup
  收尾而非嚴格無縫。我方把「嚴格無縫」設為**品質目標**(比真值更嚴),誠實記錄此差異。

## 自驗閘(8 條 AC,`validate_animation.py`)

`A1` well-formed(time 遞增/值有限/curve 合法/color 8-hex)· `A2` Loop 無縫(bone 變換 & slot alpha 首尾一致)·
`A3` Loop 有運動(非靜態)· `A4` Loop 微呼吸幅度落在真實區間 · `A5` limb 反相(rot 相關 <0)·
`A6` In→Loop 連續(In 尾姿勢 == Loop 頭姿勢)· `A7` In 比 Loop 誇張且 body 由小放大(彈入)· `A8` Out 收斂(scale≈0 & fx alpha≈0)。

**結果(robot / slot_bigwin)**:8/8 PASS。built skeleton(經 build_spine --animate)重跑亦 8/8 PASS;
setup-pose round-trip(`validate_build.py`)不受影響(MAE 0.031、0 孤兒)。
**負對照**:故意破壞(無縫破壞/零運動/limb 同相/In 不收斂/Out 不退場)→ 對應 AC 全數由 PASS 翻 FAIL → **閘有鑑別力**。
圖:`knowledge/figures/s1_animation_curves.png`(Loop 呼吸+反相、In 彈入收斂、Out 淡出)。

## 誠實界定 / 限制

1. **僅 slot_bigwin In/Loop/Out 有真值校準**。其他 genre(如 slot_reveal 的 static/idle/…/close 七段)目前
   仍套用**通用 In/Loop/Out**(每件都有進場/待機/退場,結構上成立且通過閘),但**未對映該類型的專屬 beats**。
   → 待續:genre-specific beat 生成 + 各自真值(需該類型的真實 spine)。
2. 運動為 **role→參數化程式合成**,非逐幀對映參考影片(影片輸入是 S1 更上游的獨立課題)。
3. bone 皆 parent=root 的平移/旋轉/縮放;**關節鏈(pivot 傳遞)未建**——limb 擺盪是繞件中心,
   非繞肩關節(關節 pivot 屬 S5,唯一需人微調環節)。
4. **緩動手感(bezier 具體曲線)未主觀調**:In/Out 目前多為線性/簡單段;RULES 規定主觀手感留給使用者。
5. mesh **deform timeline 未生**(窗簾式軟體形變);本步只動 bone transform + slot alpha。

## 下一步候選

- (最高)genre-specific beats(需真值 spine)/ 或 In/Out 緩動 bezier 化(接近真實彈跳手感)。
- 關節鏈(件→相鄰件 pivot 推斷)使 limb 繞關節擺盪(接 S5)。
- 候選 2(STATE):S3 weighted mesh + BBW,補「骨骼變形平滑度」未驗維度。
