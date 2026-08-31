#!/usr/bin/env python3
"""candidate 0e 真值閘 — 驗 gen_mesh_deform 生成的 mesh deform timeline。

在 main_draw 的 4 個**真實美術 mesh**(curtain_left/right 21v、shadow/shadow2 12v)上生成 deform,
用 S3 deform 評估器(deform_eval,已對藝術家真值自一致 si=0)量化。4 條 AC:

  AC1  格式/可載入:deform 結構 {skin:{slot:{att:frames}}} 合法;frame.vertices 長度==2*nv;
       time 單調自 0;attach 進 skeleton 後 deform_frames 讀回一致(round-trip)。
  AC2  乾淨閘(核心):每個 mesh × 每個 beat,所有取樣幀(keyframe + 線性內插 substep)
       self_intersections=0 / triangle_flips=0 / degenerate=0。
  AC3  無縫 + identity 介面:loop 首幀==尾幀(端點相等);intro 尾==0、outro 首==0、pulse 首尾==0
       → 與 bone timeline 的 setup identity 介面對齊,任意串接無跳變。
  AC4  非平凡運動 + 負對照鑑別力:loop 每 mesh 最大位移 > 門檻(真的會動,非 no-op);
       且(a)刻意折疊場(radial s=−2 越過 −1)被閘抓到 si/flip>0;
          (b)極端 shear(5×寬)**仍乾淨**(實證「y 向剪切保拓樸」的理論保證)。
"""
import json, os, sys
import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "mesh_gen"))

import deform_eval as de
import gen_mesh_deform as gmd

ASSET = os.path.join(HERE, "..", "..", "assets", "main_draw.json")
MIN_MOVE = 2.0   # px:loop 至少要動這麼多才算非平凡
EPS = 1e-6

# 覆蓋 5 類 beat 的合成 storyboard(mesh deform 只需 beat 名;parts 不影響)
STORYBOARD = {"beats": [
    {"beat": "idle", "parts": []},      # → loop
    {"beat": "comeout", "parts": []},   # → intro
    {"beat": "close", "parts": []},     # → outro
    {"beat": "hit", "parts": []},       # → pulse
    {"beat": "base", "parts": []},      # → hold(不發 deform)
]}


def _meshes(sk):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    return [(s, n) for s, o in atts.items() for n, a in o.items() if a.get("type") == "mesh"]


def _eval_offsets(setup, tris, signs, area, off_flat):
    v = setup + np.array(off_flat, dtype=np.float64).reshape(-1, 2)
    return de.eval_pose(v, tris, signs, area)


def run():
    sk = json.load(open(ASSET))
    meshes = _meshes(sk)
    # 生成 deform 並注入乾淨副本
    gen = json.loads(json.dumps(sk))
    gen["animations"] = {}   # 清掉藝術家動畫,只放我們生成的
    md = gmd.attach_into_animations(gen, STORYBOARD)
    skin_nm = gmd.skin_name(gen)

    R = {}

    # ---- AC1 格式/可載入 + round-trip ----
    ac1 = {"pass": True, "detail": []}
    reloaded = json.loads(json.dumps(gen))   # 模擬存檔→讀回
    for beat, deform in md.items():
        for sknm, slots in deform.items():
            ok_skin = (sknm == skin_nm)
            for slot, atts in slots.items():
                for att, frames in atts.items():
                    nv = None
                    for s, n in meshes:
                        if s == slot and n == att:
                            _, _, _, nv = de.load_mesh(gen, slot, att)
                    lens_ok = all(len(f["vertices"]) == 2 * nv for f in frames)
                    times = [f["time"] for f in frames]
                    mono = all(times[i] <= times[i + 1] + EPS for i in range(len(times) - 1)) and abs(times[0]) < EPS
                    # round-trip:deform_frames 讀回
                    rf = de.deform_frames(reloaded, beat, slot, att)
                    rt_ok = len(rf) == len(frames) and all(
                        np.allclose(np.array(rf[i][2]), np.array(frames[i]["vertices"]), atol=1e-3) for i in range(len(frames)))
                    good = ok_skin and lens_ok and mono and rt_ok
                    ac1["pass"] &= good
                    if not good:
                        ac1["detail"].append(f"{beat}/{slot}/{att}: skin={ok_skin} lens={lens_ok} mono={mono} rt={rt_ok}")
    R["AC1_wellformed_roundtrip"] = ac1

    # ---- AC2 乾淨閘(核心) ----
    ac2 = {"pass": True, "worst": {}, "per": {}}
    for slot, att in meshes:
        setup, tris, hull, nv = de.load_mesh(gen, slot, att)
        signs = [de.signed_area(setup, t) > 0 for t in tris]
        area = sum(abs(de.signed_area(setup, t)) for t in tris)
        for beat in md:
            frames = de.deform_frames(gen, beat, slot, att)
            if not frames:
                continue
            poses = de.sample_poses(setup, frames)   # keyframe + 線性 substep
            res = [de.eval_pose(v, tris, signs, area) for _, v in poses]
            worst = {"si": max(r["self_intersections"] for r in res),
                     "flip": max(r["triangle_flips"] for r in res),
                     "degen": max(r["degenerate"] for r in res),
                     "frames": len(res),
                     "clean": all(r["clean"] for r in res)}
            ac2["per"][f"{slot}/{att}::{beat}"] = worst
            ac2["pass"] &= worst["clean"]
            for k in ("si", "flip", "degen"):
                ac2["worst"][k] = max(ac2["worst"].get(k, 0), worst[k])
    R["AC2_clean_gate"] = ac2

    # ---- AC3 無縫 + identity 介面 ----
    ac3 = {"pass": True, "detail": []}
    def cat_of(beat):
        return gmd.beat_category(beat)
    for slot, att in meshes:
        for beat in md:
            frames = md[beat][skin_nm].get(slot, {}).get(att)
            if not frames:
                continue
            c = cat_of(beat)
            v0 = np.array(frames[0]["vertices"]); vL = np.array(frames[-1]["vertices"])
            m0 = float(np.abs(v0).max()); mL = float(np.abs(vL).max())
            if c == "loop":
                ok = float(np.abs(v0 - vL).max()) < 1e-3    # 端點相等(無縫)
                tag = "loop_seam"
            elif c == "intro":
                ok = mL < 1e-3                                # 尾收在 identity
                tag = "intro_tail0"
            elif c == "outro":
                ok = m0 < 1e-3                                # 首自 identity
                tag = "outro_head0"
            elif c == "pulse":
                ok = m0 < 1e-3 and mL < 1e-3                  # 首尾皆 identity
                tag = "pulse_ends0"
            else:
                ok = True; tag = "other"
            ac3["pass"] &= ok
            if not ok:
                ac3["detail"].append(f"{slot}/{att}/{beat}[{tag}] m0={m0:.4f} mL={mL:.4f}")
    R["AC3_seamless_identity"] = ac3

    # ---- AC4 非平凡 + 負對照鑑別力 ----
    ac4 = {"pass": True, "detail": {}}
    # (i) loop 每 mesh 最大位移 > 門檻
    loop_beat = next(b for b in md if cat_of(b) == "loop")
    nontrivial = True
    for slot, att in meshes:
        frames = md[loop_beat][skin_nm][slot][att]
        mx = max(float(np.abs(np.array(f["vertices"])).max()) for f in frames)
        ac4["detail"][f"loop_move::{slot}/{att}"] = round(mx, 2)
        nontrivial &= (mx > MIN_MOVE)
    # (ii) 負對照:把單一 hull 頂點拽過質心到對側 → 真正撕裂(自交/翻面)。
    #      (刻意**不**用均勻縮放:radial 均勻縮放 det=(1+s)²≥0 恆不翻面/自交,是本場族安全的原因,
    #       故不能當負對照;必須用非均勻的破壞場才能檢驗閘的鑑別力。)
    slot, att = meshes[2]  # shadow
    setup, tris, hull, nv = de.load_mesh(gen, slot, att)
    signs = [de.signed_area(setup, t) > 0 for t in tris]
    area = sum(abs(de.signed_area(setup, t)) for t in tris)
    cx, cy = setup[:, 0].mean(), setup[:, 1].mean()
    fold = np.zeros(2 * nv)
    fold[0] = -2.5 * (setup[0, 0] - cx)   # 頂點0 拽過質心到對側 → 鄰接三角互穿
    fold[1] = -2.5 * (setup[0, 1] - cy)
    r_fold = _eval_offsets(setup, tris, signs, area, fold)
    caught = (r_fold["self_intersections"] > 0 or r_fold["triangle_flips"] > 0)
    ac4["detail"]["neg_fold_caught"] = {"si": r_fold["self_intersections"], "flip": r_fold["triangle_flips"], "caught": caught}
    # (iii) 正對照:極端 shear(5×寬)仍乾淨(理論保證實證)
    slot2, att2 = meshes[0]  # curtain_left
    setup2, tris2, hull2, nv2 = de.load_mesh(gen, slot2, att2)
    signs2 = [de.signed_area(setup2, t) > 0 for t in tris2]
    area2 = sum(abs(de.signed_area(setup2, t)) for t in tris2)
    ymin, ymax = setup2[:, 1].min(), setup2[:, 1].max()
    xmin, xmax = setup2[:, 0].min(), setup2[:, 0].max()
    W5 = 5.0 * (xmax - xmin); H = max(ymax - ymin, 1e-6)
    shear = []
    for (x, y) in setup2:
        fy = (ymax - y) / H
        shear.extend([W5 * fy, 0.0])   # 巨幅 y 向剪切
    r_shear = _eval_offsets(setup2, tris2, signs2, area2, shear)
    shear_clean = r_shear["clean"]
    ac4["detail"]["pos_extreme_shear_clean"] = {"si": r_shear["self_intersections"], "flip": r_shear["triangle_flips"], "clean": shear_clean}
    ac4["pass"] = bool(nontrivial and caught and shear_clean)
    ac4["detail"]["nontrivial"] = nontrivial
    R["AC4_nontrivial_and_discrimination"] = ac4

    overall = all(R[k]["pass"] for k in R)
    R["_OVERALL_PASS"] = overall
    return R


if __name__ == "__main__":
    rep = run()
    print(json.dumps(rep, ensure_ascii=False, indent=2, default=lambda o: bool(o) if isinstance(o, (np.bool_,)) else o))
    print("\nOVERALL:", "PASS ✅" if rep["_OVERALL_PASS"] else "FAIL ❌")
    sys.exit(0 if rep["_OVERALL_PASS"] else 1)
