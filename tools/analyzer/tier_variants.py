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
# candidate (G-4''''') — 加入 `squash`(斜拉果凍擠壓,G-4'''' 的 shear + 耦合非均勻 scale 節拍):
# 它同樣是主秀節拍,但 scale 軸是**體積守恆**(scaleX·scaleY≡1),用一般 `_amp_scale`(只放大 identity
# 上方)會單邊放大 scaleX、保留 scaleY 樓地板 → **破壞守恆**。故 squash 走**耦合 amplify**
# (`_amp_scale_coupled`:放大擠壓幅度 q 並重生 scaleY=1/(1+g·q),守恆嚴格保持),見 VOLUME_CONSERVING_CATS。
MAIN_SHOW_CATS = {"hit", "reveal", "burst", "combo", "charge", "cascade", "wobble", "squash"}

# candidate J-2 / G-4''' — 依檔位可變「段數」的類別(結構性差異化,非只幅度)。
# combo 的 impact 峰**數**、wobble 的振盪**段數**隨檔位遞增;需在 gen 時把段數帶進生成器
# (結構=拓樸,事後 amplify 只能放大既有極值、加不出一段)。各類別的段數階梯彼此獨立
# (combo → TIER_COMBO_HITS,wobble → TIER_WOBBLE_CYCLES);build_animations 依類別路由。
COUNT_AWARE_CATS = {"combo", "wobble"}

# candidate G-4'''' — 產出 `shear` 通道的節拍類別(shear-emitting)。原僅 wobble(純 shearX);
# squash 加入後(shear + 耦合非均勻 scale 的體積守恆擠壓)成為第二個 shear 產出者。
# 各 shear-isolation 閘(shear_gen W5b / wobble_tier T4)以此集合認定「合法 shear 產出者」,
# 集中一處便於後續再加(避免每加一個 shear 節拍就改多個閘的硬編碼 'wobble')。
SHEAR_CATS = {"wobble", "squash"}

# candidate (G-4''''') — scale 通道為**體積守恆**(scaleX·scaleY≡1)的節拍類別。
# 這類別的檔位幅度放大**不能**用一般 `_amp_scale`(只放大 identity 上方 → 單邊放大 scaleX、保留
# scaleY 壓扁樓地板 → 破壞守恆);必須用 `_amp_scale_coupled`:放大擠壓幅度 q=scaleX−1 為 g·q、
# 再重生 scaleY=1/(1+g·q),使放大後仍 scaleX·scaleY≡1(且 scaleX≠scaleY 非均勻)。
# `build_animations` 依此集合決定對該 beat 的 amplify 是否走 coupled 路徑(shear 通道照 v'=g*v 放大,
# 與 squash 幅度同 g → 兩通道放大後仍同源耦合)。目前僅 squash;後續其他體積守恆節拍加此即可。
VOLUME_CONSERVING_CATS = {"squash"}

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


def _amp_scale(v, g):
    """scale 值幅度增益:僅放大 identity 上方 overshoot;下方(squash/collapse)樓地板不動。"""
    return 1.0 + g * (v - 1.0) if v >= 1.0 else v


# candidate (G-4''''') — 體積守恆偵測容差:squash 的 scaleX·scaleY 經 4 位小數 round 後略偏 1
# (如 1.16·0.8621=1.00004);此容差內視為體積守恆幀。非均勻門檻分離「壓擠幀」與「identity/等比幀」。
_VOL_TOL = 0.02      # |scaleX·scaleY − 1| 判為體積守恆的上限
_UNIFORM_EPS = 1e-6  # |scaleX − scaleY| ≤ 此值視為等比(identity/pulse),不走耦合


def _amp_scale_coupled(sx, sy, g):
    """體積守恆 scale 幀的**耦合** amplify → (scaleX', scaleY')。

    對「體積守恆(scaleX·scaleY≈1)且非均勻(scaleX≠scaleY)」的擠壓幀:放大擠壓幅度
    q=scaleX−1 為 g·q,重生 scaleY=1/(1+g·q) → 放大後**仍嚴格** scaleX'·scaleY'≡1(體積守恆保持)
    且 scaleX'≠scaleY'(非均勻保持)。g=1.0 → (round(sx,4), round(1/sx,4)) == 原幀(byte-identical)。
    等比/identity 幀(scaleX==scaleY,含首尾 (1,1))**不擠壓** → 退回逐分量 `_amp_scale`
    (identity 恆保 identity、上方等比 overshoot 照放大)。非守恆非均勻幀(理論上 squash 不產)亦安全退回。"""
    if abs(sx - sy) > _UNIFORM_EPS and abs(sx * sy - 1.0) <= _VOL_TOL:
        qx = 1.0 + g * (sx - 1.0)
        return round(qx, 4), round(1.0 / qx, 4)
    return round(_amp_scale(sx, g), 4), round(_amp_scale(sy, g), 4)


def amplify_bone_tl(b, g, coupled=False):
    """對單一 bone timeline 套幅度增益 g(deepcopy,保留曲線鍵)。g=1.0 → identity 變換。

    `coupled`(G-4''''')=True 時 scale 走**體積守恆耦合** amplify(squash 等 VOLUME_CONSERVING_CATS):
    擠壓幀放大 q 並重生 scaleY 保持 scaleX·scaleY≡1;identity/等比幀退回一般 `_amp_scale`。
    coupled=False(預設)→ 逐分量 `_amp_scale`(向後相容,scale/pulse 節拍不變)。
    shear 通道無論 coupled 與否皆 v'=g*v → 與 scale 同 g 放大 → squash 兩通道放大後仍同源耦合。"""
    b = copy.deepcopy(b)
    for f in b.get("scale", []):
        if coupled:
            f["x"], f["y"] = _amp_scale_coupled(f["x"], f["y"], g)
        else:
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

    `coupled`(G-4''''')轉傳給 `amplify_bone_tl`,對體積守恆節拍(squash)的 scale 走耦合 amplify。"""
    out = {}
    if "bones" in anim:
        out["bones"] = {bn: amplify_bone_tl(b, g, coupled=coupled) for bn, b in anim["bones"].items()}
    if "slots" in anim:
        out["slots"] = copy.deepcopy(anim["slots"])
    return out
