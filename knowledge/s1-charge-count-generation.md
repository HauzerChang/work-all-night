# S1 — charge 蓄力段數隨檔位遞增(candidate G-4'''''-charge,`charge_tier_stage_count` L2)

> 2026-10-03。續 (J):(J) 讓 charge 的釋放**幅度**隨檔位放大(愈高檔位釋放愈爆),但各檔位仍是
> **同樣單段長蓄力**(有「多爆」沒「充幾段」)。本次補上 charge 的充能**階梯數** `nstage` 隨檔位
> 嚴格遞增(Super 1 → Mega 2 → Omg 3 → Legend 4)。
> 這是**結構(拓樸)軸**檔位差異化的**第五個單件通道**(前四:combo 連擊數 J-2、wobble 振盪段數
> G-4'''、squash 擠壓段數 G-4'''''-c、twist 扭轉段數 G-4''''''-count),加上 cascade 的**跨件**波掃
> 次數(J-3)——與幅度軸正交可疊。

## 缺口(honest boundary 的接續)

- candidate (J) 把 charge 併入 `MAIN_SHOW_CATS`、讓 `amplify_bone_tl` 以 `_amp_scale` 放大釋放
  overshoot → **幅度**隨檔位遞增,但各檔位的 charge 仍是**同一道單段長蓄力**。
- 本次正好照那條邊界接上:**充能階梯數也隨檔位遞增**——高檔位多充幾段(逐段更深)再釋放。

## 關鍵:幅度增益加不出「充能台」(同 J-2/G-4'''/G-4'''''-c/G-4''''''-count)

充能台 = 關鍵幀**拓樸**(pre-peak 一道道逐段更深的 squash 平台,各為一個局部極小)。事後
`amplify_bone_tl` 的 `_amp_scale` 只放大 **identity 上方**的 overshoot、**下方充能樓地板不動**
(`1+g·(v−1) if v≥1 else v`)→ 既加不出一道新充能台,也不改既有台的深度 → 充能台是**結構**、
必須在 `gen_anticipate_hold` 生成當下決定。故不走 amplify,而是對 charge 檔位變體以該檔位 `nstage`
**重生成**整支 beat,再疊 (J) 的單一-g 幅度增益:

- **段數軸**(結構,gen 時決定):`nstage` [1, 2, 3, 4]。
- **幅度軸**(事後 amplify,`_amp_scale`):釋放 overshoot 隨 g=[1.0, 1.35, 1.70, 2.10] 遞增,
  下方充能樓地板(0.82–0.93)逐檔不動。
- **兩軸正交可疊**:段數 + 平增益 → 台數遞增·釋放幅度不變;增益 + 無段數 → 台數恆 1·釋放幅度遞增。

此模式與 combo/wobble/squash/twist 同構,惟**段數階梯各類別獨立**(charge → `TIER_CHARGE_STAGES`),
`build_animations` 依 `cat` 路由 `_count_maps`。

## charge 獨有的 crux(與 combo 段數的本質差異):充能台全在 identity 下方 → 不混入 combo impact 峰

combo 的段數 = **遞增 impact 峰數**(各峰 ≥ `IMPACT_PROM`=1.10,在 identity **上方**);
charge 的段數 = **pre-peak 充能台數**(各為局部極小、逐段更深,**全在 identity 下方** <1.0 <1.10)。
這是 charge count 相對 combo count **多出的一層驗證**:段數增多後,charge 必須**仍是 charge、仍非 combo**。

- **唯一 impact 峰**:不論充幾段,充能台全 <1.0 → 不計入 impact(`impact_peaks` 門檻 1.10)→
  整支 charge 恆**只有一個 impact 峰 = 釋放**。段數增多**不**造出第二個 impact 峰。
- **兩互斥簽章不混淆**:段數增多後仍 `has_charge_signature`(見下)且 `has_combo_signature` 恆 False
  (後者需 ≥3 個遞增 impact 峰)。對照 (J-2) combo count:combo 段數增多正是多長 impact 峰 ——
  同一「段數軸」在兩個通道落在**曲線的不同側**(identity 上方 vs 下方)。

### charge 簽章(兩條件並立,同 squash「守恆且非均勻」、cascade「散佈且遞增」)

`validate_more_beats.has_charge_signature`:
1. **峰前長蓄力**:`pre_peak_hold_frac`(峰前 scale <0.97 的時間佔比)≥ 0.35;
2. **squash-floor**:峰前最低 scale > `SQUASH_FLOOR`=0.50(是 squash 壓縮蓄力 ~0.85,非 reveal 的
   collapse ~0.02)。

多段充能設計天然保兩者:全段充能窗(τ≈0.03–0.55)皆 <0.97 → hold 佔比實測 ~0.80(>>0.35);
末台樓地板 0.82 > 0.50(可辨於 reveal 的塌陷)。幅度 amplify 只動 identity 上方 → 兩條件逐檔不變。

## 做了什麼(全 additive)

1. **`beat_templates.py`**:`gen_anticipate_hold` 加第 4 位置參數 `nstage=1`。`nstage==1` 走原 0g 手調
   golden(單段長蓄力,**逐位元向後相容**);`nstage≥1` 一般路徑用新 `_charge_env(peak, nstage)` 產
   nstage 道逐段更深的充能台(樓地板 `CHARGE_FLOOR_HI`=0.90 → `CHARGE_FLOOR_LO`=0.82 線性遞減,各為
   局部極小),台間 `CHARGE_REGRIP`=0.93 分隔(**<HOLD_LEVEL 0.97** → 全程算充能,保 charge≠combo:
   combo 擊間回 0.985 >0.97),末台後單發釋放 → 固定阻尼回擺尾。role 通道(limb 反向蓄力/特效 壓暗+旋轉)
   逐段加深,首尾歸零/歸一。
2. **`tier_variants.py`**:`charge` 併入 `COUNT_AWARE_CATS`;新增 `TIER_CHARGE_STAGES`
   (`slot_bigwin`: Super1→Legend4,上界 4:充能窗 τ[0.15,0.48] 均分 nstage 台 + (nstage−1) 道 re-grip,
   nstage=4 台心間距 0.11、各台/台間 0.90/0.867/0.833/0.82 vs 0.93 於 4 位小數可辨、末台 0.82>SQUASH_FLOOR、
   釋放 0.58<1 首尾 identity)+ `charge_stages_for(genre)`。
3. **`gen_animations.py`**:`build_animations` 加 `tier_charge_stages=None` 參數;`_count_maps` 加
   `"charge": tier_charge_stages`。既有 `_COUNT_AWARE_CATS` 分支已通用(count 傳給 `gen_anticipate_hold`
   第 4 位置參 `nstage`),無須改路由。**零回歸來源**:charge∈COUNT_AWARE_CATS 後,count is None 時仍
   `_DISPATCH["charge"](role, side_sign, radial)` → nstage 預設 1 → golden(與原 `else` 分支同一呼叫)。
4. **`build_spine.py`**:`--tier-variants` 時 `charge_stages_for(genre)` → `tier_charge_stages=tcstg`。
5. **`validate_charge_count.py`**(新閘,5 AC):見下。

## 驗收(`validate_charge_count.py`,先驗庫 → 真實 build_spine robot 骨架 → build_animations)

**5 AC 全 PASS**:
- **CH1 present + backward-compat**:每檔位 `charge__{tier}` 產出、finite、有 bone;**base charge 恆 1 台
  逐位元同無 count**;`tcstg=None` 時 charge 變體逐位元同 (J) 幅度-only(加性 opt-in 零回歸)。
- **CH2 crux — count monotone**:各檔位充能台數 [1,2,3,4]==宣告且嚴格遞增;每檔位每件台數一致。
  台數以 **prominence(谷底↔其後回升 ≥0.015)** 計,對 N=240 取樣下的慢坡/捨入穩健(逐樣本差會把
  re-grip/釋放的慢回升誤判成平段而漏數——實作踩雷,見下)。
- **CH3 interface+signature kept**:每檔位首尾 setup identity + 仍 `has_charge_signature`(hold 佔比≥0.35
  + squash-floor)+ settle 變號≥3 + **仍非 combo** + **唯一 impact 峰**(充能台不計 impact)+ 幅度釋放
  overshoot 仍 Super<Mega<Omg<Legend 單調(證與 (J) 疊加不衝突)。
- **CH4 orthogonality**:(a) 段數 + 平增益(全 1.0)→ 台數遞增(結構獨立於幅度);(b) 增益 + 無段數 →
  台數恆 1·釋放幅度遞增(**crux:幅度加不出第二道充能台**)。
- **CH5 neg-control**:(a) 平段數(全 1)→ 台數單調性 FALSE(證閘測遞增非恆真);(b) `slot_reveal`
  `charge_stages_for` None + `gains_for` None → 不產 charge 段數變體;(c) 只帶 `tier_charge_stages` 時,
  非-charge 的 count-aware 主秀 beat(combo/wobble/squash/twist)之 tier 變體逐位元同 (J) 幅度-only
  (charge 段數圖不外洩到別的節拍)。

端到端 `build_spine --animate --tier-variants`(可配 `--shear-pivot --twist-volume`)直出
`charge__{Super,Mega,Omg,Legend}`,`validate_build` round-trip overall_pass。回歸:`check_readiness.py`
全綠(52 閘;51 既有 + 新 charge_tier_stage_count),無 GREEN→RED。

## 實作踩雷:count 量測不可用「逐樣本差」偵測谷(慢坡誤判)

初版 `charge_stages` 用「下降進谷 → 平段(逐樣本差 ≤eps)→ 回升」偵測,在 N=240 取樣下得 [1,1,2,4]
(漏數)。根因:re-grip/釋放的**回升**每樣本斜率(如 0.90→0.93 跨 ~39 樣本 → 0.00077/樣本)**< 任何
固定 eps**,逐樣本差把慢回升誤判成「平段」而把整段併成一個谷。**改用 prominence(值域落差):谷底↔其後
回升幅度 ≥0.015 才計一台** —— 對取樣密度/捨入穩健(落差是值域量、與斜率/樣本數無關)。此為量化閘通則:
**計「極值個數」要用 prominence(值域門檻),不要用逐樣本斜率/差分門檻**。

## 關鍵發現

- **結構(段數)軸已在 combo / wobble / squash / twist **四個單件通道** + charge **第五個單件通道** +
  cascade **跨件通道** 成立**;同一 count-aware 概念在 scale 上方峰數(combo)、單軸 shear 段數(wobble)、
  shear+耦合 scale 段數(squash)、反相雙軸 shear 段數(twist)、**scale 下方充能台數(charge)**、跨件波掃
  道數(cascade)皆通用。
- **同一「段數軸」在不同通道落在曲線不同側**:combo 的段數是 identity **上方**的 impact 峰、charge 的段數
  是 identity **下方**的充能台 —— 故 charge count 要多驗一層「段數增多不混入對方的簽章」(台全在下方 →
  唯一 impact 峰 → 仍非 combo)。對照 twist/squash count 多驗的是「跨通道約束(φ/體積)段數後仍成立」:
  **帶『與他類別簽章互斥』或『跨通道約束』的 count-aware,都要多驗一層那條性質在段數增多後仍守住**。
- 充能台樓地板全在 identity 下方 → 幅度 `_amp_scale` 天然不動它們 → 段數軸與幅度軸正交**由機制保證**
  (不像 squash/twist 需耦合/重算補償)——charge 是「段數×幅度最乾淨正交」的通道。

## honest boundary(仍在)

- 充能階梯(1–4)/ 幅度 / 各台深度皆 **PROPOSAL**(手感 A 類,留使用者拍板)。
- **單一真值資產**(robot 骨架);運動基元先驗、防固化 → cap `charge_tier_stage_count` L2 併入
  `spine-anim-forge`(**仍 HOLD**)。
