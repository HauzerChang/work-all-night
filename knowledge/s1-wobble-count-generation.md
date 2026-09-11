# S1 — wobble 振盪段數隨檔位遞增(candidate G-4''',`wobble_count_generation` L2)

> 2026-09-11。續 (G-4''):(G-4'') 讓 wobble 的 shearX 峰**幅度**隨檔位遞增,但各檔位仍是**同樣 4 段**
> 阻尼振盪(有「多斜」沒「晃幾下」)。本次補上 wobble 的振盪**段數** `nosc` 隨檔位嚴格遞增
> (Super 4 → Mega 5 → Omg 6 → Legend 7)。這是繼 (J-2) combo 連擊數之後,第二個**結構(拓樸)軸**的
> 檔位差異化 —— 與幅度軸正交可疊。

## 缺口(honest boundary 的接續)

- **(G-4'')** 把 wobble 併入 `MAIN_SHOW_CATS`、讓 `amplify_bone_tl` 放大 shear → **幅度**隨檔位遞增,
  但誠實標記 honest boundary:「wobble 未接 count-aware(晃動段數隨檔位需 gen 時決定,同 J-2 對 combo)」。
- 本次(G-4''')正好照那條邊界接上:**振盪段數也隨檔位遞增**。

## 關鍵:幅度增益加不出「段數」(同 J-2 對 combo 峰數)

段數 = 關鍵幀**拓樸**(繞 0 交替變號的極值個數)。事後 `amplify_bone_tl` 只能對既有極值**同比放大**
(`v'=g*v`),無法多長一個極值 → 段數是**結構**、必須在 `gen_wobble` 生成當下決定。故不走 amplify,
而是對 wobble 檔位變體以該檔位 `nosc` **重生成**整支 beat,再疊 (G-4'') 幅度增益 g:

- **段數軸**(結構,gen 時決定):`nosc` [4,5,6,7]。
- **幅度軸**(事後 amplify):峰 |shearX| [16, 21.6, 27.2, 33.6]°(g=[1.0,1.35,1.70,2.10])。
- **兩軸正交可疊**:段數 + 平增益 → 段數遞增·峰幅不變;增益 + 無段數 → 段數恆 4·峰幅遞增。

此模式與 (J-2) 對 combo 連擊數完全同構,惟**段數階梯各類別獨立**
(combo → `TIER_COMBO_HITS`、wobble → `TIER_WOBBLE_CYCLES`),`build_animations` 依 `cat` 路由。

## 做了什麼(全 additive)

1. **`beat_templates.gen_wobble(role, side_sign, radial, nosc=4)`** 加 `nosc` 參數 + `_wobble_env(A, nosc)`
   通用阻尼振盪包絡:第 i 極值符號 `(−1)^i`(首推 +A)、幅度 `A·rⁱ`(r=WOBBLE_DAMP=0.5 阻尼)、τ 於
   `[WOBBLE_LEAD=0.16, WOBBLE_TAIL=0.80]` 均勻分布。**nosc==4 走原手調 golden(byte-identical 向後相容)**。
2. **`tier_variants.py`**:`COUNT_AWARE_CATS` 加 `"wobble"`;新增 `TIER_WOBBLE_CYCLES`(slot_bigwin
   Super4→Legend7)+ `wobble_cycles_for(genre)`。
3. **`gen_animations.py`**:`_build_beat(..., count=None)`(原 `combo_hits=3` 泛化 —— `count is None` →
   呼叫生成器**自身預設**,combo=3/wobble=4,golden byte-identical);`build_animations(...,
   tier_wobble_cycles=None)` 依 cat 從 `{"combo": tier_combo_hits, "wobble": tier_wobble_cycles}` 路由段數。
4. **`build_spine.py`**:`--tier-variants` 時一併帶 `wobble_cycles_for(genre)`。
5. **`validate_wobble_count.py`**(新,5 AC)。
6. **`check_readiness`** 新增 cap `wobble_count_generation` L2 併入 `spine-anim-forge`(仍 HOLD)。
7. 圖 `knowledge/figures/s1_wobble_count.png`(左:各檔位阻尼包絡段數遞增;右:段數 bar + 峰幅雙軸疊圖)。

## 自我驗收(`validate_wobble_count.py`,5 AC 全 PASS)

從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(tier_gains, tier_wobble_cycles)` 端到端量:

- **U1 present + backward-compat**:每檔位 `wobble__{tier}` finite/有 bone/帶 shear;**base wobble 恆 4 段**
  逐位元同無檔位;`tier_wobble_cycles=None` 時 wobble 變體逐位元同 (G-4'') 幅度-only(加性 opt-in 零回歸)。
- **U2 crux — 段數單調**:各檔位振盪段數 == 宣告 **[4,5,6,7]** 且 Super<Mega<Omg<Legend **嚴格遞增**;
  Super 段數 == base 段數(向後相容)。
- **U3 簽章保形**:**每檔位**仍 (a)首尾 shearX==0;(b)繞 0 變號 ≥3;(c)相繼極值幅度嚴格遞減(阻尼);
  **且**峰 |shearX| 仍隨檔位嚴格遞增(段數軸不抵消幅度軸,兩效可疊)。
- **U4 正交**:(a) 段數 + 平增益(全 g=1.0)→ 段數遞增·峰幅**不**遞增(結構獨立於幅度);
  (b) 增益 + 無段數(twc=None)→ 段數恆 4·峰幅遞增(兩軸可獨立開關)。
- **U5 負對照**:(a) 平段數(全 4)→ 段數單調性 FALSE(證閘測遞增非恆真);
  (b) slot_reveal 無宣告 → `wobble_cycles_for` None → 不亂加段數變體;
  (c) 段數只作用 wobble → 非-wobble 主秀 beat 的 shear 段數各檔位恆定(不外洩)。

**端到端**:`build_spine --animate --tier-variants --shear-pivot` 直出 `wobble__{Super4,Mega5,Omg6,Legend7}`
段(pivot 補償後仍 [4,5,6,7]),`validate_build` round-trip **overall_pass**。

## 關鍵發現 / 踩雷

- **段數是結構軸、幅度是強度軸,兩軸正交**:同 J-2 對 combo 的核心洞見再現於 shear 通道 —— 但一個
  抽象(count-aware)概念在**兩個不同通道**(combo=scale 峰數、wobble=shear 振盪段數)成立,證明
  「結構隨檔位、幅度隨檔位」是可推廣的檔位差異化雙軸範式。
- **段數階梯必須各類別獨立**:combo 與 wobble 的段數語意不同(連擊數 vs 晃動段數),故不共用
  `TIER_COMBO_HITS`;`_count_maps` 依 cat 路由,`_build_beat(count=None)` 讓各生成器用自身預設保 golden。
- **阻尼比 r=0.5 對任意段數保簽章**:整條包絡是等比阻尼 `A·rⁱ`,任意 nosc 下相繼極值皆嚴格遞減、
  交替變號 nosc−1 次(nosc≥4 → ≥3)→ 阻尼振盪簽章對段數天然保形(同 g 同比放大對幅度保形)。
  上界 7:特效 16°·r⁶=0.25° 仍 finite 且與前極值 0.5° 於 4 位小數可辨(遞減不塌陷)。

## honest boundary(仍在)

- 段數階梯數值 [4,5,6,7] 為 **PROPOSAL**(結構簽章客觀、晃幾下才對味的手感留使用者 A 類)。
- 目前只產 **shearX**(shearY≡0);**斜拉 squash**(shear + coupled scale 雙通道耦合)為後續。
- 單一真值資產(robot_parts)、運動基元先驗 → `spine-anim-forge` 區塊**仍 HOLD**(防固化)。

## 下一步(擇一,皆純自主)

- 產 **shearY** / **斜拉 squash**(shear + coupled scale 雙通道耦合的運動基元 + 端到端閘)。
- **(J-3)** cascade 波速/散佈/件數隨檔位(cascade 的 count-aware:跨件波的第三種檔位軸)。
- **(G-1)** `--rig`×pivot 各 flag per-bone 語意去重;**(G-2)** 主秀 beat 下 limb 繞關節 AC。
- S5→L3 仍待 **(D) 多 rig 真值**(C/資源類,使用者提供)。
