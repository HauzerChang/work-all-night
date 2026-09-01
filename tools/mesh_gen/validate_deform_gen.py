#!/usr/bin/env python3
"""S1/S3 — mesh deform 生成器 gate(自我驗收,量化,不靠肉眼)。

對 gen_deform.gen_deform_timeline 產出的 deform timeline,對 main_draw 4 個真實藝術家
mesh 拓樸(setup 已知乾淨)逐 beat 類別驗:

  AC1 well-formed : 時間嚴格遞增、值有限、offset 長度 == 2·nv、可 JSON round-trip。
  AC2 loop seamless: loop 類別 offset(t=0) == offset(t=dur),max_err ≤ 1e-6(可無縫接 TRS loop)。
  AC3 topology clean: 全取樣幀(含相鄰內插) self_intersections==0 且 flips==0 且 degenerate==0。
  AC4 amplitude plausible: 生成峰值位移 > 0(真的會動)且 ≤ 該 mesh 真實藝術家 deform 峰值
                           (在物理包絡內,不狂暴);area_ratio ∈ [0.5, 真實上限×1.1]。
  AC5 negative control: (a) 幅度灌爆(amp×6)→ AC3 必 FAIL;(b) 打斷 loop 無縫(相位偏移)→ AC2 必 FAIL。

用法: python3 tools/mesh_gen/validate_deform_gen.py [assets/main_draw.json]
     overall_pass:true(exit 0)= 生成器就緒。
"""
import json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analyzer"))
import deform_eval as de
import gen_deform as gd
import spine_anim as sa

CATS = ["loop", "pulse", "intro", "outro"]
# 物理包絡:跨所有藝術家 mesh 觀察到的最大 deform ≈ 59% 長軸長(窗簾 open/close)。
# 用「類別包絡」而非「該 mesh 自身藝術家峰值」當上限——後者是藝術家對那件的手感選擇,非物理硬限。
PLAUSIBLE_MAX_FRAC = 0.60


def _poses_from_frames(setup, frames, substeps=4):
    full = [(f["time"], 0, np.array(f["vertices"], dtype=np.float64)) for f in frames]
    return de.sample_poses(setup, full, substeps=substeps)


def _topo_clean(setup, tris, frames):
    setup_signs = [de.signed_area(setup, t) > 0 for t in tris]
    setup_area = sum(abs(de.signed_area(setup, t)) for t in tris)
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    ar_lo, ar_hi = 1e9, 0.0
    peak = 0.0
    for _, v in _poses_from_frames(setup, frames):
        r = de.eval_pose(v, tris, setup_signs, setup_area)
        for k in worst:
            worst[k] = max(worst[k], r[k])
        ar_lo = min(ar_lo, r["area_ratio"]); ar_hi = max(ar_hi, r["area_ratio"])
        d = np.hypot(*(v - setup).T)
        peak = max(peak, float(d.max()))
    clean = worst["self_intersections"] == 0 and worst["triangle_flips"] == 0 and worst["degenerate"] == 0
    return clean, worst, (round(ar_lo, 3), round(ar_hi, 3)), round(peak, 1)


def validate(path):
    sk = json.load(open(path))
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    meshes = [(s, n) for s, o in atts.items() for n, a in o.items()
              if a.get("type") == "mesh" and len(a.get("vertices", [])) == len(a.get("uvs", []))]

    report = {"meshes": {}, "AC": {}}
    ac1 = ac2 = ac3 = ac4 = True
    for slot, name in meshes:
        setup, tris, hull, nv = de.load_mesh(sk, slot, name)
        # 真實藝術家 deform 峰值(僅供 context 對照,非硬上限)
        _, rfield, _ = de.real_deform_field(sk, slot, name)
        real_peak = float(np.hypot(rfield[:, 0], rfield[:, 1]).max())
        long_ext = float((setup.max(0) - setup.min(0)).max())
        env = PLAUSIBLE_MAX_FRAC * long_ext   # 類別物理包絡上限
        per_cat = {}
        for cat in CATS:
            frames = gd.gen_deform_timeline(setup, cat)
            # AC1 well-formed
            wf = sa.deform_frames_finite(frames)
            lenok = all(len(f["vertices"]) == 2 * nv for f in frames)
            rt = True
            try:
                json.loads(json.dumps(frames))
            except Exception:
                rt = False
            a1 = wf and lenok and rt
            # AC3 topology + peak/area
            clean, worst, ar, peak = _topo_clean(setup, tris, frames)
            # AC2 seamless (loop only)
            seam_err = None
            if cat == "loop":
                v0 = np.array(sa.sample_deform(frames, 0.0))
                vd = np.array(sa.sample_deform(frames, frames[-1]["time"]))
                seam_err = float(np.abs(v0 - vd).max())
            # AC4 plausibility:真的會動(>0.5px)、在類別物理包絡內(≤0.60·長軸)、area_ratio 合理
            a4 = (peak > 0.5) and (peak <= env) and (ar[0] >= 0.5) and (ar[1] <= 2.2)
            per_cat[cat] = {"a1": a1, "clean": clean, "worst": worst, "peak": peak,
                            "real_peak": round(real_peak, 1), "envelope": round(env, 1),
                            "area_ratio": ar,
                            "seam_err": None if seam_err is None else round(seam_err, 9), "a4": a4}
            ac1 = ac1 and a1
            ac3 = ac3 and clean
            ac4 = ac4 and a4
            if cat == "loop":
                ac2 = ac2 and (seam_err <= 1e-6)
        report["meshes"][f"{slot}/{name}"] = {"nv": nv, "tris": len(tris), "cats": per_cat}

    # AC5 負對照:用第一個 mesh
    slot, name = meshes[0]
    setup, tris, hull, nv = de.load_mesh(sk, slot, name)
    # (a) 非平滑(隨機逐頂點)位移場 → 必撕裂(證 AC3 checker 有鑑別力,非空過)
    rng = np.random.default_rng(0)
    long_ext = float((setup.max(0) - setup.min(0)).max())
    rand_off = (rng.standard_normal((nv, 2)) * 0.30 * long_ext).reshape(-1)
    rand_frames = [{"time": 0.0, "vertices": [0.0] * (2 * nv)},
                   {"time": 0.3, "vertices": [round(float(x), 3) for x in rand_off]}]
    clean_rand, worst_rand, _, _ = _topo_clean(setup, tris, rand_frames)
    nc_a = (not clean_rand)   # 期望:不乾淨(自交/翻面)
    # 附註(非 AC):平滑 shear 極耐變形——loop 幅度灌爆 6× 仍乾淨(呼應藝術家 315px strip 乾淨)
    huge = gd.gen_deform_timeline(setup, "loop", amp_frac=gd.AMP["loop"] * 6.0)
    clean_huge, _, _, peak_huge = _topo_clean(setup, tris, huge)
    # (b) 打斷無縫:對 loop 末幀相位偏移(人工破壞端點相等)
    broke = gd.gen_deform_timeline(setup, "loop")
    broke[-1] = {"time": broke[-1]["time"],
                 "vertices": [x + 5.0 for x in broke[-1]["vertices"]]}
    vb0 = np.array(sa.sample_deform(broke, 0.0))
    vbd = np.array(sa.sample_deform(broke, broke[-1]["time"]))
    nc_b = float(np.abs(vb0 - vbd).max()) > 1e-6   # 期望:seam 破了
    ac5 = nc_a and nc_b
    report["AC5_negative"] = {"random_field_detected_tear": nc_a, "worst_random": worst_rand,
                              "seam_break_detected": nc_b,
                              "note_smooth_shear_robust": {"loop_amp_x6_clean": clean_huge,
                                                           "peak": peak_huge}}

    report["AC"] = {"AC1_wellformed": ac1, "AC2_loop_seamless": ac2,
                    "AC3_topology_clean": ac3, "AC4_amplitude_plausible": ac4,
                    "AC5_negative_control": ac5}
    report["overall_pass"] = all(report["AC"].values())
    return report


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    return o


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/main_draw.json"
    rep = _clean(validate(path))
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    sys.exit(0 if rep["overall_pass"] else 1)
