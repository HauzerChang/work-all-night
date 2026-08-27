# S1 #3:分鏡(storyboard)→ Spine 動畫 keyframe(讓靜態素材「會動」)

> 里程碑 2026-08-27。接續 `build_spine.py`(規格→靜態素材,animations 為空)的最後一段:
> 把分鏡先驗的 beats 轉成實際 Spine 3.8 `animations` timeline,並配純 CPU 品質閘。

## 工具

- `tools/analyzer/build_animations.py` — 生成器。輸入:build_spine 產出的 spine 目錄 + 原 PSD + genre。
  跑 `analyze_target` 取每件 struct_role(body/head/limb/effect),依 genre 先驗 beats 生成
  bone `translate`/`scale`/`rotate` + 特效件 slot `color`(alpha)timeline,寫回 `skeleton.json`。
- `tools/analyzer/validate_animations.py` — 品質閘(純 CPU,不需瀏覽器)。

標準指令:
```
python3 tools/analyzer/build_spine.py <psd> --out <dir>
python3 tools/analyzer/build_animations.py <psd> <dir> --genre slot_bigwin
python3 tools/analyzer/validate_animations.py <dir>/skeleton.json --neg
```

## 生成器設計(對應已知品質雷點)

| 原則 | 做法 |
|---|---|
| **Loop 嚴格週期**(loop 不跳) | 以正弦繞一圈取樣,週期=動畫長度;`_sine_frames` 令 k=0 與 k=N 值相等 |
| **有界且非零振幅** | 每角色一組幅度:body scale ±0.03 + ty 3px;head rot ±2.5° + ty 2px;limb rot ±3°;effect scale ±0.04 + alpha ±0.35 |
| **相位錯開**(破「全身同步紙板感」) | 每件 φ_i = i/N;呼吸/擺盪極值時間錯開 |
| **平滑緩動** | 段間套 Spine 3.8 緊湊 bezier `{"curve":0.25,"c3":0.75}`(對稱 ease-in-out) |
| squash/stretch | body/effect scale x 反相 y(面積近守恆),比純等比更有生命感 |

beat 分派:`LOOP_KEYS={Loop,loop,idle,static}`→`build_loop`;`IN_KEYS={In,comeout,land}`→`build_in`
(彈入+overshoot,末梢從偏角甩入,特效由 0 alpha 亮起);`OUT_KEYS={Out,close}`→`build_out`(縮出+淡出)。
In/Out 為**非週期**(t=0≠t=T,刻意)。

## 品質閘(5 檢查)

- **A schema**:被引用的 bone/slot 都存在。
- **B loop_cyclic**(僅 loop 類):每條 timeline 值 t=0 == t=T,gap ≤ 1e-3(含特效 alpha)。
- **C amplitude**:每個 group(translate/scale/rotate/alpha)整組至少一分量動(非零),
  且每分量峰對峰 ≤ 上限。**注意**:非零判定看「整組」,純垂直 bob(x=0,y≠0)合法。
- **D phase_div**(僅 loop 類硬閘):各 bone「綜合活動訊號」極值時間的標準差 ≥ 0.10(週期比例)。
  綜合訊號 = 各 property 以自身峰對峰正規化後偏離量總和 → rotate/scale/translate 可比;
  純旋轉件(世界原點不動)也能取到正確相位。
- **E world_motion**:root→bone 世界變換重現,回報各 bone 世界位移峰值有界非零。

## Spine 曲線取樣(驗證器核心,已自驗)

- 緊湊 bezier:`curve=cx1`、`c2=cy1`(default 0 省)、`c3=cx2`、`c4=cy2`(default 1 省);
  雙值 timeline(translate/scale)x/y **共用同一 curve**(對齊 `assets/main_draw.json` 實測)。
- `_bezier_y`:二分 s 使 X(s)=percent,取 Y(s)。自驗:對稱 ease 在 p=0.5→0.5、端點 0/1、單段單調有界;
  `stepped` hold、無 curve linear 均正確。

## 結果(2 資產全 PASS)

| 資產 | genre | anims | animated bones | Loop gap | Loop phase std | overall |
|---|---|---|---|---|---|---|
| robot_parts(5件) | slot_bigwin | In/Loop/Out | 5 | 0.0 | 0.187 | ✅ |
| Symbol_Ww(18件) | slot_symbol | land/idle | 18 | 0.0 | 0.184 | ✅ |

- setup-pose round-trip(`validate_build.py`)**仍 PASS** → 加動畫不破壞靜態幾何/貼圖。
- **負對照(閘可信度)**:`--neg` 內建兩個反例,兩者都被抓才算閘有鑑別力:
  - `flat`(所有 keyframe 同值,死圖)→ 在 C amplitude 被抓(group_pp=0)。
  - `synced`(全 bone 同相位但有振幅,同步紙板)→ 在 D phase_div 被抓(std=0)。
  - `neg_control_pass: true`。

## 誠實界定 / 限制

- **手感(緩動曲線、重量感)是主觀項**:閘只驗客觀結構(週期閉合、振幅帶、相位離散、平滑取樣可行),
  不判「好不好看」。真正手感留給使用者在 spine_inspector 目視(RULES:主觀項不自動判定)。
- 先驗動作為**類型提案**;`slot_symbol` genre 目前 UNVALIDATED(repo 無對應真值 symbol 動畫)。
  已驗證的 `slot_bigwin`(對 Award)、`slot_reveal`(對 main_draw)先驗較可信。
- **未接實機渲染**:spine-webgl CDN 被網路政策擋(既有 blocker);本閘以 CPU 重現 bone 變換替代,
  但未涵蓋 mesh deform 隨 bone 的視覺(weighted mesh 尚未生成,見 s3-robot-mesh-vs-award 限制)。
- beat 未涵蓋 `win/hit/open/reveal/...`(命中/開獎主秀)—— 目前只做 In/Loop/Out 與 land/idle;
  下一步可補「hit 短促放大閃光」「open 展開主秀」的模板。

## 下一步候選

- (a) 補 hit/open/reveal 等 beat 模板(命中強調、開獎主秀),讓 slot_reveal / bigwin 更完整。
- (b) weighted mesh + BBW(STATE 候選 2):唯一未驗維度;之後可讓 build_animations 的 bone 動畫
  真正驅動 mesh 變形,量化變形平滑度。
- (c) 對真實 Award/main_draw 動畫做「風格對照」:量測真實 idle 的振幅/相位分佈,校準本生成器的預設幅度帶。
