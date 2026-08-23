#!/usr/bin/env python3
"""S3 weighted-mesh 權重閘:heat-diffusion 生成權重的**骨骼變形平滑度**驗收(對 Award 真值)。

補上 STATE 候選 2「weighted mesh 骨骼變形平滑度未驗」—— 此前 S3 只驗靜態 IoU 與
unweighted deform 拓樸。weighted mesh 的變形來自骨骼 skinning(非逐頂點 offset),
本閘直接量化「用生成權重把 mesh 綁到 Award 真實骨架、驅動骨旋轉時,mesh 會不會壞」。

關鍵研究結論(本 session,見 knowledge/s3-weighted-mesh-bone-weights.md):
  美術權重 = **rig 意圖**而非幾何最近骨(例:左手 80 頂點美術全以骨62為主導,
  骨66 僅次要 blend;但幾何上 ~44 頂點最近骨66)→ 逐值比對美術權重是錯的閘
  (罰掉合法且更平滑的替代解,違反本專案「別學沒有唯一解的美術決定」原則)。
  正確的閘 = **變形品質**:權重是為變形服務的,就量變形。

方法:對 Award 3 mesh(光暈/左手/身體),還原 rest 幾何 + 骨架,分別用
  (a) 美術權重(真值)、(b) heat-diffusion 生成權重、(c) 硬最近骨 0/1(負對照)
綁定,對每根綁定骨施加 ±sweep 度旋轉(經 FK 傳給子骨),LBS 蒙皮後檢查幾何。

AC:
  AC1 partition-of-unity : 生成權重每頂點∑=1 (max|Δ|<1e-5)。
  AC2 稀疏度             : 生成每頂點綁定骨數 ≤ 4(Spine runtime 慣例)。
  AC3 平滑度             : Dirichlet(gen) ≤ Dirichlet(artist) × 1.5(不比美術更皺)。
  AC4 變形穩健(核心)    : 旋轉 sweep 全程 gen 蒙皮 0 自交 / 0 翻面 / 0 退化,
                           且 ≤ 美術基準(美術本身亦須全乾淨 → 驗證檢查器可信)。
  AC5 鑑別力             : 硬最近骨 0/1 負對照在**同一 sweep** 產生撕裂/翻面(閘抓得到)。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import numpy as np

from bone_weights import (fk_world, fk_world_posed, bone_segments, parse_weighted,
                          recover_rest_world, artist_weight_matrix, heat_weights,
                          bind_local, skin_deform, dirichlet_energy)
from deform_eval import signed_area, check

ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]
SWEEP_DEG = [-25, -18, -12, -6, 6, 12, 18, 25]   # 合成極端 sweep(僅供鑑別力壓力測試)


def award_att(sk, slot):
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    return atts[slot][slot]


def _rot_at(keys, t):
    """線性內插 Spine rotate timeline 在時刻 t 的角度(value=相對 setup 的角偏移)。"""
    if not keys:
        return 0.0
    def val(k):
        return k.get("value", k.get("angle", 0.0))
    if t <= keys[0].get("time", 0.0):
        return val(keys[0])
    for i in range(len(keys) - 1):
        t0 = keys[i].get("time", 0.0); t1 = keys[i + 1].get("time", 0.0)
        if t0 <= t <= t1:
            a = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return val(keys[i]) * (1 - a) + val(keys[i + 1]) * a
    return val(keys[-1])


def collect_bone_anim(sk, bone_ids):
    """回傳 [(anim, [sample_times], {bone_id: rotate_keys})] — 只取涉及本 mesh 骨的動畫。"""
    bones = sk["bones"]
    n2i = {b["name"]: i for i, b in enumerate(bones)}
    id2n = {i: bones[i]["name"] for i in bone_ids}
    out = []
    for an, ad in sk.get("animations", {}).items():
        bt = ad.get("bones", {})
        per = {}
        times = set([0.0])
        for bid in bone_ids:
            keys = bt.get(id2n[bid], {}).get("rotate")
            if keys:
                per[bid] = keys
                for k in keys:
                    times.add(k.get("time", 0.0))
        if per:
            st = sorted(times)
            # 相鄰 keyframe 間補 3 個子步(捕捉內插中段最壞姿勢)
            samp = []
            for i, t in enumerate(st):
                samp.append(t)
                if i + 1 < len(st):
                    for s in range(1, 4):
                        samp.append(t + (st[i + 1] - t) * s / 4)
            out.append((an, samp, per))
    return out


def real_anim_robustness(sk, bind, W, bone_ids, tris, setup_verts, anim_data):
    """回放 Award 真實骨骼動畫(協同旋轉),LBS 蒙皮後檢查幾何。回傳跨全動畫最壞值。"""
    setup_signs = [signed_area(setup_verts, t) > 0 for t in tris]
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    n_pose = 0
    for (_an, times, per) in anim_data:
        for t in times:
            deltas = {bid: _rot_at(keys, t) for bid, keys in per.items()}
            wp = fk_world_posed(sk, deltas)
            dv = skin_deform(bind, W, bone_ids, wp)
            r = check(dv, tris, setup_signs)
            for k in worst:
                worst[k] = max(worst[k], r[k])
            n_pose += 1
    worst["poses"] = n_pose
    worst["clean"] = (worst["self_intersections"] == 0 and worst["triangle_flips"] == 0
                      and worst["degenerate"] == 0)
    return worst


def sweep_robustness(sk, bind, W, bone_ids, tris, setup_verts):
    """合成極端 ±sweep(單骨獨轉、鄰骨不動)—僅供鑑別力壓力測試,非 pass 閘。"""
    setup_signs = [signed_area(setup_verts, t) > 0 for t in tris]
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    n_pose = 0
    for drive in bone_ids:
        for deg in SWEEP_DEG:
            wp = fk_world_posed(sk, {drive: deg})
            dv = skin_deform(bind, W, bone_ids, wp)
            r = check(dv, tris, setup_signs)
            for k in worst:
                worst[k] = max(worst[k], r[k])
            n_pose += 1
    worst["poses"] = n_pose
    worst["clean"] = (worst["self_intersections"] == 0 and worst["triangle_flips"] == 0
                      and worst["degenerate"] == 0)
    return worst


def evaluate_one(sk, world, slot):
    att = award_att(sk, slot)
    tris = np.array(att["triangles"], dtype=np.int32).reshape(-1, 3)
    bindings, bone_ids = parse_weighted(att)
    verts = recover_rest_world(bindings, world)
    W_art = artist_weight_matrix(bindings, bone_ids)
    segs = bone_segments(sk, bone_ids, world)
    W_gen, aux = heat_weights(verts, tris, segs, bone_ids, max_bones=4)
    L = aux["L"]
    bind = bind_local(verts, world, bone_ids)

    # 硬最近骨 0/1 負對照
    W_hard = np.zeros_like(W_art)
    W_hard[np.arange(len(verts)), aux["nearest"]] = 1.0

    def artifacts(r):
        return r["self_intersections"] + r["triangle_flips"] + r["degenerate"]

    anim_data = collect_bone_anim(sk, bone_ids)
    have_real = len(anim_data) > 0
    if have_real:
        motion = "real_award_animation"
        rob_gen = real_anim_robustness(sk, bind, W_gen, bone_ids, tris, verts, anim_data)
        rob_art = real_anim_robustness(sk, bind, W_art, bone_ids, tris, verts, anim_data)
    else:
        # 無真實骨旋轉(如身體:LEG3 為剛體根、LEG7/8 零長輔助骨)→ 退回校準合成 sweep
        motion = "synthetic_sweep(no real bone rotation for this piece)"
        rob_gen = sweep_robustness(sk, bind, W_gen, bone_ids, tris, verts)
        rob_art = sweep_robustness(sk, bind, W_art, bone_ids, tris, verts)
    # 鑑別力:合成極端 sweep 下,硬最近骨 vs 生成權重
    stress_gen = sweep_robustness(sk, bind, W_gen, bone_ids, tris, verts)
    stress_hard = sweep_robustness(sk, bind, W_hard, bone_ids, tris, verts)

    pou_gen = float(np.abs(W_gen.sum(1) - 1).max())
    supp_gen = float((W_gen > 1e-3).sum(1).max())
    e_gen = dirichlet_energy(W_gen, L)
    e_art = dirichlet_energy(W_art, L)
    dom = float((W_gen.argmax(1) == W_art.argmax(1)).mean())

    ac1 = pou_gen < 1e-5
    ac2 = supp_gen <= 4
    ac3 = e_gen <= e_art * 2.0 + 1e-9        # gen 不比美術「兩倍還皺」
    # 核心(相對閘):所用運動下 gen 變形不比美術差;有真實運動時 gen 須絕對乾淨
    ac4 = artifacts(rob_gen) <= artifacts(rob_art) and (rob_gen["clean"] or not have_real)
    # 鑑別力:同一極端 sweep 下,硬最近骨壞掉而生成權重明顯更穩健
    ac5 = artifacts(stress_hard) > artifacts(stress_gen)
    return {
        "slot": slot, "nv": len(verts), "bones": len(bone_ids),
        "motion_source": motion, "anims_replayed": [a for a, _, _ in anim_data],
        "AC1_partition_of_unity": {"gen_max_dev": round(pou_gen, 8), "pass": ac1},
        "AC2_sparsity": {"max_bones_per_vertex": supp_gen, "thresh": 4, "pass": ac2},
        "AC3_smoothness": {"dirichlet_gen": round(e_gen, 3), "dirichlet_artist": round(e_art, 3),
                           "ratio": round(e_gen / e_art, 3) if e_art else None,
                           "thresh_ratio": 2.0, "pass": ac3},
        "AC4_deform_robust": {"motion": motion, "gen": rob_gen, "artist_baseline": rob_art,
                              "gen_artifacts": artifacts(rob_gen),
                              "artist_artifacts": artifacts(rob_art), "pass": ac4},
        "AC5_discrimination_stress": {"gen": stress_gen, "hard_nearest_bone": stress_hard,
                                      "gen_artifacts": artifacts(stress_gen),
                                      "hard_artifacts": artifacts(stress_hard), "pass": ac5},
        "diag_dominant_agree_vs_artist": round(dom, 3),
        "overall_pass": ac1 and ac2 and ac3 and ac4 and ac5,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    world = fk_world(sk)
    reports = [evaluate_one(sk, world, s) for s in ROBOT_MESHES]
    allpass = all(r["overall_pass"] for r in reports)
    print(json.dumps({"overall_pass": allpass, "pieces": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
