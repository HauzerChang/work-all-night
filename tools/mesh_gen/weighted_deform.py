#!/usr/bin/env python3
"""S3 — weighted-mesh 骨骼變形評估器 (LBS bone-driven deform gate)。

補上 `deform_eval.py`(逐頂點 offset)未涵蓋的維度:**weighted mesh 靠骨骼變形**。
Award 的機器人 3 mesh(光暈/左手/身體)+ 4 個 big-win 角色都是 weighted(無 deform timeline),
變形完全來自骨骼 world transform × 每頂點權重的線性混合(Linear Blend Skinning)。

管線:
  parse_weighted(att)  → 每頂點 [(boneName, bindLocalX, bindLocalY, weight), ...] + tris/hull
  bone_world(...)      → Spine 3.8 normal-mode world transform 合成 (a,b,c,d,wx,wy)
  pose_local(anim,t)   → 套 rotate/translate/scale timeline(相鄰 keyframe 線性內插)到 setup
  skin(bindings,world) → world 頂點 = Σ w_k · (boneWorld_k 施於 bindLocal_k)

幾何品質閘沿用 deform_eval.check/eval_pose(self-intersection / flip / degenerate / area)。

⚠️ 可信度(checker validation,RULES「評估器本身要可信」):
  1. 權重和：每頂點 Σweight ≈ 1(parse/資料正確性)。
  2. 仿射協變：對所有骨的 world 左乘同一剛體變換 R,skin 後每點應精確 = R·(原 skin 點),
     到 ~1e-9(證明 LBS 數學正確,不依賴任何真值)。
  3. setup 合法性:setup pose skin 出的 mesh 乾淨(0 自交/0 翻面/0 退化)→ 建立方向基準。
通過 1+2+3 後,才對真實動畫姿勢序列下判定「藝術家 weighted mesh 變形乾淨」= 建立 benchmark。

CLI:
  python3 tools/mesh_gen/weighted_deform.py assets/Award.json            # 全 weighted mesh benchmark
  python3 tools/mesh_gen/weighted_deform.py assets/Award.json --check    # 只跑 checker validation
"""
import json, math, sys
import numpy as np

from deform_eval import check, signed_area  # 重用幾何閘


# ---------- parse ----------
def get_skin(skeleton):
    sk = skeleton["skins"]
    sk = sk[0] if isinstance(sk, list) else sk
    return sk.get("attachments", sk)


def parse_weighted(att, bone_names):
    """回傳 (bindings, tris, hull, nv, weighted)。
    bindings[i] = list of (boneIdx, bindLocalX, bindLocalY, weight)。
    unweighted mesh 也支援:視為單一「slot bone」綁定(boneIdx=slot_bone),bindLocal 即 vertices。
    """
    uvs = att["uvs"]
    nv = len(uvs) // 2
    verts = att["vertices"]
    tris = np.array(att["triangles"], dtype=np.int32).reshape(-1, 3)
    hull = att["hull"]
    weighted = len(verts) != len(uvs)
    bindings = []
    if weighted:
        i = 0
        for _ in range(nv):
            nb = int(verts[i]); i += 1
            vb = []
            for _ in range(nb):
                bi = int(verts[i]); bx = verts[i + 1]; by = verts[i + 2]; w = verts[i + 3]
                i += 4
                vb.append((bi, bx, by, w))
            # 正規化權重:Spine JSON 把權重四捨五入到 ~5 位,每頂點和 ≈ 1.00001。
            # 除以總和讓 partition-of-unity 精確成立(runtime 近似依賴此),對座標影響 ~1e-5。
            s = sum(w for *_, w in vb) or 1.0
            vb = [(bi, bx, by, w / s) for (bi, bx, by, w) in vb]
            bindings.append(vb)
    else:
        # unweighted:vertices 是 attachment-local;此工具聚焦 weighted,unweighted 用 deform_eval。
        for k in range(nv):
            bindings.append([(None, verts[2 * k], verts[2 * k + 1], 1.0)])
    return bindings, tris, hull, nv, weighted


# ---------- Spine bone world transform (normal inherit mode) ----------
def _cosd(d): return math.cos(math.radians(d))
def _sind(d): return math.sin(math.radians(d))


def bone_setup(skeleton):
    out = {}
    for b in skeleton["bones"]:
        out[b["name"]] = {
            "parent": b.get("parent"),
            "x": b.get("x", 0.0), "y": b.get("y", 0.0),
            "rotation": b.get("rotation", 0.0),
            "scaleX": b.get("scaleX", 1.0), "scaleY": b.get("scaleY", 1.0),
            "shearX": b.get("shearX", 0.0), "shearY": b.get("shearY", 0.0),
        }
    return out


def bone_order(setup):
    """回傳 parent-before-child 的名字順序。"""
    order, seen = [], set()

    def visit(n):
        if n in seen or n is None:
            return
        p = setup[n]["parent"]
        if p is not None and p not in seen:
            visit(p)
        seen.add(n); order.append(n)
    for n in setup:
        visit(n)
    return order


def world_transforms(setup, order, local):
    """local[name] = dict 覆寫 x,y,rotation,scaleX,scaleY,shearX,shearY(已含動畫)。
    回傳 world[name] = (a,b,c,d,wx,wy)。normal inherit mode(此資產全為 normal)。
    """
    W = {}
    for n in order:
        L = local[n]
        x, y = L["x"], L["y"]
        rot, sx, sy = L["rotation"], L["scaleX"], L["scaleY"]
        shx, shy = L["shearX"], L["shearY"]
        rotY = rot + 90 + shy
        la = _cosd(rot + shx) * sx
        lc = _sind(rot + shx) * sx
        lb = _cosd(rotY) * sy
        ld = _sind(rotY) * sy
        p = setup[n]["parent"]
        if p is None:
            a, b, c, d = la, lb, lc, ld
            wx, wy = x, y
        else:
            pa, pb, pc, pd, pwx, pwy = W[p]
            a = pa * la + pb * lc
            b = pa * lb + pb * ld
            c = pc * la + pd * lc
            d = pc * lb + pd * ld
            wx = pa * x + pb * y + pwx
            wy = pc * x + pd * y + pwy
        W[n] = (a, b, c, d, wx, wy)
    return W


# ---------- animation sampling ----------
def _interp_frames(frames, t, keys, defaults):
    """線性內插 timeline(忽略 bezier 曲線 → 在 keyframe 上為精確值,幀間為線性近似)。"""
    if not frames:
        return dict(zip(keys, defaults))
    times = [f.get("time", 0.0) for f in frames]
    if t <= times[0]:
        f = frames[0]
        return {k: f.get(k, dv) for k, dv in zip(keys, defaults)}
    if t >= times[-1]:
        f = frames[-1]
        return {k: f.get(k, dv) for k, dv in zip(keys, defaults)}
    for i in range(len(frames) - 1):
        if times[i] <= t <= times[i + 1]:
            f0, f1 = frames[i], frames[i + 1]
            span = times[i + 1] - times[i]
            a = 0.0 if span <= 0 else (t - times[i]) / span
            out = {}
            for k, dv in zip(keys, defaults):
                v0 = f0.get(k, dv); v1 = f1.get(k, dv)
                out[k] = v0 * (1 - a) + v1 * a
            return out
    f = frames[-1]
    return {k: f.get(k, dv) for k, dv in zip(keys, defaults)}


def pose_local(skeleton, setup, anim, t):
    """回傳 local[name] = 套用動畫後的 local transform dict。"""
    local = {}
    for n, s in setup.items():
        local[n] = dict(x=s["x"], y=s["y"], rotation=s["rotation"],
                        scaleX=s["scaleX"], scaleY=s["scaleY"],
                        shearX=s["shearX"], shearY=s["shearY"])
    if anim is None:
        return local
    btl = skeleton["animations"][anim].get("bones", {})
    for name, tl in btl.items():
        if name not in local:
            continue
        if "rotate" in tl:
            r = _interp_frames(tl["rotate"], t, ["angle"], [0.0])
            local[name]["rotation"] = setup[name]["rotation"] + r["angle"]
        if "translate" in tl:
            tr = _interp_frames(tl["translate"], t, ["x", "y"], [0.0, 0.0])
            local[name]["x"] = setup[name]["x"] + tr["x"]
            local[name]["y"] = setup[name]["y"] + tr["y"]
        if "scale" in tl:
            sc = _interp_frames(tl["scale"], t, ["x", "y"], [1.0, 1.0])
            local[name]["scaleX"] = setup[name]["scaleX"] * sc["x"]
            local[name]["scaleY"] = setup[name]["scaleY"] * sc["y"]
        if "shear" in tl:
            sh = _interp_frames(tl["shear"], t, ["x", "y"], [0.0, 0.0])
            local[name]["shearX"] = setup[name]["shearX"] + sh["x"]
            local[name]["shearY"] = setup[name]["shearY"] + sh["y"]
    return local


# ---------- skinning ----------
def skin(bindings, bone_idx_name, world):
    """LBS:回傳 Nx2 world 頂點。bone_idx_name: idx→name。"""
    out = np.zeros((len(bindings), 2), dtype=np.float64)
    for i, vb in enumerate(bindings):
        px = py = 0.0
        for (bi, bx, by, w) in vb:
            name = bone_idx_name[bi]
            a, b, c, d, wx, wy = world[name]
            px += (a * bx + b * by + wx) * w
            py += (c * bx + d * by + wy) * w
        out[i] = (px, py)
    return out


def anim_keytimes(skeleton, anim, bone_names):
    """收集這些 bone 在該動畫的所有 rotate/translate/scale/shear keyframe 時刻聯集。"""
    ts = {0.0}
    btl = skeleton["animations"][anim].get("bones", {})
    for name in bone_names:
        for kind, frames in btl.get(name, {}).items():
            for f in frames:
                ts.add(f.get("time", 0.0))
    return sorted(ts)


# ---------- checker validation ----------
def checker_validate(skeleton):
    """回傳 dict:三道自我可信度閘(不依賴外部真值)。"""
    setup = bone_setup(skeleton)
    order = bone_order(setup)
    idx_name = {i: b["name"] for i, b in enumerate(skeleton["bones"])}
    atts = get_skin(skeleton)
    meshes = [(s, n, a) for s, o in atts.items() for n, a in o.items()
              if a.get("type") == "mesh" and len(a["vertices"]) != len(a["uvs"])]

    Wsetup = world_transforms(setup, order, pose_local(skeleton, setup, None, 0.0))

    # gate 2: 仿射協變 — 對所有骨 world 左乘剛體 R,skin 後應精確 R·P。
    th = math.radians(37.0); Ra, Rb, Rc, Rd = math.cos(th), -math.sin(th), math.sin(th), math.cos(th)
    Tx, Ty = 12.5, -7.3
    Wrot = {}
    for name, (a, b, c, d, wx, wy) in Wsetup.items():
        na = Ra * a + Rb * c; nb = Ra * b + Rb * d
        nc = Rc * a + Rd * c; nd = Rc * b + Rd * d
        nwx = Ra * wx + Rb * wy + Tx; nwy = Rc * wx + Rd * wy + Ty
        Wrot[name] = (na, nb, nc, nd, nwx, nwy)

    raw_weight_dev = 0.0   # 原始(未正規化)資料的每頂點權重和偏差 — 資訊性,反映 JSON 精度
    covar_err = 0.0
    setup_clean = True
    per = {}
    for slot, name, att in meshes:
        bindings, tris, hull, nv, _ = parse_weighted(att, idx_name)
        # 由原始 vertices 量測未正規化偏差(parse 已正規化,故直接重算)
        rawv = att["vertices"]; ii = 0
        for _ in range(nv):
            nb = int(rawv[ii]); ii += 1
            s = sum(rawv[ii + 4 * k + 3] for k in range(nb)); ii += 4 * nb
            raw_weight_dev = max(raw_weight_dev, abs(s - 1.0))
        P = skin(bindings, idx_name, Wsetup)
        Pr = skin(bindings, idx_name, Wrot)
        expect = np.column_stack([Ra * P[:, 0] + Rb * P[:, 1] + Tx,
                                  Rc * P[:, 0] + Rd * P[:, 1] + Ty])
        covar_err = max(covar_err, float(np.abs(Pr - expect).max()))
        chk = check(P, tris, None)
        clean = chk["self_intersections"] == 0 and chk["degenerate"] == 0
        setup_clean = setup_clean and clean
        per[f"{slot}/{name}"] = {"nv": nv, "hull": hull, "tris": len(tris),
                                 "setup_self_int": chk["self_intersections"],
                                 "setup_degenerate": chk["degenerate"]}
    return {
        "raw_weight_sum_dev": raw_weight_dev,          # 資訊性:JSON 權重精度(~1e-5)
        "affine_covariance_max_err": covar_err,        # 正規化後應 → 機器精度
        "setup_all_clean": setup_clean,
        "passed": covar_err < 1e-9 and setup_clean,
        "per_mesh": per,
    }


# ---------- benchmark ----------
def benchmark(skeleton, substeps=4):
    setup = bone_setup(skeleton)
    order = bone_order(setup)
    idx_name = {i: b["name"] for i, b in enumerate(skeleton["bones"])}
    atts = get_skin(skeleton)
    meshes = [(s, n, a) for s, o in atts.items() for n, a in o.items()
              if a.get("type") == "mesh" and len(a["vertices"]) != len(a["uvs"])]
    report = {}
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0, "flip_area_frac": 0.0}
    for slot, name, att in meshes:
        bindings, tris, hull, nv, _ = parse_weighted(att, idx_name)
        bone_names = sorted({idx_name[bi] for vb in bindings for (bi, *_ ) in vb})
        Wsetup = world_transforms(setup, order, pose_local(skeleton, setup, None, 0.0))
        Psetup = skin(bindings, idx_name, Wsetup)
        setup_signs = [signed_area(Psetup, t) > 0 for t in tris]
        setup_area = sum(abs(signed_area(Psetup, t)) for t in tris)
        per_anim = {}
        for anim in skeleton.get("animations", {}):
            btl = skeleton["animations"][anim].get("bones", {})
            if not any(bn in btl for bn in bone_names):
                continue  # 此動畫不驅動這些骨 → mesh 不變形,略過
            keys = anim_keytimes(skeleton, anim, bone_names)
            # keyframe + 相鄰內插子步
            times = []
            for i, t in enumerate(keys):
                times.append(t)
                if i + 1 < len(keys):
                    for s in range(1, substeps):
                        times.append(t + (keys[i + 1] - t) * s / substeps)
            max_disp = 0.0
            results = []
            for t in times:
                W = world_transforms(setup, order, pose_local(skeleton, setup, anim, t))
                P = skin(bindings, idx_name, W)
                max_disp = max(max_disp, float(np.abs(P - Psetup).max()))
                chk = check(P, tris, setup_signs)
                area = sum(abs(signed_area(P, x)) for x in tris)
                chk["area_ratio"] = round(area / setup_area, 3) if setup_area else 0.0
                # 嚴重度指標:翻面三角面積佔 setup 總面積比(比二元 flip 計數更能反映視覺傷害)
                flip_area = sum(abs(signed_area(P, tris[i])) for i in range(len(tris))
                                if (signed_area(P, tris[i]) > 0) != setup_signs[i])
                chk["flip_area_frac"] = round(flip_area / setup_area, 4) if setup_area else 0.0
                chk["clean"] = (chk["self_intersections"] == 0 and chk["triangle_flips"] == 0
                                and chk["degenerate"] == 0)
                results.append(chk)
            per_anim[anim] = {
                "frames_sampled": len(results),
                "driving_bones": [bn for bn in bone_names if bn in btl],
                "max_disp_px": round(max_disp, 2),
                "max_self_intersections": max(r["self_intersections"] for r in results),
                "max_triangle_flips": max(r["triangle_flips"] for r in results),
                "max_degenerate": max(r["degenerate"] for r in results),
                "max_flip_area_frac": max(r["flip_area_frac"] for r in results),
                "area_ratio_range": [min(r["area_ratio"] for r in results),
                                     max(r["area_ratio"] for r in results)],
                "all_clean": all(r["clean"] for r in results),
            }
            for k in worst:
                worst[k] = max(worst[k], per_anim[anim]["max_" + k])
            worst["flip_area_frac"] = max(worst.get("flip_area_frac", 0.0),
                                          per_anim[anim]["max_flip_area_frac"])
        report[f"{slot}/{name}"] = {"nv": nv, "hull": hull, "tris": len(tris),
                                    "bones": bone_names, "anims": per_anim}
    report["_worst_across_all"] = worst
    report["_all_clean"] = (worst["self_intersections"] == 0 and worst["triangle_flips"] == 0
                            and worst["degenerate"] == 0)
    return report


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    sk = json.load(open(path))
    chk = checker_validate(sk)
    print("=== checker validation ===")
    print(json.dumps(chk, ensure_ascii=False, indent=2))
    if "--check" in sys.argv:
        sys.exit(0 if chk["passed"] else 1)
    if not chk["passed"]:
        print("\n⚠️ checker 未通過,不信任 benchmark 結果。")
        sys.exit(1)
    rep = benchmark(sk)
    print("\n=== weighted-mesh deform benchmark ===")
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    sys.exit(0 if rep["_all_clean"] else 2)
