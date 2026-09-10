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
MAIN_SHOW_CATS = {"hit", "reveal", "burst", "combo", "charge", "cascade", "wobble"}

# candidate J-2 — 依檔位可變「連擊數」的類別(結構性差異化,非只幅度)。
# combo 的 impact 峰**數**隨檔位遞增;需在 gen 時把 nhits 帶進 gen_combo(不能事後 amplify)。
COUNT_AWARE_CATS = {"combo"}

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


def _amp_scale(v, g):
    """scale 值幅度增益:僅放大 identity 上方 overshoot;下方(squash/collapse)樓地板不動。"""
    return 1.0 + g * (v - 1.0) if v >= 1.0 else v


def amplify_bone_tl(b, g):
    """對單一 bone timeline 套幅度增益 g(deepcopy,保留曲線鍵)。g=1.0 → identity 變換。"""
    b = copy.deepcopy(b)
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


def amplify_anim(anim, g):
    """對整支 beat animation 套幅度增益 g:bones 幅度放大、slots(color/alpha)原樣保留。"""
    out = {}
    if "bones" in anim:
        out["bones"] = {bn: amplify_bone_tl(b, g) for bn, b in anim["bones"].items()}
    if "slots" in anim:
        out["slots"] = copy.deepcopy(anim["slots"])
    return out
