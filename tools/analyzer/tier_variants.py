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

# 主秀類別(與 beat_templates 的節拍對應;In/Loop/Out 不在此 → 檔位無關)。
# candidate (G-4'') — 加入 `wobble`(斜拉 jelly wobble,G-4' 的 shear 通道節拍):
# 它是主秀節拍,強度理應隨檔位遞增,但幅度軸在 **shear** 而非 scale/rotate,
# 故 `amplify_bone_tl` 需一併放大 shear 通道(對 0 對稱 → v'=g*v,同 rotate/translate)。
# candidate (G-4''''') — 加入 `squash`(斜拉果凍擠壓,G-4'''' 的 shear + 體積守恆非均勻 scale 節拍):
# 它同為主秀節拍(強度理應隨檔位遞增),但 scale 軸是**耦合體積守恆**(scaleX·scaleY≡1),
# 逐軸 `_amp_scale`(只放大 identity 上方)會保留 scaleY<1 樓地板而只脹 scaleX → 破壞守恆
# (這正是 G-4'''' 當時把 squash 排除在外的 honest boundary);故用**耦合 amplify**(見 COUPLED_SCALE_CATS)。
MAIN_SHOW_CATS = {"hit", "reveal", "burst", "combo", "charge", "cascade", "wobble", "squash"}

# candidate J-2 / G-4''' / G-4'''''-c — 依檔位可變「段數」的類別(結構性差異化,非只幅度)。
# combo 的 impact 峰**數**、wobble 的振盪**段數**、squash 的擠壓**段數**隨檔位遞增;需在 gen 時把段數
# 帶進生成器(結構=拓樸,事後 amplify 只能放大既有極值、加不出一段)。各類別的段數階梯彼此獨立
# (combo → TIER_COMBO_HITS,wobble → TIER_WOBBLE_CYCLES,squash → TIER_SQUASH_CYCLES);
# build_animations 依類別路由。(G-4'''''-c)squash **同時** ∈ COUNT_AWARE_CATS 與 COUPLED_SCALE_CATS:
# 先以該檔位 nosc **重生成**(段數↑),再走**耦合** amplify(幅度↑且體積守恆)—— 段數×幅度×守恆三效正交。
COUNT_AWARE_CATS = {"combo", "wobble", "squash"}

# candidate G-4'''' — 產出 `shear` 通道的節拍類別(shear-emitting)。原僅 wobble(純 shearX);
# squash 加入後(shear + 耦合非均勻 scale 的體積守恆擠壓)成為第二個 shear 產出者。
# 各 shear-isolation 閘(shear_gen W5b / wobble_tier T4)以此集合認定「合法 shear 產出者」,
# 集中一處便於後續再加(避免每加一個 shear 節拍就改多個閘的硬編碼 'wobble')。
# (G-4''''')squash **已併入** MAIN_SHOW_CATS(檔位差異化):其 scale 通道走**耦合 amplify**
# (COUPLED_SCALE_CATS)以保體積守恆;逐軸 `_amp_scale` 會破壞守恆(見下 `_amp_scale_coupled`)。
SHEAR_CATS = {"wobble", "squash"}

# candidate G-4''''' — 需**耦合 scale amplify** 的類別(shear + 體積守恆非均勻 scale)。
# 逐軸 `_amp_scale`(只放大 identity 上方 overshoot、樓地板不動)套在 squash 上會:scaleX>1 被脹、
# scaleY<1 被保留 → scaleX·scaleY≠1(破壞面積守恆)。故對這些類別改用 `_amp_scale_coupled`:
# 放大**拉長軸**的 overshoot、壓縮軸設其**倒數** → scaleX·scaleY≡1 在任一檔位保持、非均勻度隨 g 增大。
# `build_animations` 依 cat 路由是否用耦合(squash→耦合;其餘主秀→逐軸)。
COUPLED_SCALE_CATS = {"squash"}

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


# candidate G-4'''''-c — 檔位 → squash 擠壓段數 nosc(**嚴格遞增**;base=Super=4 → 逐位元同 G-4'''' golden)。
# squash 的每個 shearX 阻尼極值處施一次體積守恆擠壓(scaleX=1+q_i,scaleY=1/(1+q_i),q_i=Q·rⁱ);
# 段數 nosc 決定「擠幾下」(shear 振盪段數 == scale 內部極值數,兩者由 `_squash_env` 同點耦合)。
# 與 wobble 共用同窗(DUR=0.8、WOBBLE_LEAD/TAIL、r=0.5)→ 上界 7 同樣安全(末極值 q=Q·r⁶ 於 6 位小數
# 仍與前一極值可辨,體積守恆 (1+q)(1/(1+q))≡1 對任意 nosc 由建構保證)。與 combo/wobble 的段數階梯
# **正交獨立**(各類別自有段數,build_animations 依 cat 路由)。crux:段數↑ 與耦合幅度增益 g↑ **正交** ——
# 重生成把極值數變多、耦合 amplify 把每個極值放大,兩者疊加後每個極值仍 scaleX·scaleY≡1(三效正交)。
TIER_SQUASH_CYCLES = {
    "slot_bigwin": {"Super": 4, "Mega": 5, "Omg": 6, "Legend": 7},
}


def squash_cycles_for(genre):
    """回傳該 genre 的 {tier: nosc};無宣告的 genre 回 None(→ squash 檔位變體不變擠壓段數)。"""
    return TIER_SQUASH_CYCLES.get(genre)


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


def amplify_bone_tl(b, g, coupled=False):
    """對單一 bone timeline 套幅度增益 g(deepcopy,保留曲線鍵)。g=1.0 → identity 變換。

    `coupled=True`(squash 等 COUPLED_SCALE_CATS):scale 走**體積守恆耦合**放大
    (`_amp_scale_coupled` → scaleX·scaleY≡1 保持);否則(其餘主秀)scale 逐軸放大 overshoot。
    """
    b = copy.deepcopy(b)
    if coupled:
        # (G-4''''')耦合 scale:scaleX/scaleY 一起以面積守恆放大(拉長軸脹、壓縮軸為其倒數)。
        for f in b.get("scale", []):
            f["x"], f["y"] = _amp_scale_coupled(f["x"], f["y"], g)
    else:
        for f in b.get("scale", []):
            f["x"] = round(_amp_scale(f["x"], g), 4)
            f["y"] = round(_amp_scale(f["y"], g), 4)
    for f in b.get("rotate", []):
        f["angle"] = round(g * f["angle"], 3)
    for f in b.get("translate", []):
        f["x"] = round(g * f["x"], 3)
        f["y"] = round(g * f["y"], 3)
    # (G-4'')shear 通道(斜拉 wobble / squash):對 0 對稱 → v'=g*v(同 rotate/translate)。
    # 每幀同比放大 → 首尾 0 仍 0(介面契約保持)、符號序列與相繼極值遞減比不變
    # (阻尼振盪簽章保形);g=1.0 → identity 變換(無 shear 的 beat 此迴圈空轉,零回歸)。
    for f in b.get("shear", []):
        f["x"] = round(g * f["x"], 4)
        f["y"] = round(g * f["y"], 4)
    return b


def amplify_anim(anim, g, coupled=False):
    """對整支 beat animation 套幅度增益 g:bones 幅度放大、slots(color/alpha)原樣保留。
    `coupled` 透傳給 `amplify_bone_tl`(squash → 體積守恆耦合 scale 放大)。"""
    out = {}
    if "bones" in anim:
        out["bones"] = {bn: amplify_bone_tl(b, g, coupled=coupled) for bn, b in anim["bones"].items()}
    if "slots" in anim:
        out["slots"] = copy.deepcopy(anim["slots"])
    return out
