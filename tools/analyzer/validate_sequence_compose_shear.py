#!/usr/bin/env python3
"""candidate (L-2) 自我驗收閘 — 大獎**序列組合**的 **shear 通道**覆蓋(純 CPU,確定性)。

**補的缺口(candidate L 誠實列出的 honest boundary)**:candidate (L) 的序列組合閘
`validate_sequence_compose` 證了把各 beat clip 串成單一可播放 timeline 時「接點無縫 / 回切逐幀
還原 / 簽章在序列脈絡中仍成立」—— 但它用 `spine_anim.sample()` 做接點與回切比對,而 **`sample()`
原本只取 rotate/translate/scale/alpha,不取 shear**。L 的正向序列(In→hit→combo→charge→cascade→
Loop→Out)**刻意**只用無 shear 的節拍繞過了這個盲點,並在 STATE/knowledge 裡誠實記下:
「shear beat(wobble/squash/twist)之 shear 通道不被 sample() 覆蓋」。本 run 把這條 boundary 補上:

  (1) 把 `shear` 納入 `spine_anim.sample()`(加性:per-bone 新增 shearX/shearY,預設 0 = setup identity;
      既有索引既有鍵的呼叫端逐位元不變);
  (2) 以**含 shear 的序列**(In→wobble→squash→twist→Loop→Out,三個斜拉節拍全帶 shear)把 compose
      的接點無縫 / 回切還原 / in-context 簽章在 **shear 通道上**釘回歸閘;
  (3) **crux 負對照** 直接證「擴充前真的看不見」:構造一個在 5 個非 shear 通道完全無縫、**只在 shear
      通道不連續**的接點 —— 擴充後的 shear-aware diff 正確判**非無縫**,而模擬擴充前盲點的 non-shear
      diff 卻回**無縫(殘差 0)** → 證 shear 覆蓋補掉了一個**真實**的接點盲點(非冗餘)。

**選題理由(延續 L / G-2 的整合閘精神,不選又一條參數軸)**:近期里程碑多為「單一 robot 加一軸」;
L-2 不加任何生成能力,而是把一個**已知的驗證盲點**關掉 —— 讓序列組合閘對一般仿射四自由度(含兩條
shear 軸)**全覆蓋**,而非只覆蓋 5/7 的通道。直指「compose 真能把一整櫃主秀 beat(含斜拉節拍)組成
可播放大獎序列,且無縫性被完整驗過」。

真值界定:beat **排序** 是 PROPOSAL(手感 A 類);但「接點 C0 無縫(含 shear)殘差」「回切逐幀還原
(含 shear)」「shear 阻尼振盪簽章在序列中仍成立」皆為**客觀可量測**不變量。負對照證閘有鑑別力。
從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations` 端到端,與 L / J / charge 同一 fixture。

AC(客觀、可量測):
  LS1 present + shear 真被驅動 : 含 shear 序列 compose 後為合法 Spine timeline(時間嚴格遞增、值 finite);
                               segments 覆蓋宣告序列;用到 bone 皆現身;**crux**:composed 真的保有 `shear`
                               timeline,且 ≥1 個 shear 段回切後有 bone 的 |shearX| 峰 ≥ SHEAR_MIN_PEAK
                               (確認在測真 shear,非空驗);並確認 `sample()` 現已輸出 shearX/shearY 鍵。
  LS2 crux — 接點無縫(含 shear): 含 shear 序列每個**內部接點**的 **shear-aware** 跨通道殘差 < SEAM_TOL
                               (三斜拉節拍皆首尾 shear==0 identity 介面 → 接點含 shear 仍無縫)。
  LS3 faithful concat(含 shear): 回切每一段 **逐幀** shear-aware 還原該孤立 clip(含 shearX/shearY)
                               → 殘差 < FAITH_TOL(證 compose 的時間平移 + 接點去重對 **shear 通道**亦無損)。
  LS4 in-context shear 簽章     : 從 **composed** 回切 wobble / twist 段,其 shear 阻尼振盪簽章仍成立
                               (shearX 繞 0 變號 ≥3 且相繼極值遞減)且 twist 兩軸反相(極值處 shearX·shearY<0);
                               且 in-context shearX 序列 == 孤立 clip(純平移無扭曲)。
  LS5 crux — 盲點負對照        : 構造「非 shear 通道全無縫、只 shear 不連續」的接點(wobble 尾 shearX=0 →
                               合成 held clip 首 shearX=HELD_SHEAR):
                               (a) shear-aware diff > NEG_MULT×SEAM_TOL(擴充後正確判非無縫)且肇因接點指認正確;
                               (b) **crux** 模擬擴充前盲點的 non-shear diff < SEAM_TOL(擴充前會誤判無縫)
                                   → 證 shear 覆蓋補掉**真實**盲點;
                               (c) 守衛:純 identity(零 shear)合成接點在 shear-aware diff 下仍 ~0
                                   (shear 覆蓋不會把真無縫接點誤判成不連續)。

用法:
  python3 validate_sequence_compose_shear.py            # 摘要
  python3 validate_sequence_compose_shear.py --json     # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze
from validate_shear_gen import _sign_changes_zero, _extrema_mags_decreasing

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"

# shear-aware setup identity(7 自由度:L 的 5 + shearX/shearY)
IDENT_FULL = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0,
              "shearX": 0.0, "shearY": 0.0}
# 模擬 candidate L 擴充前的「盲點」diff —— 只看 5 個非 shear 通道
IDENT_NONSHEAR = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}

SEAM_TOL = 1e-3      # 接點 C0 殘差上限(identity==identity 實測 ~0)
FAITH_TOL = 1e-4     # 回切還原殘差上限(純平移)
NEG_MULT = 10.0      # 負對照接點殘差須 > NEG_MULT × SEAM_TOL
SHEAR_MIN_PEAK = 5.0 # LS1:至少一個 shear 段的 |shearX| 峰須 ≥ 此(確認在測真 shear)
HELD_SHEAR = 12.0    # LS5:合成 held clip 的首幀 shearX(只在 shear 通道製造不連續)
N = 48               # 回切取樣密度

# 含 shear 的正向序列:三個斜拉節拍 wobble/squash/twist 全帶 shear,皆 identity 介面。
SHEAR_ORDER = ["In", "wobble", "squash", "twist", "Loop", "Out"]
SHEAR_BEATS = ("wobble", "squash", "twist")


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/seq_compose_shear_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


# ---------------- 量測器 ----------------
def _state_diff(s1, s2, ident):
    """兩個 sample() 狀態的跨 bone/slot 最大絕對差(缺席通道視為 setup identity)。
    `ident` 決定比對哪些通道 —— IDENT_FULL(含 shear)或 IDENT_NONSHEAR(模擬 L 擴充前盲點)。"""
    m = 0.0
    for b in set(s1["bones"]) | set(s2["bones"]):
        d1 = s1["bones"].get(b, ident)
        d2 = s2["bones"].get(b, ident)
        for k in ident:
            m = max(m, abs(d1.get(k, ident[k]) - d2.get(k, ident[k])))
    for s in set(s1["slots"]) | set(s2["slots"]):
        a1 = s1["slots"].get(s, {"alpha": 1.0})["alpha"]
        a2 = s2["slots"].get(s, {"alpha": 1.0})["alpha"]
        m = max(m, abs(a1 - a2))
    return m


def _junction_seams(anims, order, ident):
    seams = []
    for i in range(len(order) - 1):
        a, b = anims[order[i]], anims[order[i + 1]]
        end = SA.sample(a, SA.duration(a))
        start = SA.sample(b, 0.0)
        seams.append({"pair": "{}->{}".format(order[i], order[i + 1]),
                      "seam": round(_state_diff(end, start, ident), 6)})
    return seams


def _seg_shearx_series(composed, bone, start, dur, n=N):
    return [SA.sample(composed, start + dur * i / n)["bones"].get(bone, {}).get("shearX", 0.0)
            for i in range(n + 1)]


def _seg_shear_pair(composed, bone, start, dur, n=N):
    out = []
    for i in range(n + 1):
        bd = SA.sample(composed, start + dur * i / n)["bones"].get(bone, {})
        out.append((bd.get("shearX", 0.0), bd.get("shearY", 0.0)))
    return out


def _clip_shearx_series(clip, bone, n=N):
    dur = SA.duration(clip)
    return [SA.sample(clip, dur * i / n)["bones"].get(bone, {}).get("shearX", 0.0)
            for i in range(n + 1)]


def _signed_extrema(vals, dead=1e-6):
    """從**稠密取樣**序列抽出局部極值(帶號)值序列 —— 等同 validate_shear_gen 對**關鍵幀**取
    `_shear_x` 後的極值序列(稠密取樣下不能直接套 `_extrema_mags_decreasing`,先抽極值)。
    局部極值 = 比左右相鄰都 ≥(極大)或都 ≤(極小)且至少一側嚴格,|v|>dead。"""
    out = []
    for i in range(1, len(vals) - 1):
        a, b, c = vals[i - 1], vals[i], vals[i + 1]
        is_max = b >= a and b >= c and (b > a or b > c)
        is_min = b <= a and b <= c and (b < a or b < c)
        if (is_max or is_min) and abs(b) > dead:
            out.append(b)
    return out


def _shear_bone(clip):
    """clip 中第一個帶 shear timeline 的 bone(無則 None)。"""
    for bone, chans in clip.get("bones", {}).items():
        if "shear" in chans:
            return bone
    return None


def _well_formed(composed):
    for group in ("bones", "slots"):
        for chans in composed.get(group, {}).values():
            for frames in chans.values():
                last = None
                for f in frames:
                    t = f.get("time")
                    if t is None or not math.isfinite(t):
                        return False
                    if last is not None and not (t > last):
                        return False
                    last = t
                    for k, val in f.items():
                        if k == "time":
                            continue
                        if isinstance(val, (int, float)) and not math.isfinite(val):
                            return False
    return True


def _held_shear_clip(bone):
    """合成負對照 clip:僅一條 shear timeline,首幀 shearX=HELD_SHEAR(其餘通道皆 identity)。
    放在 wobble(尾 shearX=0,其餘 identity)之後 → 接點**只在 shear 通道**不連續。"""
    return {"bones": {bone: {"shear": [
        {"time": 0.0, "x": HELD_SHEAR, "y": 0.0},
        {"time": 0.2, "x": HELD_SHEAR, "y": 0.0}]}}}


def _ident_clip(bone):
    """合成純 identity clip(shear 全 0)—— LS5c 守衛:真無縫接點不該被 shear-aware diff 誤判。"""
    return {"bones": {bone: {"shear": [
        {"time": 0.0, "x": 0.0, "y": 0.0},
        {"time": 0.2, "x": 0.0, "y": 0.0}]}}}


# ---------------- AC ----------------
def ac_LS1(anims):
    composed, segs = G.compose_sequence(anims, SHEAR_ORDER)
    wf = _well_formed(composed)
    covers = [s["beat"] for s in segs] == SHEAR_ORDER
    used = set()
    for nm in SHEAR_ORDER:
        used |= set(anims[nm].get("bones", {}).keys())
    present = used <= set(composed.get("bones", {}).keys())
    # crux:composed 保有 shear timeline + sample() 現已輸出 shearX/shearY
    has_shear_tl = any("shear" in ch for ch in composed.get("bones", {}).values())
    probe_keys = set(SA.sample(composed, 0.0)["bones"].get(next(iter(composed["bones"])), {}).keys())
    sample_has_shear = {"shearX", "shearY"} <= probe_keys
    # crux:≥1 shear 段回切後真有 shear 峰
    seg_of = {s["beat"]: s for s in segs}
    peaks = {}
    for beat in SHEAR_BEATS:
        bone = _shear_bone(anims[beat])
        if bone is None:
            continue
        s = seg_of[beat]
        vs = _seg_shearx_series(composed, bone, s["start"], s["dur"])
        peaks[beat] = round(max(abs(v) for v in vs), 4)
    shear_driven = any(p >= SHEAR_MIN_PEAK for p in peaks.values())
    ok = wf and covers and present and has_shear_tl and sample_has_shear and shear_driven
    return {"pass": bool(ok), "well_formed": wf, "covers_order": covers,
            "all_bones_present": present, "composed_has_shear_timeline": has_shear_tl,
            "sample_exposes_shear": sample_has_shear, "seg_shearX_peaks": peaks,
            "shear_min_peak": SHEAR_MIN_PEAK}


def ac_LS2(anims):
    seams = _junction_seams(anims, SHEAR_ORDER, IDENT_FULL)
    worst = max((s["seam"] for s in seams), default=0.0)
    ok = worst < SEAM_TOL
    return {"pass": bool(ok), "worst_seam_full": worst, "tol": SEAM_TOL, "seams": seams}


def ac_LS3(anims):
    composed, segs = G.compose_sequence(anims, SHEAR_ORDER)
    worst = 0.0
    worst_at = None
    for s in segs:
        clip = anims[s["beat"]]
        dur = s["dur"]
        grid = 24
        for i in range(grid + 1):
            t = dur * i / grid
            d = _state_diff(SA.sample(composed, s["start"] + t), SA.sample(clip, t), IDENT_FULL)
            if d > worst:
                worst, worst_at = d, {"beat": s["beat"], "t": round(t, 4)}
    ok = worst < FAITH_TOL
    return {"pass": bool(ok), "worst_residual_full": round(worst, 9),
            "worst_at": worst_at, "tol": FAITH_TOL}


def _shear_sig_in_context(composed, seg, clip):
    bone = _shear_bone(clip)
    if bone is None:
        return {"pass": False, "reason": "no shear bone"}
    vs_ctx = _seg_shearx_series(composed, bone, seg["start"], seg["dur"])
    vs_iso = _clip_shearx_series(clip, bone)
    ext_ctx = _signed_extrema(vs_ctx)          # 從稠密序列抽局部極值,才能套阻尼判準
    nsc = _sign_changes_zero(ext_ctx)
    damp = _extrema_mags_decreasing(ext_ctx)
    match = len(vs_ctx) == len(vs_iso) and all(abs(a - c) <= 1e-4 for a, c in zip(vs_ctx, vs_iso))
    sig = nsc >= 3 and damp
    return {"pass": bool(sig and match), "bone": bone, "n_sign_changes": nsc,
            "n_extrema": len(ext_ctx), "damped": bool(damp), "match_isolated": bool(match)}


def ac_LS4(anims):
    composed, segs = G.compose_sequence(anims, SHEAR_ORDER)
    seg_of = {s["beat"]: s for s in segs}
    res = {}
    res["wobble"] = _shear_sig_in_context(composed, seg_of["wobble"], anims["wobble"])
    res["twist"] = _shear_sig_in_context(composed, seg_of["twist"], anims["twist"])
    # twist crux:兩軸反相(極值處 shearX·shearY<0)在序列脈絡中仍成立
    bone = _shear_bone(anims["twist"])
    pair = _seg_shear_pair(composed, bone, seg_of["twist"]["start"], seg_of["twist"]["dur"])
    # 取 |shearX| 的局部峰處檢反相
    antiphase = 0
    checked = 0
    for i in range(1, len(pair) - 1):
        sx = pair[i][0]
        if abs(sx) > 1.0 and abs(sx) >= abs(pair[i - 1][0]) and abs(sx) >= abs(pair[i + 1][0]):
            checked += 1
            if sx * pair[i][1] < 0:
                antiphase += 1
    twist_antiphase = checked > 0 and antiphase == checked
    res["twist_antiphase_in_context"] = {"pass": bool(twist_antiphase),
                                         "extrema_checked": checked, "antiphase": antiphase}
    ok = res["wobble"]["pass"] and res["twist"]["pass"] and twist_antiphase
    return {"pass": bool(ok), **res}


def ac_LS5(anims):
    bone = _shear_bone(anims["wobble"])
    # (a)+(b):wobble(尾 shearX=0,其餘 identity) → held(首 shearX=HELD_SHEAR,其餘 identity)
    anims2 = dict(anims)
    anims2["__held"] = _held_shear_clip(bone)
    order = ["wobble", "__held"]
    seams_full = _junction_seams(anims2, order, IDENT_FULL)
    seams_non = _junction_seams(anims2, order, IDENT_NONSHEAR)
    worst_full = max(s["seam"] for s in seams_full)
    worst_non = max(s["seam"] for s in seams_non)
    off_full = max(seams_full, key=lambda s: s["seam"])["pair"]
    a_ok = (worst_full > NEG_MULT * SEAM_TOL) and off_full == "wobble->__held"
    b_ok = worst_non < SEAM_TOL   # crux:擴充前盲點會誤判無縫
    # (c)守衛:純 identity 合成接點在 shear-aware diff 下仍 ~0
    anims3 = dict(anims)
    anims3["__ident"] = _ident_clip(bone)
    seams_id = _junction_seams(anims3, ["wobble", "__ident"], IDENT_FULL)
    worst_id = max(s["seam"] for s in seams_id)
    c_ok = worst_id < SEAM_TOL
    ok = a_ok and b_ok and c_ok
    return {"pass": bool(ok),
            "a_shear_discontinuity_caught": {"pass": bool(a_ok),
                "worst_seam_full": round(worst_full, 4), "offender": off_full},
            "b_blindspot_without_shear": {"pass": bool(b_ok),
                "worst_seam_nonshear": round(worst_non, 6),
                "note": "擴充前(non-shear diff)誤判無縫 → shear 覆蓋補掉真實盲點"},
            "c_true_seamless_not_flagged": {"pass": bool(c_ok),
                "worst_seam_full": round(worst_id, 6)}}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    missing = [nm for nm in set(SHEAR_ORDER) if nm not in anims]
    if missing:
        return {"overall_pass": False, "error": "missing beats in fixture: {}".format(missing),
                "available": sorted(anims.keys())}
    results = {"LS1_present_shear_driven": ac_LS1(anims),
               "LS2_crux_seamless_full": ac_LS2(anims),
               "LS3_faithful_concat_full": ac_LS3(anims),
               "LS4_incontext_shear_sig": ac_LS4(anims),
               "LS5_crux_blindspot_neg": ac_LS5(anims)}
    results["overall_pass"] = all(v["pass"] for v in results.values())
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    res = run()
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print("candidate (L-2) 序列組合 shear 通道覆蓋閘 — compose_sequence + sample(shear)")
        print("序列:", " -> ".join(SHEAR_ORDER))
        for k in ["LS1_present_shear_driven", "LS2_crux_seamless_full",
                  "LS3_faithful_concat_full", "LS4_incontext_shear_sig",
                  "LS5_crux_blindspot_neg"]:
            v = res.get(k, {})
            print("  {:28s} {}".format(k, "PASS" if v.get("pass") else "FAIL"))
        if "LS1_present_shear_driven" in res:
            print("    LS1 seg shearX peaks:", res["LS1_present_shear_driven"].get("seg_shearX_peaks"))
        if "LS2_crux_seamless_full" in res:
            print("    LS2 worst seam (shear-aware): {:.2e} (tol {:.0e})".format(
                res["LS2_crux_seamless_full"]["worst_seam_full"], SEAM_TOL))
        if "LS3_faithful_concat_full" in res:
            print("    LS3 worst回切殘差(含 shear): {:.2e}".format(
                res["LS3_faithful_concat_full"]["worst_residual_full"]))
        if "LS5_crux_blindspot_neg" in res:
            n = res["LS5_crux_blindspot_neg"]
            print("    LS5a shear 不連續 seam (shear-aware): {}".format(
                n["a_shear_discontinuity_caught"]["worst_seam_full"]))
            print("    LS5b 同接點 non-shear seam (擴充前盲點): {}".format(
                n["b_blindspot_without_shear"]["worst_seam_nonshear"]))
        print("OVERALL:", "PASS" if res.get("overall_pass") else "FAIL")
    return 0 if res.get("overall_pass") else 1


if __name__ == "__main__":
    sys.exit(main())
