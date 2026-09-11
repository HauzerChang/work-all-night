#!/usr/bin/env python3
"""candidate (G-4'''') 自我驗收閘 — squash & stretch:**體積守恆的耦合非均勻 scale**(純 CPU)。

至此運動基元庫的所有 beat 的 scale 皆 **x==y**(等比縮放:gen_hit/combo/cascade/pulse/loop…),
**12 條動畫原理之首 squash & stretch 完全缺席**。本次 (G-4'''') 補上 `gen_squash`:以「拉伸因子」λ(τ)
繞 1 阻尼振盪驅動,每幀 **sy=λ(拉伸軸)、sx=1/λ(壓扁軸)** → **sx·sy≡1(面積/體積守恆)**。這是**第一個
產出耦合非均勻 scale**(sx≠sy)且帶**可量化不變量**的節拍。

真值界定同 (E/H/I/J/G-4'…):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章 + 不變量非美感**;
用負對照證鑑別力。**關鍵鑑別點:非均勻 ≠ 體積守恆** —— 天真「只拉伸不壓扁」(sy=λ,sx=1)也非均勻,
但面積=λ≠1 → 負對照證閘測的是**耦合不變量**非「有非均勻 scale 即可」。從**先驗庫** → **真實
build_spine robot 骨架** → `build_animations` 端到端量,與 wobble/tier 系列同一 fixture。

AC(客觀、可量測):
  Q1 present + additive : `squash` beat 產出、finite、每 bone 皆有 scale 通道;**不產** `squash__{tier}`
                          變體(squash ∉ MAIN_SHOW_CATS,honest boundary:tier 幅度變體暫未接);且加入
                          squash 先驗後**其餘 beat 逐位元不變**(additive,含 tier 變體)。
  Q2 crux — vol preserve: squash 每個 scale 關鍵幀 |sx·sy−1| ≤ 1e-3(**面積/體積守恆不變量**)。
                          另**報告**(不 gate)關鍵幀間線性內插的取樣面積偏差(誠實:線性內插不保 1/λ 凸性)。
  Q3 squash signature   : 每 bone (a)命中幀**耦合非均勻**(sx<1<sy 且 |sx−sy|≥0.2);(b)**anticipation**
                          (命中前 ∃ sy<1 壓扁);(c)**阻尼 settle**((sy−1) 繞 0 變號≥3、命中為全域最大幅度、
                          命中後相繼極值嚴格遞減);(d)首尾 **identity**(sx=sy=1)。
  Q4 isolation          : 耦合非均勻 scale **只在 squash**:其餘所有 base beat 的 scale 關鍵幀恆 sx==sy;
                          且 squash bone **只帶 scale**(無 shear/rotate/translate/color)→ 基元孤立可辨。
  Q5 neg-control        : (a) x==y 等比 beat(真實 `hit`)→ **各向異性 FALSE**(證非均勻非恆真);
                          (b) **天真只拉伸不壓扁**(sy=λ,sx=1)→ 各向異性 TRUE 但**體積守恆 FALSE**
                          (crux 鑑別:證 Q2 測不變量非「有非均勻即可」);
                          (c) **等比拉伸**(sx==sy==λ)→ 各向異性 FALSE 且體積守恆 FALSE。

用法:
  python3 validate_squash.py            # 摘要
  python3 validate_squash.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
VOL_EPS = 1e-3      # 關鍵幀體積守恆容差
NONUNIF_MIN = 0.2   # 命中幀 |sx−sy| 最小分離(耦合非均勻)
DEAD = 1e-6


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/squash_skel_val"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _sq_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "squash"]


# ---- scale-timeline 判準(可用於真實 bone 或合成負對照)----
def _sxy(ch):
    """bone timeline → [(sx, sy), …] scale 關鍵幀(無 scale 通道回 [])。"""
    return [(f["x"], f["y"]) for f in ch.get("scale", [])]


def vol_ok(pairs, eps=VOL_EPS):
    """每幀 |sx·sy − 1| ≤ eps。"""
    return bool(pairs) and all(abs(sx * sy - 1.0) <= eps for (sx, sy) in pairs)


def max_vol_dev(pairs):
    return max((abs(sx * sy - 1.0) for (sx, sy) in pairs), default=0.0)


def _impact_idx(pairs):
    """命中幀 = |sy−1| 最大處。"""
    return max(range(len(pairs)), key=lambda i: abs(pairs[i][1] - 1.0))


def anisotropic_at_impact(pairs):
    """命中幀各向異性:sx ≠ sy。"""
    if not pairs:
        return False
    sx, sy = pairs[_impact_idx(pairs)]
    return abs(sx - sy) > 1e-6


def coupled_at_impact(pairs):
    """命中幀**耦合非均勻**:sx<1<sy 且 |sx−sy| ≥ NONUNIF_MIN(縱拉橫壓)。"""
    if not pairs:
        return False
    sx, sy = pairs[_impact_idx(pairs)]
    return sx < 1.0 and sy > 1.0 and abs(sx - sy) >= NONUNIF_MIN


def has_anticipation(pairs):
    """命中前 ∃ 關鍵幀 sy<1(壓扁蓄力,與命中拉伸反向)。"""
    if not pairs:
        return False
    imp = _impact_idx(pairs)
    return any(pairs[i][1] < 1.0 - DEAD for i in range(imp))


def damped_settle(pairs):
    """(sy−1) 繞 0 變號≥3、命中為全域最大幅度、命中後相繼極值嚴格遞減。"""
    if not pairs:
        return False
    d = [sy - 1.0 for (_, sy) in pairs]
    nz = [v for v in d if abs(v) > DEAD]
    sign_changes = sum(1 for i in range(len(nz) - 1) if nz[i] * nz[i + 1] < 0)
    imp = max(range(len(d)), key=lambda i: abs(d[i]))
    is_global_max = all(abs(d[imp]) >= abs(v) - DEAD for v in d)
    post = [abs(d[i]) for i in range(imp + 1, len(d)) if abs(d[i]) > DEAD]
    decreasing = all(post[i] > post[i + 1] for i in range(len(post) - 1))
    return sign_changes >= 3 and is_global_max and decreasing


def ends_identity(pairs):
    if not pairs:
        return False
    return (abs(pairs[0][0] - 1.0) < DEAD and abs(pairs[0][1] - 1.0) < DEAD
            and abs(pairs[-1][0] - 1.0) < DEAD and abs(pairs[-1][1] - 1.0) < DEAD)


def _sampled_vol_dev(anim, nsteps=40):
    """關鍵幀**間**線性內插的取樣面積偏差(誠實報告;不 gate —— 線性內插不保 1/λ 凸性)。"""
    dur = SA.duration(anim)
    worst = 0.0
    for k in range(nsteps + 1):
        t = dur * k / nsteps
        s = SA.sample(anim, t)
        for d in s["bones"].values():
            worst = max(worst, abs(d["scaleX"] * d["scaleY"] - 1.0))
    return worst


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)

    full = G.build_animations(skel, sb, tier_gains=gains)
    sq_beats = _sq_beats(full)
    R = {}

    # ---- Q1 present + additive ----
    q1 = {"squash_beats": sq_beats, "not_finite": [], "no_scale_bone": [], "tier_variants": [],
          "non_additive": []}
    for sq in sq_beats:
        an = full[sq]
        if not SA.all_finite(an):
            q1["not_finite"].append(sq)
        for bn, ch in an.get("bones", {}).items():
            if not ch.get("scale"):
                q1["no_scale_bone"].append("{}::{}".format(sq, bn))
    q1["tier_variants"] = [k for k in full if k.startswith(tuple(s + "__" for s in sq_beats))]
    # additive:移除 squash 先驗 beat → 其餘 beat 逐位元不變
    import copy
    sb_wo = copy.deepcopy(sb)
    sb_wo["beats"] = [b for b in sb_wo["beats"] if b["beat"] not in sq_beats]
    full_wo = G.build_animations(skel, sb_wo, tier_gains=gains)
    for k, v in full_wo.items():
        if json.dumps(v, sort_keys=True) != json.dumps(full.get(k), sort_keys=True):
            q1["non_additive"].append(k)
    q1_pass = (bool(sq_beats) and not q1["not_finite"] and not q1["no_scale_bone"]
               and not q1["tier_variants"] and not q1["non_additive"])
    R["Q1_present_additive"] = {**q1, "pass": q1_pass}

    # ---- Q2 crux: volume preservation ----
    q2 = {"kf_max_dev": {}, "kf_fail": [], "sampled_max_dev": {}}
    for sq in sq_beats:
        an = full[sq]
        worst_kf = 0.0
        for bn, ch in an.get("bones", {}).items():
            pairs = _sxy(ch)
            if not vol_ok(pairs):
                q2["kf_fail"].append("{}::{}".format(sq, bn))
            worst_kf = max(worst_kf, max_vol_dev(pairs))
        q2["kf_max_dev"][sq] = round(worst_kf, 6)
        q2["sampled_max_dev"][sq] = round(_sampled_vol_dev(an), 4)  # 誠實報告(不 gate)
    q2_pass = bool(sq_beats) and not q2["kf_fail"]
    R["Q2_volume_preserved"] = {"vol_eps": VOL_EPS, **q2, "pass": q2_pass}

    # ---- Q3 squash-stretch signature ----
    q3 = {"not_coupled": [], "no_anticipation": [], "not_damped": [], "bad_ends": [], "detail": {}}
    for sq in sq_beats:
        for bn, ch in full[sq].get("bones", {}).items():
            pairs = _sxy(ch)
            key = "{}::{}".format(sq, bn)
            c = coupled_at_impact(pairs); a = has_anticipation(pairs)
            d = damped_settle(pairs); e = ends_identity(pairs)
            q3["detail"][key] = {"coupled": c, "anticipation": a, "damped": d, "ends_id": e}
            if not c:
                q3["not_coupled"].append(key)
            if not a:
                q3["no_anticipation"].append(key)
            if not d:
                q3["not_damped"].append(key)
            if not e:
                q3["bad_ends"].append(key)
    q3_pass = (bool(q3["detail"]) and not q3["not_coupled"] and not q3["no_anticipation"]
               and not q3["not_damped"] and not q3["bad_ends"])
    R["Q3_signature"] = {**q3, "pass": q3_pass}

    # ---- Q4 isolation ----
    q4 = {"nonuniform_leak": [], "extra_channel": []}
    # (a) 其餘 base beat 的 scale 恆 sx==sy(耦合非均勻不外洩)
    for nm in full:
        if "__" in nm or nm in sq_beats:
            continue
        for bn, ch in full[nm].get("bones", {}).items():
            for (sx, sy) in _sxy(ch):
                if abs(sx - sy) > 1e-6:
                    q4["nonuniform_leak"].append("{}::{}".format(nm, bn))
                    break
    # (b) squash bone 只帶 scale(無 shear/rotate/translate);slots 無 color
    for sq in sq_beats:
        for bn, ch in full[sq].get("bones", {}).items():
            extra = [c for c in ch if c != "scale"]
            if extra:
                q4["extra_channel"].append("{}::{}::{}".format(sq, bn, extra))
        if full[sq].get("slots"):
            q4["extra_channel"].append("{}::slots".format(sq))
    q4_pass = not q4["nonuniform_leak"] and not q4["extra_channel"]
    R["Q4_isolation"] = {**q4, "pass": q4_pass}

    # ---- Q5 negative controls ----
    q5 = {}
    # (a) 真實 x==y 等比 beat(hit)→ 各向異性 FALSE
    hit = full.get("hit") or full.get("burst")
    hit_pairs = []
    for ch in (hit.get("bones", {}) if hit else {}).values():
        p = _sxy(ch)
        if p:
            hit_pairs = p; break
    a_aniso = anisotropic_at_impact(hit_pairs)
    q5["a_equal_scale_beat"] = {"beat": "hit", "anisotropic": a_aniso, "pass": (not a_aniso) and bool(hit_pairs)}
    # (b) 天真只拉伸不壓扁(sy=λ, sx=1)→ 各向異性 TRUE 但體積守恆 FALSE(crux 鑑別)
    lam = [1.0, 0.88, 1.30, 0.93, 1.06, 0.985, 1.0]
    naive = [(1.0, round(v, 4)) for v in lam]
    b_aniso = anisotropic_at_impact(naive); b_vol = vol_ok(naive)
    q5["b_naive_stretch"] = {"anisotropic": b_aniso, "vol_ok": b_vol,
                             "vol_dev_at_impact": round(max_vol_dev(naive), 4),
                             "pass": b_aniso and (not b_vol)}
    # (c) 等比拉伸(sx==sy==λ)→ 各向異性 FALSE 且體積守恆 FALSE
    uni = [(round(v, 4), round(v, 4)) for v in lam]
    c_aniso = anisotropic_at_impact(uni); c_vol = vol_ok(uni)
    q5["c_uniform_stretch"] = {"anisotropic": c_aniso, "vol_ok": c_vol,
                               "pass": (not c_aniso) and (not c_vol)}
    R["Q5_neg_control"] = {**q5, "pass": all(v["pass"] for v in q5.values())}

    R["OVERALL_PASS"] = all(R[k]["pass"] for k in R)
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    R = run()
    if a.json:
        print(json.dumps(R, ensure_ascii=False, indent=2))
    else:
        for k in ["Q1_present_additive", "Q2_volume_preserved", "Q3_signature",
                  "Q4_isolation", "Q5_neg_control"]:
            print("{:26s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("Q2 keyframe max |sx·sy−1|:", R["Q2_volume_preserved"]["kf_max_dev"],
              " sampled(inter-kf, honest):", R["Q2_volume_preserved"]["sampled_max_dev"])
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
