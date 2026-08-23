#!/usr/bin/env python3
"""S2/S3 weighted-mesh 閘 + 對 Award 真實美術權重的驗收(補 STATE 候選 2 的唯一未驗維度)。

補上 knowledge/s3-robot-mesh-vs-award 誠實界定的唯一未驗維度:「靜態覆蓋率 PASS ≠ weighted
骨骼變形品質」。本工具對 Award 的 3 個 weighted mesh 件(光暈/左手/身體,真值權重+骨架在
assets/Award.json)驗收「骨綁權重生成器(bone-heat)」是否產生**有效且變形平滑**的權重。

—— 設計原則(關鍵教訓,見 knowledge/s3-weighted-mesh-binding)——
1. **權重「符合美術」是部分主觀的美術決定**(RULES:別用演算法學沒有唯一解的美術決定)。
   → 只對**客觀性質**下 pass/fail 閘;「與美術權重的相似度」僅**報告不 gating**。
2. **變形品質閘必須對藝術家真值自校準**:單骨孤立旋轉到「真實動畫範圍」端點仍可能超出
   美術設計的有效包絡而自交(光暈實測)。→ 測試包絡 = 「**美術真值在此仍 0 自交**的最大範圍」
   (auto-clamp),確保閘公平(在美術都會壞的姿態下要求生成器不壞不合理)。
3. **相似度度量要有鑑別力**:用「相對位移誤差」(‖gen位移−art位移‖ / ‖art位移‖),不要用
   對 mesh 對角線正規化的絕對誤差 —— 後者被大件(光暈 diag 951)稀釋,連「全綁單骨」的
   壞 rig 都能過(實測)→ 無鑑別力。

客觀 pass/fail 閘:
  A1 美術權重(正對照)通過內在閘:partition-of-unity≈1(容差 2e-4 容美術浮點)、0≤w≤1、非負。
  A2 負對照(破壞單位分割)被內在閘抓到。
  A3 負對照(撕裂 rig:相鄰頂點硬綁不同骨)被變形閘抓到(自交/翻面 > 0)。
  B  re-pose 自一致性:美術 bind 在 identity pose 重建 == setup 世界頂點(MAE≈0)。
  C1 生成權重通過內在閘(partition/bounded)。
  C2 生成權重在「美術自校準包絡」內 0 自交 / 0 翻面(變形平滑度 = weighted 的核心品質)。
報告(非 gating):
  R1 與美術權重的變形相似度(相對位移誤差 worst/mean);誠實標註幾何 bone-heat 對「軟/廣」
     件(光暈)因美術做了非幾何權重選擇而發散。
  R2 每骨測試包絡 + 美術在真實範圍端點的自交數(記錄 auto-clamp 依據)。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np

from weighted_mesh import (bone_world_matrices, parse_weighted, weighted_world_vertices,
                           load_weighted_attachment, bind_offsets_for_bones)
from bbw_weights import bone_heat_weights, bone_segments_from_skeleton
from deform_eval import check, signed_area

ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]
PU_TOL = 2e-4   # 美術權重存 JSON 僅 ~5 位小數;負對照殘差 0.5 遠大於此 → 不損鑑別力


def bone_rotation_ranges(sk):
    """所有動畫裡每骨 rotate timeline 的 delta 角範圍 {name:[lo,hi]}。"""
    rng = {}
    for a in sk.get("animations", {}).values():
        for bn, tl in a.get("bones", {}).items():
            if "rotate" in tl:
                vs = [k.get("angle", 0.0) for k in tl["rotate"]]
                lo, hi = min(vs), max(vs)
                r = rng.get(bn, [0.0, 0.0])
                rng[bn] = [min(r[0], lo), max(r[1], hi)]
    return rng


def artist_weight_matrix(per_vertex, bone_indices):
    col = {b: k for k, b in enumerate(bone_indices)}
    W = np.zeros((len(per_vertex), len(bone_indices)))
    for i, entry in enumerate(per_vertex):
        for (bidx, _bx, _by, w) in entry:
            W[i, col[bidx]] += w
    return W


def artist_bind_full(per_vertex, bone_indices):
    """每骨的 bind 座標 N×2(未綁該骨處為 0,對應權重 0)。"""
    out = {}
    for bidx in bone_indices:
        arr = np.zeros((len(per_vertex), 2))
        for i, entry in enumerate(per_vertex):
            for (b2, bx, by, _w) in entry:
                if b2 == bidx:
                    arr[i] = (bx, by)
        out[bidx] = arr
    return out


def intrinsic_gate(W):
    s = W.sum(1)
    pu_err = float(np.abs(s - 1.0).max())
    wmin = float(W.min()); wmax = float(W.max())
    ok = (pu_err < PU_TOL) and (wmin >= -1e-9) and (wmax <= 1.0 + 1e-9)
    return ok, {"partition_max_err": pu_err, "w_min": round(wmin, 6), "w_max": round(wmax, 6)}


def deform_world(bindings_by_bone, W, bone_names, bone_indices, bones_world):
    n = W.shape[0]
    out = np.zeros((n, 2))
    for k, bidx in enumerate(bone_indices):
        a, b, c, d, tx, ty = bones_world[bone_names[bidx]]
        bind = bindings_by_bone[bidx]
        px = a * bind[:, 0] + b * bind[:, 1] + tx
        py = c * bind[:, 0] + d * bind[:, 1] + ty
        out[:, 0] += W[:, k] * px
        out[:, 1] += W[:, k] * py
    return out


def tears(verts, tris, setup_signs):
    g = check(verts, tris, setup_signs)
    return g["self_intersections"] + g["triangle_flips"]


def clean_envelope(setup, tris, setup_signs, art_bind, W_art, bone_names, bone_indices,
                   bname, lo, hi, sk, samples=5):
    """把 [lo,hi] 依需要向 0 收縮,直到美術真值在所有取樣角都 0 自交;回傳 clamped (lo,hi, art_tears_raw)。"""
    def art_tears(alo, ahi):
        m = 0
        for ang in np.linspace(alo, ahi, samples):
            bw = bone_world_matrices(sk, rot_override={bname: ang})
            m = max(m, tears(deform_world(art_bind, W_art, bone_names, bone_indices, bw), tris, setup_signs))
        return m
    raw = art_tears(lo, hi)
    slo, shi = lo, hi
    for _ in range(12):
        if art_tears(slo, shi) == 0:
            break
        slo *= 0.75; shi *= 0.75
    return slo, shi, raw


def validate_piece(sk, slot, bone_names, ranges, margin=1.5):
    att = load_weighted_attachment(sk, slot)
    per = parse_weighted(att)
    tris = np.array(att["triangles"], np.int32).reshape(-1, 3)
    bone_indices = sorted({e[0] for entry in per for e in entry})
    max_infl = max(len(e) for e in per)

    bw0 = bone_world_matrices(sk)
    setup = weighted_world_vertices(per, bone_names, bw0)
    setup_signs = [signed_area(setup, t) > 0 for t in tris]

    W_art = artist_weight_matrix(per, bone_indices)
    art_bind = artist_bind_full(per, bone_indices)

    # --- A1 / A2 內在閘(正 + 負對照)---
    a1_ok, a1_m = intrinsic_gate(W_art)
    rowmod = (np.arange(1, len(per) + 1)[:, None] % 3) - 1   # 確定性擾動
    a2_ok, a2_m = intrinsic_gate(W_art * (1.0 + 0.5 * rowmod))
    A2 = not a2_ok

    # --- B 自一致性 ---
    setup_recon = deform_world(art_bind, W_art, bone_names, bone_indices, bw0)
    b_mae = float(np.abs(setup_recon - setup).mean())

    # --- 生成 bone-heat ---
    segs = bone_segments_from_skeleton(sk, bone_names, bone_indices, bw0)
    W_gen = bone_heat_weights(setup, tris, segs, max_influences=max_infl)
    gen_bind = bind_offsets_for_bones(setup, bw0, bone_names, bone_indices)
    c1_ok, c1_m = intrinsic_gate(W_gen)

    # --- A3 撕裂 rig 負對照(相鄰頂點硬綁交替骨)---
    W_torn = np.zeros((len(per), len(bone_indices)))
    for i in range(len(per)):
        W_torn[i, i % len(bone_indices)] = 1.0
    torn_tears = 0

    # --- 每骨:auto-clamp 到美術-clean 包絡,測 bone-heat 平滑度 + 相似度 ---
    per_bone = []
    gen_max_tears = 0
    torn_caught = False
    rel_vals = []
    for bidx in bone_indices:
        bname = bone_names[bidx]
        if bname not in ranges:
            per_bone.append({"bone": bname, "tested": False, "reason": "no rotate timeline"})
            continue
        lo, hi = ranges[bname]
        lo *= margin; hi *= margin
        if abs(hi - lo) < 1e-6:
            per_bone.append({"bone": bname, "tested": False, "reason": "zero range"})
            continue
        slo, shi, raw = clean_envelope(setup, tris, setup_signs, art_bind, W_art,
                                       bone_names, bone_indices, bname, lo, hi, sk)
        gt = tt = 0
        for ang in np.linspace(slo, shi, 5):
            bw = bone_world_matrices(sk, rot_override={bname: ang})
            gd = deform_world(gen_bind, W_gen, bone_names, bone_indices, bw)
            ad = deform_world(art_bind, W_art, bone_names, bone_indices, bw)
            td = deform_world(gen_bind, W_torn, bone_names, bone_indices, bw)
            gt = max(gt, tears(gd, tris, setup_signs))
            tt = max(tt, tears(td, tris, setup_signs))
            artd = ad - setup; gend = gd - setup
            den = float(np.sqrt((artd ** 2).sum(1)).mean())
            if den > 1e-6:
                rel_vals.append(float(np.sqrt(((gend - artd) ** 2).sum(1)).mean()) / den)
        gen_max_tears = max(gen_max_tears, gt)
        torn_tears = max(torn_tears, tt)
        if tt > 0:
            torn_caught = True
        per_bone.append({"bone": bname, "tested": True,
                         "real_range": [round(ranges[bname][0], 1), round(ranges[bname][1], 1)],
                         "tested_envelope": [round(slo, 1), round(shi, 1)],
                         "artist_tears_at_raw_x_margin": raw,
                         "boneheat_tears": gt})

    tested_any = any(p.get("tested") for p in per_bone)
    A3 = torn_caught if tested_any else True   # 無可測骨(剛性件)→ 撕裂閘不適用
    rel = {"worst": round(max(rel_vals), 3), "mean": round(float(np.mean(rel_vals)), 3),
           "n": len(rel_vals)} if rel_vals else {"worst": 0.0, "mean": 0.0, "n": 0}

    overall = a1_ok and A2 and A3 and (b_mae < 1e-6) and c1_ok and (gen_max_tears == 0)
    return {
        "slot": slot,
        "bones": [bone_names[b] for b in bone_indices],
        "nv": len(per), "tris": len(tris), "max_influences": max_infl,
        "rigidly_skinned": not tested_any,
        "A1_artist_intrinsic": {"pass": a1_ok, **a1_m},
        "A2_broken_partition_caught": {"pass": A2, "bad": a2_m},
        "A3_torn_rig_caught": {"pass": bool(A3), "torn_tears": torn_tears,
                               "note": "no rotating bone → rigid piece, gate n/a" if not tested_any else ""},
        "B_selfconsistency_mae": {"pass": b_mae < 1e-6, "value": round(b_mae, 8)},
        "C1_gen_intrinsic": {"pass": c1_ok, **c1_m},
        "C2_gen_deform_smooth": {"pass": gen_max_tears == 0, "max_tears": gen_max_tears},
        "R1_artist_similarity_reported": {**rel,
            "note": "相對位移誤差;權重相符屬部分主觀美術決定,僅報告不 gating。"
                    "高值=幾何 bone-heat 對非幾何美術權重的發散(軟/廣件如光暈)。"},
        "R2_per_bone_envelope": per_bone,
        "overall_pass": bool(overall),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--margin", type=float, default=1.5,
                    help="測試包絡 = 真實動畫範圍 × margin(再 auto-clamp 到美術-clean)")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    bone_names = [b["name"] for b in sk["bones"]]
    ranges = bone_rotation_ranges(sk)
    reports = [validate_piece(sk, s, bone_names, ranges, a.margin) for s in ROBOT_MESHES]
    allpass = all(r["overall_pass"] for r in reports)
    print(json.dumps({"overall_pass": allpass, "pieces": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
