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


# candidate 0h — cascade(跨件錯開「波」):大獎主秀常見的「一件接一件依序亮起」節拍。
# 與 0f/0g 的 hit/reveal/combo/charge 本質不同:那些是**單件內**的時間簽章(同一 beat 套到每件、
# 每件時序相同);cascade 是**跨件**時間簽章 —— 每件依其**順序相位**錯開觸發,形成一道波。
# 故其簽章不在單件曲線裡,而在「各件峰值時刻的排序與散佈」:peak 時刻隨件序**嚴格遞增**且散佈
# 佔整段 ≥門檻(近同時觸發的 combo/hit 會 spread≈0 → 負對照分離)。
#
# 介面:採**pop 波**形(每件 identity→蓄力 dip→pop overshoot→阻尼回擺→identity),首尾皆 setup
# identity(每件皆是),故與 In/Loop/Out 可無縫串接(同 combo/charge 的可插性)。
# (另有「reveal 波」變體=每件 start collapsed 依序現身,首非 identity;pop 波保留可串接介面 + 乾淨 argmax
#  峰時刻量測,選為預設。)相位 phase∈[0,1] 由 build_animations 依件序帶入(0=第一件、1=最後一件)。

DUR.setdefault("cascade", 1.2)

# cascade 波的相位窗:第一件峰落在 LEAD、最後一件峰落在 LEAD+SPAN(皆 τ∈[0,1])。
CASCADE_LEAD = 0.16
CASCADE_SPAN = 0.54


def gen_cascade(role, side_sign=1.0, radial=(0.0, 0.0), phase=0.0):
    """跨件錯開波中的**單件** pop(依 phase 錯開)。回傳 (bone_timelines, slot_timelines)。

    每件 scale 包絡(絕對 τ,中心 c=LEAD+phase*SPAN):
      1.0(identity)→ hold 1.0 到輪到它 → 0.94(蓄力)→ peak(pop)→ 0.97→1.005(阻尼回擺)→ 1.0。
    首尾皆 identity;全域峰落在 c → 各件峰時刻隨 phase 錯開 = cascade 跨件簽章。"""
    T = DUR["cascade"]
    peak = _PEAK.get(role, 1.18)
    p = max(0.0, min(1.0, phase))
    c = CASCADE_LEAD + p * CASCADE_SPAN
    b, s = {}, {}
    # 絕對 τ 關鍵幀(嚴格遞增;c-0.09≥0.07>0、c+0.16≤0.86<1 於 phase∈[0,1] 皆成立)
    env = [(0.00, 1.000), (c - 0.09, 1.000),           # 起始 identity + hold 到輪到它
           (c - 0.05, 0.940),                           # anticipation 蓄力
           (c, peak),                                    # pop(全域峰 → 峰時刻=c)
           (c + 0.06, 0.970), (c + 0.11, 1.005),         # 阻尼回擺(settle)
           (c + 0.16, 1.000), (1.00, 1.000)]             # 回 identity + hold 到結束
    b["scale"] = _scale_frames(T, env)

    if role == "limb":
        # 末梢隨波甩出(反向蓄力→甩→回),中心對齊 c
        b["rotate"] = _rot([(0.0, 0.0), ((c - 0.05) * T, -side_sign * 6.0),
                            (c * T, side_sign * 16.0), ((c + 0.08) * T, -side_sign * 4.0),
                            ((c + 0.16) * T, 0.0), (T, 0.0)])
    elif role == "特效":
        # 每件輪到時亮度閃(蓄暗→亮→回);首尾 alpha=1(可串接),閃在 c
        s["color"] = _color([(0.0, 1.0), ((c - 0.05) * T, 0.78), (c * T, 1.0),
                            ((c + 0.08) * T, 0.9), (T, 1.0)])
        b["rotate"] = _rot([(0.0, 0.0), ((c - 0.05) * T, -8.0), (c * T, 10.0),
                            ((c + 0.1) * T, -3.0), (T, 0.0)])
    return b, s


# 供 gen_animations 註冊到 _DISPATCH / _CAT_KEYWORDS 用
HIT_KEYWORDS = ["hit", "impact", "punch", "throb", "slam", "打擊", "命中", "重擊", "衝擊"]
REVEAL_KEYWORDS = ["reveal", "open", "burst", "showup", "appear_big", "揭曉", "現身", "炸開", "開獎"]
COMBO_KEYWORDS = ["combo", "multihit", "multi_hit", "chain", "連擊", "連段", "連打"]
CHARGE_KEYWORDS = ["charge", "windup", "wind_up", "chargeup", "anticipate_hold", "蓄力", "充能", "蓄勢"]
CASCADE_KEYWORDS = ["cascade", "wave", "ripple", "sequence", "sweep", "wipe", "錯開", "波", "依序", "接連"]
