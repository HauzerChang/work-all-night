# S1 #3d — 分鏡 → 動畫 keyframe(待機/呼吸循環)

- **結論**:`build_spine` 產出的靜態素材現在會**自動配上一支無縫循環的待機/呼吸動畫**,
  由**結構角色**驅動(body 呼吸 / head 微傾 / limb 相位錯開擺盪 / effect alpha 脈動)。
  對 robot(5件,`slot_bigwin`/Loop)與 Symbol_Ww(18件,`slot_symbol`/idle)**5 條 AC 全 PASS**,
  且 `validate_build` round-trip 不受影響(setup pose 未變,MAE 0.031)。「目標圖→會動的 Spine 素材」打通。
- **依據/來源**:`tools/analyzer/storyboard_anim.py`(生成)+ `tools/analyzer/validate_anim.py`(評估器)。
  timeline 格式對齊真實 `assets/main_draw.json`(rotate/translate/scale on bones、color on slots)。
- **信心**:高(客觀幾何/格式閘 + 取樣器自驗 + 4 項負對照全鑑別)。**主觀手感(緩動曲線是否「像呼吸」)留給使用者**。
- **相關階段**:專案第 2 階段;S1 候選 0d(最高優先,見上一 log)。

## 生成規格(`storyboard_anim.build_loop_animation`)

只生 **idle/loop 這一支「循環」節拍**(最乾淨、可用 loop-closure 自驗);In/Out 屬後續。
動作由 `analyze_target` 規格的 `2_effects[].{is_effect,struct_role}` 決定:

| 角色 | timeline | 動作 | 幅度預設 |
|---|---|---|---|
| body | `scale` + `translate.y` | 呼吸(平滑半餘弦 0→peak→0)+ 胸口 y 微移 | ±3% scale、y +1%·H |
| head | `rotate` | 微點頭/傾(整正弦週期,相位 0) | ±2° |
| limb | `rotate` | 末梢擺盪,**逐件相位錯開** φ=i·2π/n_limb | ±4° |
| effect | slot `color` | alpha 脈動 base→dim→base | α 1.0→0.55→1.0 |

**無縫循環怎麼保證**:對「完整正弦/餘弦週期」以 K=8 段過取樣(9 keyframe);相位差整 2π
→ 首幀(t=0)== 末幀(t=T=1.5s),即使相位錯開仍閉合。**不寫 `curve` 鍵 = Spine 3.8 預設 linear**;
線性過取樣讓 range 直接由 keyframe 值判定(不需重算 bezier),同時足夠平滑。

實例(robot,右手 vs 左手正好反相 φ=0/π):右手 `rotate` +2.83→+4.0°,左手 −2.83→−4.0°(對稱擺動);
body scale 1.0→1.015→...;effect `色 ffffffff→ffffffee→ffffffc6`(alpha 漸降)。

## 評估器(`validate_anim.py`)—— 純 Python Spine 3.8 timeline 取樣器

不需瀏覽器(CDN 被網路政策擋)。實作 linear / stepped / **緊湊 bezier**(`curve,c2,c3,c4`,以二分求 x→y)
取樣 bone(rotate/translate/scale)與 slot color。**關鍵修正**:精確命中 keyframe 時間點時
**直接回放該 key 值**(否則 bezier 端點二分有 ~0.05 數值誤差)。

五條可機讀 AC:

| AC | 判準 | 門檻 |
|---|---|---|
| AC1 loop_closure | 每 timeline 首幀 == 末幀 | endpoint diff < 1e-3 |
| AC2 motion_present | 每條 timeline(**聚合各分量**)range > eps(非 no-op) | rot 0.2°/scale 0.002/trans 0.3px/α 0.02 |
| AC3 amp_bounded | scale∈[0.9,1.1]、|rot|≤15°、|trans|≤5%·canvas、α∈[0,1] | 幅度有界不飛出 |
| AC4 phase_stagger | limb rotate **帶號**峰值時間散佈 > 0 | ≥2 rotate bone 才判 |
| AC5 format_valid | timeline 指向存在 bone/slot;time 單調 ∈[0,T] | — |

## 兩個踩過的評估器 bug(記住)

1. **per-field 判 no-op 會誤殺**:body 只動 `translate.y`、`translate.x` 恆 0 → 若逐分量判會把 x 當 no-op。
   改為**逐 timeline 聚合**(任一分量動即算動)。
2. **用 `|angle|` 抓峰值時間對 π 相位差不敏感**(|sin| 週期 T/2,±相位峰值時間相同)→ AC4 假性失敗。
   改用**帶號峰值時間**:右手/左手反相(φ=0/π)峰值時間 0.375 vs 1.125,spread=0.75 → 正確判為錯開。

## 可信度(評估器本身)

- **取樣器自驗**:對真實 `main_draw.json` 386 個 keyframe 逐點回放,`max_replay_error=0.0` → 取樣器數學正確。
- **負對照**(對合格動畫注入缺陷,確認對應 AC pass→fail):`break_closure→AC1`、`blow_amp→AC3`、
  `zero_rotate→AC2`、`bad_bone_ref→AC5` **全部鑑別**(all_discriminating=true)。

## 標準指令

```
python3 tools/analyzer/build_spine.py assets/robot_parts.psd --out <dir> --genre slot_bigwin   # 產含動畫素材
python3 tools/analyzer/validate_anim.py <dir>/skeleton.json --neg                              # AC 閘 + 負對照
python3 tools/analyzer/validate_anim.py --selftest                                              # 取樣器自驗(對 main_draw)
```

## 誠實界定 / 限制

- 只生**循環待機**這一支;In(入場 overshoot)/Out(退場淡出)非循環,驗證方式不同(起訖≠,屬後續)。
- 幅度為**通用先驗預設**(呼吸 3%、擺盪 4°),非從目標影片反推的實測值 → S1 影片輸入到位後可校準。
- **bone 為 root 的直接子**(build_spine 現況);未做關節鏈(parent limb→body)→ 擺盪是繞件中心自轉,
  非「肩→肘」鏈式擺動。關節 pivot/父子鏈屬 S5。
- 緩動曲線用 linear 過取樣(客觀平滑),但「是否像真呼吸」是主觀手感 → 留給使用者(L2 政策)。
- mesh 件在此動畫下只受**仿射** bone 變換(rotate/scale~1.03/translate),不引入自交/翻面
  → 不需 deform-eval;weighted mesh 骨骼變形平滑度仍是獨立未驗維度(見 `s3-robot-mesh-vs-award.md`)。
