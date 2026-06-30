#!/usr/bin/env python3
"""S3→S5 銜接:自動配權 —— 把 S3 的 unweighted mesh + 骨鏈 → weighted mesh(Spine 格式)。

目前 SkelToJson 產的是中性骨架(每件一根置中 bone、mesh unweighted)。本工具讓 mesh 可被
**多骨**驅動:沿 mesh 主軸自動佈一條骨鏈 → 依「頂點到骨段距離」配權(inverse-distance + top-K
+ 沿 mesh 邊做 Laplacian 平滑)→ 輸出 Spine weighted vertices
  `[n, (boneIdx,bindX,bindY,weight)*n, ...]`(hull 頂點排最前、每頂點權重和=1,見 CLAUDE.md 雷點6)。

⚠️ 這是 **bone-distance heat**(確定性、純 CPU),非真正 BBW(需解 mesh 內部 biharmonic);
   對「骨鏈帶動 strip/blob」已足以平滑變形。BBW 列為後續。

自驗閘(復用 deform_eval 的自交/翻面幾何閘):
  AC1 partition-of-unity:每頂點權重和=1、權重≥0、bones/vertex≤上限。
  AC2 setup 重建:骨在 setup 位姿時 LBS 還原 setup 頂點(誤差≈0)→ bind 座標正確。
  AC3 deform 掃描:沿骨鏈漸進彎折一系列角度,LBS 變形後 0 自交/0 翻面/0 退化(平滑)。
真值自一致性:對 Award 真實 weighted 件驗 partition-of-unity(權重和=1)→ 確認閘可信。
負對照:硬指派最近單骨(K=1、不平滑)在彎折下應出現自交/翻面 → 閘有鑑別力。
"""
import argparse, json, os, sys, math
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import deform_eval as de


# ---------- 幾何輔助 ----------
def mesh_points(mesh):
    v = mesh["vertices"]
    return np.column_stack([np.array(v[0::2], float), np.array(v[1::2], float)])  # (nv,2) y-up local


def mesh_edges(mesh):
    es = set()
    t = np.array(mesh["triangles"], int).reshape(-1, 3)
    for tri in t:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            es.add((min(int(a), int(b)), max(int(a), int(b))))
    return list(es)


def seg_dist(p, a, b):
    ab = b - a; t = np.dot(p - a, ab) / max(np.dot(ab, ab), 1e-9)
    t = min(max(t, 0.0), 1.0)
    return np.hypot(*(p - (a + t * ab)))


# ---------- 骨鏈(沿主軸)----------
def bone_chain_along_axis(pts, n_bones):
    """沿 mesh 點雲較長軸佈 n_bones 根的骨鏈(回傳 joints (n_bones+1, 2),y-up local)。"""
    mn = pts.min(0); mx = pts.max(0); span = mx - mn
    axis = 1 if span[1] >= span[0] else 0   # 較長軸
    other = 1 - axis
    c = float(np.median(pts[:, other]))
    lo, hi = float(mn[axis]), float(mx[axis])
    joints = []
    for i in range(n_bones + 1):
        t = i / n_bones
        p = [0.0, 0.0]; p[axis] = lo + (hi - lo) * t; p[other] = c
        joints.append(p)
    return np.array(joints, float), axis


# ---------- 配權(bone-distance heat)----------
def compute_weights(pts, joints, k=2, power=2.0, smooth_iters=8, edges=None):
    nv = len(pts); nb = len(joints) - 1
    W = np.zeros((nv, nb))
    for vi, p in enumerate(pts):
        d = np.array([seg_dist(p, joints[b], joints[b + 1]) for b in range(nb)])
        w = 1.0 / (d + 1e-3) ** power
        if k and k < nb:                       # 只留最近 k 根
            cut = np.argsort(d)[k:]; w[cut] = 0.0
        W[vi] = w / max(w.sum(), 1e-12)
    # 沿 mesh 邊 Laplacian 平滑(避免相鄰頂點權重跳變 → 變形更平滑)
    if smooth_iters and edges:
        nbr = [[] for _ in range(nv)]
        for a, b in edges:
            nbr[a].append(b); nbr[b].append(a)
        for _ in range(smooth_iters):
            Wn = W.copy()
            for vi in range(nv):
                if nbr[vi]:
                    Wn[vi] = 0.5 * W[vi] + 0.5 * W[nbr[vi]].mean(0)
            W = Wn
        W = W / W.sum(1, keepdims=True)
    return W


# ---------- Spine weighted vertices ----------
def bone_setup(joints):
    """每根 bone 的 setup (origin, world_angle, length)。"""
    out = []
    for b in range(len(joints) - 1):
        o = joints[b]; d = joints[b + 1] - joints[b]
        out.append((o, math.atan2(d[1], d[0]), float(np.hypot(*d))))
    return out


def to_weighted_spine(mesh, joints, W, bone_index_offset, weight_eps=1e-3):
    """輸出 Spine weighted vertices。bindX/bindY = setup 下頂點在該 bone 局部座標。
    bone_index_offset = 這條骨鏈第一根 bone 在 skeleton bones 陣列的 index。"""
    pts = mesh_points(mesh); setup = bone_setup(joints)
    verts = []
    bpv = []
    for vi, p in enumerate(pts):
        idx = [b for b in range(W.shape[1]) if W[vi, b] > weight_eps]
        ws = np.array([W[vi, b] for b in idx]); ws = ws / ws.sum()   # 重新歸一
        verts.append(len(idx)); bpv.append(len(idx))
        for b, w in zip(idx, ws):
            o, ang, _ = setup[b]
            ca, sa = math.cos(-ang), math.sin(-ang)
            dx, dy = p[0] - o[0], p[1] - o[1]
            bx = ca * dx - sa * dy
            by = sa * dx + ca * dy
            verts += [bone_index_offset + b, round(float(bx), 3), round(float(by), 3), round(float(w), 5)]
    out = dict(mesh)
    out["vertices"] = verts
    out["_weighted"] = True
    out["_bones_per_vertex"] = bpv
    return out


# ---------- FK + LBS(供自驗閘）----------
def fk(joints, deltas):
    """forward kinematics:對每根 bone 的 local 角加 deltas[i],回傳變形後 (origin, world_angle)。"""
    setup = bone_setup(joints)
    world = []
    prev_ang = 0.0; prev_setup_ang = 0.0; o = joints[0].astype(float).copy()
    for b, (so, sang, slen) in enumerate(setup):
        local = sang - prev_setup_ang
        wang = prev_ang + local + deltas[b]
        world.append((o.copy(), wang))
        o = o + np.array([slen * math.cos(wang), slen * math.sin(wang)])
        prev_ang = wang; prev_setup_ang = sang
    return world


def lbs(weighted, joints, deltas):
    """用 weighted vertices + 變形後 bone 世界位姿,線性混合蒙皮算變形後頂點。"""
    setup = bone_setup(joints); world = fk(joints, deltas)
    boff = None
    v = weighted["vertices"]; i = 0; out = []
    # bone_index_offset = 第一個出現的 boneIdx 對應 setup[0];用相對 index
    # 重新解析:weighted 存的是絕對 skeleton index;我們需相對骨鏈起點。
    # 由 to_weighted_spine,index = offset + b。推得 offset = min boneIdx。
    idxs = []
    j = 0
    for _ in range(len(weighted["uvs"]) // 2):
        n = int(v[j]); j += 1
        for _ in range(n):
            idxs.append(int(v[j])); j += 4
    offset = min(idxs)
    while i < len(v):
        n = int(v[i]); i += 1
        x = y = 0.0
        for _ in range(n):
            bi = int(v[i]) - offset; bx, by, w = v[i + 1], v[i + 2], v[i + 3]; i += 4
            o, ang = world[bi]
            ca, sa = math.cos(ang), math.sin(ang)
            x += w * (o[0] + ca * bx - sa * by)
            y += w * (o[1] + sa * bx + ca * by)
        out.append([x, y])
    return np.array(out)


def bend_deltas(nb, total_deg):
    """沿骨鏈漸進彎折:root 不動,越往末端累積越多(每根 total/nb 度)。"""
    per = math.radians(total_deg) / nb
    return [0.0] + [per] * (nb - 1) if nb >= 1 else [0.0]


# ---------- 閘 ----------
def evaluate_weighting(mesh, joints, W, max_bend=60, sweep=6, max_bpv=4, rec_tol=0.05):
    weighted = to_weighted_spine(mesh, joints, W, bone_index_offset=10)
    pts = mesh_points(mesh)
    tris = np.array(mesh["triangles"], int).reshape(-1, 3)
    setup_signs = [de.signed_area(pts, t) > 0 for t in tris]
    setup_area = sum(abs(de.signed_area(pts, t)) for t in tris)

    # AC1 partition of unity
    sums = W.sum(1)
    bpv = np.array(weighted["_bones_per_vertex"])
    ac1 = bool(np.all(np.abs(sums - 1) < 1e-6) and np.all(W >= -1e-9) and bpv.max() <= max_bpv)

    # AC2 setup 重建(deltas=0 應還原 setup)
    nb = len(joints) - 1
    rec = lbs(weighted, joints, [0.0] * nb)
    rec_err = float(np.abs(rec - pts).max())   # 殘差來自 bindX/Y 存為 3 位小數,遠低於可見尺度
    ac2 = rec_err < rec_tol

    # AC3 deform 掃描
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    for s in range(1, sweep + 1):
        deg = max_bend * s / sweep
        for sign in (+1, -1):
            d = [x * sign for x in bend_deltas(nb, deg)]
            dv = lbs(weighted, joints, d)
            r = de.eval_pose(dv, tris, setup_signs, setup_area)
            for k in worst:
                worst[k] = max(worst[k], r[k])
    ac3 = (worst["self_intersections"] == 0 and worst["triangle_flips"] == 0 and worst["degenerate"] == 0)

    return {
        "n_bones": nb, "bones_per_vertex_max": int(bpv.max()), "bones_per_vertex_mean": round(float(bpv.mean()), 2),
        "AC1_partition_of_unity": {"pass": ac1, "weight_sum_range": [round(float(sums.min()), 6), round(float(sums.max()), 6)]},
        "AC2_setup_reconstruction": {"pass": ac2, "max_err_px": round(rec_err, 6)},
        "AC3_deform_sweep": {"pass": ac3, "max_bend_deg": max_bend, "worst": worst},
        "overall_pass": ac1 and ac2 and ac3,
    }


def weight_mesh(mesh, n_bones=3, k=2, power=2.0, smooth_iters=8):
    pts = mesh_points(mesh)
    joints, axis = bone_chain_along_axis(pts, n_bones)
    edges = mesh_edges(mesh)
    W = compute_weights(pts, joints, k=k, power=power, smooth_iters=smooth_iters, edges=edges)
    return joints, W


# ---------- truth 自一致性 ----------
def award_partition_check(award_json="assets/Award.json"):
    sk = json.load(open(award_json))
    att = sk["skins"][0]["attachments"]
    res = {}
    for slot, o in att.items():
        for name, a in o.items():
            if a.get("type") != "mesh":
                continue
            v = a["vertices"]; nuv = len(a["uvs"]) // 2
            if len(v) == nuv * 2:
                continue  # unweighted
            i = 0; sums = []
            for _ in range(nuv):
                n = int(v[i]); i += 1; s = 0.0
                for _ in range(n):
                    s += v[i + 3]; i += 4
                sums.append(s)
            res[slot] = {"sum_min": round(min(sums), 5), "sum_max": round(max(sums), 5),
                         "ok": abs(min(sums) - 1) < 1e-4 and abs(max(sums) - 1) < 1e-4}
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mesh", nargs="?", help="unweighted mesh JSON(S3 產出);省略則跑內建真實資產測試")
    ap.add_argument("--bones", type=int, default=3)
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()
    if a.mesh:
        m = json.load(open(a.mesh))
        joints, W = weight_mesh(m, n_bones=a.bones)
        rep = evaluate_weighting(m, joints, W)
        wm = to_weighted_spine(m, joints, W, bone_index_offset=10)
        if a.out:
            json.dump(wm, open(a.out, "w"), ensure_ascii=False)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        raise SystemExit(0 if rep["overall_pass"] else 1)

    # 內建自我測試(無 mesh 參數):真值自一致性 + 2 真實件 AC + 負對照
    import cv2
    from atlas_crop import extract
    from generate_mesh_v2 import generate as gen2
    os.makedirs("/tmp/aw_selftest", exist_ok=True)

    def mk(sk, at, pg, nm):
        sub = extract(at, pg, nm); p = "/tmp/aw_selftest/x.png"; cv2.imwrite(p, sub)
        return gen2(p, mode="auto")

    truth = award_partition_check()
    truth_ok = all(v["ok"] for v in truth.values())
    cases = [
        ("curtain_left strip (main_draw)", "assets/main_draw.json", "assets/main_draw.atlas",
         "assets/main_draw.png", "image/curtain_left", 3),
        ("robot 左手 blob (Award)", "assets/Award.json", "assets/Award.atlas",
         "assets/Award.png", "機器人拆件/左手", 2),
    ]
    ok = truth_ok
    print(f"truth 自一致性(Award weighted partition-of-unity): {truth_ok}  ({len(truth)} 件)")
    for label, sk, at, pg, nm, nb in cases:
        m = mk(sk, at, pg, nm)
        j, W = weight_mesh(m, n_bones=nb)
        good = evaluate_weighting(m, j, W, max_bend=60)
        jb, Wb = weight_mesh(m, n_bones=nb, k=1, smooth_iters=0)
        bad = evaluate_weighting(m, jb, Wb, max_bend=60)
        disc = good["overall_pass"] and not bad["overall_pass"]   # 正過 + 負對照失敗 = 有鑑別力
        ok = ok and disc
        print(f"  {label}: good={good['overall_pass']} bad(k=1)={bad['overall_pass']} "
              f"AC2_err={good['AC2_setup_reconstruction']['max_err_px']} "
              f"good_AC3_worst={good['AC3_deform_sweep']['worst']} bad_AC3_worst={bad['AC3_deform_sweep']['worst']} → 鑑別力={disc}")
    print("OVERALL:", ok)
    raise SystemExit(0 if ok else 1)
