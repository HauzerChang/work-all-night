# P1(物理主線基底)— 分鏡 beat → 動畫 keyframe 生成器 v1(待機呼吸 Loop)

- **結論**:`tools/analyzer/storyboard_to_anim.py` 把分鏡先驗(`genre_priors`)的 **idle/loop** beat
  轉成 Spine 3.8 `animations` timeline —— **讓 `build_spine` 的產物(原本 `animations:{}`)會動**。
  v1 生成**無縫待機呼吸 Loop**;對 main_draw 真實骨架與 build_spine 機器人產物皆 4 條 AC 全 PASS。
- **信心**:高(4 條可機讀 AC:loop 閉合 gap=0、有界運動、物理簽名 inertia_index>0、JSON round-trip;
  幅度校準自真實 `main_draw.main_idle2`)。
- **階段**:第 2 階段 / 物理主線 **P1**(使用者定案「先研究物理世界」的第一步:先有 keyframe,P2 才能注入物理)。

## 標準指令

```
python3 tools/analyzer/storyboard_to_anim.py <skeleton.json> [--body 骨名] [--period 1.2] [--sy-amp 0.12] [--save out.json]
# 印 roles + verify(4 AC);--save 才寫出加了 Loop 的 skeleton。PASS → exit 0。
```

## 設計(校準自真實資料)

- **呼吸 = scaleY 主導脈動**:量測 `main_draw.main_idle2` 的身體(`main`)= sy 0.884~1.219(±~15%)、
  sx 幾乎不變 → **非體積守恆的各向異性脈動**(與 `p1-motion-physics-analyzer` 結論一致)。
  生成器採 body scaleY 為主(預設 sy_amp=0.12)、sx 微動。
- **無縫循環**:keyframe t=0 == t=period(neutral),峰值在 period/2。
- **bezier ease-in-out**(`EASE_IN_OUT={curve:.25,c2:0,c3:.75,c4:1}`):neutral↔peak 端點速度≈0
  → 呼吸在極端有「停頓」感,且 `motion_physics` 量得 **inertia_index=1.0**(滿慣性/物理感)。
  圖:`knowledge/figures/p1_breathing_curve.png`(綠=eased 物理 / 紅=linear 機械;峰值處 |Δ|≈0.0003 = 速度≈0)。
- **角色分派 `auto_roles`**:body(軀幹)/ head(微擺)/ limbs(末梢微盪,左右反向不同步)。
  body 選取順序:①`--body` ②名稱關鍵字(身體/body/torso/chest/胸/main/軀)③後代最多的非 root 骨 ④退回第一件。

## ⭐ 測真實產物揪出的結構限制(誠實)

- **build_spine 產出為扁平 rig**:各件皆 root 直屬(無 parent-child)→ 後代數全 0,
  auto_roles 原本靠「後代最多」選 body 會誤選(機器人選到 `b_頭`)。**加名稱關鍵字優先**後正確選 `b_身體`。
  → 扁平 rig 也沒有可 lag 的父子鏈:**follow-through / 關節傳遞須待 rig 有階層**(S5 pivot / 重綁),
  或 P2 以「相鄰件相位差」近似。v1 呼吸在扁平 rig 上 = 純身體脈動(仍是有效待機)。

## AC 結果

| 標的 | body | loop 閉合 | 有界運動 | inertia_index | round-trip | 判定 |
|---|---|---|---|---|---|---|
| main_draw(真實骨架) | main(自動) | gap=0 | ✔(rot≤bound) | 1.0 | ✔ | **PASS** |
| robot(build_spine 產物) | b_身體(自動) | gap=0 | ✔ | 1.0 | ✔ | **PASS** |

## 誠實界定 / 交棒 P2

- v1 只做 **idle/loop 呼吸**(最基礎、可無縫、純 CPU);其餘 beat(comeout/open/hit/close)未做。
- 呼吸本就平滑 → inertia 已滿;**P2 物理注入**的價值在**非呼吸**動作:follow-through 相位延遲(需階層 rig)、
  overshoot 回穩(彈跳落地)、材質反應(cloth/jelly)。P1 鋪主節律,P2 疊物理層。
- 驗證用 `motion_physics.py`(P/S6 評估器)已能量產出動畫的物理簽名 → P1↔P2 共用同一把尺。
