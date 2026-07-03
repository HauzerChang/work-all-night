#!/usr/bin/env python3
"""S2 骨架閘(skeleton evaluator)— 對 Spine 骨架的結構與 pivot 配置 pass/fail + 量化。

S5(骨架半自動)的自我品質閘:沒它,骨架草案無法自主收斂(S2 樞紐)。
可機讀的部分先閘住(結構合法、pivot 與件的空間關聯);「pivot 放關節哪一點」的美術手感
仍屬人審(PLAN 已標:骨架 pivot 是唯一卡死環節)。

AC1_structure(硬條件,全過才 pass):
  - 恰一個 root(無 parent 的骨)
  - parent 存在且**先於子骨定義**(Spine 格式要求;同時保證無環)
  - 每個 slot 的 bone 存在;skin attachment 的 slot 存在
  - weighted mesh 的 bone index 在範圍內
AC2_pivot(校準自真實骨架,2026-07-03):
  - 對每個 region/mesh attachment 求 setup pose 世界頂點 → d_norm =
    「slot 控制骨世界位置到 attachment 世界 bbox 的外距」/ bbox 對角線。
  - 真實分佈:main_draw 73 att 中位數/p90 = 0、max 2.99(background 類 bone 掛遠處,合法);
    Award 176 att max 0.326(weighted 角色 mesh,合法)。
  - 閘:d_norm ≤ 0.5 的比例 ≥ 95%(main_draw 98.6% / Award 100% 過;pivot 打亂大面積爆)。
AC3_info(不閘,僅報告):bones/slots/attachments 數、無 slot 且無子骨的葉 helper 數。

限制(誠實邊界):
  - setup pose 世界變換只實作 normal transform mode、無 shear(兩份真實資產皆如此;
    Award 的 1 個 transform constraint 忽略 — 對 setup 距離分佈影響可忽略,已實測)。
  - 不評「動起來像不像」(那是 S5 之後對影片相似度的事)。
"""
import argparse, json, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np

SKIP_TYPES = {"clipping", "point", "path", "boundingbox", "linkedmesh"}


def world_transforms(bones):
    """name -> 2x3 affine(setup pose;normal mode、無 shear)。依定義序,parent 必先算好。"""
    mats = {}
    for b in bones:
        x, y = b.get("x", 0.0), b.get("y", 0.0)
        rot = math.radians(b.get("rotation", 0.0))
        sx, sy = b.get("scaleX", 1.0), b.get("scaleY", 1.0)
        c, s = math.cos(rot), math.sin(rot)
        local = np.array([[c * sx, -s * sy, x], [s * sx, c * sy, y]])
        p = b.get("parent")
        if p is None:
            mats[b["name"]] = local
        else:
            P = mats[p]
            M = np.empty((2, 3))
            M[:, :2] = P[:, :2] @ local[:, :2]
            M[:, 2] = P[:, :2] @ local[:, 2] + P[:, 2]
            mats[b["name"]] = M
    return mats


def _apply(M, pts):
    pts = np.asarray(pts, float).reshape(-1, 2)
    return pts @ M[:, :2].T + M[:, 2]


def attachment_world_pts(mats, bone_names, bone, att):
    """region/mesh(unweighted 或 weighted)→ setup 世界頂點;其餘型別回 None。"""
    t = att.get("type", "region")
    if t in SKIP_TYPES:
        return None
    if t == "region":
        w, h = att["width"], att["height"]
        r = math.radians(att.get("rotation", 0.0))
        c, s = math.cos(r), math.sin(r)
        corners = np.array([[-w/2, -h/2], [w/2, -h/2], [w/2, h/2], [-w/2, h/2]])
        corners = corners @ np.array([[c, s], [-s, c]])
        corners += [att.get("x", 0.0), att.get("y", 0.0)]
        return _apply(mats[bone], corners)
    if t == "mesh":
        v = att["vertices"]
        if len(v) == len(att["uvs"]):                      # unweighted:bone-local 座標
            return _apply(mats[bone], np.array(v).reshape(-1, 2))
        pts = []; i = 0                                     # weighted:[n,(bi,bx,by,w)*n,...]
        while i < len(v):
            n = int(v[i]); i += 1
            acc = np.zeros(2)
            for _ in range(n):
                bi, bx, by, w = int(v[i]), v[i+1], v[i+2], v[i+3]; i += 4
                acc += w * _apply(mats[bone_names[bi]], [[bx, by]])[0]
            pts.append(acc)
        return np.array(pts)
    return None


def evaluate(sk, pivot_tol=0.5, pass_frac=0.95):
    bones = sk["bones"]
    bone_names = [b["name"] for b in bones]
    name_set = set(bone_names)
    idx = {n: i for i, n in enumerate(bone_names)}

    # ---- AC1 structure ----
    roots = [b["name"] for b in bones if b.get("parent") is None]
    parent_ok = all(b.get("parent") in name_set and idx[b["parent"]] < idx[b["name"]]
                    for b in bones if b.get("parent") is not None)
    slot_bone = {s["name"]: s["bone"] for s in sk.get("slots", [])}
    slots_ok = all(bn in name_set for bn in slot_bone.values())
    skins = sk["skins"]
    att_map = skins[0]["attachments"] if isinstance(skins, list) else skins.get("attachments", skins)
    skin_slots_ok = all(s in slot_bone for s in att_map)
    weight_idx_ok = True
    for slot, d in att_map.items():
        for name, a in d.items():
            if a.get("type") == "mesh" and len(a["vertices"]) != len(a["uvs"]):
                v = a["vertices"]; i = 0
                while i < len(v):
                    n = int(v[i]); i += 1
                    for _ in range(n):
                        if not (0 <= int(v[i]) < len(bones)):
                            weight_idx_ok = False
                        i += 4
    structure = {"single_root": len(roots) == 1,
                 "parents_exist_and_precede": parent_ok,
                 "slot_bones_exist": slots_ok,
                 "skin_slots_exist": skin_slots_ok,
                 "weight_bone_indices_valid": weight_idx_ok}
    struct_pass = all(structure.values())

    # ---- AC2 pivot(結構壞掉就沒法算世界變換,跳過)----
    pivot = {"pass": False, "evaluated": 0, "note": "structure invalid → skipped"}
    if struct_pass:
        mats = world_transforms(bones)
        rows = []
        for slot, d in att_map.items():
            for name, a in d.items():
                pts = attachment_world_pts(mats, bone_names, slot_bone[slot], a)
                if pts is None:
                    continue
                bx, by = mats[slot_bone[slot]][:, 2]
                mn, mx = pts.min(0), pts.max(0)
                diag = math.hypot(*(mx - mn))
                dx = max(mn[0] - bx, 0.0, bx - mx[0])
                dy = max(mn[1] - by, 0.0, by - mx[1])
                d_norm = math.hypot(dx, dy) / max(diag, 1e-6)
                rows.append((slot, name, a.get("type", "region"), d_norm))
        n_ok = sum(1 for r in rows if r[3] <= pivot_tol)
        frac = n_ok / len(rows) if rows else 1.0
        outliers = [{"slot": s, "att": n, "type": t, "d_norm": round(d, 3)}
                    for s, n, t, d in sorted(rows, key=lambda r: -r[3]) if d > pivot_tol][:8]
        pivot = {"pass": frac >= pass_frac, "evaluated": len(rows),
                 "frac_within_tol": round(frac, 4), "tol": pivot_tol, "need_frac": pass_frac,
                 "outliers": outliers}

    # ---- AC3 info ----
    used = set(slot_bone.values())
    children = {}
    for b in bones:
        if b.get("parent"):
            children.setdefault(b["parent"], []).append(b["name"])
    leaf_helpers = [n for n in bone_names if n not in used and n not in children]
    info = {"bones": len(bones), "slots": len(slot_bone),
            "attachments": sum(len(d) for d in att_map.values()),
            "leaf_helper_bones": len(leaf_helpers)}

    overall = struct_pass and pivot["pass"]
    return {"overall_pass": overall,
            "AC1_structure": {"pass": struct_pass, **structure},
            "AC2_pivot": pivot, "AC3_info": info}


# ---------- 負對照(自驗鑑別力) ----------
def _inv(M):
    A = M[:, :2]
    Ai = np.linalg.inv(A)
    out = np.empty((2, 3))
    out[:, :2] = Ai
    out[:, 2] = -Ai @ M[:, 2]
    return out


def _negatives(sk):
    import copy, random
    rng = random.Random(11)
    out = {}
    # A. pivot 打亂 + rebind:骨插錯位置、但重算 attachment local 座標保住世界佈局
    #    (= 壞 rig 的真實樣貌:畫面對、骨錯。單純打亂骨會讓美術跟著跑,d_norm 不變 — 那不是本閘的事)
    a = copy.deepcopy(sk)
    old_mats = world_transforms(sk["bones"])
    xs = [(b.get("x", 0.0), b.get("y", 0.0)) for b in a["bones"] if b.get("parent")]
    rng.shuffle(xs)
    j = 0
    for b in a["bones"]:
        if b.get("parent"):
            b["x"], b["y"] = xs[j]; j += 1
    new_mats = world_transforms(a["bones"])
    bone_names = [b["name"] for b in a["bones"]]
    skins = a["skins"]
    att_map = skins[0]["attachments"] if isinstance(skins, list) else skins.get("attachments", skins)
    slot_bone = {s["name"]: s["bone"] for s in a.get("slots", [])}
    for slot, d in att_map.items():
        bn = slot_bone[slot]
        conv = lambda pts, old=old_mats[bn], new=new_mats[bn]: _apply(_inv(new), _apply(old, pts))
        for name, att in d.items():
            t = att.get("type", "region")
            if t == "region":
                att["x"], att["y"] = [round(v, 3) for v in
                                      conv([[att.get("x", 0.0), att.get("y", 0.0)]])[0]]
            elif t == "mesh":
                v = att["vertices"]
                if len(v) == len(att["uvs"]):                    # unweighted
                    att["vertices"] = [round(float(x), 3) for x in
                                       conv(np.array(v).reshape(-1, 2)).reshape(-1)]
                else:                                            # weighted:逐骨換 bind 座標
                    i = 0
                    while i < len(v):
                        n = int(v[i]); i += 1
                        for _ in range(n):
                            bi = int(v[i])
                            nb = bone_names[bi]
                            p = _apply(_inv(new_mats[nb]), _apply(old_mats[nb], [[v[i+1], v[i+2]]]))[0]
                            v[i+1], v[i+2] = round(float(p[0]), 3), round(float(p[1]), 3)
                            i += 4
    out["pivot_scramble_rebind"] = a

    # A2. pivot 遠位移 + rebind:所有非 root 骨平移 1.5×美術範圍(「關節插到荒謬遠處」,
    #     對任何 rig 都是強擾動;shuffle 對「件少且互相重疊」的小 rig 可能太弱 → 已知局限)
    a2 = copy.deepcopy(sk)
    spans = []
    om = world_transforms(sk["bones"])
    bn_list = [b["name"] for b in sk["bones"]]
    sm = sk["skins"]
    am = sm[0]["attachments"] if isinstance(sm, list) else sm.get("attachments", sm)
    sb = {s["name"]: s["bone"] for s in sk.get("slots", [])}
    for slot, d in am.items():
        for name, att in d.items():
            pts = attachment_world_pts(om, bn_list, sb[slot], att)
            if pts is not None:
                spans.append(pts.max(0) - pts.min(0))
    ext = float(np.max(spans)) if spans else 1000.0
    for i, b in enumerate(a2["bones"]):
        if b.get("parent"):
            b["x"] = b.get("x", 0.0) + 1.5 * ext * (1 if i % 2 else -1)
            b["y"] = b.get("y", 0.0) + 1.5 * ext
    new2 = world_transforms(a2["bones"])
    am2 = (a2["skins"][0]["attachments"] if isinstance(a2["skins"], list)
           else a2["skins"].get("attachments", a2["skins"]))
    for slot, d in am2.items():
        bn = sb[slot]
        conv = lambda pts, old=om[bn], new=new2[bn]: _apply(_inv(new), _apply(old, pts))
        for name, att in d.items():
            t = att.get("type", "region")
            if t == "region":
                att["x"], att["y"] = [round(v, 3) for v in
                                      conv([[att.get("x", 0.0), att.get("y", 0.0)]])[0]]
            elif t == "mesh":
                v = att["vertices"]
                if len(v) == len(att["uvs"]):
                    att["vertices"] = [round(float(x), 3) for x in
                                       conv(np.array(v).reshape(-1, 2)).reshape(-1)]
                else:
                    i2 = 0
                    while i2 < len(v):
                        n = int(v[i2]); i2 += 1
                        for _ in range(n):
                            bi = int(v[i2])
                            nb = bn_list[bi]
                            p = _apply(_inv(new2[nb]), _apply(om[nb], [[v[i2+1], v[i2+2]]]))[0]
                            v[i2+1], v[i2+2] = round(float(p[0]), 3), round(float(p[1]), 3)
                            i2 += 4
    out["pivot_displace_rebind"] = a2

    # B. 造環/壞階層:優先把某骨 parent 指到子孫(環);扁平階層 fallback:
    #    第一個子骨的 parent 指到陣列最後一骨(違反「parent 先定義」,Spine 同樣不合法)
    b_ = copy.deepcopy(sk)
    kids = {}
    for x in b_["bones"]:
        if x.get("parent"):
            kids.setdefault(x["parent"], []).append(x["name"])
    done = False
    for x in b_["bones"]:
        if x.get("parent") and kids.get(x["name"]):
            x["parent"] = kids[x["name"]][0]
            done = True
            break
    if not done:
        for x in b_["bones"]:
            if x.get("parent"):
                x["parent"] = b_["bones"][-1]["name"]
                break
    out["cycle_or_order"] = b_
    # C. slot 指到不存在的骨
    c = copy.deepcopy(sk)
    c["slots"][0]["bone"] = "__nonexistent__"
    out["bad_slot_bone"] = c
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton", nargs="?", default="assets/main_draw.json")
    ap.add_argument("--selftest", action="store_true", help="正對照 + 3 種負對照鑑別力驗證")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    rep = evaluate(sk)
    if not a.selftest:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        raise SystemExit(0 if rep["overall_pass"] else 1)
    ok = rep["overall_pass"]
    print(f"正對照 {a.skeleton}: overall={rep['overall_pass']} "
          f"pivot_frac={rep['AC2_pivot'].get('frac_within_tol')}")
    # scramble(件間互換)對「件少且互相重疊」的小 rig 可能太弱 → 僅報告不判死;
    # displace(位移出美術範圍)/ cycle / bad_slot 對任何 rig 都必須抓到。
    strict = {"pivot_displace_rebind", "cycle_or_order", "bad_slot_bone"}
    for label, neg in _negatives(sk).items():
        r = evaluate(neg)
        caught = not r["overall_pass"]
        if label in strict:
            ok = ok and caught
        why = ("structure" if not r["AC1_structure"]["pass"] else
               f"pivot_frac={r['AC2_pivot'].get('frac_within_tol')}")
        tag = "" if label in strict else "(informative)"
        print(f"負對照 {label}{tag}: caught={caught} ({why})")
    print("SELFTEST", "PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
