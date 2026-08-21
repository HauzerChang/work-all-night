#!/usr/bin/env python3
"""P / S6 — 動畫「物理可信度」分析器 + 評估器(第一個 bounded chunk)。

研究項目(使用者新增,2026-08-21):spine 動畫中的物理世界 —— 認知材質與其運動、
物體質量/面積/空氣阻力/慣性等屬性,目標讓產出動畫更具說服力、動態更自然。

方法論(依 RULES:確定性演算法 + 評估器,不用 ML 學「無唯一解的美術決定」):
把三個抽象目標落成**可量測的運動學簽名(kinematic signatures)**,從真實生產動畫抽取,
並以負對照(把動作線性化 → 機械感)確認評估器有鑑別力。

量測的物理簽名:
  1. **timing / 慣性(ease profile)** —— 從緊湊 bezier 曲線讀「起步/收尾速度」:
     - ease_in(慢起步)↔ 質量/慣性(重物加速慢);ease_out(慢收尾)↔ 阻尼/重量(慢停)。
     - 線性曲線 = 等速 = 機械感(ease_in=ease_out=0)。→ **inertia_index** 為核心可信度分。
  2. **follow-through / overlapping(相位延遲)** —— 父骨先動、子骨(末梢)後到:
     對「父+子皆動」的骨對做活動訊號互相關,量子骨落後父骨的相位延遲(lag>0 = 物理)。
  3. **overshoot / settle(過衝回穩)** —— 末梢停止時越過終點再回彈(阻尼彈簧 = 果凍/慣性)。
  4. **squash & stretch 體積守恆** —— scale timeline 的 sx·sy 是否維持(擠壓保體積 = 有質量的軟體)。
  5. **soft-body 形變波(材質)** —— deform timeline 的逐頂點位移是否呈行進波(布料/窗簾)。

核心閘(可負對照):inertia_index。real 動畫 >> linearized(去曲線)→ discriminative。
其餘為真實資料的「物理詞彙」描述量(供後續注入能力對照),各附 sanity。
"""
import json, math, sys
import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0].replace("/analyzer", "/mesh_gen"))
from weighted_deform_eval import _sample  # bezier-aware 取樣(重用)  # noqa: E402


# ---------- 1) ease / 慣性 ----------
def _curve_end_speeds(fr):
    """回傳緊湊 bezier 在 s=0 / s=1 的正規化速度 (v_start, v_end)。
    線性/缺省 → (1,1)(等速);stepped → (0,0)(瞬時持值,視為無慣性資訊)。
    P0=(0,0) P1=(cx1,cy1) P2=(cx2,cy2) P3=(1,1);dY/dX|0 = cy1/cx1、|1 = (1-cy2)/(1-cx2)。"""
    c = fr.get("curve")
    if c == "stepped":
        return (0.0, 0.0)
    if c is None or c == "linear":
        return (1.0, 1.0)
    cx1 = c; cy1 = fr.get("c2", 0.0); cx2 = fr.get("c3", 1.0); cy2 = fr.get("c4", 1.0)
    vs = (cy1 / cx1) if cx1 > 1e-6 else 3.0
    ve = ((1 - cy2) / (1 - cx2)) if (1 - cx2) > 1e-6 else 3.0
    return (vs, ve)


def ease_profile(sk):
    """全動畫的 timing/慣性簽名。回傳 per-anim + 總結。
    inertia_index = 平均 (ease_in + ease_out)/2,ease_in=max(0,1-v_start)、ease_out=max(0,1-v_end)。
    只計「值有變化」的過渡(相鄰 keyframe 值不同),避免佔位幀稀釋。"""
    anims = sk["animations"]
    per = {}
    for an, a in anims.items():
        eins, eouts, n = [], [], 0
        for bn, tl in a.get("bones", {}).items():
            for ch, frames in tl.items():
                keys = {"rotate": ("angle",), "translate": ("x", "y"),
                        "scale": ("x", "y"), "shear": ("x", "y")}.get(ch, ("x", "y"))
                dflt = (1.0, 1.0) if ch == "scale" else tuple(0.0 for _ in keys)
                for j in range(len(frames) - 1):
                    v0 = tuple(frames[j].get(k, d) for k, d in zip(keys, dflt))
                    v1 = tuple(frames[j + 1].get(k, d) for k, d in zip(keys, dflt))
                    if all(abs(x - y) < 1e-9 for x, y in zip(v0, v1)):
                        continue  # 值沒變 → 非運動過渡
                    vs, ve = _curve_end_speeds(frames[j])
                    eins.append(max(0.0, 1.0 - vs)); eouts.append(max(0.0, 1.0 - ve)); n += 1
        if n:
            ei = float(np.mean(eins)); eo = float(np.mean(eouts))
            per[an] = {"moves": n, "ease_in": round(ei, 3), "ease_out": round(eo, 3),
                       "inertia_index": round((ei + eo) / 2, 3),
                       "linear_frac": round(sum(1 for x, y in zip(eins, eouts)
                                                if x == 0 and y == 0) / n, 3)}
    idx = [v["inertia_index"] for v in per.values()]
    return {"per_anim": per, "inertia_index_mean": round(float(np.mean(idx)), 3) if idx else 0.0}


# ---------- 訊號取樣(給 2/3 用) ----------
def bone_signal(a_bones, bn, dur, N=48):
    """回傳骨 bn 在 [0,dur] 的正規化活動訊號(每 channel 各自 range 正規後合成的 pose 向量),
    及其速度 |Δ|。用 bezier-aware _sample。"""
    tl = a_bones.get(bn, {})
    ts = np.linspace(0, dur, N)
    cols = []
    for ch, keys, dflt in (("rotate", ("angle",), (0.0,)),
                           ("translate", ("x", "y"), (0.0, 0.0)),
                           ("scale", ("x", "y"), (1.0, 1.0))):
        if ch not in tl:
            continue
        vals = np.array([_sample(tl[ch], t, keys, dflt) for t in ts], dtype=float)
        for k in range(vals.shape[1]):
            col = vals[:, k]; rng = col.max() - col.min()
            if rng > 1e-9:
                cols.append((col - col.min()) / rng)
    if not cols:
        return ts, None, None
    pose = np.stack(cols, 1)                 # (N, C)
    speed = np.linalg.norm(np.diff(pose, axis=0), axis=1)  # (N-1,)
    return ts, pose, speed


# ---------- 2) follow-through 相位延遲 ----------
def follow_through(sk, N=48):
    bones = sk["bones"]; parent = {b["name"]: b.get("parent") for b in bones}
    lags = []; details = []
    for an, a in sk["animations"].items():
        ab = a.get("bones", {})
        dur = _anim_duration(a)
        if dur <= 0:
            continue
        both = [(bn, parent[bn]) for bn in ab if parent.get(bn) in ab]
        for child, par in both:
            _, _, cs = bone_signal(ab, child, dur, N)
            _, _, ps = bone_signal(ab, par, dur, N)
            if cs is None or ps is None or cs.sum() < 1e-6 or ps.sum() < 1e-6:
                continue
            lag = _xcorr_lag(ps, cs, max_lag=N // 3)   # child 相對 parent 的落後(樣本)
            lag_s = lag * dur / N
            lags.append(lag_s); details.append((an, child, round(lag_s, 3)))
    if not lags:
        return {"pairs": 0}
    lags = np.array(lags)
    return {"pairs": len(lags),
            "mean_lag_s": round(float(lags.mean()), 4),
            "child_lags_parent_frac": round(float((lags > 0).mean()), 3),
            "median_lag_s": round(float(np.median(lags)), 4)}


def _xcorr_lag(a, b, max_lag):
    """回傳 b(child)相對 a(parent)的落後樣本數:**正 = child 落後 parent(物理 follow-through)**。
    以位移 d 對齊,尋找使 b[i]≈a[i-d] 的 d(即 child 是 parent 延遲 d)。標準化互相關。
    (經正向對照驗證:child=roll(parent,+d) → 回 +d;符號約定已校正。)"""
    a = (a - a.mean()); b = (b - b.mean())
    if a.std() < 1e-9 or b.std() < 1e-9:
        return 0
    best, bd = -2.0, 0
    for d in range(-max_lag, max_lag + 1):
        # b[i] 對齊 a[i-d]:重疊區 i∈[max(0,d), len+min(0,d))
        i0 = max(0, d); i1 = len(b) + min(0, d)
        if i1 - i0 < 4:
            continue
        x = a[i0 - d:i1 - d]; y = b[i0:i1]
        c = float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-9))
        if c > best:
            best, bd = c, d
    return bd


# ---------- 3) overshoot / settle ----------
def overshoot_rate(sk, N=64):
    hits = tot = 0
    for an, a in sk["animations"].items():
        ab = a.get("bones", {}); dur = _anim_duration(a)
        if dur <= 0:
            continue
        for bn, tl in ab.items():
            if "rotate" not in tl:
                continue
            ts = np.linspace(0, dur, N)
            ang = np.array([_sample(tl["rotate"], t, ("angle",), (0.0,))[0] for t in ts])
            if ang.max() - ang.min() < 1.0:      # 幅度太小不計
                continue
            tot += 1
            final = ang[-1]
            # 過衝:在到達 final 之前是否越過 final(相對主要運動方向)
            peak = ang.max() if ang[np.argmax(np.abs(ang - ang[0]))] > final else ang.min()
            if abs(peak - final) > 0.15 * (ang.max() - ang.min()):
                hits += 1
    return {"rotating_bones": tot, "overshoot_frac": round(hits / tot, 3) if tot else 0.0}


# ---------- 4) squash & stretch 體積守恆 ----------
def squash_stretch(sk):
    devs = []; n = 0
    for a in sk["animations"].values():
        for bn, tl in a.get("bones", {}).items():
            if "scale" not in tl:
                continue
            for fr in tl["scale"]:
                sx = fr.get("x", 1.0); sy = fr.get("y", 1.0)
                if abs(sx - 1) < 1e-6 and abs(sy - 1) < 1e-6:
                    continue
                devs.append(abs(sx * sy - 1.0)); n += 1
    if not n:
        return {"scale_keys": 0}
    return {"scale_keys": n, "mean_area_dev": round(float(np.mean(devs)), 3),
            "volume_conserving_frac": round(float(np.mean(np.array(devs) < 0.08)), 3)}


# ---------- 5) soft-body deform 行進波(材質) ----------
def soft_body_wave(sk):
    """deform timeline:量頂點位移是否隨時間『行進』(相鄰幀位移峰值位置移動)→ 布料波。"""
    out = {}
    for an, a in sk["animations"].items():
        dfm = a.get("deform")
        if not dfm:
            continue
        for skinname, slots in dfm.items():
            for slot, atts in slots.items():
                for name, frames in atts.items():
                    peaks = []
                    for fr in frames:
                        dv = fr.get("vertices", [])
                        if len(dv) < 4:
                            continue
                        mags = [math.hypot(dv[i], dv[i + 1]) for i in range(0, len(dv) - 1, 2)]
                        if max(mags) > 1e-6:
                            peaks.append(int(np.argmax(mags)))
                    if len(peaks) >= 3:
                        travel = float(np.mean(np.abs(np.diff(peaks))))
                        out.setdefault(f"{slot}/{name}", []).append((an, round(travel, 2)))
    return {"deformed_meshes": len(out),
            "detail": {k: v for k, v in list(out.items())[:6]}}


def _anim_duration(a):
    d = 0.0
    for grp in ("bones", "slots"):
        for tl in a.get(grp, {}).values():
            for frames in (tl.values() if isinstance(tl, dict) else []):
                for fr in frames:
                    d = max(d, fr.get("time", 0.0))
    for skinname, slots in (a.get("deform") or {}).items():
        for atts in slots.values():
            for frames in atts.values():
                for fr in frames:
                    d = max(d, fr.get("time", 0.0))
    return d


# ---------- 負對照:線性化 ----------
def linearize(sk):
    """去除所有 bone 曲線 → 全部等速(機械感)。用於鑑別力負對照。"""
    s = json.loads(json.dumps(sk))
    for a in s["animations"].values():
        for tl in a.get("bones", {}).values():
            for frames in tl.values():
                for fr in frames:
                    for k in ("curve", "c2", "c3", "c4"):
                        fr.pop(k, None)
    return s


def analyze(sk):
    return {
        "ease": ease_profile(sk),
        "follow_through": follow_through(sk),
        "overshoot": overshoot_rate(sk),
        "squash_stretch": squash_stretch(sk),
        "soft_body": soft_body_wave(sk),
    }


def negative_control(sk):
    real = ease_profile(sk)["inertia_index_mean"]
    lin = ease_profile(linearize(sk))["inertia_index_mean"]
    return {"real_inertia_index": real, "linearized_inertia_index": lin,
            "discriminative": real > lin + 0.02 and lin == 0.0}


def positive_control_lag():
    """follow-through 相位延遲的方向/量正確性:child = parent 延遲 d 樣本 → 應回 +d。"""
    base = np.concatenate([np.zeros(10), np.hanning(16), np.zeros(22)])
    cases = [0, 3, 6, -4, 9]
    ok = all(_xcorr_lag(base.copy(), np.roll(base, d), 15) == d for d in cases)
    return {"cases": cases, "all_recovered": ok}


def selftest(sk):
    nc = negative_control(sk)
    pc = positive_control_lag()
    return {"negative_control_ease": nc, "positive_control_lag": pc,
            "validated": nc["discriminative"] and pc["all_recovered"]}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/main_draw.json"
    sk = json.load(open(path))
    flag = sys.argv[2] if len(sys.argv) > 2 else None
    if flag == "--negctrl":
        nc = negative_control(sk)
        print(json.dumps(nc, ensure_ascii=False, indent=2))
        sys.exit(0 if nc["discriminative"] else 1)
    if flag == "--selftest":
        st = selftest(sk)
        print(json.dumps(st, ensure_ascii=False, indent=2))
        sys.exit(0 if st["validated"] else 1)
    print(json.dumps(analyze(sk), ensure_ascii=False, indent=2))
