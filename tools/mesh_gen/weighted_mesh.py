"""S3 weighted-mesh deformation evaluator (CPU, no Spine runtime).

Reproduces Spine 3.8 bone world-transform (TransformMode.Normal) + Linear Blend
Skinning (LBS) in pure Python, so we can quantify *bone-driven* weighted-mesh
deformation quality — the one dimension `compare_robot_mesh.py` could not check
(static IoU passes but says nothing about how smoothly a bone-weighted mesh bends).

Truth source: the artist weighted meshes in `assets/Award.json` (機器人拆件/身體,
左手, 光暈) carry real bind coords + per-vertex weights + a real bone hierarchy.

Validation strategy (why the LBS/world-transform code can be trusted):
  * AC1 bind-consistency — for every multi-bone vertex, each influence stores the
    vertex's setup position expressed in *that bone's* local frame. Transforming
    each bind by its bone's setup-pose world transform must land on the SAME world
    point. Agreement to sub-pixel proves both the parse and the world-transform.
  * self-intersection / triangle-flip (reused from deform_eval) under a bend pose.
  * strain-smoothness metric: variance of the per-triangle deformation gradient
    across adjacent triangles (lower = smoother bend; this is the internal-density
    lever we will hold generated meshes to next).

Usage:
  python3 tools/mesh_gen/weighted_mesh.py            # validate against Award truth
"""
import json
import math
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from deform_eval import check, eval_pose, signed_area  # noqa: E402

DEG = math.pi / 180.0


# ---------- skeleton ----------
def load_skeleton(path):
    d = json.load(open(path))
    bones = d["bones"]
    idx = {b["name"]: i for i, b in enumerate(bones)}
    for b in bones:
        b["_parent"] = idx.get(b.get("parent")) if b.get("parent") else None
    return bones, idx


def compute_world(bones, pose=None):
    """World 2x3 affine [a,b,c,d,wx,wy] per bone. TransformMode.Normal only.

    pose: optional {bone_name: {"rotation":deg, "x":dx, "y":dy}} local deltas.
    """
    pose = pose or {}
    world = [None] * len(bones)

    def compute(i):
        if world[i] is not None:
            return world[i]
        b = bones[i]
        p = pose.get(b["name"], {})
        rot = (b.get("rotation", 0.0) + p.get("rotation", 0.0)) * DEG
        sx = b.get("scaleX", 1.0)
        sy = b.get("scaleY", 1.0)
        x = b.get("x", 0.0) + p.get("x", 0.0)
        y = b.get("y", 0.0) + p.get("y", 0.0)
        cos, sin = math.cos(rot), math.sin(rot)
        la, lb, lc, ld = cos * sx, -sin * sy, sin * sx, cos * sy
        par = b["_parent"]
        if par is None:
            world[i] = [la, lb, lc, ld, x, y]
        else:
            pa, pb, pc, pd, pwx, pwy = compute(par)
            world[i] = [
                pa * la + pb * lc, pa * lb + pb * ld,
                pc * la + pd * lc, pc * lb + pd * ld,
                pa * x + pb * y + pwx, pc * x + pd * y + pwy,
            ]
        return world[i]

    for i in range(len(bones)):
        compute(i)
    return world


def _apply(m, px, py):
    return (m[0] * px + m[1] * py + m[4], m[2] * px + m[3] * py + m[5])


# ---------- weighted mesh ----------
def parse_weighted(att):
    """Spine flattened weighted vertices -> per-vertex influences [(bone,bx,by,w)]."""
    V = att["vertices"]
    uvs = att["uvs"]
    n = len(uvs) // 2
    verts, i = [], 0
    while i < len(V):
        bc = int(V[i]); i += 1
        infl = []
        for _ in range(bc):
            infl.append((int(V[i]), V[i + 1], V[i + 2], V[i + 3])); i += 4
        verts.append(infl)
    assert len(verts) == n, (len(verts), n)
    tris = [att["triangles"][k:k + 3] for k in range(0, len(att["triangles"]), 3)]
    return {"verts": verts, "triangles": tris, "hull": att.get("hull", 0), "uvs": uvs}


def is_weighted(att):
    return att.get("type") == "mesh" and len(att["vertices"]) != len(att["uvs"])


def skin(verts, world):
    """Linear blend skinning -> Nx2 world positions."""
    out = np.zeros((len(verts), 2))
    for vi, infl in enumerate(verts):
        x = y = 0.0
        for (bi, bx, by, w) in infl:
            wx, wy = _apply(world[bi], bx, by)
            x += w * wx; y += w * wy
        out[vi] = (x, y)
    return out


def bind_consistency(verts, world):
    """AC1: multi-bone verts — spread of per-influence world positions (px)."""
    spreads = []
    for infl in verts:
        if len(infl) < 2:
            continue
        pts = [_apply(world[bi], bx, by) for (bi, bx, by, _w) in infl]
        pts = np.array(pts)
        c = pts.mean(0)
        spreads.append(float(np.linalg.norm(pts - c, axis=1).max()))
    if not spreads:
        return {"multi_bone_verts": 0, "max_spread_px": 0.0, "mean_spread_px": 0.0}
    return {"multi_bone_verts": len(spreads),
            "max_spread_px": round(max(spreads), 4),
            "mean_spread_px": round(float(np.mean(spreads)), 4)}


# ---------- deformation quality ----------
def _tri_grad(P, Q, t):
    """2x2 deformation gradient F: setup edges -> deformed edges for triangle t."""
    Ds = np.array([P[t[1]] - P[t[0]], P[t[2]] - P[t[0]]]).T
    Dm = np.array([Q[t[1]] - Q[t[0]], Q[t[2]] - Q[t[0]]]).T
    if abs(np.linalg.det(Ds)) < 1e-9:
        return None
    return Dm @ np.linalg.inv(Ds)


def strain_smoothness(setup, deformed, tris):
    """Mean Frobenius diff of deformation gradient across edge-adjacent triangles.

    Lower = smoother bend. Rigid motion -> F equal everywhere -> 0.
    """
    grads = {}
    for i, t in enumerate(tris):
        F = _tri_grad(setup, deformed, t)
        if F is not None:
            grads[i] = F
    edge2tri = {}
    for i, t in enumerate(tris):
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            edge2tri.setdefault((min(a, b), max(a, b)), []).append(i)
    diffs = []
    for tl in edge2tri.values():
        if len(tl) == 2 and tl[0] in grads and tl[1] in grads:
            diffs.append(float(np.linalg.norm(grads[tl[0]] - grads[tl[1]])))
    if not diffs:
        return {"adjacent_pairs": 0, "mean": 0.0, "max": 0.0}
    return {"adjacent_pairs": len(diffs),
            "mean": round(float(np.mean(diffs)), 4),
            "max": round(max(diffs), 4)}


def deform_eval(mesh, bones, pose):
    """Full weighted-deform report for one bone pose."""
    world0 = compute_world(bones, None)
    world1 = compute_world(bones, pose)
    setup = skin(mesh["verts"], world0)
    deformed = skin(mesh["verts"], world1)
    tris = mesh["triangles"]
    setup_signs = [signed_area(setup, t) > 0 for t in tris]
    setup_area = sum(abs(signed_area(setup, t)) for t in tris)
    r = eval_pose(deformed, tris, setup_signs, setup_area)
    r["smoothness"] = strain_smoothness(setup, deformed, tris)
    return r


# ---------- validation against Award truth ----------
PARTS = {
    # pose = a modest, within-tolerance bend used as the smoothness baseline;
    # drivers = the bones swept to measure each part's bend tolerance.
    "身體": {"slot": "機器人拆件/身體",
             "pose": {"4_LEG7": {"rotation": 18}, "4_LEG8": {"rotation": -18}},
             "drivers": ["4_LEG7", "4_LEG8"]},
    "左手": {"slot": "機器人拆件/左手", "pose": {"4_LEG9": {"rotation": 35}},
             "drivers": ["4_LEG9"]},
    "光暈": {"slot": "機器人拆件/光暈", "pose": {"4_LEG6": {"rotation": 12}},
             "drivers": ["4_LEG6"]},
}


def bend_tolerance(mesh, bones, drivers, hi=70, step=2):
    """Largest antagonistic single-step bend (deg) that stays clean. Drivers
    alternate sign so multi-bone parts get a genuine differential bend."""
    last = 0
    for ang in range(step, hi + 1, step):
        pose = {b: {"rotation": ang * (1 if i % 2 == 0 else -1)}
                for i, b in enumerate(drivers)}
        if deform_eval(mesh, bones, pose)["clean"]:
            last = ang
        else:
            return last, False
    return last, True  # clean through the whole sweep


def _get_att(skins, slot):
    atts = {s["name"]: s["attachments"] for s in skins}["default"]
    return atts[slot][slot]


def validate(path):
    d = json.load(open(path))
    bones, _ = load_skeleton(path)
    skins = d["skins"]
    print("=== weighted-mesh deform evaluator: Award truth validation ===")
    all_ok = True
    for label, cfg in PARTS.items():
        att = _get_att(skins, cfg["slot"])
        mesh = parse_weighted(att)
        world0 = compute_world(bones, None)
        bc = bind_consistency(mesh["verts"], world0)
        # AC1: multi-bone bind positions must agree sub-pixel at setup
        ac1 = bc["multi_bone_verts"] == 0 or bc["max_spread_px"] < 1.0
        rep = deform_eval(mesh, bones, cfg["pose"])
        ac2 = rep["clean"]  # baseline bend produces no self-intersection / flip
        tol, full = bend_tolerance(mesh, bones, cfg["drivers"])
        n = len(mesh["verts"])
        print(f"\n[{label}] n={n} hull={mesh['hull']} internal={n - mesh['hull']} "
              f"tris={len(mesh['triangles'])}")
        print(f"  AC1 bind-consistency: multi={bc['multi_bone_verts']} "
              f"max_spread={bc['max_spread_px']}px mean={bc['mean_spread_px']}px "
              f"-> {'PASS' if ac1 else 'FAIL'}")
        print(f"  AC2 baseline bend clean: self_x={rep['self_intersections']} "
              f"flips={rep['triangle_flips']} degen={rep['degenerate']} "
              f"area_ratio={rep['area_ratio']} -> {'PASS' if ac2 else 'FAIL'}")
        print(f"  bend-tolerance (max clean differential bend): "
              f"{('>=' + str(tol)) if full else tol} deg")
        print(f"  strain-smoothness (artist baseline): mean={rep['smoothness']['mean']} "
              f"max={rep['smoothness']['max']} over {rep['smoothness']['adjacent_pairs']} pairs")
        all_ok = all_ok and ac1 and ac2
    return all_ok


def negative_control(path):
    """Sanity: a bogus world-transform (skip parent chain) must break bind-consistency."""
    d = json.load(open(path))
    bones, _ = load_skeleton(path)
    att = _get_att(d["skins"], PARTS["身體"]["slot"])
    mesh = parse_weighted(att)
    flat = [dict(b, _parent=None) for b in bones]  # break hierarchy
    bad = bind_consistency(mesh["verts"], compute_world(flat, None))
    print("\n=== negative control (broken hierarchy) ===")
    print(f"  max_spread={bad['max_spread_px']}px (should be >> 1px) -> "
          f"{'PASS' if bad['max_spread_px'] > 5.0 else 'FAIL'}")
    return bad["max_spread_px"] > 5.0


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_HERE, "..", "..", "assets", "Award.json")
    ok = validate(p)
    neg = negative_control(p)
    print(f"\nOVERALL: {'PASS' if ok and neg else 'FAIL'}")
    sys.exit(0 if ok and neg else 1)
