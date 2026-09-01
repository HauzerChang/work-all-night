#!/usr/bin/env python3
"""candidate 0d 續 — mesh **deform** timeline 生成器(純 CPU,確定性)。

補上 gen_animations.py 的缺口:此前只生成 bone TRS + slot color alpha,
**mesh 不會變形**(窗簾/軟體 deform 未生成)。本檔把「role/beat → 空間位移場 × 時間 shape」
確定性地具體化為 Spine 3.8 `deform` timeline(unweighted mesh 的逐頂點 offset)。

── 位移場模型(grounded in artist 真值,非臆測)──────────────────────────
量測 main_draw 4 個真實藝術家 mesh 的 deform(見 knowledge/s1-mesh-deform-generator.md):
  · 錨定在**長軸一端**(窗簾頂 rail:|deform|=0),自由端(底)|deform|=max;
  · 位移**主要沿短軸(水平掃動)**,幅度**~線性**於「距錨邊的距離」;
  · 窗簾峰值 ~59% 長軸長、陰影 ~19%,且全幀拓樸乾淨(藝術家真值)。
故確定性場: offset_perp[i] = A · w_i · shape(τ) ,w_i = 距錨邊的正規化距離 ∈[0,1]
  (錨邊 w=0、自由端 w=1),shape(τ) 為 beat 類別相依的時間曲線,τ=t/dur。
「哪一端錨定」無法從單張 mesh 得知 → 用 prior(預設長軸 max 端=頂錨定,可參數覆寫)。

── beat 類別 → 時間 shape(與 gen_animations 的 TRS beat 介面一致:多數在 setup identity 收合)──
  loop  : sin(2πτ) 無縫擺盪(端點=0 → offset 全零,可無縫接 TRS loop);加輕微 travelling-wave 漣漪。
  pulse : sin(πτ) 對稱陣風(0→peak→0,首尾 identity)。
  intro : 由「掃開」姿態衰減回 setup(首=掃開、尾=identity → 接 loop)。 [reveal:非零起點]
  outro : 由 setup 生長到「掃出」姿態(首=identity、尾=掃出)。            [reveal:非零終點]
  hold  : 無 deform(空)。

輸出即 Spine 3.8 deform 幀 [{"time":.., "vertices":[dx0,dy0,...]}](offset=0,全長)。
單位/座標:vertices 為 attachment-local y-up 逐頂點 offset(px),與 deform_eval.apply_deform 對齊。
"""
import math
import numpy as np

# 與 gen_animations.DUR 對齊(beat 類別 → 時長秒)
DUR = {"intro": 0.6, "loop": 2.0, "outro": 0.4, "hold": 1.0, "pulse": 0.5}
LOOP_SAMPLES = 12   # loop 每 cycle 正弦取樣
BEAT_SAMPLES = 8    # intro/outro/pulse 取樣幀數

# 幅度預設(佔長軸長的比例);可被 gate 自動下修(5 輪預算)
AMP = {"loop": 0.06, "pulse": 0.10, "intro": 0.35, "outro": 0.35}
RIPPLE_K = 0.8      # loop travelling-wave 每單位 w 的相位滯後(rad)


def _axes(setup):
    """回傳 (long_axis, perp_axis, anchor_coord, extent_long)。
    long_axis = 較長的一軸(0=x,1=y);錨邊預設在 long_axis 的 max 端。"""
    mn = setup.min(0); mx = setup.max(0)
    ext = mx - mn
    long_axis = 0 if ext[0] >= ext[1] else 1
    perp_axis = 1 - long_axis
    return long_axis, perp_axis, float(mx[long_axis]), float(max(ext[long_axis], 1e-6))


def _weights(setup, anchor="max"):
    """w_i = 距錨邊的正規化距離 ∈[0,1](錨邊 0、自由端 1)。"""
    long_axis, perp_axis, cmax, ext = _axes(setup)
    mn = setup[:, long_axis].min()
    if anchor == "max":               # 頂錨定(預設):距頂越遠(越靠底)w 越大
        w = (cmax - setup[:, long_axis]) / ext
    else:                             # 底錨定
        w = (setup[:, long_axis] - mn) / ext
    return np.clip(w, 0.0, 1.0), long_axis, perp_axis, ext


def _shape_loop(tau):
    return math.sin(2 * math.pi * tau)


def _offsets_at(setup, w, perp_axis, ext, cat, amp_frac, tau, sway_sign=-1.0):
    """回傳該 τ 的全長 offset 向量 (2*nv,)。"""
    nv = setup.shape[0]
    off = np.zeros((nv, 2), dtype=np.float64)
    A = amp_frac * ext
    if cat == "loop":
        # travelling-wave:底部相位滯後 → 漣漪;端點 τ=0/1 同相 → 無縫
        for i in range(nv):
            off[i, perp_axis] = sway_sign * A * w[i] * math.sin(2 * math.pi * tau - RIPPLE_K * w[i])
    elif cat == "pulse":
        g = math.sin(math.pi * tau)                    # 0→1→0
        off[:, perp_axis] = sway_sign * A * w * g
    elif cat == "intro":
        s = (1.0 - tau) * (1.0 + 0.3 * math.sin(2 * math.pi * 2 * tau))  # 掃開→identity,尾=0
        off[:, perp_axis] = sway_sign * A * w * s
    elif cat == "outro":
        s = tau                                        # identity→掃出
        off[:, perp_axis] = sway_sign * A * w * s
    return off.reshape(-1)


def gen_deform_timeline(setup, category, anchor="max", amp_frac=None, sway_sign=-1.0):
    """回傳 Spine 3.8 deform 幀 list [{"time","vertices"}]。setup: (nv,2) y-up。
    hold → []。loop 端點強制相等(無縫)。"""
    setup = np.asarray(setup, dtype=np.float64).reshape(-1, 2)
    if category == "hold":
        return []
    if amp_frac is None:
        amp_frac = AMP.get(category, 0.1)
    w, long_axis, perp_axis, ext = _weights(setup, anchor)
    T = DUR.get(category, 1.0)
    if category == "loop":
        n = LOOP_SAMPLES
    else:
        n = BEAT_SAMPLES
    frames = []
    vecs = []
    for k in range(n + 1):
        tau = k / n
        vec = _offsets_at(setup, w, perp_axis, ext, category, amp_frac, tau, sway_sign)
        vecs.append(vec)
    if category == "loop":
        vecs[-1] = vecs[0].copy()      # 無縫:消浮點殘差
    for k, vec in enumerate(vecs):
        frames.append({"time": round(k / n * T, 4),
                       "vertices": [round(float(x), 3) for x in vec]})
    return frames


def build_deform_block(skeleton, category, slots=None, anchor="max", amp_frac=None, sway_sign=-1.0):
    """對 skeleton 內所有(或指定)unweighted mesh 產生一支 animation 的 deform 區塊。
    回傳 {skinName: {slot: {attName: frames}}}(Spine 3.8 deform 結構)。"""
    skin = skeleton["skins"]
    skin_name = "default"
    if isinstance(skin, list):
        skin_name = skin[0].get("name", "default")
        atts = skin[0].get("attachments", skin[0])
    else:
        atts = skin.get("attachments", skin)
    block = {}
    for slot, o in atts.items():
        if slots is not None and slot not in slots:
            continue
        for name, a in o.items():
            if a.get("type") != "mesh":
                continue
            if len(a.get("vertices", [])) != len(a.get("uvs", [])):
                continue   # weighted mesh:此生成器只處理 unweighted(逐頂點 offset)
            nv = len(a["uvs"]) // 2
            setup = np.array(a["vertices"], dtype=np.float64).reshape(nv, 2)
            frames = gen_deform_timeline(setup, category, anchor, amp_frac, sway_sign)
            if frames:
                block.setdefault(slot, {})[name] = frames
    return {skin_name: block} if block else {}


if __name__ == "__main__":
    import json, sys
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/main_draw.json"
    cat = sys.argv[2] if len(sys.argv) > 2 else "loop"
    sk = json.load(open(path))
    blk = build_deform_block(sk, cat)
    skin_name = next(iter(blk))
    for slot, atts in blk[skin_name].items():
        for name, fr in atts.items():
            mags = [math.hypot(f["vertices"][0], f["vertices"][1]) for f in fr]
            print(f"{slot}/{name}: {len(fr)} frames, cat={cat}")
