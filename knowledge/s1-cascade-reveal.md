# S1 (J-15) cascade 入場波變體:每件 collapsed→依序 burst 現身(entrance vs pop)

> 結論先行:至 (J-14) 為止,cascade 一直是 **pop 波**(每件恆 identity、依序短暫放大再回 identity,首尾皆
> identity);J-5..J-14 只動波的**方向 / 散佈 / 段數**,從未動**單件運動基元**。J-15 新增 **reveal 入場波**:
> 把單件運動由「pop 脈衝」換成「reveal 入場」——每件**起始 collapsed**(scale≈0 + alpha 0,隱形),依 phase
> **依序 burst 現身**(collapsed → 蓄勢 hold → overshoot burst → 阻尼回穩 identity),現身後**保持 identity 到結尾**。
> 這是一條與 pop **語意不同**的跨件波:pop 是「一件接一件閃一下(全程可見)」,reveal 是「一件接一件冒出來(揭幕 /
> 入場)」。**首幀非 identity**(所有件 collapsed)是兩者乾淨鑑別點。

- **信心**:高(5 AC 全 PASS,真實 robot 骨架端到端,含零回歸 + 負對照 + argmax 良定義 crux)。
- **階段**:S1 反推分析器(動畫 keyframe 生成端,主秀 beat 運動基元擴充)。cap `cascade_reveal` **L2**,併入
  `spine-anim-forge`(仍 HOLD,防半成品固化)。

## 做了什麼(全 additive,pop 路徑逐位元不變)

1. `beat_templates.gen_cascade(..., reveal=False)`:新增 `reveal` 參數。`reveal=False`(預設)→ 原 **pop 波**
   (逐位元向後相容);`reveal=True` → 委派 `_gen_cascade_reveal`(入場波),且因入場為一次性 → **`nrip` 必須 1**
   (否則 ValueError),`span` 上界更緊(`CASCADE_LEAD+span+0.24<1` → span≲0.60,否則 ValueError)。
2. `_gen_cascade_reveal(role, side_sign, T, peak, p, sp)`:單件入場包絡。現身中心 `c = CASCADE_LEAD + p*sp`
   (== 單 sweep pop 的中心 → **入場序 == pop 的 phase 序**)。
   - scale:`COLLAPSE(0.02)` 藏 → hold COLLAPSE 到輪到它 → **overshoot burst**(peak>1,唯一峰)→ 0.95 → 1.02 → 1.0 → hold 1.0。
   - alpha:0(藏)→ 0(hold)→ 1(burst 時亮)→ hold 1。所有 role 皆淡入(collapsed = scale≈0 **且** alpha 0,雙重隱形)。
   - limb / 特效 另加 rotate(內收藏 → burst 甩出 → 阻尼回正)。
3. `_build_beat` / `build_animations` / `build_spine.build` 加 `cascade_reveal` 旗標(mirror `twist_volume` 的 bool 線程);
   CLI `build_spine --cascade-reveal`。`cascade_reveal=False` 全程逐位元同舊行為。
4. 新閘 `validate_cascade_reveal.py`(J-15,5 AC)。

## crux:處理「多件 collapse 疊加對 argmax 的擾動」(本 run 核心設計決策)

reveal 的量化風險:若單件只是「collapsed hold → 升到 identity 後**平台**」(整段尾端 =1.0 的平地),則該件
`argmax(scaleX)` 會落在**尾端 identity 平台的第一個取樣點**,量不到真正的**現身時刻** → 多件在 τ=0 的 collapsed 平台
+ 尾端 identity 平台使跨件現身序**不可靠**(這正是 STATE 候選清單標注的「多件 collapse 疊加對 argmax 的擾動」)。

**解法**:讓每件 burst 時有**唯一 overshoot 峰**(peak>1,現身後只回到 1.0)→ `argmax(scaleX)` 唯一落在其 burst
時刻(高於尾端 identity 平台)→ 跨件現身序以 per-bone argmax **可靠量得**(各件 timeline 獨立,峰唯一,不互相干擾)。
R4(c) 固化:每件全域 `max(scaleX) > 1.0 + 0.05` 且 burst 落在 `τ < 1`(非尾端平台);實測 robot:
`b_光暈 max=1.35`、`b_身體 max=1.28`、其餘 `1.18`,burst τ = [0.22, 0.355, 0.49, 0.625, 0.76](嚴格遞增)。

## 5 AC(全 PASS,真實 robot 骨架,`assets/robot_parts.psd`)

- **R1 present + backward-compat**:reveal build 產每個 cascade beat 且 finite / 有 bone;`cascade_reveal=False`
  **逐位元同預設(pop,零回歸)**;reveal=True 下**非 cascade 主秀 beat 逐位元不變**(reveal 只作用 cascade)。
- **R2 reveal ordering(crux)**:各件 **burst 時刻**(argmax scaleX)依 phase(件序)**嚴格遞增**
  `[0.22, 0.355, 0.49, 0.625, 0.76]`,散佈 0.54 ≥ 門檻(仍是一道有序入場波)。
- **R3 entrance interface(crux)**:**首幀所有件 collapsed**(scaleX≈0.02 **且** alpha≈0,**非 identity**)+
  **尾幀所有件 identity**(scaleX≈1 **且** alpha≈1 → 入場波後可接 Loop,同其他主秀 beat 的**尾端**契約);
  每件現身後**停在 identity**(burst+0.2 之後仍 ≥0.9,不回 collapse)。
- **R4 reveal vs pop + neg-control**:
  - (a) **crux 乾淨分離**:同一 beat,pop 首幀 `scaleX==1`(identity)、reveal 首幀 `scaleX≈0.02`(collapsed);
    pop 首幀 `alpha==1`、reveal 首幀 `alpha≈0`。
  - (b) **neg-control**:pop **不**滿足 reveal 的「首幀 collapsed」(證閘非恆真);reveal **不**滿足 pop 的
    「首幀 == 尾幀 == identity」。
  - (c) **crux argmax 良定義**:每件全域 max > 1.05 且 burst 落在 τ<1(不被 collapsed/identity 平台搶走)。
- **R5 metric + dir + guards**:
  - (a) burst 排序在 N(240)與 HIRES(9600)取樣下**一致**(metric 良定義)。
  - (b) **dir discriminator**:reveal + `cascade_dir="lr"` 下 burst 序 == x 排序 **≠** 件序(reveal **沿用** J-5/J-6/J-7..
    的方向 threading — 入場序隨 cascade_dir)。
  - (c) **guards**:reveal×nrip>1 → ValueError(一次性入場)、reveal×span 過大(CASCADE_LEAD+span+0.24≥1)→
    ValueError;build 與 gen_cascade 直呼**雙驗**。
  - (d) **端到端**:`build_spine --animate --cascade-reveal` 產可載入 spine(cascade anim finite + 首幀 collapsed)。

## 關鍵發現

1. **cascade 有兩條正交軸**:「波的方向 / 散佈 / 段數」(J-5..J-14,動**哪件何時** pop)與「**單件運動基元**」
   (J-15,pop vs reveal,動**每件做什麼**)。前十個候選全在第一條軸上疊方向 source,J-15 是**第一個**動第二條軸。
2. **reveal 入場波的首幀非 identity 使介面契約與其他主秀 beat 不同**:**尾**可接 Loop(尾 == setup identity),
   **首**不可接在 Loop 之後(首 collapsed)——這是刻意的**入場 / 揭幕**語意(大獎開場「角色逐一登場」),
   不是 bug。pop / hit / combo / charge / wobble / squash / twist 皆首尾 identity(可插 Loop 間),reveal 是唯一
   首非 identity 的主秀 beat(單件 `gen_reveal` 早已如此,J-15 是其**跨件**版)。
3. **overshoot 峰是讓「依序現身序可量」的關鍵設計**:解掉尾端 identity 平台對 argmax 的擾動(見上 crux)——
   這呼應 J-系列反覆出現的「真訊號常需讓量測點唯一 / 不被平台或混疊搶走」(cf. J-5 的 HIRES 消混疊、J-8 的符號定號)。
4. **一般化靠特例逐位元等價釘住**:`reveal=False` 逐位元同 pop(呼應 J-6 的 lr/rl==θ=0°/180°、L-7 的等值向量≡scalar)。

## honest boundary

- 用 reveal 還是 pop(以及哪個 beat 該入場)仍屬**美術手感**(A 類 PROPOSAL);本閘只新增一個**確定性**運動基元
  + 其跨件入場波,不替使用者決定何時用。
- 入場包絡的窗寬 / overshoot / 阻尼係數為量級選擇(沿用單件 `gen_reveal` 的手調值)。
- reveal 與 count(nrip)**互斥**(入場為一次性);與 span 相容但上界更緊(span≲0.60)。這是語意限制,非缺陷。
- 單一真值資產(robot);無改任何 pop 生成 / 產線值(reveal=False 逐位元不變)。與 `spine-anim-forge` 同 **HOLD**。
