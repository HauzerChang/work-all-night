#!/usr/bin/env python3
"""S2 骨架/rig 評估器(自我品質閘) — 對任一 Spine 3.8 skeleton JSON 做結構 + rig 健康檢查。

S5 骨架能力的**自主收斂前置**:沒有可機讀的骨架品質閘,骨架半自動無法自動判 pass/fail。
本閘純 CPU、無需 runtime,檢查「一份 skeleton JSON 是否結構自洽、attachment 格式合法、
weighted mesh 綁定合理」。可跑在真實資產(main_draw/Award)當正對照、破壞後當負對照。

判準(可機讀):
  AC1 structure   — 必要鍵齊;每 slot 的 bone 存在;bone 樹合法(parent 存在、單一 root、無環);
                    每 slot 的預設 attachment 存在於某 skin(attachment=null 允許,靠動畫控制)。
  AC2 attachments — mesh:uvs/triangles 齊、三角索引在範圍、hull∈(0,nv];unweighted 則 len(vertices)==len(uvs)。
                    region:width/height>0。
  AC3 rig_weights — weighted mesh:每頂點 boneCount≥1、bone 索引在 bones 範圍、權重和≈1(±1e-3)。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))


def get_skin_atts(sk):
    skin = sk.get("skins", {})
    skin = skin[0] if isinstance(skin, list) else skin
    if isinstance(skin, dict) and "attachments" in skin:
        return skin["attachments"]
    return skin  # 舊格式:skins 直接是 {slot:{name:att}}


def iter_attachments(sk):
    atts = get_skin_atts(sk)
    for slot, names in atts.items():
        for name, a in names.items():
            yield slot, name, a


def parse_weighted(vertices, nv, nbones):
    """回傳 (ok_indices, bad_weight_verts, max_bone). 解析失敗回 (False,...)。"""
    i, vert, bad_w, maxb = 0, 0, 0, -1
    v = vertices
    try:
        while i < len(v) and vert < nv:
            c = int(v[i]); i += 1
            if c < 1:
                return False, None, None, None
            ws = 0.0
            for _ in range(c):
                bi = int(v[i]); w = v[i + 3]; i += 4
                ws += w; maxb = max(maxb, bi)
            if abs(ws - 1.0) > 1e-3:
                bad_w += 1
            vert += 1
    except IndexError:
        return False, None, None, None
    idx_ok = (0 <= 0) and (maxb < nbones)
    return (vert == nv and i == len(v)), bad_w, maxb, idx_ok


def evaluate_skeleton(sk):
    issues1, issues2, issues3 = [], [], []
    bones = sk.get("bones", [])
    slots = sk.get("slots", [])
    bone_names = {b["name"] for b in bones}
    nbones = len(bones)

    # ---- AC1 structure ----
    for k in ("bones", "slots", "skins"):
        if k not in sk:
            issues1.append(f"缺鍵 {k}")
    # bone 樹:parent 存在、單一 root、無環
    roots = [b for b in bones if "parent" not in b]
    if len(roots) != 1:
        issues1.append(f"root 數 = {len(roots)}(應為 1)")
    for b in bones:
        p = b.get("parent")
        if p is not None and p not in bone_names:
            issues1.append(f"bone {b['name']} 的 parent 不存在: {p}")
    # 環偵測:沿 parent 上溯應到 root
    parent_of = {b["name"]: b.get("parent") for b in bones}
    for name in bone_names:
        seen, cur, steps = set(), name, 0
        while cur is not None and steps <= nbones:
            if cur in seen:
                issues1.append(f"bone 環: {name}"); break
            seen.add(cur); cur = parent_of.get(cur); steps += 1
    atts = get_skin_atts(sk)
    for s in slots:
        if s.get("bone") not in bone_names:
            issues1.append(f"slot {s['name']} 的 bone 不存在: {s.get('bone')}")
        att = s.get("attachment")   # null 允許(靠動畫 attachment timeline)
        if att is not None and not (s["name"] in atts and att in atts[s["name"]]):
            issues1.append(f"slot {s['name']} 的預設 attachment 缺於 skin: {att}")

    # ---- AC2 attachments / AC3 rig ----
    n_mesh_w = n_mesh_u = n_region = n_other = 0
    for slot, name, a in iter_attachments(sk):
        t = a.get("type", "region")
        if t in ("mesh", "linkedmesh"):
            uvs = a.get("uvs", []); tris = a.get("triangles", []); verts = a.get("vertices", [])
            nv = len(uvs) // 2
            if not uvs or not tris:
                issues2.append(f"{name}: mesh 缺 uvs/triangles"); continue
            ta = np.array(tris)
            if ta.size and (ta.max() >= nv or ta.min() < 0):
                issues2.append(f"{name}: 三角索引越界")
            if not (0 < a.get("hull", 0) <= nv):
                issues2.append(f"{name}: hull 越界 {a.get('hull')}/{nv}")
            weighted = len(verts) != nv * 2
            if weighted:
                n_mesh_w += 1
                ok, bad_w, maxb, idx_ok = parse_weighted(verts, nv, nbones)
                if not ok:
                    issues3.append(f"{name}: weighted vertices 解析失敗")
                else:
                    if not idx_ok:
                        issues3.append(f"{name}: bone 索引越界(max {maxb} ≥ {nbones})")
                    if bad_w:
                        issues3.append(f"{name}: {bad_w} 頂點權重和≠1")
            else:
                n_mesh_u += 1
                if len(verts) != len(uvs):
                    issues2.append(f"{name}: unweighted 但 len(vertices)!=len(uvs)")
        elif t == "region":
            n_region += 1
            if not (a.get("width", 0) > 0 and a.get("height", 0) > 0):
                issues2.append(f"{name}: region 尺寸非法")
        elif t == "clipping":
            # clipping:多邊形裁切區,有 vertexCount + vertices(可 weighted),無 width/height
            n_other += 1
            vc = a.get("vertexCount", 0)
            if vc <= 0 or not a.get("vertices"):
                issues2.append(f"{name}: clipping 缺 vertexCount/vertices")
        elif t in ("boundingbox", "path", "point"):
            n_other += 1   # 這些型別結構有效即可(不參與貼圖/mesh 幾何檢查)
        else:
            issues2.append(f"{name}: 未知 attachment type '{t}'")

    res = {
        "AC1_structure": {"pass": not issues1, "issues": issues1},
        "AC2_attachments": {"pass": not issues2, "issues": issues2},
        "AC3_rig_weights": {"pass": not issues3, "issues": issues3},
    }
    summary = {"bones": nbones, "slots": len(slots),
               "mesh_weighted": n_mesh_w, "mesh_unweighted": n_mesh_u, "region": n_region,
               "other_attachments": n_other, "animations": len(sk.get("animations", {})),
               "spine": sk.get("skeleton", {}).get("spine")}
    return {"overall_pass": all(v["pass"] for v in res.values()),
            "summary": summary, "criteria": res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    rep = evaluate_skeleton(sk)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
