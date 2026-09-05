# S1 (G) — 關節 pivot 感知的 keyframe(candidate 0i)

> 里程碑 2026-09-05。把 **S5 的接觸縫 pivot 餵給 S1 keyframe 生成器**,讓結構子件(頭/肢體)
> **繞解剖關節旋轉,而非繞件中心** —— 純 keyframe 補償路徑,不需結構重綁(--rig)。

## 動機(缺口)

`gen_animations` 對結構子件加 `rotate` timeline 時,bone 位在**件中心** O。Spine 的 rotate 讓
attachment **繞 bone 原點旋轉**,所以生成的「手臂擺盪 / 點頭」其實是**繞件自己的中心原地打轉**,
而非繞肩 / 頸關節。`--rig` 走「把 bone 實際搬到接觸縫」的**結構解**;本 chunk 補上另一條路:
**bone 留在件中心,靠同步的 translate 補償**達到繞任意 pivot 旋轉(**keyframe 解**,扁平骨架即可)。

## 數學:剛體繞 pivot 的 translate 補償

件上與 pivot P 重合的點,其 bone-local 座標 `p = P − O`。加了 rotate θ 後世界點為
`world(p) = (O + translate) + R(θ)·(P − O)`。令其恆等於 P:

```
translate(θ) = P − O − R(θ)(P−O) = (R(θ) − I)(O − P) ≡ Δ(θ)
```

即:**對每個 rotate 幀角度 θ,同步加上 translate 補償 Δ(θ)=(R(θ)−I)(O−P)**,件就繞 P 旋轉。
- `θ=0 ⟹ Δ=0` → **不擾動 setup identity**(In 尾、Out 首、pulse 端點自動保住)。
- loop 端點角度相等 ⟹ Δ 端點相等 ⟹ **無縫保留**。
- 故此補償對既有介面契約(In 歸位 / Loop 無縫 / Out 收合)**天然中性**,驗收 AC5 實測全過。

## 實作

- `tools/analyzer/pivot_keyframe.py`
  - `rotate_about_pivot_delta(O, P, θ)` → Δ 閉式。
  - `compensate_bone(b, O, P, subdiv=8)`:就地把單 bone 的 timelines 改成繞 P。讀 `rotate`,
    **新建/合併** `translate`(疊加在既有 translate,如 intro 徑向歸位之上)。
    **細分**:Δ(θ) 對 θ 非線性,故把每對相鄰 rotate 幀**細分 8 段**取樣角度→線性內插 translate,
    使幀間不動點殘差 → sub-0.001px(僅端點嚴格為零仍不夠,故細分)。
- `gen_animations.build_animations(skeleton, storyboard, pivots=None)`:給 `pivots={safe件名:(Px,Py)}`
  後,凡該件有 `rotate` 即套 `compensate_bone`(O 取自 bone setup x/y)。**未給 → 原行為(繞件中心),完全向後相容**。
- `build_spine.py --pivot`(需 `--animate`,且**非 --rig**):`compute_part_pivots` 復用 `rig_layout`
  (`infer_tree` + `contact_seam_joint`)的 **joint 判定**,只取 `joint==True` 的結構子件 pivot
  (與 --rig 完全一致);pivot 世界座標記入 `build_meta.json`(供 validator 讀真值)。
  **--rig 已把 bone 搬到關節,故旋轉本就繞關節,不需 --pivot;兩者互補、非併用。**

## honest boundary

- 只有**有推得接觸縫 pivot 的結構子件**(頭/肢體)吃補償;**rig 根(body,無父)+ 特效件**
  維持繞件中心(與 S5 rig_layout / infer_tree 的 role 判定一致,effect 為輸入語意)。
- 不動點性質是對**旋轉分量**成立。scale / 徑向 translate 這類**非旋轉**運動仍會搬動 P
  (intro 縮放 0.02→1 尤甚),故驗收以「旋轉為主」段落(**loop 肢體純 rotate**)量測。
- 旋轉方向採標準 CCW `R(θ)`,補償與 validator 世界取樣器**用同一約定**,故不動點 AC 與座標約定
  無關(內部自洽);與真實 Spine runtime 對齊屬既有 pipeline 共同假設。

## 驗收(`validate_pivot_keyframe.py`,對 robot_parts,6 AC 全 PASS)

| AC | 內容 | 結果 |
|---|---|---|
| AC1 formula | Δ 閉式 → 繞 P 後 P 精確不動(θ=0,15,−25,90,179°);θ=0→Δ=0 | err < 1e-9 |
| AC2 fixed_point | 端到端 --pivot,Loop 肢體 pivot 世界點跨全幀位移 | 頭/左手/右手皆 **0.0001px** |
| AC3 neg_control | 無補償(--animate)pivot 位移 == 閉式 `2\|P-O\|sin(θpk/2)` **且**被補償壓掉 ≥20×,≥1 肢體實質顯著 | 量測 14.326/2.62/10.998px **精確吻合閉式**;補償後 >20000× 縮減 |
| AC4 still_rotates | 件遠端點(離 pivot 200px)確有位移(補償沒凍結旋轉) | 13~32px |
| AC5 interface | --pivot 產物仍過 `validate_anim` 全 AC | 4/4 pass |
| AC6 discriminative | (a) 隨機 pivot Q → Q 不動但**真 P 會動 18.97px**(P 專屬);(b) P==O → Δ≡0 no-op | pass |

**關鍵發現**:AC3 的無補償位移**逐 bone 精確等於閉式 `2\|P-O\|sin(θpk/2)`**(14.326==14.326…)
→ 同時證了 ①世界取樣模型正確 ②無補償情形**確實是繞件中心**。頭的位移小(2.62px)不是弱點而是
**忠實反映**:點頭僅 3°、頸關節距頭心僅 ~50px;絕對門檻(5px)會誤殺,故 AC3 改用**閉式吻合 + 相對壓縮比**
的原理化判準,另設「≥1 肢體位移 ≥5px」的實質性全域閘。

## 與路線圖關係

- 對應 STATE「建議下一個」**(G) S1 (e) 關節 pivot 推斷接 keyframe**。
- 這是 **S5 pivot(接觸縫)↔ S1 keyframe** 的**首個接點**:S5 之前只服務 --rig(結構重綁),
  現在也能服務扁平骨架的動畫生成。
- 新增 cap `pivot_aware_keyframe` L2,併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、
  單一真值資產,防固化)。
- 續(擇一,皆自主):把 pivot 補償推廣到 **pulse/hit 等有 rotate 的主秀 beat**(目前 loop 已涵蓋,
  intro/pulse 因並存 scale/徑向而不動點僅對旋轉分量成立 → 可做「分離旋轉分量」的更嚴 AC);
  或 **cascade × pivot**(跨件波 + 各繞自身關節)。
