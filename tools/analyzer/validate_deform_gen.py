#!/usr/bin/env python3
"""candidate 0e 驗收閘 — mesh deform timeline 生成器(`gen_deform.py`)自我品質閘。

真相來源:`deform_eval`(真實位移場、逐頂點拓樸檢查),已對真實 main_draw 4 mesh × 9 anim
全乾淨(_checker_validated=True)驗證可信。本閘對**生成的** deform timeline 逐幀套同一檢查。

AC(全可機讀,不靠肉眼):
  AC1 結構/有限   :每 frame time 嚴格遞增、offset 為 int、vertices 長度==2*nv、值皆有限;compact bezier 鍵有限。
  AC2 逐幀乾淨    :對每 mesh × 每 deform beat,以 deform_eval.sample_poses 展開生成 timeline(含相鄰幀內插)
                   → 每 pose eval_pose 皆 clean(self_intersections=0/flips=0/degenerate=0)。
  AC3 loop 無縫   :loop beat 首 frame vertices == 末 frame vertices(皆 0)→ 位移場端點一致。
  AC4 setup 介面  :所有生成 beat(intro/loop/pulse)首尾 frame 位移==0 → 回 setup → beat 間可無縫串接。
  AC5 幅度校準    :每 mesh 全 frame 逐頂點最大位移 ≤ 該 mesh 真實 deform 場最大幅度(不超真實裕度)。
  AC6 負對照鑑別力:把生成場**逐頂點打亂**(破壞空間平滑)→ 至少一 mesh 有非乾淨幀(閘抓得到)。
  AC7 端到端(真生成 mesh):`build_spine --animate --deform`(robot_parts)→ 其**生成的** mesh(光暈)
                   deform timeline 逐幀乾淨;且 bone/slot animation 不受影響(validate_anim 回歸另跑)。
"""
import json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
import deform_eval as de
import gen_deform as gd


def _setup_geom(a):
    setup = np.array(a["vertices"], float).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    signs = [de.signed_area(setup, t) > 0 for t in tris]
    area = sum(abs(de.signed_area(setup, t)) for t in tris)
    return setup, tris, signs, area


def _find_frames(anim, slot, name):
    for skinnm, slots in anim.get("deform", {}).items():
        if slot in slots and name in slots[slot]:
            return slots[slot][name]
    return None


def _clean_over_timeline(setup, tris, signs, area, frames):
    """把生成 frames 展開(sample_poses 含相鄰幀內插)→ 每 pose 是否乾淨。回傳 (all_clean, worst)。"""
    fr = [(f["time"], f["offset"], np.array(f["vertices"], float)) for f in frames]
    poses = de.sample_poses(setup, fr, substeps=4)
    res = [de.eval_pose(v, tris, signs, area) for _, v in poses]
    worst = {k: max(r[k] for r in res) for k in ("self_intersections", "triangle_flips", "degenerate")}
    return all(r["clean"] for r in res), worst, len(poses)


def _synth_storyboard():
    # beat 名對映 gen_animations.beat_category:come_out→intro / idle_loop→loop / hit→pulse / close→outro
    return {"beats": [{"beat": "come_out", "parts": []}, {"beat": "idle_loop", "parts": []},
                      {"beat": "hit", "parts": []}, {"beat": "close", "parts": []}]}


def check_finite_frames(frames, nv):
    last = -1e18
    for f in frames:
        t = f.get("time")
        if not isinstance(t, (int, float)) or not np.isfinite(t) or t <= last:
            return False
        last = t
        if not isinstance(f.get("offset"), int):
            return False
        v = f.get("vertices", [])
        if len(v) != 2 * nv or not all(np.isfinite(v)):
            return False
        for k in ("curve", "c2", "c3", "c4"):
            if k in f and not (f[k] == "stepped" or np.isfinite(f[k])):
                return False
    return True


def run():
    results = {}
    sk = json.load(open("assets/main_draw.json", encoding="utf-8"))
    meshes = [(s, n) for (_, s, n, _) in gd._mesh_attachments(sk)]
    story = _synth_storyboard()

    # 每件用自己的真實場(最 faithful);同時記錄各件真實最大幅度供 AC5
    per_src, real_max = {}, {}
    for s, n in meshes:
        uvs, field, _ = de.real_deform_field(sk, s, n)
        per_src[(s, n)] = (uvs, field)
        real_max[(s, n)] = float(np.hypot(field[:, 0], field[:, 1]).max())

    # 生成 deform(寫進深拷貝的 animations)
    tgt = json.loads(json.dumps(sk))
    tgt["animations"] = {b["beat"]: {} for b in story["beats"]}
    gd.build_deform(tgt, story, None, None, per_mesh_source=per_src)
    tgt_att = {(s, n): a for (_, s, n, a) in gd._mesh_attachments(tgt)}

    ac1 = ac2 = ac3 = ac4 = ac5 = True
    ac2_detail, ac5_detail = {}, {}
    for (s, n) in meshes:
        a = tgt_att[(s, n)]
        setup, tris, signs, area = _setup_geom(a)
        nv = len(a["uvs"]) // 2
        mesh_peak = 0.0
        for beat, anim in tgt["animations"].items():
            frames = _find_frames(anim, s, n)
            if not frames:
                continue
            if not check_finite_frames(frames, nv):
                ac1 = False
            clean, worst, _ = _clean_over_timeline(setup, tris, signs, area, frames)
            if not clean:
                ac2 = False
                ac2_detail[f"{s}@{beat}"] = worst
            # AC3/AC4:端點=0
            v0 = np.array(frames[0]["vertices"]); vL = np.array(frames[-1]["vertices"])
            if not (np.allclose(v0, 0) and np.allclose(vL, 0)):
                ac4 = False
                if gd.beat_category(beat) == "loop" and frames[0]["vertices"] != frames[-1]["vertices"]:
                    ac3 = False
            for f in frames:
                vv = np.array(f["vertices"], float)
                mesh_peak = max(mesh_peak, float(np.hypot(vv[0::2], vv[1::2]).max()))
        ac5_detail[s] = {"gen_peak": round(mesh_peak, 1), "real_max": round(real_max[(s, n)], 1)}
        if mesh_peak > real_max[(s, n)] + 1e-6:
            ac5 = False

    results["AC1_structural_finite"] = ac1
    results["AC2_clean_over_timeline"] = {"pass": ac2, "nonclean": ac2_detail}
    results["AC3_loop_seamless"] = ac3
    results["AC4_setup_interface"] = ac4
    results["AC5_amplitude_calibrated"] = {"pass": ac5, "detail": ac5_detail}

    # AC6 負對照:壞生成器的真實失敗模式 = **不尊重空間平滑的不連貫位移場**。
    #   逐頂點打亂真實場(incoherent)× 3(蓋過稀疏拓樸的自交裕度)→ 應在**全部** mesh 被閘抓到。
    #   對照發現(informative):把**連貫**真實場等比放大(×4)反而**不破**(合法運動方向、只是變大)
    #   → 證閘抓的是「拓樸損壞」非「幅度大」;我方生成器沿連貫場、peak≤0.7× → 有裕度。
    rng = np.random.default_rng(0)
    nc_detail = {}
    scramble_hits = coherent_clean = 0
    for (s, n) in meshes:
        a = tgt_att[(s, n)]
        setup, tris, signs, area = _setup_geom(a)
        uvs, field = per_src[(s, n)]
        target = {"uvs": a["uvs"], "vertices": a["vertices"], "triangles": a["triangles"]}
        scr = gd.synthesize(target, uvs, field[rng.permutation(len(field))] * 3.0, "loop")
        coh = gd.synthesize(target, uvs, field * 4.0, "loop")   # 連貫放大(對照)
        c_scr, w_scr, _ = _clean_over_timeline(setup, tris, signs, area, scr)
        c_coh, _, _ = _clean_over_timeline(setup, tris, signs, area, coh)
        scramble_hits += (not c_scr); coherent_clean += c_coh
        nc_detail[s] = {"scramble3x_damage": w_scr["self_intersections"] + w_scr["triangle_flips"],
                        "coherent4x_clean": c_coh}
    nc_pass = (scramble_hits == len(meshes))
    results["AC6_negcontrol_detected"] = {"pass": nc_pass,
                                          "scramble3x_hits": f"{scramble_hits}/{len(meshes)}",
                                          "coherent4x_stays_clean": f"{coherent_clean}/{len(meshes)}",
                                          "worst_per_mesh": nc_detail}

    # AC7 端到端:build_spine --animate --deform(robot_parts)→ 其生成 mesh deform 逐幀乾淨
    from build_spine import build
    outdir = os.path.join("specs", "_deform_e2e_spine")   # *_spine → 已 gitignore(可重生,不進版控)
    summ = build("assets/robot_parts.psd", outdir, genre="slot_bigwin", animate=True, deform=True)
    bsk = json.load(open(os.path.join(outdir, "skeleton.json"), encoding="utf-8"))
    bmeshes = gd._mesh_attachments(bsk)
    e2e_ok = len(bmeshes) > 0
    e2e_detail = {"mesh_parts": summ.get("mesh_parts", []), "checked": {}}
    for (_, s, n, a) in bmeshes:
        setup, tris, signs, area = _setup_geom(a)
        beats_checked = 0
        for beat, anim in bsk.get("animations", {}).items():
            fr = _find_frames(anim, s, n)
            if not fr:
                continue
            clean, _, _ = _clean_over_timeline(setup, tris, signs, area, fr)
            beats_checked += 1
            if not clean:
                e2e_ok = False
        e2e_detail["checked"][f"{s}/{n}"] = {"beats_with_deform": beats_checked}
        if beats_checked == 0:
            e2e_ok = False
    results["AC7_end2end_generated_mesh"] = {"pass": e2e_ok, "detail": e2e_detail}

    results["OVERALL_PASS"] = (ac1 and ac2 and ac3 and ac4 and ac5 and nc_pass and e2e_ok)
    return results


if __name__ == "__main__":
    r = run()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r["OVERALL_PASS"] else 1)
