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
# candidate (G-4''''') — 加入 `squash`(斜拉果凍擠壓,shear + 耦合非均勻 scale 的體積守恆節拍):
# 亦主秀節拍,強度應隨檔位遞增。但其幅度軸同時在 **shear**(可直接 v'=g*v)與 **體積守恆 scale pair**
# —— 後者不能逐軸放大(拉長軸 scaleX>1 會被放大、壓扁軸 scaleY<1 被 `_amp_scale` 保留 → 破壞
# scaleX·scaleY==1),必須**耦合 amplify**(見 COUPLED_SCALE_CATS / `_amp_scale_pair`)。
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
# (G-4''''')squash 已接檔位幅度差異化(在 MAIN_SHOW_CATS)且以耦合 amplify(COUPLED_SCALE_CATS)
# 放大擠壓量而不破壞 scaleX·scaleY==1;shear 通道則同 wobble 走 v'=g*v。
SHEAR_CATS = {"wobble", "squash"}

# candidate G-4''''' — scale 通道需**耦合 amplify** 的節拍類別(體積守恆 squash pair)。
# 一般 scale 節拍(hit/combo/charge…)逐軸 `_amp_scale`(只放大 identity 上方 overshoot);
# 但 squash 的 scale 是 (scaleX=1+q, scaleY=1/(1+q)) 的**體積守恆 pair**,逐軸放大會破壞守恆
# (拉長軸放大、壓扁軸樓地板不動 → 積≠1)。故這些類別的 scale 走 `_amp_scale_pair`:放大擠壓量 q
# 於拉長軸(1+g·q,與 `_amp_scale` 對 overshoot 同式),另一軸取倒數還原守恆(1/(1+g·q))。
# shear 通道仍走 v'=g*v(與 wobble 同)—— squash 兩通道同檔位增益 g 一起放大(耦合擠壓 + 斜拉)。
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


def _amp_scale(v, g):
    """scale 值幅度增益:僅放大 identity 上方 overshoot;下方(squash/collapse)樓地板不動。"""
    return 1.0 + g * (v - 1.0) if v >= 1.0 else v


def _amp_scale_pair(scx, scy, g):
    """candidate G-4''''' — **耦合** scale 幅度增益:放大體積守恆 squash pair 的擠壓量,
    而**不破壞** scaleX·scaleY==1。

    squash 的每個極值幀 = (scaleX=1+q, scaleY=1/(1+q)),q=拉長量、體積守恆(積≡1)、非均勻。
    擠壓量 q 取**拉長軸**(值較大者)之 (v−1),放大成 g·q → 拉長軸 = 1+g·q(與 `_amp_scale` 對
    overshoot 完全同式),另一軸取倒數還原守恆 = 1/(1+g·q)。⇒
      ① identity(1,1)→ 不變(g 無關,首尾介面契約對所有檔位保形);
      ② scaleX·scaleY≡1 逐檔位保持(耦合 → 體積守恆簽章不被檔位放大破壞,這是 crux);
      ③ 擠壓幅度(aniso / |scaleX−1|)隨 g 單調變大(檔位簽章);
      ④ 各極值 q_i=Q·rⁱ → 放大後 g·q_i 仍嚴格遞減(阻尼簽章保形,共同正因子 g)。
    純均勻 scale(scx==scy,含 identity)→ 退回逐軸 `_amp_scale`(非 squash pair,不強加耦合)。
    數值一律 round 到 4 位(對齊 `gen_squash`/`_amp_scale` 的 scale 精度 → g=1.0 時逐位元 == base;
    4 位下 |scaleX·scaleY−1| ≲ 1e-4,遠在體積守恆容差 TOL_VOL=0.02 內)。"""
    if abs(scx - scy) < 1e-9:            # 均勻(含 identity):非 squash pair,逐軸處理
        return round(_amp_scale(scx, g), 4), round(_amp_scale(scy, g), 4)
    if scx >= scy:                        # x 為拉長軸
        nx = 1.0 + g * (scx - 1.0)
        return round(nx, 4), round(1.0 / nx, 4)
    ny = 1.0 + g * (scy - 1.0)            # y 為拉長軸
    return round(1.0 / ny, 4), round(ny, 4)


def amplify_bone_tl(b, g, coupled_scale=False):
    """對單一 bone timeline 套幅度增益 g(deepcopy,保留曲線鍵)。g=1.0 → identity 變換。

    `coupled_scale`(G-4''''')=True 時,scale 幀以 `_amp_scale_pair` **耦合**放大(體積守恆 squash pair,
    見 COUPLED_SCALE_CATS);預設 False → 逐軸 `_amp_scale`(一般主秀節拍的 overshoot 樓地板規則)。"""
    b = copy.deepcopy(b)
    if coupled_scale:
        for f in b.get("scale", []):
            f["x"], f["y"] = _amp_scale_pair(f["x"], f["y"], g)
    else:
        for f in b.get("scale", []):
            f["x"] = round(_amp_scale(f["x"], g), 4)
            f["y"] = round(_amp_scale(f["y"], g), 4)
    for f in b.get("rotate", []):
        f["angle"] = round(g * f["angle"], 3)
    for f in b.get("translate", []):
        f["x"] = round(g * f["x"], 3)
        f["y"] = round(g * f["y"], 3)
    # (G-4'')shear 通道(斜拉 wobble):對 0 對稱 → v'=g*v(同 rotate/translate)。
    # 每幀同比放大 → 首尾 0 仍 0(介面契約保持)、符號序列與相繼極值遞減比不變
    # (阻尼振盪簽章保形);g=1.0 → identity 變換(無 shear 的 beat 此迴圈空轉,零回歸)。
    for f in b.get("shear", []):
        f["x"] = round(g * f["x"], 4)
        f["y"] = round(g * f["y"], 4)
    return b


def amplify_anim(anim, g, coupled_scale=False):
    """對整支 beat animation 套幅度增益 g:bones 幅度放大、slots(color/alpha)原樣保留。
    `coupled_scale`(G-4''''')轉傳給 `amplify_bone_tl`(squash 等體積守恆 pair 用耦合放大)。"""
    out = {}
    if "bones" in anim:
        out["bones"] = {bn: amplify_bone_tl(b, g, coupled_scale) for bn, b in anim["bones"].items()}
    if "slots" in anim:
        out["slots"] = copy.deepcopy(anim["slots"])
    return out
