#!/usr/bin/env python3
"""candidate (J) — slot_bigwin 檔位(tier)幅度差異化(純 CPU,確定性)。

`genre_priors.slot_bigwin` 宣告 `tiers=[Super,Mega,Omg,Legend]` 已久,但生成器從未用它:
所有檔位共用同一組 beat 幅度 —— 又一「模板/宣告就緒 ≠ 生成器接上」的缺口(同 (E)/(H)/(I))。
本模組把檔位轉成**主秀幅度增益** g(檔位愈高、主秀愈爆),端到端接進 `build_animations`,
每個主秀 beat 依檔位產出一支 `{beat}__{tier}` 變體。

## 幅度增益規則(關鍵:對「setup identity 介面」與「結構簽章」皆保形)

  - scale 通道:對 identity(=1)之**上方** overshoot 放大 → `v' = 1 + g*(v−1)` **僅當 v≥1**;
    v<1(anticipation squash / reveal collapse 語意樓地板)**保持不變**(檔位無關)。
    ⇒ ① 端點=identity 的幀 g 後仍=identity(**介面契約對所有檔位保持**,可插 Loop 間);
       ② overshoot 峰隨 g **單調變大**(檔位簽章);
       ③ squash/collapse 樓地板檔位無關(**誠實**:蓄力深度/藏匿是結構語意,非大獎強度);
       ④ (scale−1) 的**符號序列不變** → hit/combo/charge 的 anticipation+settle 簽章逐檔保持
          (上方幀變大、下方幀不動、零幀仍零 → 變號數與遞增性都保留)。
  - rotate/translate 通道:對 0 對稱 → `v' = g*v`(0 仍 0,幅度隨 g 放大)。
  - color/alpha:**不動**(可見度非運動幅度;放大 alpha 會破壞 collapse/burst 語意且可能溢出 [0,1])。

只放大**主秀**類別(hit/reveal/burst/combo/charge/cascade);In/Loop/Out(進退場/待機)
**檔位無關**(idle 呼吸不該隨大獎檔位脹縮 → 負對照)。base tier(Super)g=1.0 →
`amplify_*` 為 identity 變換 → **逐位元 == 無檔位輸出**(向後相容)。

單位/格式同 `gen_animations` / `beat_templates`。bezier 緊湊鍵(curve/c2/c3/c4、stepped/linear)
以 deepcopy 保留,只覆寫數值欄位。
"""
import copy
import math

# 主秀類別(與 beat_templates 的節拍對應;In/Loop/Out 不在此 → 檔位無關)。
# candidate (G-4'') — 加入 `wobble`(斜拉 jelly wobble,G-4' 的 shear 通道節拍):
# 它是主秀節拍,強度理應隨檔位遞增,但幅度軸在 **shear** 而非 scale/rotate,
# 故 `amplify_bone_tl` 需一併放大 shear 通道(對 0 對稱 → v'=g*v,同 rotate/translate)。
# candidate (G-4''''') — 加入 `squash`(斜拉果凍擠壓,G-4'''' 的 shear + 體積守恆非均勻 scale 節拍):
# 它同為主秀節拍(強度理應隨檔位遞增),但 scale 軸是**耦合體積守恆**(scaleX·scaleY≡1),
# 逐軸 `_amp_scale`(只放大 identity 上方)會保留 scaleY<1 樓地板而只脹 scaleX → 破壞守恆
# (這正是 G-4'''' 當時把 squash 排除在外的 honest boundary);故用**耦合 amplify**(見 COUPLED_SCALE_CATS)。
# candidate (G-4''''''-tier) — 加入 `twist`(反相雙軸 shear,G-4'''''' 首度驅動 shearY 的節拍):
# 它同為主秀節拍(強度理應隨檔位遞增),幅度軸在**兩條 shear 軸**。twist 純 shear(無 scale 通道,
# 故**不**在 COUPLED_SCALE_CATS),`amplify_bone_tl` 的 shear 迴圈以同一 g 同時放大 shearX 與 shearY
# (v'=g*v,對 0 對稱)⇒ shearY/shearX = −TWIST_PHI 逐檔**不變**(單一 g 對兩軸同比)、反相(乘積符號)
# 與阻尼簽章亦保形 → **反相雙軸幾何 scale-invariant**(愈高檔位擰愈狠,但仍是同一種雙軸 shear 扭轉)。
MAIN_SHOW_CATS = {"hit", "reveal", "burst", "combo", "charge", "cascade", "wobble", "squash", "twist"}

# candidate J-2 / G-4''' / G-4'''''-c / G-4''''''-count — 依檔位可變「段數」的類別(結構性差異化,非只幅度)。
# combo 的 impact 峰**數**、wobble 的振盪**段數**、squash 的擠壓**段數**、twist 的扭轉**段數**隨檔位遞增;
# 需在 gen 時把段數帶進生成器(結構=拓樸,事後 amplify 只能放大既有極值、加不出一段)。各類別的段數階梯彼此獨立
# (combo → TIER_COMBO_HITS,wobble → TIER_WOBBLE_CYCLES,squash → TIER_SQUASH_CYCLES,twist → TIER_TWIST_CYCLES);
# build_animations 依類別路由。
# (G-4'''''-c)squash 加入:它同時是 COUPLED_SCALE_CATS,故段數重生成後仍走**耦合** amplify —— 段數×幅度×
# 體積守恆三效正交可疊(每檔位每擠壓極值 scaleX·scaleY≡1,不論擠壓幾段)。
# (G-4''''''-count)twist 加入:它是**兩條 shear 軸**的反相雙軸節拍(∈SHEAR_CATS,非 COUPLED_SCALE_CATS)。
# 段數重生成後兩軸各多長 nosc 個阻尼極值,每個新極值仍由 `_twist_env` 建構 shearY=−TWIST_PHI·shearX
# → **φ 比值由建構保證,與段數無關**;再套幅度增益(單一 g 對兩軸同比)→ 段數×幅度×φ 保形三效正交可疊
# (每檔位不論扭幾段,兩軸同比 φ 恆定、反相不變)。這是 twist count 獨有的 crux(比照 squash count 的體積守恆)。
# (G-4'''''-charge)charge 加入:它是**單發蓄力充能**節拍(∈MAIN_SHOW_CATS、純 scale,非 SHEAR/COUPLED),
# 充能-釋放**階段數** ncharge 隨檔位遞增(每階一段持續 hold + 遞增 release)。幅度 amplify 加不出第二階
# (階數=關鍵幀拓樸,gen 時決定),故對 charge 檔位變體以該檔位 ncharge **重生成**再套幅度增益(正交可疊)。
# **crux(與 combo count 的差異)**:兩者都是「N 個遞增 scale 峰」,但 combo 峰間是**短** dip(擊間微回 >0.97),
# charge 每階是**持續**低 hold(sustained run <0.97)—— 計數簽章須多驗「每階一段持續 hold」才與 combo 鑑別。
COUNT_AWARE_CATS = {"combo", "wobble", "squash", "twist", "charge"}

# candidate G-4'''' — 產出 `shear` 通道的節拍類別(shear-emitting)。原僅 wobble(純 shearX);
# squash 加入後(shear + 耦合非均勻 scale 的體積守恆擠壓)成為第二個 shear 產出者;
# (G-4'''''')twist 加入後(反相雙軸 shear,首度驅動 shearY)成為第三個 —— 亦合法帶 shear。
# 各 shear-isolation 閘(shear_gen W5b / wobble_tier T4)以此集合認定「合法 shear 產出者」,
# 集中一處便於後續再加(避免每加一個 shear 節拍就改多個閘的硬編碼 'wobble')。
# (G-4''''')squash **已併入** MAIN_SHOW_CATS(檔位差異化):其 scale 通道走**耦合 amplify**
# (COUPLED_SCALE_CATS)以保體積守恆;逐軸 `_amp_scale` 會破壞守恆(見下 `_amp_scale_coupled`)。
SHEAR_CATS = {"wobble", "squash", "twist"}

# candidate G-4''''' — 需**耦合 scale amplify** 的類別(shear + 體積守恆非均勻 scale)。
# 逐軸 `_amp_scale`(只放大 identity 上方 overshoot、樓地板不動)套在 squash 上會:scaleX>1 被脹、
# scaleY<1 被保留 → scaleX·scaleY≠1(破壞面積守恆)。故對這些類別改用 `_amp_scale_coupled`:
# 放大**拉長軸**的 overshoot、壓縮軸設其**倒數** → scaleX·scaleY≡1 在任一檔位保持、非均勻度隨 g 增大。
# `build_animations` 依 cat 路由是否用耦合(squash→耦合;其餘主秀→逐軸)。
COUPLED_SCALE_CATS = {"squash"}

# candidate G-4''''''-vol-tier — 需**依放大後 shear 重算等向補償 scale** 的類別(volume-conserving twist)。
# twist(vol_conserve)的補償 scale 是 shear 的**非線性**函數 `s = 1/√cos(shearX − shearY)`;
# tier 放大把 shear 同比拉大(shearX'=g·shearX、shearY'=g·shearY → 兩基底夾角偏離 Δ'=(shearX−shearY)·g),
# 於是 cos(Δ') 變小、真正的守恆補償變成 `s' = 1/√cos(g·Δ)` —— 對 g **非線性**。逐軸 `_amp_scale(s,g)`
# 只做**線性**內插 `1+g·(s−1)`,追不上這條非線性曲線 → 破壞 det≡1(見 `validate_twist_volume_tier.py` VTT3 負對照)。
# 也**不能**用 squash 的 `_amp_scale_coupled`(那是 `sy'=1/sx'` 的倒數耦合,對「等向且值來自 shear」的 twist
# 補償無意義)。故對這些類別改走 `_recompute_twist_scale_iso`:先放大 shear,再**依放大後的 shear 重算**每個
# scale 極值的等向 s → det≡1 **由建構(等向補償=cos 的反推)保證**在任一檔位保持,補償量隨檔位非線性遞增。
# 只有在 twist 掛了體積守恆 scale 通道(build_animations 的 twist_volume=True)時才路由到此;否則 twist 純 shear。
VOL_TWIST_CATS = {"twist"}

# 檔位 → 主秀幅度增益(**嚴格遞增**;base=Super=1.0 → 向後相容逐位元不變)。
# 增益上界經檢核:最大 role peak(特效 1.35 → q=0.35)在 Legend g=2.1 下 → 1.735(無翻面);
# combo settle 回彈 1.030 → Legend 1.063 < IMPACT_PROM(1.10)→ 不會被誤計為 impact 峰。
# (G-4'')wobble shearX 峰(特效 16°)在 Legend g=2.1 下 → 33.6°:仍是有限、合理的斜拉量
# (|shear|<90° 恆不奇異;真 Spine local det=cos(shear) 在 33.6° 為 0.83>0),阻尼比 r=0.5 逐幀
# 同比放大 → 符號序列與遞減比不變(結構簽章保形,見 amplify_bone_tl 對 shear 的處理)。
TIER_GAIN = {
    "slot_bigwin": {"Super": 1.0, "Mega": 1.35, "Omg": 1.70, "Legend": 2.10},
}


def gains_for(genre):
    """回傳該 genre 的 {tier: gain};無宣告 tier 的 genre 回 None(→ 不產檔位變體)。"""
    return TIER_GAIN.get(genre)


# candidate J-2 — 檔位 → combo 連擊數(**嚴格遞增**;base=Super=3 → 逐位元同 0g 手調三連擊)。
# 上界 6:combo T=0.9s 內容納 6 峰仍時間嚴格遞增且峰間不塌陷(見 _combo_env 週期檢核)。
TIER_COMBO_HITS = {
    "slot_bigwin": {"Super": 3, "Mega": 4, "Omg": 5, "Legend": 6},
}


def combo_hits_for(genre):
    """回傳該 genre 的 {tier: nhits};無宣告的 genre 回 None(→ combo 檔位變體不變連擊數)。"""
    return TIER_COMBO_HITS.get(genre)


# candidate G-4''' — 檔位 → wobble 振盪段數 nosc(**嚴格遞增**;base=Super=4 → 逐位元同 G-4' 手調 golden)。
# 上界 7:wobble T=0.8s 內容納 7 個阻尼極值於 [LEAD,TAIL] 仍時間嚴格遞增;r=0.5 阻尼下末極值
# (特效 16°·r⁶=0.25°)仍 finite 且與前極值(0.5°)於 4 位小數可辨(遞減簽章不塌陷,見 _wobble_env)。
# 與 combo 的段數階梯正交獨立(各類別自有段數,build_animations 依 cat 路由)。
TIER_WOBBLE_CYCLES = {
    "slot_bigwin": {"Super": 4, "Mega": 5, "Omg": 6, "Legend": 7},
}


def wobble_cycles_for(genre):
    """回傳該 genre 的 {tier: nosc};無宣告的 genre 回 None(→ wobble 檔位變體不變振盪段數)。"""
    return TIER_WOBBLE_CYCLES.get(genre)


# candidate G-4'''''-c — 檔位 → squash 擠壓段數 nosc(**嚴格遞增**;base=Super=4 → 逐位元同 G-4'''' base squash)。
# 上界 7:squash 與 wobble 共用 `_squash_env`/`_wobble_env` 的同一窗 [WOBBLE_LEAD,WOBBLE_TAIL] 與阻尼 r=0.5,
# 故 nosc≤7 的極值時間嚴格遞增、末極值 finite 且可辨(比照 TIER_WOBBLE_CYCLES 上界論證)。與 wobble 的段數
# 階梯**正交獨立**(各類別自有段數,build_animations 依 cat 路由)。**關鍵**:段數增多不破體積守恆 ——
# 每個新擠壓極值仍由 `_squash_env` 建構 (1+q_i, 1/(1+q_i)) → scaleX·scaleY≡1,再經耦合 amplify 仍守恆。
TIER_SQUASH_CYCLES = {
    "slot_bigwin": {"Super": 4, "Mega": 5, "Omg": 6, "Legend": 7},
}


def squash_cycles_for(genre):
    """回傳該 genre 的 {tier: nosc};無宣告的 genre 回 None(→ squash 檔位變體不變擠壓段數)。"""
    return TIER_SQUASH_CYCLES.get(genre)


# candidate G-4''''''-count — 檔位 → twist 扭轉段數 nosc(**嚴格遞增**;base=Super=4 → 逐位元同 G-4'''''' base twist)。
# 上界 7:twist 與 wobble/squash 共用 `_twist_env`/`_wobble_env` 的同一窗 [WOBBLE_LEAD,WOBBLE_TAIL] 與阻尼 r=0.5,
# 故 nosc≤7 的極值時間嚴格遞增、末極值 finite 且可辨(比照 TIER_WOBBLE_CYCLES/TIER_SQUASH_CYCLES 上界論證;
# head 最小軸 shearY 7°·r⁶≈0.109° 仍與前極值 0.219° 於 4 位小數可辨)。與 wobble/squash 的段數階梯**正交獨立**
# (各類別自有段數,build_animations 依 cat 路由)。**twist 獨有(crux)**:段數增多 → 兩軸各多長阻尼極值,每個新極值
# 仍由 `_twist_env` 建構 shearY=−TWIST_PHI·shearX → φ 比值由建構保證(與段數無關),再經單一-g 幅度增益仍同比 →
# 段數×幅度×φ 保形三效正交可疊。
TIER_TWIST_CYCLES = {
    "slot_bigwin": {"Super": 4, "Mega": 5, "Omg": 6, "Legend": 7},
}


def twist_cycles_for(genre):
    """回傳該 genre 的 {tier: nosc};無宣告的 genre 回 None(→ twist 檔位變體不變扭轉段數)。"""
    return TIER_TWIST_CYCLES.get(genre)


# candidate G-4'''''-charge — 檔位 → charge 蓄力充能**階段數** ncharge(**嚴格遞增**;base=Super=1 → 逐位元同手調單發)。
# 上界 4:charge T=0.8s,各階均分 CHARGE_FINALE(0.72)/ncharge,ncharge=4 → 每階寬 0.18,階內 dip/hold/release
# 時間嚴格遞增、各階 release τ 嚴格遞增(0.144/0.324/0.504/0.684<settle 0.82)、每階 hold(0.42w≈0.076τ≈18 樣本
# @N=240)仍遠長於 combo 短 dip(≈5–6 樣本)→ 計數鑑別不塌陷。與 combo/wobble/squash/twist 的段數階梯**正交獨立**
# (各類別自有段數,build_animations 依 cat 路由 _count_maps)。**crux**:幅度 amplify 加不出第二階(階數=gen 時
# 決定的關鍵幀拓樸)→ 以該檔位 ncharge **重生成**再套幅度增益 g(階數×幅度兩效正交可疊);與 combo 不同之處在
# 每階須保「持續 hold」(sustained run <0.97)—— 這是 charge count 簽章與 combo count 的鑑別子(見 validate_charge_count.py)。
TIER_CHARGE_CYCLES = {
    "slot_bigwin": {"Super": 1, "Mega": 2, "Omg": 3, "Legend": 4},
}


def charge_cycles_for(genre):
    """回傳該 genre 的 {tier: ncharge};無宣告的 genre 回 None(→ charge 檔位變體不變蓄力階段數)。"""
    return TIER_CHARGE_CYCLES.get(genre)


# candidate J-3 — 檔位 → cascade 跨件波**掃過整體的次數** nrip(**嚴格遞增**;base=Super=1 → 逐位元同基礎單 sweep cascade)。
# **與 combo/wobble/squash/twist 的段數本質不同**:那些是**單件內**極值數(同一件連幾下);cascade 的 nrip 是
# **跨件波掃幾道**(段數落在**跨件時序**通道,cascade∈_PHASE_AWARE)。上界 4:cascade T=1.2s 內均分 4 個 sweep 窗,
# 每窗寬 1/4、窗內包絡壓縮 1/4 → 窗間隙 0.75/4>0(時間嚴格遞增、互不重疊)、末窗峰時 (4−0.14)/4=0.965<1(首尾仍 identity);
# 每件 pop 4 次、各 pop 峰值同(=role peak≥1.18>IMPACT_PROM)→ impact 峰數==nrip 可辨。與單件段數階梯**正交獨立**
# (cascade 段數自成一路,build_animations 依 cat 路由 _count_maps)。**crux**:幅度 amplify 加不出第二道 sweep
# (拓樸=gen 時決定的關鍵幀窗),故對 cascade 檔位變體以該檔位 nrip **重生成**再套幅度增益 g(正交可疊)。
TIER_CASCADE_RIPPLES = {
    "slot_bigwin": {"Super": 1, "Mega": 2, "Omg": 3, "Legend": 4},
}


def cascade_ripples_for(genre):
    """回傳該 genre 的 {tier: nrip};無宣告的 genre 回 None(→ cascade 檔位變體不變波掃次數)。"""
    return TIER_CASCADE_RIPPLES.get(genre)


# candidate J-4 — 檔位 → cascade 跨件波**散佈幅度** span(一道 sweep 內各件峰時刻的散佈;**嚴格遞增**;
# base=Super=CASCADE_SPAN=0.54 → 逐位元同基礎)。**與 J-3 nrip 結構軸正交**:nrip=波掃**幾道**(拓樸,關鍵幀窗數);
# span=一道波內各件峰時刻**多開**(magnitude of cross-part staggering)。**crux(honest distinction)**:span 語意是
# 「幅度」(愈高檔位波掃愈開)但**不能用幅度機制**(post-hoc 值增益 g 的 `v'=g·v`)加大 —— 跨件散佈活在關鍵幀的
# **時間位置**(峰中心 c_k),不在**值**;g 只放大 pop 深度(scale 峰值),峰時刻不動 → 散佈不變。故 span 必須在
# gen 當下**重生成**(比照 count 軸的重生成機制),雖語意屬幅度(magnitude in the **time-position** domain)。
# 上界 <0.68:末件末幀 (LEAD+span+0.16)<1 → span<1−0.16−0.16=0.68(任一 nrip 首尾仍 identity)。
# Legend 0.66<0.68(餘裕 0.02);與 nrip 同時帶入 → nrip 道各以該檔位 span 散佈(兩軸皆重生成、可疊)。
TIER_CASCADE_SPAN = {
    "slot_bigwin": {"Super": 0.54, "Mega": 0.58, "Omg": 0.62, "Legend": 0.66},
}


def cascade_span_for(genre):
    """回傳該 genre 的 {tier: span};無宣告的 genre 回 None(→ cascade 檔位變體不變跨件散佈)。"""
    return TIER_CASCADE_SPAN.get(genre)


# candidate J-5 — genre → cascade 跨件波的**建議相位來源**(波方向)。與 nrip(J-3)/span(J-4)/深度(J)三軸**正交**:
# 方向只決定「哪件何時 pop」(相位來源:空間位置 vs 件序),不決定「幾道波/一道多開/多深」。
# "co"(中心外擴)最貼 slot 大獎的「從中心爆開」體感;**仍為 opt-in**——build_animations 預設 cascade_dir=None(件序,
# byte-identical),只有 build_spine --cascade-dir(或此表被顯式查用)才改相位來源,確保對既有 golden 零回歸。
TIER_CASCADE_DIR = {
    "slot_bigwin": "co",
}


def cascade_dir_for(genre):
    """回傳該 genre 的**建議** cascade 波方向字串("lr"/"rl"/"co"/"oc");無宣告的 genre 回 None(→ 件序,byte-identical)。"""
    return TIER_CASCADE_DIR.get(genre)


def _amp_scale(v, g):
    """scale 值幅度增益:僅放大 identity 上方 overshoot;下方(squash/collapse)樓地板不動。"""
    return 1.0 + g * (v - 1.0) if v >= 1.0 else v


def _amp_scale_coupled(sx, sy, g):
    """candidate G-4''''' — **體積守恆耦合** scale 增益(squash 專用)。

    放大**拉長軸**(值 ≥1 的一軸)的 overshoot(用 `_amp_scale`,與其餘主秀 scale 增益同語意),
    壓縮軸設為其**倒數** → scaleX·scaleY≡1(面積守恆)在任一檔位保持。回傳 (scaleX', scaleY')。

    - identity 幀:squash 首尾 sx==sy==1.0 → 走 sx≥sy 支 → `_amp_scale(1,g)=1` → (1,1)**介面契約保持**。
    - 非均勻度:|scaleX'−scaleY'| = |(1+g·q) − 1/(1+g·q)| 隨 g **單調增大**(擠壓愈強 → 檔位簽章)。
    - 與逐軸 `_amp_scale` 的差異(crux):後者對 sy<1 走樓地板(不動),只脹 sx → scaleX·scaleY≠1
      (破壞守恆);本函式由 sx' 反推 sy'=1/sx' → 守恆**由建構保證**(不論輸入 sy 的捨入誤差)。
    """
    if sx >= sy:                    # 拉長軸=scaleX(squash 恆 scaleX≥1≥scaleY)
        sx2 = _amp_scale(sx, g)
        return round(sx2, 4), round(1.0 / sx2, 4)
    sy2 = _amp_scale(sy, g)         # 對稱處理(拉長軸在 Y)以防未來別種耦合擠壓
    return round(1.0 / sy2, 4), round(sy2, 4)


def _recompute_twist_scale_iso(sh_frames, sc_frames):
    """candidate G-4''''''-vol-tier — 依**已放大**的反相雙軸 shear **重算**等向補償 scale,維持 det≡1。

    volume-conserving twist 的補償 `s = 1/√cos(shearX − shearY)` 對 shear **非線性**(cos);tier 放大把兩軸
    同比拉大(Δ'=(shearX−shearY)·g)後,真正的守恆補償是 `s' = 1/√cos(g·Δ)`,故不能沿用 base 的 s 做線性
    放大 —— 必須以**放大後**的 shear 重算。`sh_frames` 須已含 g 放大後的 shearX/shearY(呼叫端先跑 shear 迴圈);
    對每個 scale 幀,依**同 time** 的(已放大)shear 值算 s=1/√cos(shx−shy),等向寫回 (s,s)。
    - shear=0 的首尾幀 → cos(0)=1 → s=1 → **identity 介面自動保持**(可插 Loop 間,任一檔位)。
    - 捨入比照 `_twist_scale_env`/`gen_twist`(先 round(s,6) 再 round(,4))→ g=1.0 逐位元同 base twist(vol)。
    - 無對應 shear 的 scale 幀(理論上不會:twist vol 的 scale/shear 同 τ 共生)→ 保守取 s=1(identity)。"""
    sh_by_t = {round(f["time"], 4): (f["x"], f["y"]) for f in sh_frames}
    for f in sc_frames:
        shx, shy = sh_by_t.get(round(f["time"], 4), (0.0, 0.0))
        det_shear = math.cos(math.radians(shx - shy))     # 反相雙軸 shear 放大後的面積縮放(≤1)
        s = round(1.0 / math.sqrt(det_shear), 6) if det_shear > 0 else 1.0
        f["x"] = round(s, 4)
        f["y"] = round(s, 4)                              # 等向:twist 各向異性全由 shear 提供


def amplify_bone_tl(b, g, coupled=False, twist_vol=False):
    """對單一 bone timeline 套幅度增益 g(deepcopy,保留曲線鍵)。g=1.0 → identity 變換。

    scale 通道的三種放大路由(互斥):
      - `twist_vol=True`(VOL_TWIST_CATS,volume-conserving twist):**先放大 shear**,再依放大後 shear
        **重算**等向補償 scale(`_recompute_twist_scale_iso` → det≡1;s 對 g 非線性,見該函式)。
      - `coupled=True`(squash 等 COUPLED_SCALE_CATS):scale 走**體積守恆耦合**放大
        (`_amp_scale_coupled` → scaleX·scaleY≡1,壓縮軸=拉長軸倒數)。
      - 否則(其餘主秀):scale 逐軸放大 identity 上方 overshoot。
    rotate/translate/shear 皆對 0 對稱 → v'=g*v(每幀同比 → 首尾 0 仍 0、阻尼/反相簽章保形;g=1 空轉零回歸)。
    """
    b = copy.deepcopy(b)
    for f in b.get("rotate", []):
        f["angle"] = round(g * f["angle"], 3)
    for f in b.get("translate", []):
        f["x"] = round(g * f["x"], 3)
        f["y"] = round(g * f["y"], 3)
    # (G-4'')shear 通道(斜拉 wobble / squash / twist):v'=g*v。**須在 scale 之前**——
    # twist_vol 的補償 scale 要讀「放大後」的 shear 重算(見下 _recompute_twist_scale_iso)。
    for f in b.get("shear", []):
        f["x"] = round(g * f["x"], 4)
        f["y"] = round(g * f["y"], 4)
    if twist_vol:
        # (G-4''''''-vol-tier)twist 體積守恆:補償 scale 依**已放大** shear 非線性重算 → det≡1。
        _recompute_twist_scale_iso(b.get("shear", []), b.get("scale", []))
    elif coupled:
        # (G-4''''')耦合 scale:scaleX/scaleY 一起以面積守恆放大(拉長軸脹、壓縮軸為其倒數)。
        for f in b.get("scale", []):
            f["x"], f["y"] = _amp_scale_coupled(f["x"], f["y"], g)
    else:
        for f in b.get("scale", []):
            f["x"] = round(_amp_scale(f["x"], g), 4)
            f["y"] = round(_amp_scale(f["y"], g), 4)
    return b


def amplify_anim(anim, g, coupled=False, twist_vol=False):
    """對整支 beat animation 套幅度增益 g:bones 幅度放大、slots(color/alpha)原樣保留。
    `coupled`(squash → 體積守恆耦合 scale)/`twist_vol`(volume-conserving twist → 依放大後 shear 重算
    等向補償 scale)透傳給 `amplify_bone_tl`。二者互斥。"""
    out = {}
    if "bones" in anim:
        out["bones"] = {bn: amplify_bone_tl(b, g, coupled=coupled, twist_vol=twist_vol)
                        for bn, b in anim["bones"].items()}
    if "slots" in anim:
        out["slots"] = copy.deepcopy(anim["slots"])
    return out
