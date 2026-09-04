#!/usr/bin/env python3
"""candidate 0f — big-win「主秀 beat」keyframe 模板(純 CPU,確定性)。

補上 candidate 0d(`gen_animations.py`)缺的**主秀節拍**:0d 的 `gen_pulse` 只是
identity→peak→identity 的**對稱三角脈衝**,缺兩個經典動畫原理:
  1. **Anticipation(預備)** —— 出手前先反向蓄力(squash 下蹲 / 反向甩)。
  2. **Settle / follow-through(收尾回彈)** —— 命中後**越過 identity 再阻尼回擺**,而非直線回。

本模組提供兩個主秀模板(role-aware),皆為 setup identity/collapse 介面 → 可與
In/Loop/Out 無縫串接;其**結構簽章**(反向預備 + 阻尼回擺)可被 `validate_beat_templates.py`
量化,並與「天真對稱脈衝」在負對照中明確分離(評估器可信度)。

  - `gen_hit`   : Anticipation → Impact → Settle。**首尾皆 identity**(可插在 Loop 循環間當重音)。
  - `gen_reveal`: Collapsed → 蓄勢 hold → Burst overshoot → Settle。**首 collapsed(scale~0/alpha 0)、尾 identity**
                  (大獎「現身」;之後可接 Loop)。

單位同 Spine runtime(見 `spine_anim.py`):rotate=角度增量(度)、scale=乘在 setup(=1)的倍率、
translate=相對 setup local 位移(px)、color=8-hex RGBA(alpha=末兩碼)。所有內插為 linear:
關鍵幀值本身即編碼阻尼回擺,sampler 線性穿越 identity → 結構簽章對取樣穩健、負對照乾淨。
"""
import math

# 由 gen_animations 借用基元(時長表、格式化器);本模組再擴充 DUR。
from gen_animations import DUR as _BASE_DUR, _rot, _xy, _color

# 主秀 beat 時長(秒)。加進共享 DUR,讓 spine_anim.duration/validate 一致。
DUR = dict(_BASE_DUR)
DUR.setdefault("hit", 0.5)
DUR.setdefault("reveal", 0.7)

# role → impact 峰值倍率(scale overshoot)。特效/身體給大、末梢/頭給中。
_PEAK = {"body": 1.28, "特效": 1.35, "head": 1.18, "limb": 1.18}


def _scale_frames(T, taus_vals):
    """[(τ∈[0,1], scale_mult)] → Spine scale timeline(x==y 等比)。"""
    return [{"time": round(tau * T, 4), "x": round(v, 4), "y": round(v, 4)} for (tau, v) in taus_vals]


def gen_hit(role, side_sign=1.0, radial=(0.0, 0.0)):
    """Anticipation → Impact → Settle。首尾 identity。回傳 (bone_timelines, slot_timelines)。

    scale 包絡(τ):1.0 →(蓄力)0.93 →(命中)peak →(回彈下衝)0.965 →(回彈上衝)1.015 → 0.995 → 1.0。
    (scale-1) 依序 0,−,+,−,+,−,0 → 反向預備 + 阻尼回擺,與對稱脈衝(僅單 + 峰)結構相異。"""
    T = DUR["hit"]
    peak = _PEAK.get(role, 1.18)
    b, s = {}, {}
    env = [(0.00, 1.000), (0.14, 0.930), (0.32, peak),
           (0.52, 0.965), (0.72, 1.015), (0.88, 0.995), (1.00, 1.000)]
    b["scale"] = _scale_frames(T, env)

    if role == "limb":
        # 末梢 whip:反向蓄力 → 甩出 → 阻尼回擺(首尾 0)
        b["rotate"] = _rot([(0.00 * T, 0.0), (0.14 * T, -side_sign * 6.0),
                            (0.32 * T, side_sign * 18.0), (0.55 * T, -side_sign * 5.0),
                            (0.78 * T, side_sign * 2.0), (1.00 * T, 0.0)])
    elif role == "head":
        # 點頭衝擊:先微抬(預備)再下砸再回彈
        b["rotate"] = _rot([(0.00 * T, 0.0), (0.14 * T, 3.0), (0.32 * T, -10.0),
                            (0.55 * T, 4.0), (0.78 * T, -1.5), (1.00 * T, 0.0)])
    elif role == "特效":
        # 亮度閃:先暗(蓄)再亮再阻尼;加旋轉甩(反向預備)
        s["color"] = _color([(0.00 * T, 1.0), (0.14 * T, 0.72), (0.32 * T, 1.0),
                             (0.55 * T, 0.85), (0.78 * T, 0.97), (1.00 * T, 1.0)])
        b["rotate"] = _rot([(0.00 * T, 0.0), (0.14 * T, -8.0), (0.32 * T, 12.0),
                            (0.60 * T, -4.0), (1.00 * T, 0.0)])
    return b, s


def gen_reveal(role, side_sign=1.0, radial=(0.0, 0.0)):
    """Collapsed → 蓄勢 hold → Burst overshoot → Settle。首 collapsed、尾 identity。

    scale:0.02(藏)→ 0.02(hold 蓄勢)→ peak(炸開越過 1)→ 0.95(下衝)→ 1.02(上衝)→ 1.0。
    alpha:0(藏)→ 0(hold)→ 1(burst)→ 1(保持)。首尾介面:start collapsed / end identity。"""
    T = DUR["reveal"]
    peak = _PEAK.get(role, 1.18)
    b, s = {}, {}
    env = [(0.00, 0.020), (0.20, 0.020), (0.45, peak),
           (0.65, 0.950), (0.82, 1.020), (1.00, 1.000)]
    b["scale"] = _scale_frames(T, env)
    # alpha:蓄勢期全透明,burst 起點(τ0.30)開始亮,τ0.45 全亮後保持
    s["color"] = _color([(0.00 * T, 0.0), (0.20 * T, 0.0), (0.30 * T, 0.2),
                         (0.45 * T, 1.0), (1.00 * T, 1.0)])
    if role == "limb":
        # 甩開:藏(內收)→ 爆出旋轉 → 阻尼回正
        b["rotate"] = _rot([(0.00 * T, side_sign * 25.0), (0.20 * T, side_sign * 25.0),
                            (0.45 * T, -side_sign * 8.0), (0.70 * T, side_sign * 3.0),
                            (1.00 * T, 0.0)])
    elif role == "特效":
        b["rotate"] = _rot([(0.00 * T, -30.0), (0.20 * T, -30.0), (0.45 * T, 10.0),
                            (0.75 * T, -4.0), (1.00 * T, 0.0)])
    return b, s


# candidate 0g — 擴充主秀節拍庫:multi-hit combo(連擊)+ anticipate-hold(蓄力充能)。
# 兩者仍是 setup identity 介面(首尾 identity → 可插 Loop 間),各有**可量化且互不相同**的結構
# 簽章,與單發 hit / 對稱脈衝在負對照乾淨分離:
#   - combo         : **多個遞增 impact 峰**(≥3 個 ≥1.10 的局部極大,且嚴格遞增)—— 單發 hit 只有 1 峰。
#   - anticipate_hold: **延長蓄力 hold**(峰前有一段持續低於 setup 的長充能區,佔比 ≥0.35)—— hit 蓄力僅短暫 dip。
# 兩者都仍保有 0f 的 anticipation(峰前 <1)+ settle(阻尼回擺,(scale-1) 變號 ≥3)通用簽章。

DUR.setdefault("combo", 0.9)
DUR.setdefault("anticipate_hold", 0.8)

# 主秀 impact 峰門檻(區隔「真 impact」與 settle 回彈/loop 微呼吸)。loop 最大 ~1.03、hit settle ~1.015。
IMPACT_PROM = 1.10


def gen_combo(role, side_sign=1.0, radial=(0.0, 0.0)):
    """Multi-hit combo(連擊):三段**遞增** impact,各含蓄力 dip + 部分回擺,尾段阻尼回穩。首尾 identity。

    scale 峰嚴格遞增 p1<p2<p3(=role peak);峰間回落 <1(下一擊的蓄力)→ 簽章 = 遞增 impact 峰數 ≥3
    (單發 hit 僅 1 峰 → 負對照分離)。仍具通用 anticipation(峰前 <1)+ settle(尾段回擺變號 ≥3)。"""
    T = DUR["combo"]
    peak = _PEAK.get(role, 1.18)
    q = peak - 1.0
    # 遞增三峰;p1 夾 ≥1.10 確保計入 impact(role peak 最小 1.18 → q=0.18 → p1=1.108)。
    p1 = max(1.10, 1.0 + 0.60 * q)
    p2 = 1.0 + 0.80 * q
    p3 = peak
    b, s = {}, {}
    env = [(0.00, 1.000),
           (0.05, 0.950), (0.13, p1), (0.20, 0.980),   # hit 1
           (0.26, 0.940), (0.35, p2), (0.43, 0.970),   # hit 2(蓄力更深)
           (0.50, 0.920), (0.62, p3),                  # hit 3 finale(蓄力最深、峰最大)
           (0.74, 0.955), (0.85, 1.030), (0.93, 0.995), (1.00, 1.000)]  # 阻尼回擺(<IMPACT_PROM)
    b["scale"] = _scale_frames(T, env)

    if role == "limb":
        # 三連甩,末梢反向蓄力 → 甩出,幅度隨連擊遞增;首尾 0
        b["rotate"] = _rot([(0.00 * T, 0.0), (0.13 * T, side_sign * 8.0), (0.20 * T, 0.0),
                            (0.35 * T, side_sign * 12.0), (0.43 * T, 0.0),
                            (0.62 * T, side_sign * 18.0), (0.74 * T, -side_sign * 5.0),
                            (1.00 * T, 0.0)])
    elif role == "head":
        b["rotate"] = _rot([(0.00 * T, 0.0), (0.13 * T, -6.0), (0.20 * T, 0.0),
                            (0.35 * T, -9.0), (0.43 * T, 0.0), (0.62 * T, -13.0),
                            (0.74 * T, 4.0), (1.00 * T, 0.0)])
    elif role == "特效":
        # 每擊亮度閃(蓄暗→亮),遞增;首尾回 1
        s["color"] = _color([(0.00 * T, 1.0), (0.05 * T, 0.80), (0.13 * T, 1.0),
                             (0.26 * T, 0.78), (0.35 * T, 1.0), (0.50 * T, 0.72),
                             (0.62 * T, 1.0), (1.00 * T, 1.0)])
        b["rotate"] = _rot([(0.00 * T, 0.0), (0.13 * T, side_sign * 8.0),
                            (0.35 * T, -side_sign * 8.0), (0.62 * T, side_sign * 14.0),
                            (1.00 * T, 0.0)])
    return b, s


def gen_anticipate_hold(role, side_sign=1.0, radial=(0.0, 0.0)):
    """Anticipate-hold(蓄力充能):長時間 squash 蓄力 hold → 單發大釋放 overshoot → 阻尼回擺。首尾 identity。

    scale:1.0 →(快速下蹲)0.85 →(**長 hold** 充能,佔比 ≥0.35)0.85 → peak(釋放)→ 回擺 → 1.0。
    簽章 = **峰前持續低於 0.97 的時間佔比 ≥0.35**(長蓄力)—— hit 的蓄力僅短暫 dip(佔比小)→ 負對照分離。"""
    T = DUR["anticipate_hold"]
    peak = _PEAK.get(role, 1.18)
    b, s = {}, {}
    env = [(0.00, 1.000), (0.08, 0.900), (0.15, 0.850), (0.45, 0.850),  # 長蓄力 hold(τ0.15–0.45)
           (0.58, peak),                                                  # 釋放 overshoot
           (0.70, 0.955), (0.82, 1.020), (0.92, 0.995), (1.00, 1.000)]   # 阻尼回擺
    b["scale"] = _scale_frames(T, env)

    if role == "limb":
        # 反向蓄力拉滿並 hold → 爆甩 → 回正
        b["rotate"] = _rot([(0.00 * T, 0.0), (0.15 * T, -side_sign * 10.0), (0.45 * T, -side_sign * 10.0),
                            (0.58 * T, side_sign * 16.0), (0.75 * T, -side_sign * 4.0), (1.00 * T, 0.0)])
    elif role == "特效":
        # 蓄力期壓暗並 hold → 釋放瞬亮 → 回穩;旋轉蓄力拉滿再甩
        s["color"] = _color([(0.00 * T, 1.0), (0.15 * T, 0.55), (0.45 * T, 0.55),
                             (0.58 * T, 1.0), (1.00 * T, 1.0)])
        b["rotate"] = _rot([(0.00 * T, 0.0), (0.15 * T, -18.0), (0.45 * T, -18.0),
                            (0.58 * T, 8.0), (0.78 * T, -3.0), (1.00 * T, 0.0)])
    return b, s


# candidate 0h — cascade(跨件錯開 reveal):**跨件時序**簽章,補 0f/0g 的**單件時序**簽章。
# 前述 beat(hit/reveal/combo/charge)都描述**單一件**的時間包絡;cascade 則描述**多件之間**
# 的相對時序 —— 各件依空間順序**錯開** onset 逐一 reveal(掃出 / 波狀 pop-in),而非同時炸開。
# 因此 cascade 不是又一個 per-bone 包絡,而是 build_animations 對整個 beat 的**件間相位**編排;
# 本模組只提供「單件在給定 onset 的錯開 reveal 包絡」,件間 onset 由 gen_animations 依 bone 空間序指派。
#
# cascade 的跨件簽章(validate_cascade.py 量化):
#   - **stagger spread**:件的 scale 峰時間分佈跨度 /T ≥ 門檻(同時 reveal → 跨度≈0 → 負對照分離)。
#   - **monotone sweep**:峰時間沿空間序(bone x)**嚴格遞增**(掃向一致;打亂 onset → 破)。
# 介面同 reveal 家族:首 collapsed(scale~0/alpha 0)、尾 identity(可接 Loop)。
DUR.setdefault("cascade", 1.4)


def gen_cascade_part(role, side_sign, radial, onset, width, T, eps=1e-3):
    """cascade 中**單一件**的錯開 reveal(時間單位為秒,非 τ)。

    [0, onset] 維持 collapsed(scale~0.02 / alpha 0,件尚未輪到)→ [onset, onset+width] burst pop
    (collapsed→overshoot→阻尼回擺→identity, alpha 0→1)→ [onset+width, T] hold identity。
    首幀 collapsed、尾幀 identity(reveal 家族介面)。onset>0 的件在自己 onset 前保持隱藏,
    故整個 beat 呈現「件依序 pop-in」的掃動;onset 由呼叫端(gen_animations)依空間序指派。"""
    peak = _PEAK.get(role, 1.18)
    on, w = float(onset), float(width)

    def _seq(hold_val, mid_pairs, end_val):
        """組件內時間序:首幀(hold_val)→[onset 維持 hold]→中段 mid_pairs→尾補 (T,end_val)。
        onset≈0 時省略重複 hold 幀;on+w≈T 時省略尾幀(避免重複時間)。"""
        seq = [(0.0, hold_val)]
        if on > eps:
            seq.append((on, hold_val))
        seq += mid_pairs
        if T - seq[-1][0] > eps:
            seq.append((T, end_val))
        return seq

    # --- scale:collapsed hold → burst overshoot → 阻尼回擺 → identity ---
    sc = _seq(0.020,
              [(on + 0.45 * w, peak), (on + 0.70 * w, 0.950),
               (on + 0.90 * w, 1.020), (on + w, 1.000)],
              1.000)
    b = {"scale": [{"time": round(t, 4), "x": round(v, 4), "y": round(v, 4)} for (t, v) in sc]}

    # --- alpha:蓄勢期全透明,burst 起點漸亮,峰後保持 ---
    al = _seq(0.0, [(on + 0.30 * w, 0.2), (on + 0.45 * w, 1.0)], 1.0)
    b_color = _color(al)

    # --- role rotate:在自身 window 內甩入回正(首尾皆隱藏姿/identity)---
    if role == "limb":
        rot = _seq(side_sign * 25.0,
                   [(on + 0.45 * w, -side_sign * 8.0), (on + 0.70 * w, side_sign * 3.0), (on + w, 0.0)],
                   0.0)
        b["rotate"] = _rot(rot)
    elif role == "特效":
        rot = _seq(-30.0, [(on + 0.45 * w, 10.0), (on + 0.75 * w, -4.0), (on + w, 0.0)], 0.0)
        b["rotate"] = _rot(rot)
    return b, {"color": b_color}


# 供 gen_animations 註冊到 _DISPATCH / _CAT_KEYWORDS 用
HIT_KEYWORDS = ["hit", "impact", "punch", "throb", "slam", "打擊", "命中", "重擊", "衝擊"]
REVEAL_KEYWORDS = ["reveal", "open", "burst", "showup", "appear_big", "揭曉", "現身", "炸開", "開獎"]
COMBO_KEYWORDS = ["combo", "multihit", "multi_hit", "chain", "連擊", "連段", "連打"]
CHARGE_KEYWORDS = ["charge", "windup", "wind_up", "chargeup", "anticipate_hold", "蓄力", "充能", "蓄勢"]
CASCADE_KEYWORDS = ["cascade", "sweep", "sequential", "stagger", "ripple", "wave",
                    "錯開", "接連", "連鎖", "波", "掃"]
