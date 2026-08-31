#!/usr/bin/env python3
"""candidate 0e — 分鏡(storyboard)→ Spine 3.8 `deform` timeline(純 CPU,確定性)。

補上 gen_animations(0d)的缺口:0d 只生成 **bone TRS + slot alpha**,mesh(窗簾/軟件/光暈)
**不會 deform**。本檔為 skin 內每個 mesh attachment 生成逐頂點 deform timeline,讓 build --animate
產出的軟件真正會「飄/脹/縮」,而非整片剛性隨骨走。

設計原則(RULES:確定性演算法 + 評估器,不用 ML 學美術決定):
  mesh role → deform 基元(primitive)。核心用**仿射(affine)場**——它把 setup 的直線邊「精確」
  映成新直線邊(仿射映射與線性內插可交換),故對**任意幅度**都不自交/不翻面(可證明乾淨):
  - **affine swing**(布料/窗簾):dx = A·fy·swing(t)、dy = 0。fy=(ymax−y)/h 對 y **線性** →
    整體為仿射剪切 → 直線邊仍為直線邊 → 恆乾淨。看起來像窗簾整片左右擺(底邊擺幅大)。
  - **radial-breathe**(光暈/陰影/軟 blob):offset_i = s(t)·(p_i − centroid)。**均勻縮放亦是仿射** →
    直線邊精確保持 → s > −1 時恆乾淨。看起來像光暈脈動呼吸。
  可選的**行進波**(相位隨 fy 變 → 對 y **非線性**,非仿射)較好看但**不保證**乾淨(非線性剪切會讓
    直線邊互穿);故波幅經 `deform_eval` 逐幀閘**自動遞減**至乾淨(最差退化為純仿射,仍乾淨且非平凡)。

⚠️ **踩雷更正(2026-08-31)**:曾誤以為「純 y 剪切=平面雙射→恆保拓樸」。雙射只保證**點**不重合,
   但 mesh 的**直線邊**是在位移後頂點間重畫的,非仿射位移下直線邊可互穿 → 會自交。
   只有**仿射**場(線性剪切、均勻縮放、平移、旋轉)才精確保直線邊。故本檔以仿射為保證核心 + 波幅閘控。

beat 類別對映(與 gen_animations 一致,確定性):
  - loop :無縫(端點值相等,正弦/ucos 取樣)。
  - intro:由 billow/縮小 → **收在 setup identity(deform=0)**(與 bone timeline 的 identity 介面對齊)。
  - outro:由 identity → billow/collapse。
  - pulse:identity → peak → identity(首尾皆 0)。
  - hold :identity(不發 deform)。
三 beat 皆以 deform=0(setup)為介面 → 可與 0d 的 bone timeline 無縫串接。

⚠️ **刻意用線性內插(不加 bezier curve 鍵)**:讓相鄰 keyframe 之間的任一中間幀都是兩個
   保拓樸場的凸組合 → 中間幀也保證乾淨(bezier 可能 overshoot 出凸包,破壞保證)。

Spine 3.8 deform 格式:animations[beat]["deform"][skinName][slot][attName] = [{time, vertices:[dx,dy,...]}, ...]
  vertices 為逐頂點 local 位移(offset=0,全長 2*nv;y-up,與 mesh.vertices 同慣例)。
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

# 與 gen_animations 共用 beat 類別/時長判定
from gen_animations import beat_category, DUR, LOOP_SAMPLES

# 幅度。affine 部分(swing/scale)恆乾淨;wave 部分經閘自動遞減。
AMP = {
    "shear": {"loop": 0.16, "intro": 0.55, "outro": 0.55, "pulse": 0.30},  # affine swing ×bbox 寬
    "radial": {"loop": 0.06, "intro": 0.35, "outro": 0.9, "pulse": 0.22},  # 縮放係數 s
}
WAVE_FRAC = 0.5    # 行進波幅相對 affine swing 幅的初始比例(閘不過則遞減)
WAVE_K = 2.2       # 行進波數(相位隨 fy 累積的圈數 ×2π;此為非仿射項)
GATE_TRIES = 6     # 波幅遞減嘗試次數(RULES:自我修正 ≤ 迭代預算)
GATE_SHRINK = 0.5  # 每次不過就把波幅 ×此


# ---------- role 判定(mesh 名/slot → 場族) ----------
_RADIAL_HINTS = ["shadow", "glow", "光暈", "光", "陰影", "shade", "halo", "flash", "aura", "spark"]


def mesh_role(slot, name):
    """回傳 'radial'(光暈/陰影/軟 blob)或 'shear'(布料/窗簾/其餘)。確定性關鍵字判定。"""
    low = (str(slot) + "/" + str(name)).lower()
    for h in _RADIAL_HINTS:
        if h in low:
            return "radial"
    return "shear"


# ---------- 取樣 τ(無縫用端點強制相等) ----------
def _loop_taus():
    return [i / LOOP_SAMPLES for i in range(LOOP_SAMPLES + 1)]


# ---------- 場族(輸入 setup verts (nv,2),回傳每 τ 的 full offset (2*nv,)) ----------
def _bbox(v):
    xs = [p[0] for p in v]; ys = [p[1] for p in v]
    return min(xs), min(ys), max(xs), max(ys)


def _shear_field(verts, amp_frac, taus, mode, wave_frac):
    """dx = fy·[ A·swing(τ)  (仿射,恆乾淨)  +  A·wave_frac·wave(fy,τ) (非仿射,閘控) ];dy=0。
    pinned 在 ymax(頂邊)、free 在 ymin。swing(τ) 對 y 線性 → 仿射;wave 相位隨 fy → 非仿射。
    mode: 'loop'/'settle'(intro→0)/'grow'(outro 0→峰)/'pulse'(0→峰→0)。"""
    xmin, ymin, xmax, ymax = _bbox(verts)
    w = max(xmax - xmin, 1e-6); h = max(ymax - ymin, 1e-6)
    A = amp_frac * w
    frames = []
    for tau in taus:
        env = {"loop": 1.0, "settle": (1.0 - tau), "grow": tau,
               "pulse": math.sin(math.pi * tau)}[mode]
        off = []
        for (x, y) in verts:
            fy = (ymax - y) / h                       # 0 頂(pinned)→ 1 底(free),對 y 線性
            phase = WAVE_K * 2 * math.pi * fy
            if mode == "loop":
                swing = A * fy * math.sin(2 * math.pi * tau)                       # 仿射:整片擺
                wave = A * wave_frac * fy * (math.sin(2 * math.pi * tau + phase)   # 非仿射:行進波
                                             - math.sin(2 * math.pi * tau))        #  (扣掉 affine 分量,只留漣漪)
            else:
                swing = A * fy * env * 0.6                                         # 仿射:整片 billow(線性 in fy)
                wave = A * wave_frac * fy * math.sin(phase) * env                  # 非仿射:形狀漣漪
            off.extend([swing + wave, 0.0])
        frames.append(off)
    if mode == "loop":            # 端點強制相等 → 無縫
        frames[-1] = list(frames[0])
    return frames


def _radial_field(verts, amp, taus, mode):
    """offset_i = s(τ)·(p_i − centroid)。均勻縮放,s>−1 恆保拓樸。
    mode: 'loop'(ucos 脈動)/'settle'(縮小→identity,帶 overshoot)/'grow'(identity→collapse)/'pulse'。"""
    cx = sum(p[0] for p in verts) / len(verts)
    cy = sum(p[1] for p in verts) / len(verts)
    frames = []
    for tau in taus:
        if mode == "loop":
            s = amp * (1 - math.cos(2 * math.pi * tau)) / 2.0          # 0→peak→0 無縫
        elif mode == "settle":                                         # intro:−0.8 縮小 → +overshoot → 0
            s = (-0.8) * (1 - tau) ** 2 + 0.15 * math.sin(math.pi * tau)
        elif mode == "grow":                                          # outro:0 → −amp collapse
            s = -abs(amp) * tau
        else:  # pulse
            s = amp * math.sin(math.pi * tau)
        s = max(s, -0.98)                                             # 保 det>0
        off = []
        for (x, y) in verts:
            off.extend([s * (x - cx), s * (y - cy)])
        frames.append(off)
    if mode == "loop":
        frames[-1] = list(frames[0])
    return frames


_MODE = {"intro": "settle", "outro": "grow", "pulse": "pulse", "loop": "loop"}


def _gate_clean(verts, tris, offs):
    """用 deform_eval 逐幀(含線性內插 substep)檢查 offs 是否全乾淨。tris 為 None 時跳過(視為乾淨)。"""
    if tris is None:
        return True
    import numpy as np
    import deform_eval as de
    setup = np.array(verts, dtype=np.float64)
    T = np.array(tris, dtype=np.int32).reshape(-1, 3)
    signs = [de.signed_area(setup, t) > 0 for t in T]
    area = sum(abs(de.signed_area(setup, t)) for t in T)
    frames = [(i, 0, np.array(o, dtype=np.float64)) for i, o in enumerate(offs)]
    for _, v in de.sample_poses(setup, frames):
        r = de.eval_pose(v, T, signs, area)
        if not r["clean"]:
            return False
    return True


def gen_mesh_timeline(verts, category, role, tris=None):
    """回傳該 mesh 在此 beat 的 deform frames [{time, vertices}],或 None(hold/identity 不發)。
    非仿射的行進波幅經 deform_eval 逐幀閘**自動遞減**至乾淨(最差退化純仿射,恆乾淨)。"""
    if category == "hold":
        return None
    T = DUR[category]
    taus = _loop_taus() if category == "loop" else [i / LOOP_SAMPLES for i in range(LOOP_SAMPLES + 1)]
    mode = _MODE[category]
    if role == "radial":
        offs = _radial_field(verts, AMP["radial"][category], taus, mode)  # 仿射,恆乾淨
    else:
        wf = WAVE_FRAC
        offs = _shear_field(verts, AMP["shear"][category], taus, mode, wf)
        for _ in range(GATE_TRIES):
            if _gate_clean(verts, tris, offs):
                break
            wf *= GATE_SHRINK                                            # 遞減非仿射波幅
            offs = _shear_field(verts, AMP["shear"][category], taus, mode, wf)
        else:
            offs = _shear_field(verts, AMP["shear"][category], taus, mode, 0.0)  # 純仿射保底
    frames = []
    for tau, off in zip(taus, offs):
        frames.append({"time": round(tau * T, 4), "vertices": [round(o, 3) for o in off]})
    return frames


# ---------- mesh 蒐集 + 注入 ----------
def attachments_map(skeleton):
    """兼容兩種 skin schema,回傳 (skinName, {slot:{att:attachment}})。
      - list 形(main_draw/官方):[{"name":..,"attachments":{slot:{att}}}]
      - map  形(build_spine):{"default":{slot:{att}}}
    """
    skins = skeleton["skins"]
    if isinstance(skins, list):
        s0 = skins[0]
        return s0.get("name", "default"), s0.get("attachments", {})
    # map 形:{skinName: {slot:{att}}}
    nm = next(iter(skins))
    return nm, skins[nm]


def list_meshes(skeleton, with_tris=False):
    """回傳 [(slot, attName, setup_verts(nv,2))],with_tris=True 時附 triangles(供閘)。"""
    _, atts = attachments_map(skeleton)
    out = []
    for slot, obj in atts.items():
        for name, a in obj.items():
            if isinstance(a, dict) and a.get("type") == "mesh":
                nv = len(a["uvs"]) // 2
                vs = a["vertices"][:2 * nv]
                verts = [(vs[2 * i], vs[2 * i + 1]) for i in range(nv)]
                if with_tris:
                    out.append((slot, name, verts, a.get("triangles")))
                else:
                    out.append((slot, name, verts))
    return out


def skin_name(skeleton):
    return attachments_map(skeleton)[0]


def build_mesh_deform(skeleton, storyboard, roles=None):
    """為每個 beat × 每個 mesh 生成 deform,回傳 {beat: {skinName: {slot: {att: frames}}}}。
    roles: 選填 {att_or_slot: 'radial'|'shear'} 覆蓋自動判定。"""
    meshes = list_meshes(skeleton, with_tris=True)
    sk = skin_name(skeleton)
    roles = roles or {}
    out = {}
    for beat in storyboard["beats"]:
        name = beat["beat"]
        cat = beat_category(name)
        deform = {}
        for slot, att, verts, tris in meshes:
            role = roles.get(att) or roles.get(slot) or mesh_role(slot, att)
            frames = gen_mesh_timeline(verts, cat, role, tris=tris)
            if frames is None:
                continue
            deform.setdefault(sk, {}).setdefault(slot, {})[att] = frames
        if deform:
            out[name] = deform
    return out


def attach_into_animations(skeleton, storyboard, roles=None):
    """把 deform 併進 skeleton['animations'](與 gen_animations 的 bones/slots 並存)。"""
    md = build_mesh_deform(skeleton, storyboard, roles)
    anims = skeleton.setdefault("animations", {})
    for beat, deform in md.items():
        anims.setdefault(beat, {})["deform"] = deform
    return md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton_json")
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--inplace", action="store_true")
    a = ap.parse_args()
    from analyze_target import analyze
    sk = json.load(open(a.skeleton_json, encoding="utf-8"))
    spec = analyze(a.psd, a.genre)
    md = attach_into_animations(sk, spec["3_motion_storyboard"])
    if a.inplace:
        json.dump(sk, open(a.skeleton_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"beats_with_deform": list(md.keys()),
                      "meshes": [f"{s}/{n}" for s, n, _ in list_meshes(sk)]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
