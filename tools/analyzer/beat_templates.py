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


# 供 gen_animations 註冊到 _DISPATCH / _CAT_KEYWORDS 用
HIT_KEYWORDS = ["hit", "impact", "punch", "throb", "slam", "打擊", "命中", "重擊", "衝擊"]
REVEAL_KEYWORDS = ["reveal", "open", "burst", "showup", "appear_big", "揭曉", "現身", "炸開", "開獎"]
