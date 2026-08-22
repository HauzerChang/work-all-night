#!/usr/bin/env python3
"""S3 — weighted-mesh (LBS) deform 評估器:量化「骨綁權重網格在骨骼動畫下會不會壞」。

補上 `deform_eval.py` 未涵蓋的唯一維度:**weighted mesh 骨骼變形平滑度**。
unweighted mesh 由 per-vertex deform offset 變形(deform_eval 已處理);
weighted mesh 由**骨骼**經 linear blend skinning(LBS)變形 —— 需要:
  1. 從骨階層 + 動畫 rotate/translate/scale timeline 算各骨 world transform。
  2. Spine 3.8 weighted `computeWorldVertices`:
       wx = Σ_b w_b · (bindX·a_b + bindY·b_b + worldX_b)
       wy = Σ_b w_b · (bindX·c_b + bindY·d_b + worldY_b)
  3. 逐取樣幀跑幾何閘(自交/翻面/退化 → 重用 deform_eval.eval_pose)。

用途(對真實 Award 機器人 weighted mesh 建立 ground-truth,同 deform_eval 的自驗範式):
  - 正對照:藝術家真權重 + 真實動畫 → 應全乾淨(藝術家基準)。
  - 負對照:退化權重(硬指派最近單骨)→ 閘應在接縫抓到自交/翻面(鑑別力)。

⚠️ Spine 雷點:bind 座標在 **bone-local** 空間;bones list 已是階層序(parent 先於 child);
   scale timeline 值為 setup scale 的**乘數**(預設 1);rotate/translate 值為 setup 的**加量**。
   角度單位為度;無 shear(這批骨 shear=0)故用簡化旋轉矩陣。
"""
import json, math
import numpy as np
from deform_eval import signed_area, eval_pose


# ---------- 解析 ----------
def _skin_atts(sk):
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)


def decode_weighted(a):
    """回傳 (per_vertex_entries, uvs Nx2, tris Mx3, hull)。
    entry = [(boneIdx, bindX, bindY, weight), ...]。若非 weighted 回傳 None。"""
    verts = a["vertices"]; uvs = a["uvs"]
    nv = len(uvs) // 2
    if len(verts) == nv * 2:
        return None  # unweighted
    i = 0; entries = []
    for _ in range(nv):
        nb = int(verts[i]); i += 1
        e = []
        for _b in range(nb):
            bi = int(verts[i]); bx = verts[i + 1]; by = verts[i + 2]; w = verts[i + 3]; i += 4
            e.append((bi, bx, by, w))
        entries.append(e)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    return entries, np.array(uvs, dtype=np.float64).reshape(-1, 2), tris, a.get("hull")


# ---------- 骨骼 world transform ----------
def _cosd(d): return math.cos(math.radians(d))
def _sind(d): return math.sin(math.radians(d))


def _sample_timeline(frames, t, keys, defaults):
    """線性內插一條 timeline 在時間 t 的值(對拓樸閘足夠;關鍵幀處為精確值)。
    frames: [{time,<keys>,...}];keys: 要取的欄位;defaults: 對應預設值。"""
    if not frames:
        return list(defaults)
    times = [f.get("time", 0.0) for f in frames]
    def val(f, k, dfl): return f.get(k, dfl)
    if t <= times[0]:
        return [val(frames[0], k, d) for k, d in zip(keys, defaults)]
    if t >= times[-1]:
        return [val(frames[-1], k, d) for k, d in zip(keys, defaults)]
    for i in range(len(times) - 1):
        if times[i] <= t <= times[i + 1]:
            span = times[i + 1] - times[i]
            a = 0.0 if span < 1e-9 else (t - times[i]) / span
            out = []
            for k, dfl in zip(keys, defaults):
                v0 = val(frames[i], k, dfl); v1 = val(frames[i + 1], k, dfl)
                out.append(v0 * (1 - a) + v1 * a)
            return out
    return [val(frames[-1], k, d) for k, d in zip(keys, defaults)]


def bone_world_transforms(sk, anim_name, t):
    """回傳 {boneIdx: (a,b,c,d,wx,wy)},在動畫 anim_name 時間 t 的各骨 world transform。
    anim_name=None → setup pose。"""
    bones = sk["bones"]
    name2idx = {b["name"]: i for i, b in enumerate(bones)}
    anim_bones = {}
    if anim_name is not None:
        anim_bones = sk.get("animations", {}).get(anim_name, {}).get("bones", {})
    W = {}
    for i, b in enumerate(bones):
        rot = b.get("rotation", 0.0)
        x = b.get("x", 0.0); y = b.get("y", 0.0)
        sx = b.get("scaleX", 1.0); sy = b.get("scaleY", 1.0)
        tl = anim_bones.get(b["name"], {})
        if "rotate" in tl:
            rot += _sample_timeline(tl["rotate"], t, ["angle"], [0.0])[0]
        if "translate" in tl:
            dx, dy = _sample_timeline(tl["translate"], t, ["x", "y"], [0.0, 0.0])
            x += dx; y += dy
        if "scale" in tl:
            mx, my = _sample_timeline(tl["scale"], t, ["x", "y"], [1.0, 1.0])
            sx *= mx; sy *= my
        # local matrix (無 shear)
        la = _cosd(rot) * sx; lb = -_sind(rot) * sy
        lc = _sind(rot) * sx; ld = _cosd(rot) * sy
        parent = b.get("parent")
        if parent is None:
            W[i] = (la, lb, lc, ld, x, y)
        else:
            pa, pb, pc, pd, px, py = W[name2idx[parent]]
            W[i] = (
                pa * la + pb * lc, pa * lb + pb * ld,
                pc * la + pd * lc, pc * lb + pd * ld,
                pa * x + pb * y + px, pc * x + pd * y + py,
            )
    return W


def skin_vertices(entries, W):
    """LBS:回傳 Nx2 world 座標。"""
    out = np.zeros((len(entries), 2), dtype=np.float64)
    for vi, e in enumerate(entries):
        wx = wy = 0.0
        for (bi, bx, by, w) in e:
            a, b, c, d, tx, ty = W[bi]
            wx += (bx * a + by * b + tx) * w
            wy += (bx * c + by * d + ty) * w
        out[vi] = (wx, wy)
    return out


# ---------- 取樣時間 ----------
def anim_keytimes(sk, anim_name, bone_idxs):
    """收集所有相關骨 timeline 的關鍵時間(union),外加相鄰線性 substep。"""
    bones = sk["bones"]
    names = {bones[i]["name"] for i in bone_idxs}
    ab = sk.get("animations", {}).get(anim_name, {}).get("bones", {})
    ts = set([0.0])
    for nm in names:
        for tlname, frames in ab.get(nm, {}).items():
            for f in frames:
                ts.add(f.get("time", 0.0))
    ts = sorted(ts)
    dense = []
    for i, t in enumerate(ts):
        dense.append(t)
        if i + 1 < len(ts):
            for s in range(1, 4):
                dense.append(t + (ts[i + 1] - t) * s / 4)
    return dense


# ---------- 評估一個 weighted mesh ----------
def eval_weighted_mesh(sk, slot, name, anims=None, entries_override=None, verbose=False):
    atts = _skin_atts(sk)
    dec = decode_weighted(atts[slot][name])
    if dec is None:
        raise ValueError(f"{slot}/{name} 非 weighted mesh")
    entries, uvs, tris, hull = dec
    if entries_override is not None:
        entries = entries_override
    bone_idxs = sorted({bi for e in entries for (bi, _, _, _) in e})

    # setup pose 幾何(基準 signs / area)
    Wsetup = bone_world_transforms(sk, None, 0.0)
    setup_v = skin_vertices(entries, Wsetup)
    setup_signs = [signed_area(setup_v, t) > 0 for t in tris]
    setup_area = sum(abs(signed_area(setup_v, t)) for t in tris)
    setup_res = eval_pose(setup_v, tris, setup_signs, setup_area)

    if anims is None:
        # 只跑有動到相關骨的動畫
        anims = []
        for an, body in sk.get("animations", {}).items():
            bt = body.get("bones", {})
            if any(sk["bones"][i]["name"] in bt for i in bone_idxs):
                anims.append(an)

    per_anim = {}
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    for an in anims:
        times = anim_keytimes(sk, an, bone_idxs)
        res = []
        for t in times:
            W = bone_world_transforms(sk, an, t)
            v = skin_vertices(entries, W)
            res.append(eval_pose(v, tris, setup_signs, setup_area))
        agg = {
            "frames": len(res),
            "max_self_intersections": max(r["self_intersections"] for r in res),
            "max_triangle_flips": max(r["triangle_flips"] for r in res),
            "max_degenerate": max(r["degenerate"] for r in res),
            "area_ratio_range": [min(r["area_ratio"] for r in res), max(r["area_ratio"] for r in res)],
            "all_clean": all(r["clean"] for r in res),
        }
        per_anim[an] = agg
        for k in worst:
            worst[k] = max(worst[k], agg["max_" + k])
    clean = (worst["self_intersections"] == 0 and worst["triangle_flips"] == 0 and worst["degenerate"] == 0)
    return {
        "nv": len(entries), "tris": len(tris), "hull": hull,
        "bones_used": [sk["bones"][i]["name"] for i in bone_idxs],
        "setup_clean": setup_res["clean"], "setup": setup_res,
        "anims": per_anim, "worst": worst, "all_clean": clean,
    }


# ---------- 負對照:退化權重(硬指派最近單骨)----------
def degenerate_weights(sk, slot, name):
    """把每頂點權重塌成『最近單骨、weight=1』(bindX/bindY 仍取該骨的 setup-local 原值)。
    這破壞多骨混合的平滑過渡 → 骨在接縫附近相對運動時應撕裂/翻面。"""
    atts = _skin_atts(sk)
    entries, uvs, tris, hull = decode_weighted(atts[slot][name])
    out = []
    for e in entries:
        top = max(e, key=lambda x: x[3])  # 權重最大的那根骨
        out.append([(top[0], top[1], top[2], 1.0)])
    return out


# ---------- 關節彎折壓力(結構件的正式鑑別控制)----------
def joint_bend_stress(sk, slot, name, child_bone, deg_max=60.0, steps=12, entries_override=None):
    """對真實骨架施加合成的『關節彎折』:把 child_bone 相對其 parent 額外旋轉 0→deg_max。
    這是 smooth(藝術家)vs hard(單骨)權重差異最明顯的場景(BBW 的核心動機):
    hard 指派在接縫處『糖果紙塌陷』撕裂;smooth 混合平滑彎折。
    回傳 (first_bad_deg, worst),first_bad_deg=None 表示到 deg_max 都乾淨。"""
    atts = _skin_atts(sk)
    dec = decode_weighted(atts[slot][name])
    entries = entries_override if entries_override is not None else dec[0]
    tris = dec[2]
    name2idx = {b["name"]: i for i, b in enumerate(sk["bones"])}
    ci = name2idx[child_bone]

    Wsetup = bone_world_transforms(sk, None, 0.0)
    setup_v = skin_vertices(entries, Wsetup)
    signs = [signed_area(setup_v, t) > 0 for t in tris]
    area = sum(abs(signed_area(setup_v, t)) for t in tris)

    first_bad = None
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    for s in range(1, steps + 1):
        dd = deg_max * s / steps
        # 重算 world:在 child bone 的 local rotation 上加 dd
        W = _bend_transforms(sk, ci, dd)
        v = skin_vertices(entries, W)
        r = eval_pose(v, tris, signs, area)
        for k in worst:
            worst[k] = max(worst[k], r[k])
        if first_bad is None and not r["clean"]:
            first_bad = round(dd, 1)
    return first_bad, worst


def _bend_transforms(sk, child_idx, extra_deg):
    """setup pose,但把 bones[child_idx] 的 local rotation 額外 +extra_deg。"""
    bones = sk["bones"]
    name2idx = {b["name"]: i for i, b in enumerate(bones)}
    W = {}
    for i, b in enumerate(bones):
        rot = b.get("rotation", 0.0) + (extra_deg if i == child_idx else 0.0)
        x = b.get("x", 0.0); y = b.get("y", 0.0)
        sx = b.get("scaleX", 1.0); sy = b.get("scaleY", 1.0)
        la = _cosd(rot) * sx; lb = -_sind(rot) * sy
        lc = _sind(rot) * sx; ld = _cosd(rot) * sy
        parent = b.get("parent")
        if parent is None:
            W[i] = (la, lb, lc, ld, x, y)
        else:
            pa, pb, pc, pd, px, py = W[name2idx[parent]]
            W[i] = (pa * la + pb * lc, pa * lb + pb * ld,
                    pc * la + pd * lc, pc * lb + pd * ld,
                    pa * x + pb * y + px, pc * x + pd * y + py)
    return W


# ---------- runner ----------
def run_robot(path="assets/Award.json"):
    sk = json.load(open(path))
    targets = [("機器人拆件/身體", "機器人拆件/身體"),
               ("機器人拆件/左手", "機器人拆件/左手"),
               ("機器人拆件/光暈", "機器人拆件/光暈")]
    # 件角色分類:structural(不透明結構件,閘從嚴)vs soft-effect(軟光暈,容許重疊)
    STRUCTURAL = {"機器人拆件/身體", "機器人拆件/左手"}
    report = {"positive_control": {}}
    for slot, name in targets:
        report["positive_control"][slot] = eval_weighted_mesh(sk, slot, name)

    # 關節彎折鑑別控制:選一個『骨區交錯』的結構件(身體,LEG7 相對 LEG3 splay),
    # smooth(藝術家)應比 hard(單骨)撐更大彎角才首次出現撕裂。
    body = "機器人拆件/身體"
    hard = degenerate_weights(sk, body, body)
    fb_smooth, w_smooth = joint_bend_stress(sk, body, body, "4_LEG7", deg_max=90, steps=18)
    fb_hard, w_hard = joint_bend_stress(sk, body, body, "4_LEG7", deg_max=90, steps=18, entries_override=hard)
    report["joint_bend_discriminative"] = {
        "part": body, "bent_bone": "4_LEG7",
        "smooth_first_bad_deg": fb_smooth, "smooth_worst": w_smooth,
        "hard_first_bad_deg": fb_hard, "hard_worst": w_hard,
    }

    pos = report["positive_control"]
    # AC1: 所有真實 mesh 的 LBS setup pose 幾何乾淨(骨綁 world 計算正確)
    ac1 = all(v["setup_clean"] for v in pos.values())
    # AC2: 結構件在其全部真實動畫下 0 自交/翻面(藝術家品質基準;生成器將對齊此)
    ac2 = all(pos[s]["all_clean"] for s in STRUCTURAL)
    # AC3: 鑑別力 — 骨區交錯的結構件上,smooth 權重比 hard 撐更大彎角才首次撕裂
    #      (證明此閘能為未來 BBW 生成器評分權重品質;None 視為 ∞)
    def _f(x): return float("inf") if x is None else x
    ac3 = _f(fb_smooth) > _f(fb_hard)
    report["_AC"] = {
        "AC1_setup_lbs_clean": ac1,
        "AC2_structural_positive_control_clean": ac2,
        "AC3_smooth_beats_hard_under_joint_bend": ac3,
        "overall_pass": ac1 and ac2 and ac3,
    }
    # 校準備註(誠實界定,見 knowledge/s3-weighted-deform-evaluator.md)
    report["_notes"] = {
        "soft_effect_exception": "機器人拆件/光暈(軟光暈)在其 In streak 自交+翻面屬藝術家刻意"
                                 "(單骨 4_LEG6 飛離 ~470px);故『0 自交』非通用閘,需依件角色分級。",
        "topology_gate_scope": "此閘量『撕裂/翻面』;骨區可分離的件(左手)hard 指派亦不撕裂但彎折僵硬 —"
                               "『彎折平滑度』需另配 seam 連續性/應變指標(後續)。",
    }
    return report


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    rep = run_robot(path)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
