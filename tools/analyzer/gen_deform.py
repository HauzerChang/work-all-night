#!/usr/bin/env python3
"""candidate 0e — 為 mesh 軟件(curtain / shadow / 布料等)生成 **deform timeline**(純 CPU,確定性)。

背景:`gen_animations.py`(candidate 0d)只生 bone TRS + slot color,所以 build --animate 出來的
軟件只會被父骨**剛體搬動**,不會像真實 main_draw 窗簾那樣**逐頂點變形**(9 支動畫全有 deform)。
本模組補上這個缺口:對 skin 裡的每個 mesh attachment,生成 Spine 3.8 `deform` timeline。

運動基元(motion primitive,美術手感為先驗、幾何安全性由 deform_eval 閘把關):
  **駐波微顫(standing-wave shimmer)**——沿件的短軸位移,位移量 =
      A · env(s) · sin(2π·k·s) · temporal(τ)
  其中 s = 頂點沿**長軸**的正規化座標(0..1);env(s)=(1-s)(懸掛模型:固定端 s=1 不動、
  自由端 s=0 擺最多);sin(2π k s) 給空間駐波結構;temporal(τ) 給時間相位。

  temporal(τ) 依 beat 類別:
    loop  → sin(2πτ)      # 一個完整循環,τ=0 與 τ=1 皆 =0
    其他  → sin(πτ)       # 0→peak→0 的單擺
  **關鍵:兩者在 τ=0 與 τ=1 皆回到 0 → deform 端點 == setup identity**
  → (a) loop 無縫循環;(b) 與 gen_animations 的 bone timeline 共用「setup identity 介面」,
     任意 beat 串接無跳變(對齊 candidate 0d 的 AC4)。

  A = amp_frac · 短軸 extent(預設 amp_frac=0.08;真實窗簾 deform 達 314px 仍乾淨,此值極保守)。

單位:Spine local(y-up),與 mesh setup `vertices` 同空間。輸出 sparse 格式
  {"time": t, "offset": 0, "vertices": [dx0,dy0,...]}(offset=0、全長)。
"""
import math
import numpy as np

# 與 gen_animations 對齊的 beat 時長 / 取樣(避免循環 import,重列常數)
DUR = {"intro": 0.6, "loop": 2.0, "outro": 0.4, "hold": 1.0, "pulse": 0.5}
LOOP_SAMPLES = 12


def _get_skins(skeleton):
    """回傳 [(skin_name, attachments_dict)]。相容 3.8 list 形與 build_spine 的 {name:atts} dict 形。"""
    sk = skeleton["skins"]
    out = []
    if isinstance(sk, list):
        for entry in sk:
            out.append((entry.get("name", "default"), entry.get("attachments", {})))
    elif isinstance(sk, dict):
        if "attachments" in sk:  # 單一 skin 直接帶 attachments
            out.append((sk.get("name", "default"), sk["attachments"]))
        else:                     # build_spine 形:{skin_name: {slot: {att: ...}}}
            for name, atts in sk.items():
                out.append((name, atts))
    return out


def mesh_attachments(skeleton):
    """回傳 [(skin_name, slot, att_name, setup Nx2)] —— **unweighted** mesh attachment。

    ⚠️ 只收 unweighted mesh。weighted mesh(`len(vertices) != len(uvs)`,CLAUDE.md 雷點 #6)靠**骨骼
    skinning** 驅動變形,deform 對它不是對的機制(且 setup 位置不在 `vertices` 裡而需經 bind 逆變換
    還原)。軟件(curtain/shadow/布料)本就是 unweighted mesh + deform 驅動 —— 正是本模組的標的。"""
    res = []
    for skin_name, atts in _get_skins(skeleton):
        for slot, entry in atts.items():
            for att_name, a in entry.items():
                if a.get("type") != "mesh":
                    continue
                if len(a["vertices"]) != len(a["uvs"]):   # weighted → 跳過(非 deform 機制)
                    continue
                nv = len(a["uvs"]) // 2
                setup = np.array(a["vertices"], dtype=np.float64).reshape(nv, 2)
                res.append((skin_name, slot, att_name, setup))
    return res


def _temporal(cat, tau):
    if cat == "loop":
        return math.sin(2 * math.pi * tau)
    return math.sin(math.pi * tau)


def standing_wave_offsets(setup, tau, cat, amp_frac=0.08, wavenum=1.0):
    """回傳該時刻的逐頂點位移 Nx2(local, y-up)。"""
    n = len(setup)
    ext = setup.max(0) - setup.min(0)
    long_ax = 0 if ext[0] >= ext[1] else 1
    short_ax = 1 - long_ax
    L = ext[long_ax] or 1.0
    A = amp_frac * (ext[short_ax] or 1.0)
    mn = setup.min(0)
    s = (setup[:, long_ax] - mn[long_ax]) / L        # 0..1 沿長軸
    env = 1.0 - s                                    # 懸掛:自由端(s=0)最大
    tval = _temporal(cat, tau)
    off = np.zeros((n, 2))
    off[:, short_ax] = A * env * np.sin(2 * math.pi * wavenum * s) * tval
    return off


def gen_deform_frames(setup, cat, amp_frac=0.08, wavenum=1.0):
    """回傳 Spine deform frames:[{"time","offset","vertices"}],端點強制回 identity(seamless)。"""
    dur = DUR.get(cat, DUR["loop"])
    samples = LOOP_SAMPLES if cat == "loop" else max(6, LOOP_SAMPLES // 2)
    frames = []
    for i in range(samples + 1):
        tau = i / samples
        off = standing_wave_offsets(setup, tau, cat, amp_frac, wavenum)
        frames.append([tau * dur, off])
    # 端點強制 identity(消浮點殘差,保證 seamless + identity 介面)
    frames[0][1] = np.zeros_like(frames[0][1])
    frames[-1][1] = np.zeros_like(frames[-1][1])
    out = []
    for (t, off) in frames:
        flat = off.reshape(-1)
        out.append({"time": round(float(t), 4),
                    "offset": 0,
                    "vertices": [round(float(v), 4) for v in flat]})
    return out


def add_deform_to_anim(skeleton, anim, cat, amp_frac=0.08, wavenum=1.0, only_soft=None):
    """把 deform timeline 注入 skeleton["animations"][anim]["deform"]。
    only_soft: 若給定 set(att_name),只對這些 mesh 生成(軟件語意過濾);None=全部 mesh。
    回傳注入的 (skin,slot,att) 清單。"""
    injected = []
    per_skin = {}
    for skin_name, slot, att_name, setup in mesh_attachments(skeleton):
        if only_soft is not None and att_name not in only_soft:
            continue
        frames = gen_deform_frames(setup, cat, amp_frac, wavenum)
        per_skin.setdefault(skin_name, {}).setdefault(slot, {})[att_name] = frames
        injected.append((skin_name, slot, att_name))
    if per_skin:
        a = skeleton["animations"].setdefault(anim, {})
        dfm = a.setdefault("deform", {})
        for skin_name, slots in per_skin.items():
            dst = dfm.setdefault(skin_name, {})
            for slot, atts in slots.items():
                dst.setdefault(slot, {}).update(atts)
    return injected


def beat_category(name):
    """從 gen_animations 借過來的 beat 分類(避免硬相依,重列最小版)。"""
    try:
        from gen_animations import beat_category as bc
        return bc(name)
    except Exception:
        return "loop"


def add_deform_for_beats(skeleton, amp_frac=0.08, wavenum=1.0, only_soft=None):
    """對 skeleton 既有的每個 animation(beat)依其類別注入 mesh deform。回傳摘要。"""
    summary = {}
    for anim in list(skeleton.get("animations", {}).keys()):
        cat = beat_category(anim)
        if cat == "hold":
            continue  # 定格不變形
        inj = add_deform_to_anim(skeleton, anim, cat, amp_frac, wavenum, only_soft)
        if inj:
            summary[anim] = {"category": cat, "meshes": len(inj)}
    return summary


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton_json")
    ap.add_argument("--amp-frac", type=float, default=0.08)
    ap.add_argument("--wavenum", type=float, default=1.0)
    ap.add_argument("--inplace", action="store_true")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton_json, encoding="utf-8"))
    summary = add_deform_for_beats(sk, a.amp_frac, a.wavenum)
    if a.inplace:
        json.dump(sk, open(a.skeleton_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"deform_injected": summary}, ensure_ascii=False, indent=2))
