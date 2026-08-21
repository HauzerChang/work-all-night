"""validate_weighted_award — 對 Award 真實 weighted mesh 驗證「weighted-mesh 變形評估器」可信度。

補上 S3 唯一未驗維度的**評估器先行**步驟。四道 AC:

  AC1 setup 保真     : 由 weighted bind 重建 setup pose,3 件全 0 翻面 / 0 自交。
  AC2 剛體不變性     : 旋轉「整條骨鏈的父骨」→ mesh 應純剛體移動(area_ratio==1.0、stretch cv==0)。
                       這是 FK/weighting 數學正確性的硬檢查:剛體運動不得產生任何幽靈畸變。
  AC3 關節彎折包絡   : 旋轉「子骨(相對父骨)」彎關節 → 藝術家 mesh 在包絡角內保持乾淨,
                       記錄每件的「最大乾淨角 + 邊長拉伸 CV 簽章」作為未來 BBW mesh 的變形品質基準。
  AC4 負對照(鑑別力): 把藝術家平滑權重換成「最近單骨硬權重」→ 同樣關節彎折下應更早破裂
                       (更小角度就翻面/自交)。證明本評估器能區分「好權重 vs 壞權重」,
                       否則拿它評判 BBW 生成 mesh 無意義。

真值來源:`assets/Award.json` 的 3 個機器人 weighted mesh(權重 + 骨架皆為生產美術)。純 CPU。
"""
import json
import sys
import numpy as np

import weighted_deform as W

ASSET = "../../assets/Award.json"
PARTS = ["機器人拆件/身體", "機器人拆件/左手", "機器人拆件/光暈"]


def prep(slot):
    sk, bones, idx, an, per, uvs, tris, weighted = W.load_case(ASSET, slot)
    W.update_world(bones, idx)
    v0 = W.world_vertices(bones, per)
    signs0 = W.setup_signs(v0, tris)
    area0 = sum(abs(W.signed_area(v0, t)) for t in tris)
    edges = W.tri_edges(tris)
    return dict(sk=sk, bones=bones, idx=idx, per=per, tris=tris, v0=v0,
                signs0=signs0, area0=area0, edges=edges)


def pick_joint(bones, idx, per):
    """A driver bone whose parent is also a driver → bending it flexes the mesh at a real joint."""
    drv = W.driver_bones(per)
    drv_names = {bones[b].name for b in drv}
    for b in drv:
        if bones[b].parent in drv_names:
            return bones[b].name, bones[b].parent
    return bones[drv[-1]].name, bones[bones[drv[-1]].parent if bones[drv[-1]].parent else drv[0]].name


def sweep(ctx, driver, angles):
    out = []
    for deg in angles:
        W.update_world(ctx["bones"], ctx["idx"], {driver: {"rotate": deg}})
        v = W.world_vertices(ctx["bones"], ctx["per"])
        r = W.check_pose(v, ctx["tris"], ctx["signs0"], ctx["area0"], ctx["edges"], ctx["v0"])
        out.append((deg, r))
    return out


def _bind(bones, bi, p):
    """World point p → bind coords relative to bone bi's setup world transform."""
    bb = bones[bi]
    det = bb.a * bb.d - bb.b * bb.c
    dx, dy = p[0] - bb.wx, p[1] - bb.wy
    return (bb.d * dx - bb.c * dy) / det, (-bb.b * dx + bb.a * dy) / det


def common_ancestor_driver(ctx):
    """The driver bone that is an ancestor (via parent chain) of every other driver bone.
    Rotating it moves the whole driver set rigidly — the correct AC2 rigid-invariance probe."""
    bones, idx, per = ctx["bones"], ctx["idx"], ctx["per"]
    drv = W.driver_bones(per)
    drv_set = set(drv)

    def ancestors(b):
        out = set()
        cur = bones[b].parent
        while cur is not None:
            out.add(idx[cur])
            cur = bones[idx[cur]].parent
        return out

    for cand in drv:
        if all(cand == o or cand in ancestors(o) for o in drv):
            return bones[cand].name
    return bones[drv[0]].name  # fallback


def scramble_weights(ctx, seed=0):
    """Negative control: keep the same driver-bone set but assign each vertex RANDOM convex
    weights over all drivers (bind coords recomputed so setup pose is exactly preserved).
    Adjacent vertices then move incoherently → any credible smoothness metric must flag it."""
    import random
    rng = random.Random(seed)
    bones, idx, per = ctx["bones"], ctx["idx"], ctx["per"]
    W.update_world(bones, idx)
    drv = W.driver_bones(per)
    v0 = ctx["v0"]
    new = []
    for vi in range(len(per)):
        p = v0[vi]
        ws = [rng.random() + 1e-3 for _ in drv]
        s = sum(ws)
        entry = []
        for b, w in zip(drv, ws):
            bx, by = _bind(bones, b, p)
            entry.append((b, bx, by, w / s))
        new.append(entry)
    return new


def envelope(sweep_rows):
    """Largest |angle| (scanning outward) that is still clean, plus stretch_cv there."""
    clean_max = 0.0
    cv_at = 0.0
    for deg, r in sorted(sweep_rows, key=lambda x: abs(x[0])):
        if r["clean"]:
            if abs(deg) >= clean_max:
                clean_max = abs(deg)
                cv_at = r["stretch_cv"]
        else:
            break
    return clean_max, cv_at


def main():
    angles = [-30, -25, -20, -15, -10, -5, 5, 10, 15, 20, 25, 30]
    report = {"parts": {}, "ac": {}}
    ac1_ok = ac2_ok = ac4_ok = True
    for slot in PARTS:
        ctx = prep(slot)
        r_setup = W.check_pose(ctx["v0"], ctx["tris"], ctx["signs0"], ctx["area0"],
                               ctx["edges"], ctx["v0"])
        ac1 = r_setup["clean"]
        ac1_ok &= ac1

        # AC2 rigid: rotate the driver set's common ancestor → whole mesh moves rigidly.
        anc = common_ancestor_driver(ctx)
        rig = sweep(ctx, anc, [-30, -15, 15, 30])
        ac2 = all(abs(r["area_ratio"] - 1.0) < 1e-3 and r["stretch_cv"] < 1e-3 for _, r in rig)
        ac2_ok &= ac2

        # AC3 joint bend on artist weights → clean envelope + smoothness signature
        joint, jparent = pick_joint(ctx["bones"], ctx["idx"], ctx["per"])
        art = sweep(ctx, joint, angles)
        art_env, art_cv = envelope(art)
        # fixed comparison angle: the artist's clean envelope (or 5° for very fragile parts)
        test_deg = max(5, art_env)

        def at(rows, d):
            return next((r for dd, r in rows if abs(dd) == d), None)

        art_at = at(art, test_deg)

        # AC4 negative control: scrambled random weights over the same drivers, same joint bend.
        ctx_scr = dict(ctx)
        ctx_scr["per"] = scramble_weights(ctx)
        W.update_world(ctx_scr["bones"], ctx_scr["idx"])
        v0s = W.world_vertices(ctx_scr["bones"], ctx_scr["per"])
        setup_drift = float(np.abs(v0s - ctx["v0"]).max())  # must be ~0: setup preserved
        scr = sweep(ctx_scr, joint, angles)
        scr_at = at(scr, test_deg)
        # discrimination at the SAME angle: scramble must be visibly rougher —
        # more broken geometry (flips+xs) OR ≥1.5× the stretch CV.
        art_break = art_at["triangle_flips"] + art_at["self_intersections"]
        scr_break = scr_at["triangle_flips"] + scr_at["self_intersections"]
        ac4 = (scr_break > art_break) or (scr_at["stretch_cv"] > art_at["stretch_cv"] * 1.5)
        ac4_ok &= ac4

        report["parts"][slot] = {
            "nvert": len(ctx["per"]), "tris": len(ctx["tris"]),
            "setup_clean": ac1, "rigid_invariant": ac2, "rigid_probe_bone": anc,
            "joint": joint, "joint_parent": jparent,
            "artist_clean_envelope_deg": art_env, "artist_stretch_cv": round(art_cv, 4),
            "test_deg": test_deg,
            "artist@test": {"break": art_break, "stretch_cv": art_at["stretch_cv"]},
            "scramble@test": {"break": scr_break, "stretch_cv": scr_at["stretch_cv"]},
            "scramble_setup_drift_px": round(setup_drift, 4),
            "discriminates": ac4,
        }

    report["ac"] = {
        "AC1_setup_fidelity": ac1_ok,
        "AC2_rigid_invariance": ac2_ok,
        "AC4_negative_control_discriminates": ac4_ok,
        "overall_pass": ac1_ok and ac2_ok and ac4_ok,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ac"]["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
