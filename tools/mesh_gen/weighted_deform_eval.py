#!/usr/bin/env python3
"""S3 — weighted-mesh 骨骼變形品質閘(補上唯一未驗維度)。

背景:deform_eval.py 只處理 unweighted mesh(deform timeline 逐頂點偏移)。
Award 機器人 3 個 mesh 件是 **weighted、無 deform timeline**,靠骨骼蒙皮變形。
compare_robot_mesh.py 只驗**靜態**覆蓋率 IoU,未涵蓋「骨骼拉扯下變形平滑度」。
本閘用 spine_skin 重現藝術家蒙皮變形,對綁定骨施加**真實動畫 pose**,量化拓樸品質。

⚠️ 校準原則(對照 RULES.md「變形閘用真實位移場,不要用未校準 stress_field」):
   pose 來源 = Award 自己的動畫 bone timeline(真值),不是合成 graded 旋轉。
   實測發現(見 knowledge/s3-weighted-deform-gate.md):
   - **In/Out = 入場/出場整體 squash/pop 過場**(光暈 Legend_In t=0 就 si=71、Legend_Out 縮到
     area 0.169 消失)→ 原始 mesh 幾何本就自交,是藝術家可接受的極短過場、視覺被遮/動態模糊掩蓋,
     **不是 mesh 品質訊號** → 只報告、不當 clean 閘。
   - **Loop = 穩態律動**,才是「變形平滑度」該乾淨的地方 → 作為 must-be-clean 真值。

三段(先確立評估器可信,再拿來判生成 mesh):
  AC_setup     :setup pose 蒙皮 mesh 乾淨(sanity + 蒙皮數學基本正確)。
  AC_loop_clean:所有 *_Loop 動畫 pose,藝術家 mesh 全程 0 自交/0 翻面/0 退化
                → 同時驗證蒙皮數學(錯的話真實旋轉會爆)+ 建立穩態平滑真值。PRIMARY。
  AC_discrim   :負對照 — 硬綁最近骨(單骨 w=1,骨界不連續)。在「藝術家仍乾淨」的最大放大倍率下,
                硬綁版出現可偵測自交/翻面 → 證明本閘有鑑別力(見 knowledge)。

通過 = 評估器可信,可作為 S3 生成 weighted mesh 的變形閘。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from spine_skin import (load_skeleton, compute_world, parse_weighted, skin_vertices,
                        get_attachment, mesh_bones)
from deform_eval import signed_area
from geom_fast import tri_edges, eval_pose_fast

ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


# ---------- 動畫 pose 取樣(真實 bone timeline;rotate/translate/scale 線性內插) ----------
def anim_overrides(sk, anim, time, amp=1.0):
    """回傳該動畫在 time 的每骨 override(相對 setup 的 delta;scale 為乘數)。
    amp!=1 時把偏移量放大(僅供 AC_discrim 壓力探測;delta 對 0 放大,scale 對 1 放大)。
    ⚠️ 限制:忽略 bezier curve(散鍵 {curve,c2..}),用線性內插近似;keyframe 上為精確值。"""
    ad = sk["animations"][anim]
    ov = {}
    for bname, tls in ad.get("bones", {}).items():
        e = {}
        for kind, frames in tls.items():
            ts = [f.get("time", 0.0) for f in frames]
            if time <= ts[0]:
                f = nf = frames[0]; a = 0.0
            elif time >= ts[-1]:
                f = nf = frames[-1]; a = 0.0
            else:
                i = max(j for j, t in enumerate(ts) if t <= time)
                f = frames[i]; nf = frames[i + 1]
                a = (time - ts[i]) / (ts[i + 1] - ts[i]) if ts[i + 1] > ts[i] else 0.0
            if kind == "rotate":
                e["rotation"] = (f.get("angle", 0) * (1 - a) + nf.get("angle", 0) * a) * amp
            elif kind == "translate":
                e["x"] = (f.get("x", 0) * (1 - a) + nf.get("x", 0) * a) * amp
                e["y"] = (f.get("y", 0) * (1 - a) + nf.get("y", 0) * a) * amp
            elif kind == "scale":
                sx = f.get("x", 1) * (1 - a) + nf.get("x", 1) * a
                sy = f.get("y", 1) * (1 - a) + nf.get("y", 1) * a
                e["scaleX"] = 1 + (sx - 1) * amp
                e["scaleY"] = 1 + (sy - 1) * amp
        ov[bname] = e
    return ov


def anim_times(sk, anim, sub=3):
    ad = sk["animations"][anim]
    ts = set()
    for tls in ad.get("bones", {}).values():
        for frames in tls.values():
            for f in frames:
                ts.add(f.get("time", 0.0))
    ts = sorted(ts)
    out = []
    for i, t in enumerate(ts):
        out.append(t)
        if i + 1 < len(ts):
            for s in range(1, sub):
                out.append(t + (ts[i + 1] - t) * s / sub)
    return out or [0.0]


def _mesh_ctx(sk, bones, n2i, slot):
    att = get_attachment(sk, slot)
    bind, nv = parse_weighted(att)
    tris = np.array(att["triangles"], np.int32).reshape(-1, 3)
    edges = tri_edges(tris)
    world0 = compute_world(bones, n2i)
    S = skin_vertices(world0, bind)
    signs = np.array([signed_area(S, t) > 0 for t in tris])
    area = sum(abs(signed_area(S, t)) for t in tris)
    return att, bind, nv, tris, edges, S, signs, area


def _worst_over(sk, bones, n2i, bind, tris, edges, signs, area, anims, amp=1.0, sub=3):
    wsi = wfl = wdg = 0
    ar = [9.9, 0.0]
    for anim in anims:
        for time in anim_times(sk, anim, sub):
            wp = compute_world(bones, n2i, anim_overrides(sk, anim, time, amp))
            r = eval_pose_fast(skin_vertices(wp, bind), tris, edges, signs, area)
            wsi = max(wsi, r["self_intersections"]); wfl = max(wfl, r["triangle_flips"])
            wdg = max(wdg, r["degenerate"])
            ar = [min(ar[0], r["area_ratio"]), max(ar[1], r["area_ratio"])]
    return {"max_self_intersections": wsi, "max_triangle_flips": wfl,
            "max_degenerate": wdg, "area_ratio_range": [round(ar[0], 3), round(ar[1], 3)]}


# ---------- 負對照:硬綁最近骨 ----------
def hard_bind(bones, world0, S, mb, nv):
    borig = {bi: np.array([world0[bi]["worldX"], world0[bi]["worldY"]]) for bi in mb}
    nb = []
    for vi in range(nv):
        p = S[vi]
        bi = min(mb, key=lambda b: float(np.hypot(*(p - borig[b]))))
        w = world0[bi]
        det = w["a"] * w["d"] - w["b"] * w["c"]
        dx = p[0] - w["worldX"]; dy = p[1] - w["worldY"]
        bx = (w["d"] * dx - w["b"] * dy) / det
        by = (-w["c"] * dx + w["a"] * dy) / det
        nb.append([(bi, bx, by, 1.0)])
    return nb


def procrustes_rms(S, U):
    S = S - S.mean(0); U = U - U.mean(0)
    S = S / np.sqrt((S ** 2).sum() / len(S)); U = U / np.sqrt((U ** 2).sum() / len(U))
    Uu, _, Vt = np.linalg.svd(S.T @ U)
    return float(np.sqrt(((S - U @ (Uu @ Vt).T) ** 2).sum(1).mean()))


def evaluate_piece(sk, bones, n2i, slot, loops, inout, amps, sub):
    att, bind, nv, tris, edges, S, signs, area = _mesh_ctx(sk, bones, n2i, slot)
    world0 = compute_world(bones, n2i)
    mb = mesh_bones(att)

    # AC_setup
    r0 = eval_pose_fast(S, tris, edges, signs, area)
    ac_setup = {"self_intersections": r0["self_intersections"],
                "triangle_flips": r0["triangle_flips"],
                "pass": r0["self_intersections"] == 0 and r0["triangle_flips"] == 0}

    # AC_loop_clean(藝術家 mesh 在 Loop pose 全程乾淨)
    loop_art = _worst_over(sk, bones, n2i, bind, tris, edges, signs, area, loops, 1.0, sub)
    ac_loop = {**loop_art,
               "pass": (loop_art["max_self_intersections"] == 0 and
                        loop_art["max_triangle_flips"] == 0 and
                        loop_art["max_degenerate"] == 0)}

    # In/Out 過場(僅報告,不當閘)
    io_art = _worst_over(sk, bones, n2i, bind, tris, edges, signs, area, inout, 1.0, sub) if inout else {}

    # AC_discrim(硬綁負對照;找「藝術家仍乾淨」的最大 amp,硬綁應壞)
    hb = hard_bind(bones, world0, S, mb, nv)
    discrim = []
    found = False
    for amp in amps:
        art = _worst_over(sk, bones, n2i, bind, tris, edges, signs, area, loops, amp, sub)
        art_clean = (art["max_self_intersections"] == 0 and art["max_triangle_flips"] == 0)
        hbw = _worst_over(sk, bones, n2i, hb, tris, edges, signs, area, loops, amp, sub)
        hb_bad = (hbw["max_self_intersections"] > 0 or hbw["max_triangle_flips"] > 0)
        discrim.append({"amp": amp, "artist_clean": art_clean,
                        "hardbind_si": hbw["max_self_intersections"],
                        "hardbind_flips": hbw["max_triangle_flips"]})
        if art_clean and hb_bad:
            found = True
    ac_discrim = {"pass": found, "probes": discrim}

    piece_pass = ac_setup["pass"] and ac_loop["pass"] and ac_discrim["pass"]
    return {
        "nv": nv, "bones": [bones[i]["name"] for i in mb],
        "procrustes_rms_setup_vs_uv": round(procrustes_rms(S, np.array(att["uvs"]).reshape(-1, 2)), 4),
        "AC_setup": ac_setup,
        "AC_loop_clean": ac_loop,
        "inout_transient_report": io_art,
        "AC_discrim": ac_discrim,
        "piece_pass": piece_pass,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--amps", default="1,2,3,5")
    ap.add_argument("--sub", type=int, default=3)
    a = ap.parse_args()
    amps = [float(x) for x in a.amps.split(",")]
    sk, bones, n2i = load_skeleton(a.skeleton)
    loops = [x for x in sk["animations"] if x.endswith("_Loop")]
    inout = [x for x in sk["animations"] if x.endswith("_In") or x.endswith("_Out")]
    out = {"skeleton": a.skeleton, "loops": loops,
           "note": "In/Out=入出場過場(整體 squash/pop),只報告不當閘;Loop=穩態,must-be-clean",
           "pieces": {}}
    ok = True
    for slot in ROBOT_MESHES:
        p = evaluate_piece(sk, bones, n2i, slot, loops, inout, amps, a.sub)
        out["pieces"][slot] = p
        ok = ok and p["piece_pass"]
    out["evaluator_trustworthy"] = ok
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
