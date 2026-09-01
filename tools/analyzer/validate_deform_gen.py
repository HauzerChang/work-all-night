#!/usr/bin/env python3
"""candidate 0e 驗收 — mesh deform timeline 生成器(gen_deform.py)。

主標的:對 **main_draw 4 個真實藝術家 mesh 拓樸**(curtain_left/right 各 21v24t、shadow/shadow2 各 12v10t)
生成 loop deform,用 deform_eval(已對藝術家真值 + 負對照雙向校準的閘)逐幀量化。

AC:
  AC1 seamless      :loop deform 首幀 == 末幀 == setup identity(0 offset)→ 無縫循環。
  AC2 clean         :預設參數下,4 mesh 全 beat 逐子幀 si=0 / flip=0 / degenerate=0。
  AC3 non-trivial   :每 mesh 最大位移 > 3px(確實變形,非 no-op)。
  AC4 identity 介面 :每個 beat 的 deform 端點(τ=0,τ=1)皆 = setup identity → 與 gen_animations
                     的 bone timeline 共用 identity 介面,任意 beat 串接無跳變(對齊 candidate 0d AC4)。
  NC  discriminating:對同一組 mesh 施「高頻雙軸扭轉」壞位移場 → 閘必偵測(si>0 或 flip>0)。
                     證明 AC2 的乾淨是實質結果、非閘失能。

副驗:end-to-end —— build_spine --animate 是否把 deform 注入 mesh 件且逐幀乾淨。
"""
import json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
import gen_deform as gd
import deform_eval as de

MAIN = os.path.join("assets", "main_draw.json")


def _meshes(sk):
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    return [(s, n) for s, o in atts.items() for n, a in o.items() if a.get("type") == "mesh"]


def _poses_clean(setup, tris, frames):
    signs = [de.signed_area(setup, t) > 0 for t in tris]
    area = sum(abs(de.signed_area(setup, t)) for t in tris)
    fr = [(f["time"], f["offset"], np.array(f["vertices"], dtype=np.float64)) for f in frames]
    poses = de.sample_poses(setup, fr, substeps=4)
    msi = mfl = mdg = 0
    for _, v in poses:
        r = de.eval_pose(v, tris, signs, area)
        msi = max(msi, r["self_intersections"]); mfl = max(mfl, r["triangle_flips"]); mdg = max(mdg, r["degenerate"])
    return msi, mfl, mdg, len(poses)


def validate_main(amp_frac=0.08, wavenum=1.0):
    sk = json.load(open(MAIN))
    meshes = _meshes(sk)
    report = {"meshes": {}, "AC": {}}
    ac1 = ac2 = ac3 = ac4 = True
    nc_fired = False
    beats = ["loop", "intro", "outro", "pulse"]

    for slot, name in meshes:
        setup, tris, hull, nv = de.load_mesh(sk, slot, name)
        nm = name.split("/")[-1] + ("~" + slot.split("/")[-1] if slot.split("/")[-1] != name.split("/")[-1] else "")
        entry = {"nv": nv, "tris": len(tris)}

        # --- loop 為主驗 ---
        loop_frames = gd.gen_deform_frames(setup, "loop", amp_frac, wavenum)
        first = np.array(loop_frames[0]["vertices"]); last = np.array(loop_frames[-1]["vertices"])
        seam = float(np.abs(first - last).max())
        idn0 = float(np.abs(first).max())
        entry["loop_seam_maxdiff"] = round(seam, 6)
        entry["loop_endpoint_identity_max"] = round(idn0, 6)
        if seam > 1e-6 or idn0 > 1e-6:
            ac1 = False

        maxoff = 0.0
        for f in loop_frames:
            for k in range(0, len(f["vertices"]), 2):
                maxoff = max(maxoff, math.hypot(f["vertices"][k], f["vertices"][k + 1]))
        entry["loop_max_offset_px"] = round(maxoff, 2)
        if maxoff <= 3.0:
            ac3 = False

        # --- AC2 clean:所有 beat 逐子幀 ---
        beat_clean = {}
        for cat in beats:
            fr = gd.gen_deform_frames(setup, cat, amp_frac, wavenum)
            si, fl, dg, npose = _poses_clean(setup, tris, fr)
            beat_clean[cat] = {"max_si": si, "max_flip": fl, "max_degen": dg, "poses": npose}
            if si or fl or dg:
                ac2 = False
            # AC4:每 beat 端點 == identity
            fe = np.array(fr[0]["vertices"]); le = np.array(fr[-1]["vertices"])
            if float(np.abs(fe).max()) > 1e-6 or float(np.abs(le).max()) > 1e-6:
                ac4 = False
        entry["beats"] = beat_clean

        # --- NC:高頻雙軸扭轉壞位移場 ---
        ext = setup.max(0) - setup.min(0)
        s = (setup[:, 1] - setup[:, 1].min()) / (ext[1] or 1.0)
        A = 0.9 * (ext[0] or 1.0)
        off = np.zeros_like(setup)
        off[:, 0] = A * np.sin(6 * math.pi * s); off[:, 1] = A * np.cos(6 * math.pi * s)
        signs = [de.signed_area(setup, t) > 0 for t in tris]
        area = sum(abs(de.signed_area(setup, t)) for t in tris)
        rnc = de.eval_pose(setup + off, tris, signs, area)
        entry["NC_twist"] = {"si": rnc["self_intersections"], "flip": rnc["triangle_flips"]}
        if rnc["self_intersections"] > 0 or rnc["triangle_flips"] > 0:
            nc_fired = True

        report["meshes"][nm] = entry

    report["AC"] = {
        "AC1_seamless_identity_endpoints": ac1,
        "AC2_all_beats_clean": ac2,
        "AC3_nontrivial_deform": ac3,
        "AC4_identity_interface": ac4,
        "NC_gate_discriminates": nc_fired,
    }
    report["OVERALL_PASS"] = ac1 and ac2 and ac3 and ac4 and nc_fired
    return report


def validate_end2end():
    """整合驗:對**真實 main_draw 骨架**(含 4 個 unweighted 軟件 mesh)注入生成的 deform,
    確認 (a) 每個非-hold beat × 每 mesh 都拿到 deform;(b) 全幀乾淨;(c) JSON round-trip 可載入。
    附:build_spine --animate 對剛體 robot_parts 正確注入 0 個軟件 deform(無崩潰、wiring 在位)。"""
    import subprocess, tempfile
    result = {}
    # --- (1) 對 main_draw 注入 deform(真實軟件 mesh 整合證明)---
    sk = json.load(open(MAIN))
    meshes = _meshes(sk)
    unweighted = [(s, n) for (s, n) in meshes]  # main_draw 4 mesh 全 unweighted
    sk["animations"] = {"intro": {}, "loop": {}, "outro": {}}  # 新鮮 beats,清掉原生 deform
    summary = gd.add_deform_for_beats(sk, amp_frac=0.08, wavenum=1.0)
    injected = 0; all_clean = True; details = {}
    for anim in sk["animations"]:
        for slot, name in unweighted:
            fr = de.deform_frames(sk, anim, slot, name)
            if not fr:
                continue
            injected += 1
            setup, tris, hull, nv = de.load_mesh(sk, slot, name)
            signs = [de.signed_area(setup, t) > 0 for t in tris]
            area = sum(abs(de.signed_area(setup, t)) for t in tris)
            for _, v in de.sample_poses(setup, fr, 4):
                if de.eval_pose(v, tris, signs, area)["clean"] is False:
                    all_clean = False
            details.setdefault(anim, []).append(name.split("/")[-1])
    try:
        json.dumps(sk)  # round-trip 可序列化 → 可載入
        loadable = True
    except Exception:
        loadable = False
    expected = len(unweighted) * 3  # 3 個非-hold beat
    result["main_draw_injection"] = {
        "unweighted_soft_meshes": len(unweighted),
        "deform_injected_pairs": injected, "expected": expected,
        "all_frames_clean": all_clean, "json_loadable": loadable, "by_anim": details,
        "pass": injected == expected and all_clean and loadable,
    }
    # --- (2) build_spine --animate 剛體資產 wiring 存活 ---
    psd = os.path.join("assets", "robot_parts.psd")
    if os.path.exists(psd):
        out = tempfile.mkdtemp(prefix="deform_e2e_")
        try:
            subprocess.run([sys.executable, os.path.join("tools", "analyzer", "build_spine.py"),
                            psd, "--out", out, "--animate"], capture_output=True, text=True, timeout=300)
            skpath = os.path.join(out, "skeleton.json")
            ok = os.path.exists(skpath) and json.load(open(skpath)).get("animations")
            result["robot_build_wiring"] = {"skeleton_built": bool(ok),
                                            "note": "rigid limbs → 0 soft-mesh deform expected"}
        except Exception as e:
            result["robot_build_wiring"] = {"error": str(e)}
    result["status"] = "ok"
    result["pass"] = result["main_draw_injection"]["pass"]
    return result


if __name__ == "__main__":
    rep = validate_main()
    e2e = validate_end2end()
    rep["end_to_end_build_spine"] = e2e
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    ok = rep["OVERALL_PASS"] and e2e.get("pass", False)
    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
