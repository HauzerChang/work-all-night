#!/usr/bin/env python3
"""candidate 0d — 分鏡(storyboard)→ Spine 3.8 `animations` keyframe(純 CPU,確定性)。

輸入:build_spine.py 產出的 skeleton.json(bones/slots/skin,animations 為空)
      + analyze_target 的 `3_motion_storyboard`(每檔位 beat × 每件 role/action 的**符號**描述)。
輸出:把三個 beat(In/Loop/Out)具體化為可載入的 Spine 3.8 timeline(bone rotate/translate/scale
      + slot color alpha),寫回 skeleton.json 的 `animations`。

設計原則(RULES:確定性演算法 + 評估器,不用 ML 學美術決定):
  role → 運動基元(motion primitive)的固定對映,幅度/相位為可調參數。
  - Loop:整體微呼吸;用**正弦取樣**關鍵幀(N/cycle),端點強制相等 → 無縫(AC2)。
    body=縮放呼吸、head=點頭、limb=末梢擺盪(**左右反相**)、特效=alpha 脈動+緩轉。
  - In  :scale 0→overshoot→1、alpha 0→1、limb 旋轉甩入、translate 由外側徑向歸位;**收在 setup identity**。
  - Out :由 identity → 收斂(scale/alpha→0)。
  三 beat 皆以 setup identity 為介面 → In 尾 == Loop 首/尾 == Out 首,可無縫串接(AC4)。

單位同 Spine runtime:rotate=角度增量(度)、translate=相對 setup local 位移(px)、
scale=乘在 setup(=1)的倍率、color=8-hex RGBA(alpha=末兩碼)。
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

# beat 類別 → 時長(秒)。beat 名為 genre 相依,先歸類再驅動基元(跨 genre 通用)。
DUR = {"intro": 0.6, "loop": 2.0, "outro": 0.4, "hold": 1.0, "pulse": 0.5}
LOOP_SAMPLES = 12  # loop 每 cycle 的正弦取樣數
EASE = 0.25        # intro/outro bezier 緩動控制(ease-out 近似)

# beat 名(小寫,含中英)→ 語意類別。未命中預設 loop(最安全:無縫、可 idle)。
_CAT_KEYWORDS = {
    "intro": ["in", "comeout", "come_out", "open", "appear", "enter", "start", "入場", "進場", "出現"],
    "outro": ["out", "close", "exit", "disappear", "leave", "end", "退場", "離場", "消失"],
    "loop": ["loop", "idle", "breath", "待機", "循環", "呼吸"],
    "hold": ["static", "hold", "base", "靜態", "定格"],
    # pulse = 泛用對稱脈衝(輕重音);主秀節拍 hit/reveal 由 beat_templates 提供更完整簽章
    # (見本檔尾端註冊),故 hit/burst 移出 pulse。
    "pulse": ["flash", "win", "閃"],
}


def beat_category(name):
    low = str(name).lower()
    # 精確 token 優先(避免子字串誤判,如 'legend' 含 'end')
    for cat, kws in _CAT_KEYWORDS.items():
        for kw in kws:
            if low == kw:
                return cat
    for cat, kws in _CAT_KEYWORDS.items():
        for kw in kws:
            if kw in low:
                return cat
    return "loop"


def safe(name):
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


def _alpha_hex(a):
    v = max(0, min(255, int(round(a * 255))))
    return "ffffff{:02x}".format(v)


def _rot(frames):
    return [{"time": round(t, 4), "angle": round(a, 3)} for (t, a) in frames]


def _xy(frames):
    return [{"time": round(t, 4), "x": round(x, 3), "y": round(y, 3)} for (t, x, y) in frames]


def _color(frames):
    return [{"time": round(t, 4), "color": _alpha_hex(a)} for (t, a) in frames]


def _loop_sine(amp, phase=0.0, kind="sin"):
    """回傳 [(t, value)] 一個無縫循環(端點值相等)。
    kind: 'sin' → amp*sin(2πτ+phase);'ucos' → amp*(1-cos(2πτ))/2(0→peak→0)。"""
    T = DUR["loop"]
    pts = []
    for i in range(LOOP_SAMPLES + 1):
        tau = i / LOOP_SAMPLES
        if kind == "sin":
            v = amp * math.sin(2 * math.pi * tau + phase)
        else:  # ucos:0 在端點,peak 在中點
            v = amp * (1 - math.cos(2 * math.pi * tau)) / 2.0
        pts.append((tau * T, v))
    # 端點強制相等 → 無縫(消除浮點殘差)
    pts[-1] = (pts[-1][0], pts[0][1])
    return pts


def _bez(frames_with_curve):
    """給每筆(除最後)插入 ease-out bezier 緊湊鍵。"""
    for f in frames_with_curve[:-1]:
        f["curve"] = EASE
        f["c2"] = 0.0
        f["c3"] = EASE
        f["c4"] = 1.0
    return frames_with_curve


def gen_loop(role, side_sign, radial=None):
    """Loop:回傳 (bone_timelines, slot_timelines)。"""
    b, s = {}, {}
    if role == "body":
        sc = _loop_sine(0.02, kind="sin")   # ±2% 呼吸
        b["scale"] = [{"time": round(t, 4), "x": round(1 + v, 4), "y": round(1 + v, 4)} for (t, v) in sc]
        b["translate"] = _xy([(t, 0.0, v) for (t, v) in _loop_sine(4.0, kind="sin")])
    elif role == "head":
        b["rotate"] = _rot([(t, v) for (t, v) in _loop_sine(3.0, kind="sin")])
    elif role in ("limb",):
        # 末梢擺盪,左右**反相**(side_sign=±1)→ 明確錯開(AC3 相位)
        b["rotate"] = _rot([(t, side_sign * v) for (t, v) in _loop_sine(5.0, kind="sin")])
    elif role == "特效":
        # alpha 脈動 + scale 微脹 + 緩轉(皆無縫)
        s["color"] = _color([(t, 1.0 - v) for (t, v) in _loop_sine(0.22, kind="ucos")])
        sc = _loop_sine(0.03, kind="ucos")
        b["scale"] = [{"time": round(t, 4), "x": round(1 + v, 4), "y": round(1 + v, 4)} for (t, v) in sc]
        b["rotate"] = _rot([(t, v) for (t, v) in _loop_sine(4.0, kind="sin")])
    return b, s


def gen_in(role, side_sign, radial):
    """In:入場爆發,收在 identity。radial=(ux,uy) 徑向外側單位向量(件由外側歸位)。"""
    T = DUR["intro"]
    b, s = {}, {}
    ux, uy = radial
    if role == "特效":
        b["scale"] = _bez([{"time": 0.0, "x": 0.02, "y": 0.02},
                            {"time": round(0.5 * T, 4), "x": 1.25, "y": 1.25},
                            {"time": round(T, 4), "x": 1.0, "y": 1.0}])
        b["rotate"] = _bez(_rot([(0.0, -40.0), (T, 0.0)]))
        s["color"] = _color([(0.0, 0.0), (0.5 * T, 1.0), (T, 1.0)])
    else:
        # scale 0→overshoot→1
        b["scale"] = _bez([{"time": 0.0, "x": 0.02, "y": 0.02},
                            {"time": round(0.7 * T, 4), "x": 1.12, "y": 1.12},
                            {"time": round(T, 4), "x": 1.0, "y": 1.0}])
        # translate 由外側 40px 歸位
        b["translate"] = _bez(_xy([(0.0, ux * 40.0, uy * 40.0), (T, 0.0, 0.0)]))
        s["color"] = _color([(0.0, 0.0), (T, 1.0)])
        if role == "limb":
            b["rotate"] = _bez(_rot([(0.0, side_sign * 20.0), (T, 0.0)]))
        elif role == "head":
            b["rotate"] = _bez(_rot([(0.0, 8.0), (0.6 * T, -4.0), (T, 0.0)]))
    return b, s


def gen_out(role, side_sign, radial):
    """Out:由 identity 收斂(scale/alpha→0)。"""
    T = DUR["outro"]
    b, s = {}, {}
    ux, uy = radial
    b["scale"] = _bez([{"time": 0.0, "x": 1.0, "y": 1.0},
                       {"time": round(T, 4), "x": 0.02, "y": 0.02}])
    s["color"] = _color([(0.0, 1.0), (T, 0.0)])
    if role in ("limb", "特效"):
        b["translate"] = _bez(_xy([(0.0, 0.0, 0.0), (T, ux * 20.0, uy * 20.0)]))
    if role == "特效":
        b["rotate"] = _bez(_rot([(0.0, 0.0), (T, 25.0)]))
    return b, s


def gen_hold(role, side_sign, radial):
    """hold/static:定格於 identity(2 幀 identity,構成合法短動畫,首尾皆 identity)。"""
    T = DUR["hold"]
    b = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0}, {"time": round(T, 4), "x": 1.0, "y": 1.0}]}
    return b, {}


def gen_pulse(role, side_sign, radial):
    """pulse/hit:identity→peak→identity 的對稱脈衝(首尾皆 identity → 可無縫串接)。"""
    T = DUR["pulse"]
    b, s = {}, {}
    if role == "特效":
        b["scale"] = _bez([{"time": 0.0, "x": 1.0, "y": 1.0},
                            {"time": round(0.5 * T, 4), "x": 1.3, "y": 1.3},
                            {"time": round(T, 4), "x": 1.0, "y": 1.0}])
        s["color"] = _color([(0.0, 1.0), (0.5 * T, 0.6), (T, 1.0)])
    else:
        peak = 1.12 if role == "body" else 1.08
        b["scale"] = _bez([{"time": 0.0, "x": 1.0, "y": 1.0},
                            {"time": round(0.5 * T, 4), "x": peak, "y": peak},
                            {"time": round(T, 4), "x": 1.0, "y": 1.0}])
        if role == "limb":
            b["rotate"] = _bez(_rot([(0.0, 0.0), (0.5 * T, side_sign * 10.0), (T, 0.0)]))
    return b, s


_DISPATCH = {"intro": gen_in, "loop": gen_loop, "outro": gen_out, "hold": gen_hold, "pulse": gen_pulse}

# candidate 0f — 註冊 big-win 主秀 beat 模板(anticipation+settle)。放檔尾避免與 beat_templates
# 形成 import 迴圈:beat_templates 只需本檔上方已定義的 DUR/_rot/_xy/_color。
try:
    from beat_templates import gen_hit as _gen_hit, gen_reveal as _gen_reveal, \
        gen_combo as _gen_combo, gen_anticipate_hold as _gen_charge, gen_cascade as _gen_cascade, \
        HIT_KEYWORDS as _HIT_KW, REVEAL_KEYWORDS as _REVEAL_KW, \
        COMBO_KEYWORDS as _COMBO_KW, CHARGE_KEYWORDS as _CHARGE_KW, \
        CASCADE_KEYWORDS as _CASCADE_KW, DUR as _DUR_EXT
    _DISPATCH["hit"] = _gen_hit
    _DISPATCH["reveal"] = _gen_reveal
    _DISPATCH["combo"] = _gen_combo
    _DISPATCH["charge"] = _gen_charge
    _DISPATCH["cascade"] = _gen_cascade
    DUR.update(_DUR_EXT)  # 讓 hit/reveal/combo/charge/cascade 時長對 spine_anim.duration 一致
    # 主秀類別置前:exact/substring 命中優先於泛用 pulse(combo/charge/cascade 亦置前)
    _CAT_KEYWORDS = {"cascade": _CASCADE_KW, "combo": _COMBO_KW, "charge": _CHARGE_KW,
                     "hit": _HIT_KW, "reveal": _REVEAL_KW, **_CAT_KEYWORDS}
except ImportError:
    pass

# cascade 是**跨件時序**類別:單件產生器需知道自己在件序中的相位(phase∈[0,1])。
# 只有這類別要吃 phase,故集中列名,build_animations 依此決定是否帶入(其餘類別簽章不變)。
_PHASE_AWARE = {"cascade"}


def build_animations(skeleton, storyboard, pivots=None):
    """回傳 animations dict(beat 名為 key)。

    pivots(可選,candidate 0i / S1 (e)):{safe_part_name: (Px, Py)} 關節 pivot 世界座標
      (與 bone 的 x/y 同一座標系)。提供時,產生 `rotate` 通道的件(limb/head/特效)改為
      **繞關節 pivot 旋轉**而非繞件中心(bone 原點),用補償平移實現(見 `articulate`)。
      預設 None → 完全沿用原行為(向後相容,既有 validator 不受影響)。"""
    # 件名 → bone/slot / setup 位置
    bone_of = {b["name"].removeprefix("b_"): b for b in skeleton["bones"] if b["name"] != "root"}
    # 畫布中心(用於徑向)
    W = skeleton["skeleton"]["width"]
    H = skeleton["skeleton"]["height"]
    cx, cy = W / 2.0, H / 2.0

    anims = {}
    for beat in storyboard["beats"]:
        name = beat["beat"]
        cat = beat_category(name)
        bones_tl, slots_tl = {}, {}
        limb_seen = 0
        # 跨件時序類別(cascade)需先知道**有效件**總數以配相位;先過濾出真正有 bone 的件。
        valid = [pe for pe in beat["parts"] if bone_of.get(safe(pe["part"])) is not None]
        nvalid = len(valid)
        for pi, pe in enumerate(valid):
            part = pe["part"]; role = pe["role"]
            sname = safe(part)
            bname = "b_" + sname
            bd = bone_of.get(sname)
            # 左右反相:依遇到 limb 的順序交替 ±1(確定性)
            side_sign = 1.0
            if role == "limb":
                side_sign = 1.0 if limb_seen % 2 == 0 else -1.0
                limb_seen += 1
            # 徑向外側單位向量(件中心相對畫布中心)
            dx, dy = bd.get("x", cx) - cx, bd.get("y", cy) - cy
            n = math.hypot(dx, dy) or 1.0
            radial = (dx / n, dy / n)

            if cat in _PHASE_AWARE:
                # 件序相位:第一件 0、最後一件 1(單件時 0)→ 各件峰時刻依序錯開
                phase = 0.0 if nvalid <= 1 else pi / (nvalid - 1)
                b, sdict = _DISPATCH[cat](role, side_sign, radial, phase)
            else:
                b, sdict = _DISPATCH[cat](role, side_sign, radial)
            # candidate 0i(S1 (e)):有 pivot 且該件產了 rotate → 改繞關節 pivot 旋轉。
            # 件 bone 仍在件中心 O=(bd.x,bd.y);pivot P 由 S5 infer_pivots 推得。
            if pivots and b.get("rotate") and sname in pivots:
                from articulate import articulate_about_pivot
                O = (bd.get("x", cx), bd.get("y", cy))
                nr, nt = articulate_about_pivot(b["rotate"], O, pivots[sname],
                                                base_translate=b.get("translate"))
                b["rotate"] = nr
                if nt:
                    b["translate"] = nt
            if b:
                bones_tl[bname] = b
            if sdict:
                slots_tl[sname] = sdict
        anim = {}
        if bones_tl:
            anim["bones"] = bones_tl
        if slots_tl:
            anim["slots"] = slots_tl
        anims[name] = anim
    return anims


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton_json", help="build_spine 產出的 skeleton.json")
    ap.add_argument("--psd", default="assets/robot_parts.psd", help="用於取 storyboard 的來源 PSD")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--inplace", action="store_true", help="寫回 skeleton.json")
    a = ap.parse_args()
    from analyze_target import analyze
    sk = json.load(open(a.skeleton_json, encoding="utf-8"))
    spec = analyze(a.psd, a.genre)
    anims = build_animations(sk, spec["3_motion_storyboard"])
    sk["animations"] = anims
    if a.inplace:
        json.dump(sk, open(a.skeleton_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"animations": list(anims.keys()),
                      "beats": {k: {"bones": len(v.get("bones", {})), "slots": len(v.get("slots", {}))}
                                for k, v in anims.items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
