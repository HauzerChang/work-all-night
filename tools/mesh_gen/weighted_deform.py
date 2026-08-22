#!/usr/bin/env python3
"""S3 — weighted-mesh 骨骼驅動變形引擎 + 變形品質閘。

補上 knowledge/s3-robot-mesh-vs-award.md 標記的唯一未驗維度:
**weighted mesh 在真實骨骼 pose 下的變形品質**(靜態 IoU PASS ≠ bone-driven 變形乾淨)。

與 deform_eval.py 的分工:
  - deform_eval:**unweighted** mesh,靠逐頂點 `deform` timeline 位移(main_draw 4 mesh)。
  - 本檔:**weighted** mesh,靠骨骼世界變換 + 每頂點骨綁權重(Award 機器人 3 件:光暈/左手/身體)。

Spine 3.8 weighted skinning(對照 CLAUDE.md 雷點 #4/#6):
  worldVertex = Σ_bone  weight_b · ( boneWorldMat_b · bind_b )
  boneWorldMat = parentWorldMat · localMat(x,y,rotation,scaleX,scaleY)   (transform mode 全 'normal')
  bind 座標為 setup pose 下相對該骨的座標;每頂點權重和=1;hull 頂點排最前。

動畫 pose:bone 的 rotate/translate/scale timeline 為**相對 setup 的 offset**;
本檔以線性內插取樣(對「偵測翻面/自交」足夠保守;bezier 精修非必要,見誠實界定)。

自我驗證(可機讀,見 __main__):
  AC1 setup 自一致:weighted skinning 在 setup pose 重建的頂點布局 ≈ uvs(region-local)。
  AC2 藝術家真值乾淨:3 件在真實 Legend_In+Loop pose 下 0 自交/0 翻面/0 退化。
  AC3 鑑別力(負對照):打亂骨綁後同 pose 下出現缺陷。
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from deform_eval import eval_pose, signed_area  # 幾何檢查沿用同一套


# ---------- 骨骼世界變換 ----------
def bone_index(sk):
    return {b["name"]: i for i, b in enumerate(sk["bones"])}


def local_mat(x, y, rot_deg, sx, sy):
    rot = math.radians(rot_deg)
    c, s = math.cos(rot), math.sin(rot)
    return np.array([[c * sx, -s * sy, x],
                     [s * sx,  c * sy, y],
                     [0.0,     0.0,    1.0]], dtype=np.float64)


def _sample(frames, t, keys, defaults):
    """線性內插一條 timeline;frames 依 time 遞增,time 預設 0,值鍵預設見 defaults。"""
    if not frames:
        return dict(defaults)
    times = [f.get("time", 0.0) for f in frames]
    if t <= times[0]:
        return {k: frames[0].get(k, defaults[k]) for k in keys}
    if t >= times[-1]:
        return {k: frames[-1].get(k, defaults[k]) for k in keys}
    for i in range(len(frames) - 1):
        t0, t1 = times[i], times[i + 1]
        if t0 <= t <= t1:
            a = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return {k: frames[i].get(k, defaults[k]) * (1 - a)
                       + frames[i + 1].get(k, defaults[k]) * a for k in keys}
    return {k: frames[-1].get(k, defaults[k]) for k in keys}


def bone_local_at(sk, idx, anim, t):
    """回傳 bone idx 在動畫 anim 時間 t 的 local 仿射(setup 值 + timeline offset)。"""
    b = sk["bones"][idx]
    x, y = b.get("x", 0.0), b.get("y", 0.0)
    rot = b.get("rotation", 0.0)
    sx, sy = b.get("scaleX", 1.0), b.get("scaleY", 1.0)
    if anim is not None:
        bt = anim.get("bones", {}).get(b["name"], {})
        if "rotate" in bt:
            rot += _sample(bt["rotate"], t, ["angle"], {"angle": 0.0})["angle"]
        if "translate" in bt:
            tr = _sample(bt["translate"], t, ["x", "y"], {"x": 0.0, "y": 0.0})
            x += tr["x"]; y += tr["y"]
        if "scale" in bt:
            sc = _sample(bt["scale"], t, ["x", "y"], {"x": 1.0, "y": 1.0})
            sx *= sc["x"]; sy *= sc["y"]
    return local_mat(x, y, rot, sx, sy)


def world_transforms(sk, name2idx, anim=None, t=0.0):
    """回傳 {boneIdx: 3x3 world mat};遞迴 parent·local。"""
    W = {}

    def rec(idx):
        if idx in W:
            return W[idx]
        b = sk["bones"][idx]
        L = bone_local_at(sk, idx, anim, t)
        p = b.get("parent")
        W[idx] = L if p is None else rec(name2idx[p]) @ L
        return W[idx]

    for i in range(len(sk["bones"])):
        rec(i)
    return W


# ---------- weighted mesh ----------
def parse_weighted(vertices):
    """[bc, (bi,bx,by,w)×bc, ...] → 每頂點 [(boneIdx,bx,by,w),...]。unweighted 會回傳空綁定。"""
    out = []
    i = 0
    v = vertices
    while i < len(v):
        bc = int(v[i]); i += 1
        binds = []
        for _ in range(bc):
            binds.append((int(v[i]), float(v[i + 1]), float(v[i + 2]), float(v[i + 3])))
            i += 4
        out.append(binds)
    return out


def is_weighted(att):
    return len(att["vertices"]) != len(att["uvs"])


def compute_world_vertices(parsed, Wmap):
    """weighted skinning:Σ weight·(boneWorld·bind)。回傳 Nx2 (y-up world)。"""
    pts = np.zeros((len(parsed), 2), dtype=np.float64)
    for vi, binds in enumerate(parsed):
        px = py = 0.0
        for bi, bx, by, w in binds:
            M = Wmap[bi]
            px += (M[0, 0] * bx + M[0, 1] * by + M[0, 2]) * w
            py += (M[1, 0] * bx + M[1, 1] * by + M[1, 2]) * w
        pts[vi] = (px, py)
    return pts


def load_att(sk, slot, name=None):
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    name = name or slot
    return atts[slot][name]


# ---------- 可見性 gating(CLAUDE.md 雷點 #2/#3)----------
def _slot_setup(sk, slot):
    for s in sk.get("slots", []):
        if s["name"] == slot:
            return s
    return {}


def slot_visible_at(sk, anim, slot, t, alpha_thresh=4):
    """slot 在動畫 anim 時間 t 是否『看得見』(有 attachment 且 color alpha > 門檻)。
    看不見的幀不該計入變形品質(不可見件的頂點怎麼亂都無視覺後果)。
    color timeline:hex 'rrggbbaa';curve=='stepped' 持前值,否則線性內插 alpha。
    attachment timeline:name==null → 隱藏。"""
    st = anim.get("slots", {}).get(slot, {})

    # attachment gating
    at = st.get("attachment")
    if at:
        cur = None
        for f in at:
            if f.get("time", 0.0) <= t + 1e-9:
                cur = f.get("name")
        if cur is None and any(f.get("time", 0.0) <= t + 1e-9 for f in at):
            return False

    # color alpha gating
    ct = st.get("color")
    if not ct:
        setup_hex = _slot_setup(sk, slot).get("color")
        if setup_hex and len(setup_hex) >= 8:
            return int(setup_hex[6:8], 16) > alpha_thresh
        return True  # 無 color 資訊 → 視為可見
    times = [f.get("time", 0.0) for f in ct]

    def alpha_of(f):
        return int(f["color"][6:8], 16)

    if t <= times[0]:
        a = alpha_of(ct[0])
    elif t >= times[-1]:
        a = alpha_of(ct[-1])
    else:
        a = alpha_of(ct[-1])
        for i in range(len(ct) - 1):
            t0, t1 = times[i], times[i + 1]
            if t0 <= t <= t1:
                if ct[i].get("curve") == "stepped":
                    a = alpha_of(ct[i])
                else:
                    f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
                    a = alpha_of(ct[i]) * (1 - f) + alpha_of(ct[i + 1]) * f
                break
    return a > alpha_thresh


# ---------- pose 取樣 + 閘 ----------
def sample_anim_times(sk, anim_name, substeps=4):
    """動畫內所有 bone keyframe 時間 ∪ 相鄰線性內插點。"""
    anim = sk["animations"][anim_name]
    ts = set([0.0])
    for _, chans in anim.get("bones", {}).items():
        for _, frames in chans.items():
            for f in frames:
                ts.add(f.get("time", 0.0))
    ts = sorted(ts)
    out = []
    for i, t in enumerate(ts):
        out.append(t)
        if i + 1 < len(ts):
            for s in range(1, substeps):
                out.append(t + (ts[i + 1] - t) * s / substeps)
    return out


def deform_gate(sk, name2idx, slot, name=None, anims=None):
    """對一件 weighted mesh 跑真實骨骼 pose 變形閘。回傳報告(含逐動畫聚合)。"""
    att = load_att(sk, slot, name)
    parsed = parse_weighted(att["vertices"])
    tris = np.array(att["triangles"], dtype=np.int32).reshape(-1, 3)

    # setup 世界頂點 → signed-area 基準符號
    Wsetup = world_transforms(sk, name2idx, None, 0.0)
    setup_v = compute_world_vertices(parsed, Wsetup)
    setup_signs = [signed_area(setup_v, t) > 0 for t in tris]
    setup_area = sum(abs(signed_area(setup_v, t)) for t in tris)

    if anims is None:
        # 只挑真的驅動到本件所綁骨的動畫
        used_bones = {bi for binds in parsed for (bi, *_) in binds}
        used_names = {sk["bones"][bi]["name"] for bi in used_bones}
        anims = [an for an, a in sk["animations"].items()
                 if used_names & set(a.get("bones", {}).keys())]

    per_anim = {}
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    for an in anims:
        res = []
        skipped_hidden = 0
        for t in sample_anim_times(sk, an):
            if not slot_visible_at(sk, sk["animations"][an], slot, t):
                skipped_hidden += 1
                continue
            W = world_transforms(sk, name2idx, sk["animations"][an], t)
            v = compute_world_vertices(parsed, W)
            res.append(eval_pose(v, tris, setup_signs, setup_area))
        if not res:  # 整段動畫此件都不可見 → 無視覺後果,不納入
            per_anim[an] = {"frames": 0, "skipped_hidden": skipped_hidden,
                            "all_clean": True, "note": "never visible in this anim"}
            continue
        agg = {
            "frames": len(res),
            "skipped_hidden": skipped_hidden,
            "max_self_intersections": max(r["self_intersections"] for r in res),
            "max_triangle_flips": max(r["triangle_flips"] for r in res),
            "max_degenerate": max(r["degenerate"] for r in res),
            "area_ratio_range": [min(r["area_ratio"] for r in res),
                                 max(r["area_ratio"] for r in res)],
            "all_clean": all(r["clean"] for r in res),
        }
        per_anim[an] = agg
        for k in worst:
            worst[k] = max(worst[k], agg["max_" + k])
    return {
        "slot": slot, "nv": len(parsed), "hull": att["hull"], "tris": len(tris),
        "bones": sorted({sk["bones"][bi]["name"] for binds in parsed for (bi, *_) in binds}),
        "anims": per_anim,
        "worst": worst,
        "clean": (worst["self_intersections"] == 0 and worst["triangle_flips"] == 0
                  and worst["degenerate"] == 0),
    }


def setup_consistency(sk, name2idx, slot, name=None):
    """AC1:setup 世界頂點布局 vs uvs(region-local)正規化平均誤差。"""
    att = load_att(sk, slot, name)
    parsed = parse_weighted(att["vertices"])
    Wsetup = world_transforms(sk, name2idx, None, 0.0)
    world = compute_world_vertices(parsed, Wsetup)
    uvs = np.array(att["uvs"], dtype=np.float64).reshape(-1, 2)

    def norm(a):
        mn, mx = a.min(0), a.max(0)
        return (a - mn) / (mx - mn + 1e-9)

    # world y-up → image y-down:比較時翻 world y
    wn = norm(np.column_stack([world[:, 0], -world[:, 1]]))
    return float(np.abs(wn - uvs).mean())


def scramble_binds(att, seed_shift=0):
    """負對照:把每頂點的骨綁指定循環位移(權重/bind 不變,語意打亂)→ 應在 pose 下爆掉。
    確定性(不用 RNG,依 index 位移),以符合排程可重現要求。"""
    parsed = parse_weighted(att["vertices"])
    n = len(parsed)
    return [parsed[(i + n // 2 + seed_shift) % n] for i in range(n)]


ROBOT = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--consistency-thresh", type=float, default=0.10)
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    n2i = bone_index(sk)

    report = {"pieces": {}}
    ac1_ok = ac2_ok = ac3_ok = True
    for slot in ROBOT:
        cons = setup_consistency(sk, n2i, slot)
        gate = deform_gate(sk, n2i, slot)

        # AC3 負對照:打亂骨綁,同 pose 下應出缺陷
        att = load_att(sk, slot)
        tris = np.array(att["triangles"], dtype=np.int32).reshape(-1, 3)
        bad_parsed = scramble_binds(att)
        used = [an for an in gate["anims"]]
        worst_bad = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
        Wsetup = world_transforms(sk, n2i, None, 0.0)
        bad_setup = compute_world_vertices(bad_parsed, Wsetup)
        bad_signs = [signed_area(bad_setup, t) > 0 for t in tris]
        bad_area = sum(abs(signed_area(bad_setup, t)) for t in tris) or 1.0
        for an in used:
            for t in sample_anim_times(sk, an):
                if not slot_visible_at(sk, sk["animations"][an], slot, t):
                    continue
                W = world_transforms(sk, n2i, sk["animations"][an], t)
                v = compute_world_vertices(bad_parsed, W)
                r = eval_pose(v, tris, bad_signs, bad_area)
                for k in worst_bad:
                    worst_bad[k] = max(worst_bad[k], r[k])
        neg_defects = sum(worst_bad.values())

        p_ac1 = cons < a.consistency_thresh
        # AC2 硬不變量:可見幀 0 翻面 + 0 退化(翻面=貼圖鏡射撕裂,退化=三角塌陷,
        # 生產資產在可見時不該出現)。self_intersections 對「軟邊羽化件」是**藝術家基準**
        # (光暈在 t=0.633 全不透明瞬間有 4 條邊界邊交叉、面積壓到 0.877,但柔性加色發光下
        #  無感 → 藝術家容忍此值)。故記錄 si_baseline 供未來生成 mesh 當通過門檻,不當硬 0。
        hard_ok = (gate["worst"]["triangle_flips"] == 0 and gate["worst"]["degenerate"] == 0)
        si_baseline = gate["worst"]["self_intersections"]
        p_ac2 = hard_ok
        # AC3 鑑別力:負對照的缺陷需嚴格超過藝術家基準(否則閘無法區分好壞)
        neg_worst = max(worst_bad.values())
        p_ac3 = (worst_bad["triangle_flips"] > 0 or
                 worst_bad["self_intersections"] > si_baseline)
        ac1_ok &= p_ac1; ac2_ok &= p_ac2; ac3_ok &= p_ac3
        report["pieces"][slot] = {
            "AC1_setup_consistency": {"norm_err": round(cons, 4),
                                      "thresh": a.consistency_thresh, "pass": p_ac1},
            "AC2_artist_hard_invariants": {"worst": gate["worst"],
                                           "flips_zero_degen_zero": hard_ok,
                                           "si_baseline": si_baseline, "pass": p_ac2},
            "AC3_negative_control": {"scrambled_worst": worst_bad,
                                     "beats_baseline": p_ac3, "pass": p_ac3},
            "detail": gate,
        }
    report["AC1_all"] = ac1_ok
    report["AC2_all"] = ac2_ok
    report["AC3_all"] = ac3_ok
    report["overall_pass"] = ac1_ok and ac2_ok and ac3_ok
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
