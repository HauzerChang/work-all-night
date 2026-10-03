# S1 charge 蓄力充能階段數隨檔位遞增(candidate G-4'''''-charge)

> 結論:count-aware(結構/段數軸)推到最後一個尚未接的**單件主秀通道** charge(anticipate_hold)。
> 依據:`tools/analyzer/validate_charge_count.py` 5 AC 全 PASS + `check_readiness.py` 0 RED。
> 信心:高(確定性演算法 + 量化閘 + 負對照;階數階梯本身為 PROPOSAL 手感 A 類)。
> 相關階段:第 2 階段(用工具鍛鍊 S1 分析器→生成器)。里程碑:2026-10-03 run 001。

## 做了什麼

candidate (J) 已讓 charge 的 release 峰**幅度**隨大獎檔位遞增(愈高檔位愈爆),但各檔位仍是**同樣 1 階**
單發蓄力充能 —— 有「多爆」沒「蓄幾段」。本次補上充能-釋放**階段數** `ncharge` 隨檔位嚴格遞增
(Super 1 → Mega 2 → Omg 3 → Legend 4):愈高檔位愈多階蓄力,每階 = 快速下蹲 → **長 hold** 充能 →
release overshoot(遞增)→ 微回,末階 release = role peak。

## 為何不能用幅度增益加出階段(與 count 系列同理)

階數是關鍵幀**拓樸**(dip→hold→release 的窗數),必須在 `gen_anticipate_hold` 生成當下決定;事後
`amplify_bone_tl` 只能同比放大既有 overshoot、無法多長一階。故對 charge 檔位變體以該檔位 `ncharge`
**重生成**整個 beat,再疊 (J) 幅度增益 g → 與幅度軸**正交可疊**(階數 [1,2,3,4] × release 峰幅皆遞增)。

## charge 獨有 crux — 計數簽章須多驗一層(與 combo count 的鑑別)

**combo 與 charge count 的外形相同** —— 都是「N 個遞增 scale 峰」。光數 impact 峰**無法鑑別**
(combo 也是遞增 N 峰)。差別在**峰間**:
- **combo**:峰間只有**短** dip(擊間微回 >HOLD_LEVEL 0.97),hold 佔比小。
- **charge**:每階在 release 前有一段**持續**低 hold(sustained,佔該階大半)。

故 charge count 簽章在「階數 == ncharge」之外**多驗一層**:**每一階都是真蓄力階**(該階區間內
scale<0.97 的 hold 佔比 ≥ 門檻)。以此對 combo 做負對照 —— combo 每階 hold 佔比 ≤0.34 < 門檻 0.60
→ **FAIL charge-count 簽章**。這證「數峰 + 每階持續 hold」兩條件並立才是 charge count,呼應 (J-3)
「跨件 count 比單件 count 多驗一層」與「真簽章常需兩獨立條件並立」的通則。

實測(N=240):charge 每階 hold 佔比 min 0.707;combo 每階 max 0.338 → 門檻 0.60 居中,兩側皆 >0.1 餘裕。

## 實作(全 additive)

- `beat_templates.gen_anticipate_hold(role, side_sign, radial, ncharge=1)`:`ncharge==1` 走手調 golden 分支
  (逐位元向後相容);`ncharge>1` 走 `_charge_env(peak, ncharge)` 通用多階包絡(每階 dip 0.90 / hold floor
  0.85 / release p=1+q(0.55+0.45f) 遞增,末階=peak;首階 release 夾 ≥IMPACT_PROM;階間微回 0.975>HOLD_LEVEL
  不併入下一階 hold;末階後固定 settle 尾,峰 <IMPACT_PROM)。rotate/color 對齊各階峰、幅度隨階遞增。
- `tier_variants.py`:`charge` 併入 `COUNT_AWARE_CATS`(純 scale,非 SHEAR/COUPLED → 走逐軸 amplify);
  新增 `TIER_CHARGE_CYCLES = {slot_bigwin:{Super1,Mega2,Omg3,Legend4}}` + `charge_cycles_for`。
- `gen_animations.build_animations(tier_charge_cycles=None)`:`_count_maps` 加 `"charge"` 鍵,依 cat 路由。
- `build_spine.py`:`--tier-variants` 透傳 `charge_cycles_for(genre)` → `tier_charge_cycles`。
- `validate_charge_count.py`(新,5 AC)。

## 自我驗證(AC-first,量化)— `validate_charge_count.py` 5 AC 全 PASS

從先驗庫 → **真實 build_spine robot 骨架** → `build_animations(tier_gains, tier_charge_cycles)` 端到端量。

- **CC1 present + backward-compat**:每檔位 `charge__{tier}` 產出、finite、有 bone;base charge 恆 1 階且
  逐位元同無檔位;`charge__Super`(ncharge=1,g=1)逐位元==base charge;`tier_charge_cycles=None` 時 charge
  變體逐位元同 (J) 幅度-only(加性 opt-in 零回歸)。
- **CC2 crux — stage count monotone**:各檔位階數(= impact release 峰數)== 宣告 [1,2,3,4] 且嚴格遞增;
  Super 階數 == base(1)。
- **CC3 signature preserved**:每檔位仍 (a) 首尾 setup identity(可插 Loop);(b) 具 charge 簽章
  (峰前長蓄力佔比 ≥0.35 且峰前非塌陷 >SQUASH_FLOOR → 非 reveal);(c) **每一階** hold 佔比 ≥0.60
  (crux 多驗層);(d) 階內 release 峰嚴格遞增(末階=role peak)。且峰幅仍隨檔位嚴格遞增(階數軸不抵消幅度軸)。
- **CC4 orthogonality**:(a) 階數 + 平增益(g=1)→ 階數遞增、峰幅**不**遞增;(b) 增益 + 無階數 →
  階數恆 1、峰幅遞增(兩軸可獨立開關)。
- **CC5 neg-control**:(a) 平階數(全 1)→ 單調性 FALSE;(b) **crux discriminator** combo 變體(同為 N 遞增峰)
  每階 hold 佔比 0.31–0.34 < 0.60 → FAIL charge-count 簽章,且 combo 確有 ≥3 遞增峰(證「每階持續 hold」是
  鑑別子非「combo 沒峰」);(c) 階數只作用 charge:非-charge 主秀變體逐位元同幅度-only,`charge_cycles_for(slot_reveal)`
  回 None 不亂加。

## 回歸

`python3 tools/check_readiness.py` → 0 RED(新增 cap `charge_tier_count_aware` L2 GREEN,併入 `spine-anim-forge`,仍 HOLD)。

## 關鍵發現

1. **count-aware(段數軸)至此補齊全部單件主秀 beat**:combo(連擊數)/ wobble(振盪段)/ squash(擠壓段)/
   twist(扭轉段)/ **charge(蓄力階)** 五通道 + cascade 跨件波掃次數(J-3)。結構軸的鋪設在單件通道完整收斂。
2. **外形相同的兩種 count 必須靠「峰間行為」鑑別**:combo 與 charge count 都是「N 遞增 scale 峰」,只數峰會
   把兩者混為一談;真正的鑑別在峰間(combo 短 dip vs charge 持續 hold)。計數簽章要多驗「每階是否保有該
   beat 的本質簽章」(此處=每階一段持續 hold),否則「加階」可能悄悄把 charge 退化成 combo。
3. **向後相容錨點選 base 的自然值**:charge golden 是單發 → Super=1(同 cascade nrip Super=1),`ncharge==1`
   走手調 golden 分支保逐位元相容(同 combo nhits==3 / wobble nosc==4 的 golden 分支模式)。

## honest boundary(仍在)

- 階數階梯 [1,2,3,4] 為 PROPOSAL(手感 A 類,留給使用者微調);上界 4(charge T=0.8s 窗容量)。
- 單一真值資產(robot)。`spine-anim-forge` 仍 HOLD,成熟度不變(運動基元仍先驗手感、單一真值資產,防固化)。
