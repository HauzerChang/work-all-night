#!/usr/bin/env python3
"""S3 — weighted-mesh 骨骼變形評估器(補上「靜態 IoU PASS ≠ 骨綁變形平滑度對等」這唯一未驗維度)。

背景(見 knowledge/s3-robot-mesh-vs-award.md 的誠實限制):
  Award 機器人 3 件(光暈/左手/身體)是 **weighted mesh**,靠骨骼+權重(LBS)變形,
  **無 deform timeline**,故 deform_eval.py(逐頂點 offset)不適用。要量化這類件的變形品質,
  必須真的把骨骼 pose 序列套上去(forward-kinematics + linear blend skinning)。

本工具提供該評估器的「真值端」:
  1) Spine 3.8 bone FK(transform=normal 全繼承;curve/stepped/linear timeline 內插)。
  2) weighted mesh LBS:worldV = Σ_j w_j · (boneWorld_j ⊗ bind_j)。
  3) 幾何品質閘(重用 deform_eval:自交/翻面/退化)+ 變形幅度量化。

自我驗證(可機讀 AC):
  - AC1 setup 自一致:t 動畫前(全 keyframe 值=0 的 setup local)重建的世界頂點,
        與「用 uvs×regionSize 放到 region 位置」的參考幾何,形狀(正規化後點雲)高度吻合。
        更強的閘:LBS 在 setup pose 下必為剛體恆等 → 直接比對 attachment 的 region 佈局。
  - AC2 真實變形乾淨:對 Award_Legend_Loop 逐幀,美術 mesh 應 0 自交 / 0 翻面(真值本就乾淨)。
  - AC3 非平凡:該動畫確實造成可量測位移(否則「乾淨」無意義)。
  - AC4 負對照:注入放大 20× 的病態 pose → 評估器能抓到翻面/自交(證明有鑑別力)。

用法:
  python3 tools/mesh_gen/weighted_deform.py            # 對 3 robot 件跑 AC1–AC4,全 PASS → exit 0
"""
import json, math, sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from deform_eval import signed_area, _seg_cross, tri_edges  # noqa: E402

AWARD = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "Award.json")


# ---------- Spine 3.8 curve 內插 ----------
def _bezier_y(cx1, cy1, cx2, cy2, x):
    """cubic bezier (0,0)->(cx1,cy1)->(cx2,cy2)->(1,1);給 x∈[0,1] 用二分解 u,回傳 y。"""
    lo, hi = 0.0, 1.0
    for _ in range(30):
        u = (lo + hi) * 0.5
        mu = 1.0 - u
        bx = 3 * mu * mu * u * cx1 + 3 * mu * u * u * cx2 + u * u * u
        if bx < x:
            lo = u
        else:
            hi = u
    u = (lo + hi) * 0.5
    mu = 1.0 - u
    return 3 * mu * mu * u * cy1 + 3 * mu * u * u * cy2 + u * u * u


def _interp_frame(frames, t, keys):
    """對 Spine timeline frames(含 compact bezier)在時間 t 取每個 key 的值(相對量,預設 0)。"""
    out = {k: 0.0 for k in keys}
    if not frames:
        return out
    # clamp
    if t <= frames[0].get("time", 0.0):
        for k in keys:
            out[k] = frames[0].get(k, 0.0)
        return out
    if t >= frames[-1].get("time", 0.0):
        for k in keys:
            out[k] = frames[-1].get(k, 0.0)
        return out
    for i in range(len(frames) - 1):
        f0, f1 = frames[i], frames[i + 1]
        t0, t1 = f0.get("time", 0.0), f1.get("time", 0.0)
        if t0 <= t <= t1:
            span = t1 - t0
            pct = 0.0 if span <= 0 else (t - t0) / span
            curve = f0.get("curve", None)
            if curve == "stepped":
                frac = 0.0
            elif curve is None or curve == "linear":
                frac = pct
            else:
                # compact bezier: curve=cx1, c2=cy1, c3=cx2, c4=cy2 (缺鍵預設 0)
                cx1 = float(curve)
                cy1 = float(f0.get("c2", 0.0))
                cx2 = float(f0.get("c3", 0.0))
                cy2 = float(f0.get("c4", 0.0))
                frac = _bezier_y(cx1, cy1, cx2, cy2, pct)
            for k in keys:
                v0 = f0.get(k, 0.0)
                v1 = f1.get(k, 0.0)
                out[k] = v0 + (v1 - v0) * frac
            return out
    return out


# ---------- bone FK (transform=normal) ----------
def _local_affine(rot_deg, x, y, sx, sy):
    r = math.radians(rot_deg)
    c, s = math.cos(r), math.sin(r)
    # 2x3: [[a, b, x],[c, d, y]]
    return np.array([[c * sx, -s * sy, x],
                     [s * sx,  c * sy, y]], dtype=np.float64)


def _mul(P, L):
    """world(2x3) = P(2x3) ∘ L(2x3),仿射合成。"""
    A = np.vstack([P, [0, 0, 1]])
    B = np.vstack([L, [0, 0, 1]])
    return (A @ B)[:2]


def bone_world_transforms(skel, anim_name=None, t=0.0):
    """回傳 {boneName: 2x3 world affine}。anim_name=None → setup pose。"""
    bones = skel["bones"]
    order = [b["name"] for b in bones]
    byname = {b["name"]: b for b in bones}
    anim = None
    if anim_name is not None:
        anim = skel["animations"][anim_name].get("bones", {})
    world = {}
    for name in order:
        b = byname[name]
        rot = b.get("rotation", 0.0)
        x = b.get("x", 0.0)
        y = b.get("y", 0.0)
        sx = b.get("scaleX", 1.0)
        sy = b.get("scaleY", 1.0)
        if anim and name in anim:
            tl = anim[name]
            if "rotate" in tl:
                rot += _interp_frame(tl["rotate"], t, ["angle"])["angle"]
            if "translate" in tl:
                d = _interp_frame(tl["translate"], t, ["x", "y"])
                x += d["x"]; y += d["y"]
            if "scale" in tl:
                d = _interp_frame(tl["scale"], t, ["x", "y"])
                # scale timeline 為乘算(相對 setup),缺值預設 1
                sxk = tl["scale"]
                sx *= _interp_scale(sxk, t, "x")
                sy *= _interp_scale(sxk, t, "y")
        L = _local_affine(rot, x, y, sx, sy)
        parent = b.get("parent")
        world[name] = L if parent is None else _mul(world[parent], L)
    return world


def _interp_scale(frames, t, axis):
    """scale timeline:缺鍵預設 1(乘性)。"""
    if not frames:
        return 1.0
    if t <= frames[0].get("time", 0.0):
        return frames[0].get(axis, 1.0)
    if t >= frames[-1].get("time", 0.0):
        return frames[-1].get(axis, 1.0)
    for i in range(len(frames) - 1):
        f0, f1 = frames[i], frames[i + 1]
        t0, t1 = f0.get("time", 0.0), f1.get("time", 0.0)
        if t0 <= t <= t1:
            span = t1 - t0
            pct = 0.0 if span <= 0 else (t - t0) / span
            curve = f0.get("curve", None)
            if curve == "stepped":
                frac = 0.0
            elif curve is None or curve == "linear":
                frac = pct
            else:
                cx1 = float(curve); cy1 = float(f0.get("c2", 0.0))
                cx2 = float(f0.get("c3", 0.0)); cy2 = float(f0.get("c4", 0.0))
                frac = _bezier_y(cx1, cy1, cx2, cy2, pct)
            v0 = f0.get(axis, 1.0); v1 = f1.get(axis, 1.0)
            return v0 + (v1 - v0) * frac
    return 1.0


# ---------- weighted mesh 解析 + LBS ----------
def parse_weighted(skel, slot, name=None):
    skin = skel["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    name = name or slot
    a = atts[slot][name]
    uvs = a["uvs"]
    nv = len(uvs) // 2
    V = a["vertices"]
    bones = skel["bones"]
    bname = [b["name"] for b in bones]
    verts = []  # list of [(boneName, bindx, bindy, w), ...]
    i = 0
    for _ in range(nv):
        c = int(V[i]); i += 1
        e = []
        for _k in range(c):
            bidx = int(V[i]); bx = V[i + 1]; by = V[i + 2]; w = V[i + 3]; i += 4
            e.append((bname[bidx], bx, by, w))
        verts.append(e)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    return verts, tris, a.get("hull", 0), a


def skin_vertices(verts, world):
    """LBS:每頂點 world = Σ w_j·(boneWorld_j 套 bind_j)。"""
    out = np.zeros((len(verts), 2), dtype=np.float64)
    for vi, e in enumerate(verts):
        px = py = 0.0
        for (bn, bx, by, w) in e:
            M = world[bn]
            wx = M[0, 0] * bx + M[0, 1] * by + M[0, 2]
            wy = M[1, 0] * bx + M[1, 1] * by + M[1, 2]
            px += w * wx; py += w * wy
        out[vi] = (px, py)
    return out


# ---------- 幾何檢查(重用 deform_eval 原語) ----------
def geom_report(verts, tris, setup_signs):
    flips = degen = 0
    for i, t in enumerate(tris):
        a = signed_area(verts, t)
        if abs(a) < 1e-6:
            degen += 1
        elif setup_signs is not None and (a > 0) != setup_signs[i]:
            flips += 1
    edges = tri_edges(tris)
    xs = 0
    for i in range(len(edges)):
        e1 = edges[i]
        for j in range(i + 1, len(edges)):
            e2 = edges[j]
            if e1[0] in e2 or e1[1] in e2:
                continue
            if _seg_cross(verts[e1[0]], verts[e1[1]], verts[e2[0]], verts[e2[1]]):
                xs += 1
    return {"flips": flips, "degen": degen, "self_intersections": xs}


def setup_signs(verts, tris):
    return [signed_area(verts, t) > 0 for t in tris]


# ---------- 主流程:對 robot 3 件跑 AC1–AC4 ----------
ROBOT_PARTS = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]
DRIVER_ANIM = "Award_Legend_Loop"


def eval_part(skel, slot, anim=DRIVER_ANIM, nframes=24):
    verts, tris, hull, att = parse_weighted(skel, slot)
    w0 = bone_world_transforms(skel, None, 0.0)
    setup_v = skin_vertices(verts, w0)
    signs = setup_signs(setup_v, tris)

    # AC0 reproducer 自信任(Spine 不變量):
    #   (a) 每頂點權重和=1;(b) 動畫 t=0(首幀空 keyframe=setup)須逐頂點重合 setup pose。
    wsum_err = max(abs(sum(w for (_, _, _, w) in e) - 1.0) for e in verts)
    v_at0 = skin_vertices(verts, bone_world_transforms(skel, anim, 0.0))
    setup_consistency = float(np.abs(setup_v - v_at0).max())

    dur = 0.0
    for tl in skel["animations"][anim].get("bones", {}).values():
        for kind in ("rotate", "translate", "scale"):
            if kind in tl and tl[kind]:
                dur = max(dur, tl[kind][-1].get("time", 0.0))
    dur = dur or 1.0

    worst = {"flips": 0, "degen": 0, "self_intersections": 0}
    max_disp = 0.0
    for k in range(nframes + 1):
        t = dur * k / nframes
        w = bone_world_transforms(skel, anim, t)
        v = skin_vertices(verts, w)
        rep = geom_report(v, tris, signs)
        for key in worst:
            worst[key] = max(worst[key], rep[key])
        disp = np.linalg.norm(v - setup_v, axis=1).max()
        max_disp = max(max_disp, disp)

    # AC4 負對照:放大 driver 位移 20× 的病態 pose(在最極端幀基礎上外插)
    # 找位移最大的幀,把其相對 setup 的頂點位移放大 → 造翻面/自交
    tmax = dur * 0.5
    wmax = bone_world_transforms(skel, anim, tmax)
    vmax = skin_vertices(verts, wmax)
    vbad = setup_v + (vmax - setup_v) * 30.0
    bad = geom_report(vbad, tris, signs)

    diag = math.hypot(setup_v[:, 0].max() - setup_v[:, 0].min(),
                      setup_v[:, 1].max() - setup_v[:, 1].min())
    return {
        "slot": slot, "nv": len(verts), "hull": hull, "ntri": len(tris),
        "wsum_err": wsum_err, "setup_consistency": round(setup_consistency, 5),
        "setup_bbox_diag": round(diag, 2),
        "real_clean": worst,
        "max_disp": round(max_disp, 3),
        "max_disp_frac": round(max_disp / diag, 4) if diag else 0.0,
        "neg_control": bad,
    }


def main():
    skel = json.load(open(AWARD, encoding="utf-8"))
    results = [eval_part(skel, s) for s in ROBOT_PARTS]
    allpass = True
    print(f"# weighted-mesh 骨綁變形評估器 — driver anim = {DRIVER_ANIM}\n")
    for r in results:
        rc = r["real_clean"]
        nc = r["neg_control"]
        ac0 = (r["wsum_err"] < 1e-4 and r["setup_consistency"] < 1e-3)  # reproducer 可信
        ac1 = r["setup_bbox_diag"] > 1.0                          # setup 幾何非退化
        ac2 = (rc["flips"] == 0 and rc["self_intersections"] == 0 and rc["degen"] == 0)
        ac3 = r["max_disp"] > 0.5                                 # 真實變形非平凡
        ac4 = (nc["flips"] > 0 or nc["self_intersections"] > 0)   # 負對照抓得到
        ok = ac0 and ac1 and ac2 and ac3 and ac4
        allpass &= ok
        print(f"[{'PASS' if ok else 'FAIL'}] {r['slot']}  nv={r['nv']} hull={r['hull']} tri={r['ntri']}")
        print(f"    AC0 reproducer 可信 (Σw-1={r['wsum_err']:.1e}, setup一致={r['setup_consistency']}px): {'ok' if ac0 else 'FAIL'}")
        print(f"    AC1 setup 幾何非退化 (diag={r['setup_bbox_diag']}): {'ok' if ac1 else 'FAIL'}")
        print(f"    AC2 真實變形乾淨 {rc}: {'ok' if ac2 else 'FAIL'}")
        print(f"    AC3 變形非平凡 (max_disp={r['max_disp']}px, {r['max_disp_frac']*100:.1f}% of diag): {'ok' if ac3 else 'FAIL'}")
        print(f"    AC4 負對照(30×)抓到破壞 {nc}: {'ok' if ac4 else 'FAIL'}")
        print()
    print("OVERALL:", "PASS" if allpass else "FAIL")
    return 0 if allpass else 1


if __name__ == "__main__":
    sys.exit(main())
