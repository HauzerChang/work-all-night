# S1 #3 分鏡 → Spine 3.8 動畫 keyframe(素材「會動」)

- **結論**:把分析器的 **動作分鏡(3_motion_storyboard)** 的每個 beat(In/Loop/Out …)+ 每件的
  結構角色(body/head/limb/effect)**確定性地**合成成 Spine 3.8 `animations` 的 bone/slot timeline,
  讓 `build_spine.py` 產出的素材從只有 setup pose 變成「會動」。對 2 份真實 PSD(robot 5件 / Symbol_Ww 18件)
  × 2 類型(slot_bigwin/slot_symbol)**動畫閘全 PASS**,且 round-trip 靜態 setup pose 不受影響(MAE 0.031)。
- **信心**:高(每條 AC 由 `validate_animation.py` 量化;閘本身有 5 個負對照 + 1 正對照 self-test 確認可信)。
- **階段**:第 2 階段 / S1(里程碑:規格→素材 pipeline 由「靜態可載入」推進到「會動可載入」)。
- **工具**:`tools/analyzer/gen_animation.py`(合成)、`validate_animation.py`(量化閘,含 `--selftest` 負對照)。
  已整合進 `build_spine.py`(預設 animate,`--no-animate` 可關)。

## 標準指令

```
# 端到端(build 即含動畫)
python3 tools/analyzer/build_spine.py assets/robot_parts.psd --out /tmp/robot_spine
python3 tools/analyzer/validate_animation.py /tmp/robot_spine/skeleton.json   # 14 檢查全 PASS → exit 0

# 閘可信度負對照(先跑這個再信閘)
python3 tools/analyzer/validate_animation.py --selftest                       # 5 壞 + 1 好 全對 → exit 0
```

## 動作語彙(beat × 角色 → timeline)

| beat | body | head | limb | effect |
|---|---|---|---|---|
| **In**(入場爆發) | scale 0.2→1.12→1.0 + 由下彈入 | 微轉+隨入 | rotate −40→+12→0(左右反向甩) | scale 0→1.3→1.0 + slot alpha 0→ff |
| **Loop**(待機) | 呼吸 scale ±1.5~2.5% + 微浮 | 微點頭 ±2° | rotate ±4°,**相位錯開** | scale ±3% + slot alpha ff↔cc |
| **Out**(退場) | scale→0 | scale→0 | scale→0 | scale→0 + alpha→0(收斂更快) |

- 其他類型的 beat 名(comeout/open/hit/land/win→In;idle/loop/static/accent→Loop;close→Out)
  以 `BEAT_SYNTH` 映射到這三大骨幹;同函式多 beat 以實際 beat 名當 animation 名去重。

## 驗收 AC(全由閘量化,不靠肉眼)

- **AC1 結構合法**:bone/slot 存在;每 timeline `time` 嚴格遞增;緊湊 bezier `curve` 僅
  缺省(linear)/ "stepped" / 4 數值散鍵(`curve,c2,c3,c4`)之一。
- **AC2 語意幅度分帶**:In 有大幅(scale_dev≥0.08 或 rotate_range≥20°)+ effect alpha 0→255;
  Loop **首尾同值(seamless)** 且小幅(scale_dev≤0.06、rotate_range≤12°)但非零;Out 末幀 scale/alpha≈0。
- **AC3 角色分化**:effect 有 slot color(alpha)timeline;≥2 limb 時 Loop 峰值時刻錯開。
- **AC4 非平凡**:每 animation 有 timeline 且運動幅度 >0。

視覺證據:`knowledge/figures/s1_animation_curves.png`(In overshoot / In 左右反向甩 / Loop 相位錯開交叉「X」/ Out 歸零)。

## 閘揪到的兩個真實 bug(過程,非事後美化)

1. **Loop 首個 limb 零幅**:初版用三角波 `tri` 在 `tri(0)=tri(0.5)=0` 取樣 → `limb_idx=0` 的 limb
   Loop 擺盪幅度為 0(不動)。AC3 因另一 limb 恰好有值而僥倖過,但 metrics 露餡。
   → 改 `swing(t)=A·sin(2π t/dur + φ_i)`,每 ¼ 週期取樣(0,¼,½,¾,dur),末幀顯式對齊首幀。
   保證非零幅度、峰值依相位錯開、sin 週期性天然 seamless。
2. **多 limb 資產 In 中幀時刻碰撞**:初版中幀時刻 `min(peak+0.06·idx, dur)`,Symbol_Ww 有 8 limb →
   `idx≥4` 時 clamp 到 `dur` → 與末幀同時刻 → `time` 非嚴格遞增(AC1 抓到)。
   → 改中幀 = `peak + frac·(dur−peak)·0.6`(frac=idx/n ∈[0,1)),永遠嚴格落在 (0,dur)。

**教訓**:量化 metrics(而非只看 pass/fail 布林)才揪得出「僥倖過關」的退化 case;每次都印範圍值再判定。

## Spine 3.8 技術點(本次落實)

- 緊湊 bezier 用**散鍵** `{"curve":cx1,"c2":cy1,"c3":cx2,"c4":cy2}`(landmine #7);末幀不放 curve(linear 尾)。
- slot 顏色/透明用 `"color":"rrggbbaa"` hex;effect 炸開/淡出用 alpha 段。
- animation 名即 beat 名;bone=`b_<safe(件名)>`、slot=`<safe(件名)>` 與 build_spine 完全一致。

## 誠實界定 / 下一步

- **動作幅度/相位/緩動曲線是「類型先驗參數」**(確定性映射),非從影片觀測學來;真手感(緩動、重量感)
  屬主觀項,依 RULES 留給使用者。閘只保證**客觀**:合法、語意分帶、seamless、非平凡、角色分化。
- **未驗**:實機(spine-webgl/Cocos)播放視覺 —— CDN 被網路政策擋(見 STATE),需離線 renderer 或使用者放行。
- 下一步候選:(a) 把 #5 遮擋/露出的 reveal 區接到動畫(移開遮擋件時序);(b) 關節 pivot 推斷後,
  limb 動作改繞真實關節旋轉(現為件中心);(c) mesh 件的 deform timeline(呼吸讓軟邊 mesh 形變,接 S3)。
