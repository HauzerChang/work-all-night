#!/usr/bin/env python3
"""candidate (M) 自我驗收閘 — 大獎序列**序列化成可載入資產**的 round-trip(純 CPU,確定性)。

**補的缺口(「X 就緒 ≠ 產線成立」在序列化層的實例)**:candidate (L) 的 `compose_sequence` docstring 一路
宣稱其輸出「可直接塞進 `skeleton["animations"][序列名]`」、是「一段真正可**載入/播放**的大獎序列」—— 但在此
之前**沒有任何產線路徑**把它寫進真實 skeleton.json,也**沒有任何閘**驗過「序列化(json.dump round 到產檔精度)
→ 重新載入 後,這支**單一**合成 timeline 仍是**結構合法、可被 Spine 3.8 載入、且逐幀還原**的 animation」。
`validate_build` 只驗 setup pose 的**靜態**幾何/atlas 編碼,**從不碰 animation**。本次把這條 boundary 關掉:
新增 `gen_animations.emit_sequence_animation`(把合成序列實際加進 skeleton 的 animations,additive)+
`forward_sequence_order`(正向播放順序 PROPOSAL),並以本閘從**先驗庫 → 真實 build_spine robot 骨架 →
build_animations → emit → json.dump → 重載**端到端把 round-trip 保真 + Spine 3.8 結構合法性釘回歸閘。

**crux / 本 run 的核心**:
  ① 合成序列是**多個 beat 的時間平移 + 接點去重**後的**單一** timeline —— Spine 3.8 的 `SkeletonJson` 對每條
     timeline 要求**時間嚴格遞增**;合成/去重 + `_shift_frames` 的 6 位 round **第一次**在序列化形態下被檢驗
     (M3:重載後每通道嚴格遞增、finite、緊湊 bezier 散鍵與 color 8-hex 皆存活)。
  ② round-trip 保真要證**嚴格相等(max diff == 0)**而非「< tol」—— Python json 以 repr 寫浮點可逐位元還原,
     但這是**宣稱**,M2 以密集取樣 + 逐段回切證實(並由 M5c 擾動對照證「0 是有意義的、比較器非空驗」)。

**選題理由(不選又一條參數軸)**:延續 (L)/(L-2)/(L-3)/(L-4) 刻意選**整合 / 組合閘**,直指 north star
「產出**可載入 Spine** 的大獎序列動畫」—— 把 compose 從「in-memory 量測對象」推成「真實可載入資產」。

真值界定:正向播放**順序**屬美術手感(A 類,identity-介面 beat 可自由排序,見 L5c);但「序列化 round-trip
逐幀還原」「重載後每通道時間嚴格遞增(Spine 載入前提)」「回切逐段還原孤立 beat」皆為**客觀可量測**不變量。
負對照(① 注入非嚴格遞增通道 → M3 檢查器抓出 ② emit 覆蓋既有 beat / order 含未知 beat → 拒絕 ③ 擾動一值 →
round-trip 比較器偵測得到)證閘有鑑別力、非空驗。

AC(客觀、可量測):
  M1 present+emission additive : `emit_sequence_animation` 就地加入 "BigWin";與各獨立 beat **並存**且
                                 各既有 beat 逐位元不變(emission 純 additive、不動既有值);BigWin 非空、
                                 用到的 bone 皆在 skeleton;segments 覆蓋 order;總時長==末段 start+dur。
  M2 crux round-trip fidelity  : 整份 skeleton 以 build_spine 同參數 json.dump → 重載;重載的 "BigWin" 在
                                 [0,dur] 密集取樣 + 各段邊界取樣,與 in-memory 合成 `sample()` **max diff==0**
                                 → 證序列化對合成 timeline **無損**(可載入資產逐幀==設計)。
  M3 crux Spine3.8 struct ok   : 重載的 "BigWin" 每條 (bone/slot,channel) timeline **時間嚴格遞增**
                                 (Spine SkeletonJson 硬性要求;合成/去重+6 位 round 後首次在序列化形態檢驗)、
                                 全部 time/value finite、**≥1** 緊湊 bezier 散鍵 {"curve":..,c2,c3,c4} 存活
                                 (非空驗:序列真帶緩動)、**≥1** color 8-hex 存活。
  M4 faithful concat (reloaded): 從**重載的** "BigWin" 逐段回切(時間減 offset),每段逐幀還原**孤立 beat** 的
                                 `sample()`(殘差 ≤ CONCAT_TOL)→ 證序列化 + compose 平移/去重對各段**無損**;
                                 每內部接點 C0(前段尾==後段首,殘差 ≤ SEAM_TOL);重載 duration==in-mem==末段。
  M5 neg-control + guards      : (a) **crux**:把重載序列的某通道注入非嚴格遞增幀(等時間 / 遞減)→ 結構檢查器
                                 回報 non-strict(證 M3 非空驗、真能擋下 Spine 載不進的 timeline);
                                 (b) emit 覆蓋既有 beat 名(如 "Loop")→ ValueError;order 含未知 beat → KeyError;
                                 (c) 擾動重載序列的某一值 → round-trip max diff > 0(證 M2 的 0 是有意義的、
                                 比較器對差異有鑑別力)。

用法:
  python3 validate_sequence_build.py            # 摘要
  python3 validate_sequence_build.py --json     # 完整 JSON
"""
import argparse, copy, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
SEQ_NAME = "BigWin"

CONCAT_TOL = 1e-4     # 回切逐幀還原孤立 beat 的殘差上限(純平移/去重應 0)
SEAM_TOL = 1e-3       # 內部接點 C0 殘差上限(identity-介面正向序列應 ~0)
NSAMP = 400           # round-trip 密集取樣點數


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/seq_build_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


# ---------------- 結構檢查器(可重用;M3 與 M5a 共用) ----------------
def _nonstrict_channels(anim):
    """回傳所有「時間非嚴格遞增」的 (group,part,channel,t_prev,t_next);空 list = 合法可載入。"""
    bad = []
    for grp in ("bones", "slots"):
        for part, chans in anim.get(grp, {}).items():
            for ch, frames in chans.items():
                ts = [f.get("time", 0.0) for f in frames]
                for a, b in zip(ts, ts[1:]):
                    if not (b > a):
                        bad.append([grp, part, ch, a, b])
    return bad


def _all_finite(anim):
    for grp in ("bones", "slots"):
        for chans in anim.get(grp, {}).values():
            for frames in chans.values():
                for f in frames:
                    for k, v in f.items():
                        if isinstance(v, (int, float)) and not math.isfinite(v):
                            return False
    return True


def _count_bezier_color(anim):
    nbez = ncolor = 0
    for chans in anim.get("bones", {}).values():
        for frames in chans.values():
            for f in frames:
                if isinstance(f.get("curve"), (int, float)):
                    nbez += 1
    for chans in anim.get("slots", {}).values():
        for f in chans.get("color", []):
            if isinstance(f.get("color"), str) and len(f["color"]) >= 8:
                ncolor += 1
    return nbez, ncolor


def _serialize_reload(skeleton):
    """整份 skeleton 以 build_spine 同參數(ensure_ascii=False, indent=1)序列化→重載,回傳重載的 skeleton。"""
    path = "/tmp/seq_build_skel/skeleton_seq.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(skeleton, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return json.load(open(path, encoding="utf-8"))


def _max_sample_diff(a0, a1, times):
    m = 0.0
    for t in times:
        m = max(m, G._state_max_diff(SA.sample(a0, t), SA.sample(a1, t)))
    return m


# ---------------- AC ----------------
def ac_M1(skel, anims, order, segments):
    seq = skel["animations"][SEQ_NAME]
    coexist = all(nm in skel["animations"] for nm in set(order))
    # emission additive:各獨立 beat 的值與 build_animations 原產逐位元相同(emit 不動既有值)
    additive = all(skel["animations"][nm] == anims[nm] for nm in set(order))
    nonempty = bool(seq.get("bones")) and bool(seq.get("slots"))
    skel_bones = {b["name"] for b in skel["bones"]}
    bones_ok = all(b in skel_bones for b in seq.get("bones", {}))
    order_covered = [s["beat"] for s in segments] == order
    dur = SA.duration(seq)
    last = segments[-1]
    dur_ok = abs(dur - (last["start"] + last["dur"])) <= 1e-6
    ok = coexist and additive and nonempty and bones_ok and order_covered and dur_ok
    return {"pass": bool(ok), "order": order, "coexist_with_beats": bool(coexist),
            "emission_additive_beats_unchanged": bool(additive), "seq_nonempty": bool(nonempty),
            "bones_in_skeleton": bool(bones_ok), "order_covered": bool(order_covered),
            "duration": round(dur, 6), "duration_matches_segments": bool(dur_ok),
            "n_individual_beats": len(anims)}


def ac_M2(skel_reload, seq_inmem, segments):
    seq_re = skel_reload["animations"][SEQ_NAME]
    dur = SA.duration(seq_inmem)
    times = [dur * i / NSAMP for i in range(NSAMP + 1)]
    # 另加各段邊界(接點)取樣,確保去重接點也逐位元還原
    for s in segments:
        times.append(s["start"])
        times.append(min(s["start"] + s["dur"], dur))
    diff = _max_sample_diff(seq_inmem, seq_re, times)
    ok = diff == 0.0
    return {"pass": bool(ok), "roundtrip_max_sample_diff": diff, "exact_zero": bool(ok),
            "n_sample_points": len(times)}


def ac_M3(skel_reload):
    seq_re = skel_reload["animations"][SEQ_NAME]
    nonstrict = _nonstrict_channels(seq_re)
    strict_ok = len(nonstrict) == 0
    finite_ok = _all_finite(seq_re)
    nbez, ncolor = _count_bezier_color(seq_re)
    curves_ok = nbez >= 1
    color_ok = ncolor >= 1
    ok = strict_ok and finite_ok and curves_ok and color_ok
    return {"pass": bool(ok), "strictly_increasing_time": bool(strict_ok),
            "n_nonstrict_channels": len(nonstrict), "nonstrict_sample": nonstrict[:3],
            "all_finite": bool(finite_ok), "compact_bezier_frames": nbez, "bezier_preserved": bool(curves_ok),
            "color_hex_frames": ncolor, "color_preserved": bool(color_ok)}


def ac_M4(skel_reload, anims, segments):
    seq_re = skel_reload["animations"][SEQ_NAME]
    dur = SA.duration(seq_re)
    # 逐段回切(時間減 offset)還原孤立 beat
    concat_res = {}
    for s in segments:
        beat = s["beat"]; off = s["start"]; bdur = s["dur"]
        iso = anims[beat]
        m = 0.0
        for i in range(61):
            t = bdur * i / 60.0
            m = max(m, G._state_max_diff(SA.sample(seq_re, off + t), SA.sample(iso, t)))
        # 同一 beat 名(如重複 Loop)取最差;以 beat@start 作鍵保唯一
        concat_res["{}@{:.3f}".format(beat, off)] = round(m, 8)
    concat_ok = all(v <= CONCAT_TOL for v in concat_res.values())
    # 內部接點 C0(前 beat 尾 == 後 beat 首)—— **在 clip 端點層量**(前 beat sample(dur) vs 後 beat sample(0)),
    # 同 candidate L 的 L2 接點閘。⚠️ **不可**從 composed 時間軸以 `sample(bt−ε)` vs `sample(bt+ε)` 量:L / L-4
    # 已發現 ① compose 去重把接點抹成**單幀**→同一時間點恆連續(量 0 是空驗);② 若取 ±ε 兩側則捕捉的是接點附近
    # **真實非零速度** × ε(velocity×ε ≈ 0.01)—— 是**量測 artifact 非不連續**。正確 C0 判準在**孤立 beat 的端點切值**
    # (非空驗:In 尾=identity vs hit 首=identity→0,但 burst 首=collapsed≠identity 會非 0,見 L5);經 M4 concat
    # 已證重載序列逐段 == 孤立 beat,故此端點判準同時綁定重載資產。
    seam_res = {}
    for i in range(len(segments) - 1):
        ps, ns = segments[i], segments[i + 1]
        prev_tail = SA.sample(anims[ps["beat"]], ps["dur"])
        next_head = SA.sample(anims[ns["beat"]], 0.0)
        seam_res["{}->{}".format(ps["beat"], ns["beat"])] = round(
            G._state_max_diff(prev_tail, next_head), 6)
    seam_ok = all(v <= SEAM_TOL for v in seam_res.values())
    dur_ok = abs(dur - (segments[-1]["start"] + segments[-1]["dur"])) <= 1e-6
    ok = concat_ok and seam_ok and dur_ok
    return {"pass": bool(ok), "concat_faithful": bool(concat_ok), "concat_residuals": concat_res,
            "concat_tol": CONCAT_TOL, "seams_C0": bool(seam_ok), "seam_residuals": seam_res,
            "seam_tol": SEAM_TOL, "reloaded_duration": round(dur, 6), "duration_ok": bool(dur_ok)}


def ac_M5(skel_reload, anims, order):
    seq_re = skel_reload["animations"][SEQ_NAME]
    # (a) crux:注入非嚴格遞增通道 → 結構檢查器須抓出
    # (a1) 等時間(重複);(a2) 遞減
    inj_eq = copy.deepcopy(seq_re)
    some_bone = next(iter(inj_eq["bones"]))
    some_ch = next(iter(inj_eq["bones"][some_bone]))
    fr = inj_eq["bones"][some_bone][some_ch]
    fr.append(dict(fr[-1]))  # 複製末幀 → 等時間(非嚴格遞增)
    eq_caught = len(_nonstrict_channels(inj_eq)) >= 1
    inj_dec = copy.deepcopy(seq_re)
    fr2 = inj_dec["bones"][some_bone][some_ch]
    bad = dict(fr2[-1]); bad["time"] = fr2[-1]["time"] - 1.0  # 遞減
    fr2.append(bad)
    dec_caught = len(_nonstrict_channels(inj_dec)) >= 1
    # 守衛:合法序列本身無 non-strict(對照)
    clean_ok = len(_nonstrict_channels(seq_re)) == 0
    a_ok = eq_caught and dec_caught and clean_ok
    # (b) emit 守衛:覆蓋既有 beat 名 → ValueError;order 含未知 beat → KeyError
    overwrite_guarded = False
    try:
        G.emit_sequence_animation({"animations": dict(anims)}, anims, order, name="Loop")
    except ValueError:
        overwrite_guarded = True
    unknown_guarded = False
    try:
        G.emit_sequence_animation({"animations": {}}, anims, ["In", "__nope__", "Out"], name="X")
    except KeyError:
        unknown_guarded = True
    b_ok = overwrite_guarded and unknown_guarded
    # (c) 擾動一值 → round-trip 比較器偵測得到(證 M2 的 0 有意義)
    perturbed = copy.deepcopy(seq_re)
    pb = next(iter(perturbed["bones"]))
    pc = next(iter(perturbed["bones"][pb]))
    vkey = next(k for k in perturbed["bones"][pb][pc][0] if k != "time" and k != "curve"
                and isinstance(perturbed["bones"][pb][pc][0][k], (int, float)))
    perturbed["bones"][pb][pc][0][vkey] += 5.0
    dur = SA.duration(seq_re)
    diff = _max_sample_diff(seq_re, perturbed, [dur * i / 50.0 for i in range(51)])
    c_ok = diff > 0.0
    ok = a_ok and b_ok and c_ok
    return {"pass": bool(ok),
            "a_struct_checker_teeth": {"pass": bool(a_ok), "equal_time_caught": bool(eq_caught),
                                       "decreasing_time_caught": bool(dec_caught),
                                       "clean_seq_strict": bool(clean_ok)},
            "b_emit_guards": {"pass": bool(b_ok), "overwrite_existing_raises": bool(overwrite_guarded),
                              "unknown_beat_raises": bool(unknown_guarded)},
            "c_roundtrip_discriminator": {"pass": bool(c_ok), "perturbed_diff": round(diff, 6)}}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    order = G.forward_sequence_order(anims)
    needed = set(order)
    missing = [nm for nm in needed if nm not in anims]
    if missing:
        return {"overall_pass": False, "error": "missing beats in fixture: {}".format(missing),
                "available": sorted(anims.keys())}
    # 保留 build_animations 原產各 beat 的獨立副本(供 M1 的 additive 複驗、M4 回切對照)
    iso_anims = copy.deepcopy(anims)
    seq_inmem_src = copy.deepcopy(anims)
    # 鏡像 build_spine 產線:先把各 beat 裝進 skeleton["animations"],再 emit 序列 → 兩者並存於同一 skeleton。
    skel["animations"] = anims
    segments = G.emit_sequence_animation(skel, anims, order, name=SEQ_NAME)
    seq_inmem = skel["animations"][SEQ_NAME]
    # 另以未被 emit 汙染的獨立 anims 重算一份 in-memory 合成(與 skel 內那份應逐位元同;M2 的設計真值)
    composed_check, _ = G.compose_sequence(seq_inmem_src, order)
    skel_reload = _serialize_reload(skel)
    results = {
        "M1_present_emission_additive": ac_M1(skel, iso_anims, order, segments),
        "M2_crux_roundtrip_fidelity": ac_M2(skel_reload, composed_check, segments),
        "M3_crux_spine38_struct_valid": ac_M3(skel_reload),
        "M4_faithful_concat_reloaded": ac_M4(skel_reload, iso_anims, segments),
        "M5_neg_control_guards": ac_M5(skel_reload, iso_anims, order),
    }
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
        print("candidate (M) 大獎序列 → 可載入資產 round-trip 閘 — emit_sequence_animation + serialize/reload")
        for k in ["M1_present_emission_additive", "M2_crux_roundtrip_fidelity",
                  "M3_crux_spine38_struct_valid", "M4_faithful_concat_reloaded",
                  "M5_neg_control_guards"]:
            v = res.get(k, {})
            print("  {:34s} {}".format(k, "PASS" if v.get("pass") else "FAIL"))
        if "error" in res:
            print("  ERROR:", res["error"])
        if "M2_crux_roundtrip_fidelity" in res:
            p = res["M2_crux_roundtrip_fidelity"]
            print("    round-trip max sample diff = {} (exact-zero={}, {} pts)".format(
                p["roundtrip_max_sample_diff"], p["exact_zero"], p["n_sample_points"]))
        if "M3_crux_spine38_struct_valid" in res:
            p = res["M3_crux_spine38_struct_valid"]
            print("    strict-increasing={} non-strict={} | bezier={} color-hex={}".format(
                p["strictly_increasing_time"], p["n_nonstrict_channels"],
                p["compact_bezier_frames"], p["color_hex_frames"]))
        if "M5_neg_control_guards" in res:
            p = res["M5_neg_control_guards"]
            print("    struct-teeth(eq/dec)={}/{} emit-guards(overwrite/unknown)={}/{} perturb-diff={}".format(
                p["a_struct_checker_teeth"]["equal_time_caught"],
                p["a_struct_checker_teeth"]["decreasing_time_caught"],
                p["b_emit_guards"]["overwrite_existing_raises"],
                p["b_emit_guards"]["unknown_beat_raises"],
                p["c_roundtrip_discriminator"]["perturbed_diff"]))
        print("OVERALL:", "PASS" if res.get("overall_pass") else "FAIL")
    return 0 if res.get("overall_pass") else 1


if __name__ == "__main__":
    sys.exit(main())
