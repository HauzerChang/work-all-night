# S1 (J-15c) cascade 晃動波變體:每件依序阻尼 shearX 晃起→回穩(第一個把 shear 錯開成跨件波)

> 結論先行:至 (J-15) 為止,cascade 的**單件運動基元**有兩種——**pop**(scale 脈衝,J-5..J-14)與
> **reveal**(scale+alpha 入場,J-15),兩者都走 **scale 通道**。J-15c 新增**第三個**運動基元 **wobble 晃動波**:
> 把單件運動換成 `gen_wobble` 的**純 shearX 阻尼振盪**——每件 shearX 自 identity(0)起,依 phase **依序晃起**
> (爆出一串遞減交替的 shearX 極值 A→−rA→+r²A→−r³A),再回穩到 0。這是**第一個把 `shear` 通道錯開成跨件波**
> 的 cascade(前面所有 cascade 皆 scale/rotate/color 通道)。

- **信心**:高(5 AC 全 PASS,真實 robot 骨架端到端,含零回歸 + 負對照 + argmax 良定義 crux + 三運動基元彼此分離)。
- **階段**:S1 反推分析器(動畫 keyframe 生成端,主秀 beat 運動基元擴充)。cap `cascade_wobble` **L2**,併入
  `spine-anim-forge`(仍 HOLD,防半成品固化)。

## 為什麼有價值(不是又一個 geo 方向 source)

J-5..J-14 十個候選全在 cascade 的**第一條軸**(波方向/散佈/段數=哪件何時);J-15 reveal 是第一個動**第二條軸**
(單件運動基元=每件做什麼)。J-15c 是**第三個**單件運動基元,且關鍵在於它**走不同的 transform 通道**:

| 運動基元 | 通道 | 首幀 | 尾幀 | 可接 Loop |
|---|---|---|---|---|
| pop(J-5..J-14) | scale(+limb/特效 rotate/color) | identity | identity | 兩端 |
| reveal(J-15) | scale + alpha | **collapsed**(非 identity) | identity | **僅尾端** |
| **wobble(J-15c)** | **純 shearX** | identity(shearX=0) | identity(shearX=0) | **兩端** |

前面所有 cascade(pop/reveal)皆 scale/rotate/color 通道,**shear 從未進過跨件波**。J-15c 證實 J-15 揭示的
「跨件時序軸 × 單件運動基元軸」兩正交軸**可承載任意 transform 通道的運動基元**(scale→shear)——運動基元軸
不綁定特定通道,是一條真正通用的軸。

## 做了什麼(全 additive,pop 路徑逐位元不變)

1. `beat_templates.gen_cascade(..., wobble=False)` 新增參數:`wobble=False`(預設)→ 逐位元同 pop;
   `wobble=True` 委派 `_gen_cascade_wobble`(一次性單道波 → `nrip` 須 1,否則 ValueError;與 `reveal` 互斥,
   同開 ValueError)。
2. `_gen_cascade_wobble(role, side_sign, T, p, sp)`:單件晃動包絡——晃起中心 `c = CASCADE_LEAD + p*sp`
   (== 單 sweep pop 的中心 → 晃起序 == pop 的 phase 序);shearX:0(identity)→ hold 0 到 c →
   `A → −rA → +r²A → −r³A`(遞減交替 4 極值,A=role 峰值×side_sign,r=WOBBLE_DAMP,同 gen_wobble)→ 0(回穩)。
   4 極值壓進晃起窗 `[c, c+0.24]`(偏移 `CASCADE_WOBBLE_OFFS=(0,0.08,0.16,0.24)`),前後補 identity(0)。
   上界守衛:`c + 0.24 < 1`(= `CASCADE_LEAD + sp + 0.24 < 1` → sp≲0.60,同 reveal)。
3. `gen_animations._build_beat` / `build_animations` / `build_spine.build` 加 `cascade_wobble` 旗標
   (mirror `cascade_reveal`);`build_spine --cascade-wobble`。

## crux:跨件晃起序如何可量(argmax 範式第三個實例)

每件 shearX 的**首個極值**幅度 A(阻尼下最大,後續 rA/r²A/r³A 遞減)唯一落在其晃起中心 c →
per-bone `argmax(|shearX|)` 可靠量得跨件晃起時刻 → 跨件晃起序可量。與 pop 用**峰時刻**、reveal 用
`argmax(scaleX)`(overshoot 峰解掉尾端 identity 平台)同屬 **per-bone argmax 範式**,只是量的通道不同
(pop/reveal 量 scaleX、wobble 量 |shearX|)。

## 5 AC(真實 robot 骨架,build_spine → build_animations 端到端)

- **W1 present + backward-compat**:wobble build 產每 cascade beat finite/有 bone;`cascade_wobble=False` 逐位元
  同 pop(零回歸);wobble=True 下非 cascade 主秀 beat(7 個)逐位元不變(wobble 只作用 cascade)。
- **W2 crux wobble ordering**:各件晃起時刻 argmax(|shearX|) 依 phase(件序)嚴格遞增
  `[0.16, 0.295, 0.43, 0.565, 0.70]`(== `c = CASCADE_LEAD + p·SPAN`)+散佈 0.54≥0.30(仍一道有序晃動波)。
- **W3 crux shear primitive**:每件運動基元走 shear 通道(有 `shear` timeline、shearX **阻尼振盪**:繞 0 變號 ≥3
  且相繼極值 |值| 嚴格遞減,如身體 `14→−7→3.5→−1.75`)且**無 scale 脈衝**(scaleX 全程 identity);**首尾 shearX==0**
  (兩端 identity → 兩端可接 Loop)。
- **W4 wobble vs pop/reveal**:(a) crux 同一 beat pop 走 scale(shearX≡0、scaleX 有脈衝)vs wobble 走 shear
  (scaleX≡identity、shearX 有擺動)→ 乾淨分離;(b) neg-control pop **不**滿足 wobble shearX 阻尼振盪、wobble **不**
  滿足 reveal「首幀 collapsed scaleX≈0.02」(證閘非恆真);(c) vs reveal wobble 首幀 shearX==0/scaleX==identity
  非 collapsed、reveal 首幀 scaleX≈0.02 → **三種單件運動基元彼此乾淨分離**。
- **W5 metric + dir + guards**:(a) 晃起排序 N 與 HIRES 取樣下一致(metric 良定義);(b) **dir discriminator**
  wobble + cascade_dir="lr" 下晃起序 == x 排序 ≠ 件序(wobble 沿用 dir threading);(c) guards wobble×nrip>1 /
  wobble×span 過大 / wobble×reveal 同開 皆 ValueError(build 與 gen 雙驗);(d) 端到端
  `build_spine --animate --cascade-wobble` 產可載入 spine(cascade anim finite + 含 shear + 首尾 shearX=0)。

## 關鍵發現

1. **cascade 的「單件運動基元」軸可承載任意 transform 通道**——pop/reveal 走 scale,wobble 走 shear,是第一個
   進跨件波的 shear 通道。運動基元軸不綁定特定通道,是一條真正通用的軸(呼應 G-4 系列把一般仿射四自由度逐一
   被真實 beat 驅動:這裡把 shear 進一步錯開成跨件波)。
2. **介面契約由運動基元本身決定,不由 cascade 決定**——pop 與 wobble 皆「首尾 identity 兩端可接 Loop」但走不同
   通道(scale vs shear),reveal 則首端 collapsed 不可接。同一條跨件波,不同運動基元的端點契約可不同。
3. **per-bone argmax 範式跨通道通用**——pop 量 scaleX 峰時刻、reveal 量 argmax(scaleX)(overshoot 唯一峰)、
   wobble 量 argmax(|shearX|)(首極值阻尼下最大)。只要運動基元在晃起時刻有唯一全域極值,跨件序就可量。
4. **一般化靠特例逐位元等價釘住**——wobble=False≡pop 逐位元,呼應 reveal=False≡pop、J-6 lr/rl≡0°/180°、
   L-7 等值向量≡scalar。

## honest boundary

- 用 pop/reveal/wobble(哪個 beat 該晃)皆屬美術手感(**A 類 PROPOSAL**);本閘只新增一個**確定性**運動基元 +
  其跨件晃動波。
- 晃起包絡窗(`CASCADE_WOBBLE_OFFS`)/阻尼比(`WOBBLE_DAMP`)沿用 gen_wobble 的量級選擇。
- wobble 與 nrip(多道波)互斥、與 reveal 互斥、與 span/dir 正交;span 上界同 reveal(≲0.60)。
- 無改任何 pop 生成/產線值(wobble=False 逐位元不變);單一真值資產(robot_parts.psd)。
- **wobble 尚未接 tier 幅度 / count-aware**(後續可比照 J:晃起 shear 峰隨檔位遞增;或 nosc 隨檔位,
  但跨件晃動波為一次性單道,段數軸語意須另定)。
