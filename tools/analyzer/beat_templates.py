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


# candidate J-2 — 連擊「數」隨檔位遞增:combo 的 impact 峰**數** = nhits(可變)。
# base(Super)nhits=3 → 逐位元同 0g 手調三連擊(向後相容);高檔位 nhits>3 由通用生成器
# 產**遞增 nhits 峰**,仍保 setup identity 介面 + 遞增峰簽章 + settle 阻尼回擺(與 charge 互斥
# ——擊間微回 >0.97、峰前 hold 佔比隨 nhits 增大反而降低)。與 tier 幅度增益(candidate J)正交:
# nhits 決定「連幾下」(結構,gen 時決定)、gain 決定「多爆」(幅度,事後 amplify)—— 兩者可疊。
COMBO_FIRST_TAU = 0.12   # 第一擊峰 τ
COMBO_FINALE_TAU = 0.62  # 末擊(finale)峰 τ(其後接 settle 尾)


def _combo_env(peak, nhits):
    """通用 nhits 連擊 scale 包絡 → [(τ∈[0,1], scale)]。峰嚴格遞增、首尾 identity、settle。

    第 i 擊(0-based,f=i/(nhits−1)):峰前 dip(遞深 0.95→0.90)、峰 p=1+q(0.60+0.40f)(遞增,
    末擊=role peak)、擊間微回 0.985(>HOLD_LEVEL 0.97 → 不算蓄力,保 combo≠charge)。
    末擊後接固定 settle 尾(0.955→1.030→0.995→1.0,峰 <IMPACT_PROM)。"""
    q = peak - 1.0
    first, finale = COMBO_FIRST_TAU, COMBO_FINALE_TAU
    dip_off, rec_off = 0.05, 0.035
    env = [(0.00, 1.000)]
    peak_taus = []
    for i in range(nhits):
        f = i / (nhits - 1) if nhits > 1 else 0.0
        tau = first + (finale - first) * f
        p = 1.0 + q * (0.60 + 0.40 * f)
        if i == 0:
            p = max(1.10, p)            # 首峰夾 ≥IMPACT_PROM 確保計入 impact
        env.append((round(tau - dip_off, 4), round(0.95 - 0.05 * f, 4)))  # 蓄力 dip(遞深)
        env.append((round(tau, 4), round(p, 4)))                          # impact 峰(遞增)
        if i < nhits - 1:
            env.append((round(tau + rec_off, 4), 0.985))                  # 擊間微回(>0.97)
        peak_taus.append(tau)
    env += [(0.74, 0.955), (0.85, 1.030), (0.93, 0.995), (1.00, 1.000)]   # 阻尼回擺(<IMPACT_PROM)
    return env, peak_taus


def gen_combo(role, side_sign=1.0, radial=(0.0, 0.0), nhits=3):
    """Multi-hit combo(連擊):**nhits** 段**遞增** impact,各含蓄力 dip + 部分回擺,尾段阻尼回穩。首尾 identity。

    scale 峰嚴格遞增(末擊=role peak);峰間回落 <1(下一擊的蓄力)→ 簽章 = 遞增 impact 峰數 = nhits
    (單發 hit 僅 1 峰 → 負對照分離)。仍具通用 anticipation(峰前 <1)+ settle(尾段回擺變號 ≥3)。
    `nhits`(candidate J-2)隨檔位遞增(Super 3 → Legend 6);**nhits=3 逐位元同 0g 手調**(向後相容)。"""
    T = DUR["combo"]
    peak = _PEAK.get(role, 1.18)
    b, s = {}, {}
    if nhits == 3:
        # 0g 手調 golden 三連擊(保留原關鍵幀 → byte-identical 向後相容)
        q = peak - 1.0
        p1 = max(1.10, 1.0 + 0.60 * q)
        p2 = 1.0 + 0.80 * q
        p3 = peak
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

    # 通用 nhits(candidate J-2):遞增 nhits 峰;rotate/color 對齊各峰、幅度隨擊遞增,首尾歸零/歸一。
    env, peak_taus = _combo_env(peak, nhits)
    b["scale"] = _scale_frames(T, env)
    n = nhits

    def _mag(i, base, span):
        return base + span * (i / (n - 1) if n > 1 else 0.0)

    if role == "limb":
        fr = [(0.00 * T, 0.0)]
        for i, tau in enumerate(peak_taus):
            fr.append((tau * T, side_sign * _mag(i, 8.0, 10.0)))          # 甩出(遞增)
        fr.append((1.00 * T, 0.0))
        b["rotate"] = _rot(fr)
    elif role == "head":
        fr = [(0.00 * T, 0.0)]
        for i, tau in enumerate(peak_taus):
            fr.append((tau * T, -_mag(i, 6.0, 7.0)))                      # 點頭砸(遞增)
        fr.append((0.74 * T, 4.0))
        fr.append((1.00 * T, 0.0))
        b["rotate"] = _rot(fr)
    elif role == "特效":
        cf = [(0.00 * T, 1.0)]
        rf = [(0.00 * T, 0.0)]
        for i, tau in enumerate(peak_taus):
            cf.append(((tau - 0.05) * T, round(0.80 - 0.08 * (i / (n - 1) if n > 1 else 0.0), 4)))  # 蓄暗(遞深)
            cf.append((tau * T, 1.0))                                     # 閃亮
            rf.append((tau * T, (side_sign if i % 2 == 0 else -side_sign) * _mag(i, 8.0, 6.0)))
        cf.append((1.00 * T, 1.0))
        rf.append((1.00 * T, 0.0))
        s["color"] = _color(cf)
        b["rotate"] = _rot(rf)
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


# candidate G-4' — wobble(斜拉 jelly wobble):**第一個產出 `shear` 通道的生成器**。
# 補上 G-4 的 honest boundary —— G-4 補齊了「件繞關節 pivot 的一般仿射(含 shear)」的**公式 + 閘**
# (`transform_matrix_full`/`pivot_channels_affine`/`apply_pivots(include_shear=True)`),但當時
# **沒有任何 beat 生成器產出 shear 通道**(產線主秀只用 rotate/scale),AC7 只用**合成** shear 驗過管路。
# 本 beat 讓某節拍(斜拉 squash / 果凍晃)實際產出 shear 通道,`build_spine --shear-pivot` 帶
# `include_shear=True` 端到端補償 → 把「公式/閘就緒 ≠ 生成器接上」這最後一段接上(見 STATE (G-4')）。
#
# 運動基元 = **阻尼 shearX 擺動**(純 shearX 斜拉,shearY≡0):skew 來回,幅度**遞減**收回 identity。
# 結構簽章(可量化、與天真單調 shear 在負對照乾淨分離):
#   1. 首尾 shearX == 0(setup identity 介面 → 可插在 Loop 循環間,同其他主秀 beat)。
#   2. **阻尼振盪**:shearX 序列**繞 0 變號 ≥3**(振盪+回穩)且**相繼極值幅度嚴格遞減**(阻尼)。
# 天真「0→A→hold」單調 shear:0 次變號、無遞減 → 負對照分離,證閘測的是阻尼振盪非「有 shear 即可」。
#
# 純 shear(不帶 scale/rotate)→ shear 通道**孤立可辨**:產線中僅 wobble 有 shear,其餘 beat 皆無
# (負對照 W5b),使 `apply_pivots(include_shear=True)` 的補償對象明確。

DUR.setdefault("wobble", 0.8)

# role → shearX 峰值(度)。特效/身體較大、末梢/頭中等(同 _PEAK 的相對關係)。
_WOBBLE_SHEAR = {"body": 14.0, "特效": 16.0, "head": 10.0, "limb": 12.0}
WOBBLE_DAMP = 0.5   # 相繼極值幅度衰減比(A → −0.5A → +0.25A → −0.125A)
# candidate G-4''' — 通用阻尼振盪的極值 τ 窗(首極值落 LEAD、末極值落 TAIL,皆 τ∈[0,1]):
# nosc≠4 由 `_wobble_env` 於此窗均勻布極值(nosc==4 走下方 golden 手調路,byte-identical 向後相容)。
WOBBLE_LEAD = 0.16
WOBBLE_TAIL = 0.80


def _wobble_env(A, nosc):
    """通用**阻尼 shearX 振盪**包絡 → [(τ∈[0,1], shearX)]。首尾 identity(0),`nosc` 個交替遞減極值。

    第 i 極值(0-based):符號 (−1)^i(首推 +A)、幅度 A·rⁱ(r=WOBBLE_DAMP 阻尼);τ 於
    [WOBBLE_LEAD, WOBBLE_TAIL] 均勻分布。⇒ 繞 0 變號 nosc−1 次(nosc≥4 → ≥3)、相繼極值幅度
    嚴格遞減(阻尼簽章)、首尾 0(setup identity 介面,可插 Loop)。振盪**段數 = nosc**(結構,
    gen 時決定,事後 amplitude amplify 加不出來 —— 同 J-2 combo 峰數)。"""
    r = WOBBLE_DAMP
    env = [(0.00, 0.0)]
    for i in range(nosc):
        f = i / (nosc - 1) if nosc > 1 else 0.0
        tau = WOBBLE_LEAD + (WOBBLE_TAIL - WOBBLE_LEAD) * f
        env.append((round(tau, 4), ((-1.0) ** i) * A * (r ** i)))
    env.append((1.00, 0.0))
    return env


def gen_wobble(role, side_sign=1.0, radial=(0.0, 0.0), nosc=4):
    """斜拉 jelly wobble:**阻尼 shearX 擺動**(純 shear 通道)。回傳 (bone_timelines, slot_timelines)。

    shearX 包絡(τ):0 →(+A skew)→(−rA 反向)→(+r²A)→ …(共 `nosc` 個交替遞減極值)→ 0
    (r=WOBBLE_DAMP)。首尾 identity(shearX=0);shearY≡0(純斜拉)。相繼極值 A>rA>r²A>… →
    **遞減=阻尼**,繞 0 變號 nosc−1 次(nosc≥4 → ≥3)→ 振盪簽章。
    `side_sign` 決定首推方向(左右件反相,同 loop/limb 慣例)。
    `nosc`(candidate G-4''')= 晃動振盪**段數**,隨檔位遞增(Super 4 → Legend 7);
    **nosc==4 逐位元同 G-4' 手調 golden 4 極值**(向後相容 byte-identical)。"""
    T = DUR["wobble"]
    A = _WOBBLE_SHEAR.get(role, 12.0) * side_sign
    r = WOBBLE_DAMP
    b, s = {}, {}
    if nosc == 4:
        # G-4' 手調 golden 4 極值(保留原 τ 關鍵幀 → byte-identical 向後相容;base wobble 恆走此路)
        env = [(0.00, 0.0), (0.16, A), (0.38, -r * A),
               (0.60, r * r * A), (0.80, -r * r * r * A), (1.00, 0.0)]
    else:
        # 通用 nosc(candidate G-4''):遞增 nosc 個阻尼極值,首尾 identity、簽章保形
        env = _wobble_env(A, nosc)
    b["shear"] = [{"time": round(tau * T, 4), "x": round(sx, 4), "y": 0.0} for (tau, sx) in env]
    return b, s


# candidate G-4'''' — squash(斜拉果凍**擠壓**):**第一個同時產出 `shear` + 耦合 `scale`(非均勻)通道
# 的生成器**。補上 G-4/G-4' 一路留到現在的 honest boundary —— G-4 補齊了「件繞關節 pivot 的**一般仿射**
# (含 shear **且** 非均勻 scale sx≠sy)」的公式/閘,但 AC4/AC7 的非均勻 scale 只用**合成**值驗管路;
# G-4' 的 wobble 只產**純 shearX**(scaleX≡scaleY≡1)。本 beat 讓某節拍實際產出**耦合的 shear + 非均勻
# scale** —— 斜拉時同時「擠壓保體積」(squash & stretch):skew 來回的同時,拉長一軸、壓縮另一軸使
# **面積守恆**(scaleX·scaleY==1)。`build_spine --shear-pivot`(include_shear=True 隱含 include_scale)
# 端到端把「rotate/scale/**shear** 三通道」一起繞關節 pivot 補償 → 件做**真正的一般仿射**(非相似)變換
# 而 pivot 精確不動(這是 G-4 通用 Δ=(M−I)(O−P) 公式第一次被**生成器產的**非均勻 scale + shear 同時驅動)。
#
# 運動基元 = **阻尼 shearX 擺動 + 耦合體積守恆 squash**(shearY≡0,squash 掛在 scaleX/scaleY):
#   shearX(τ):同 wobble 阻尼擺動 0→+A→−rA→+r²A→…→0(繞 0 變號、相繼極值遞減)。
#   scale(τ):每個 shear 極值時刻 i 施一次 squash —— scaleX=1+q_i(拉長)、scaleY=1/(1+q_i)(壓扁),
#     q_i=Q·rⁱ(擠壓幅度隨 shear 一起阻尼)⇒ **scaleX·scaleY==1(面積守恆)且 scaleX≠scaleY(非均勻)**;
#     首尾 scaleX==scaleY==1(identity 介面)。squash 幅度 q_i 與 |shearX| 同源同阻尼 → **兩通道耦合**。
# 結構簽章(可量化、負對照乾淨分離,證閘測的是「耦合體積守恆 squash」非「有 scale 即可」):
#   1. 首尾 identity(shearX==0、scaleX==scaleY==1)→ 可插 Loop 間(同其他主秀 beat)。
#   2. shear 阻尼振盪(同 wobble:繞 0 變號 ≥3 + 相繼極值嚴格遞減)。
#   3. **體積守恆 squash 耦合(crux)**:每個 shear 極值幀 (a)scaleX·scaleY≈1(面積守恆);
#      (b)scaleX≠scaleY(非均勻=真擠壓,非等比 pulse);(c)squash 幅度 |scaleX−1| 隨極值嚴格遞減(阻尼耦合)。
# 負對照:等比 scale(scaleX==scaleY,pulse)→(b)FALSE;非守恆 scale(scaleX,scaleY 皆拉長,積≠1)
#   →(a)FALSE —— 證(a)(b)彼此獨立、閘非「有 scale + 有 shear 即通過」。

DUR.setdefault("squash", 0.8)

# role → squash 首極值拉長量 Q(=scaleX−1 峰;特效/身體大、末梢/頭中,同 _WOBBLE_SHEAR 相對關係)。
_SQUASH_STRETCH = {"body": 0.14, "特效": 0.16, "head": 0.10, "limb": 0.12}


def _squash_env(A, Q, nosc):
    """通用**阻尼 shearX 擺動 + 耦合體積守恆 squash** 包絡。回傳 (shear_env, scale_env):
      shear_env = [(τ, shearX)]  首尾 0、`nosc` 個交替遞減極值(同 `_wobble_env`)。
      scale_env = [(τ, scaleX, scaleY)]  首尾 (1,1)、每極值 (1+q_i, 1/(1+q_i)),q_i=Q·rⁱ。

    兩者極值 τ 同點(shear 極值即 squash 極值 → 耦合);r=WOBBLE_DAMP 共用阻尼 → shear 與 squash
    同源同衰減。scaleX·scaleY≡1(面積守恆)、scaleX≠scaleY(非均勻)、squash 幅度 q_i 隨極值遞減。"""
    r = WOBBLE_DAMP
    sh = [(0.00, 0.0)]
    sc = [(0.00, 1.0, 1.0)]
    for i in range(nosc):
        f = i / (nosc - 1) if nosc > 1 else 0.0
        tau = WOBBLE_LEAD + (WOBBLE_TAIL - WOBBLE_LEAD) * f
        q = Q * (r ** i)
        sh.append((round(tau, 4), ((-1.0) ** i) * A * (r ** i)))
        sc.append((round(tau, 4), round(1.0 + q, 6), round(1.0 / (1.0 + q), 6)))
    sh.append((1.00, 0.0))
    sc.append((1.00, 1.0, 1.0))
    return sh, sc


def gen_squash(role, side_sign=1.0, radial=(0.0, 0.0), nosc=4):
    """斜拉果凍擠壓:**阻尼 shearX 擺動 + 耦合體積守恆 squash**(shear + 非均勻 scale 雙通道)。
    回傳 (bone_timelines, slot_timelines)。

    shearX 同 `gen_wobble`(阻尼擺動,首尾 0);scale 每個 shear 極值施體積守恆 squash
    (scaleX=1+q,scaleY=1/(1+q),q=Q·rⁱ 隨極值阻尼)→ scaleX·scaleY==1 且 scaleX≠scaleY,首尾 (1,1)。
    `side_sign` 決定 shear 首推方向;`nosc`=振盪/擠壓段數(預設 4,與 wobble 同窗;count-aware 為後續)。"""
    T = DUR["squash"]
    A = _WOBBLE_SHEAR.get(role, 12.0) * side_sign
    Q = _SQUASH_STRETCH.get(role, 0.12)
    b, s = {}, {}
    sh, sc = _squash_env(A, Q, nosc)
    b["shear"] = [{"time": round(tau * T, 4), "x": round(sx, 4), "y": 0.0} for (tau, sx) in sh]
    b["scale"] = [{"time": round(tau * T, 4), "x": round(scx, 4), "y": round(scy, 4)}
                  for (tau, scx, scy) in sc]
    return b, s


# 供 gen_animations 註冊到 _DISPATCH / _CAT_KEYWORDS 用
HIT_KEYWORDS = ["hit", "impact", "punch", "throb", "slam", "打擊", "命中", "重擊", "衝擊"]
REVEAL_KEYWORDS = ["reveal", "open", "burst", "showup", "appear_big", "揭曉", "現身", "炸開", "開獎"]
COMBO_KEYWORDS = ["combo", "multihit", "multi_hit", "chain", "連擊", "連段", "連打"]
CHARGE_KEYWORDS = ["charge", "windup", "wind_up", "chargeup", "anticipate_hold", "蓄力", "充能", "蓄勢"]
CASCADE_KEYWORDS = ["cascade", "wave", "ripple", "sequence", "sweep", "wipe", "錯開", "波", "依序", "接連"]
WOBBLE_KEYWORDS = ["wobble", "jelly", "sway", "skew", "shear", "lean", "斜拉", "果凍", "晃", "搖擺"]
# squash 專屬關鍵字(與 wobble 區隔:wobble=純 shear 擺,squash=shear+耦合體積守恆擠壓)。
SQUASH_KEYWORDS = ["squash", "stretch", "jellysquash", "diagsquash", "squish", "擠壓", "壓擠", "斜擠", "擠"]
