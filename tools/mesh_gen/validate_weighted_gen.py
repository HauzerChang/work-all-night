#!/usr/bin/env python3
"""S3 — 生成 weighted mesh 的變形品質對照閘(整合 AC)。

用**已校準**的 `weighted_deform_eval`(_checker_validated=True + 負對照有鑑別力),
對我方 `generate_weighted_mesh` 產出的 weighted mesh,在**真實動畫骨骼 pose** 下量化:
  AC-W1  clean:可見幀 0 自交 / 0 翻面 / 0 退化(= 達美術水準的拓樸穩健)。
  AC-W2  smoothness:面積梯度 CV 與美術同量級(≤ 美術 ×1.5)→ 骨綁權重平滑度達標。
  AC-W3  頂點經濟度:記錄 gen vs art 頂點數(可調 interior_spacing 觀察密度↔平滑度)。

真值:美術這 3 件的權重+骨架已在 Award.json;骨集合沿用真值(見 generator 限制)。
"""
import json, sys
import numpy as np

import spine_skeleton as ss
from weighted_deform_eval import eval_part, load_part, DRIVING_ANIMS
from generate_weighted_mesh import generate_part

PARTS = ["機器人拆件/左手", "機器人拆件/身體", "機器人拆件/光暈"]


def art_metrics(sk, slot):
    vw, tris, hull, name = load_part(sk.data, slot)
    per_anim, worst, setup = eval_part(sk, slot, name, vw, tris, DRIVING_ANIMS)
    cv = _cv_range(per_anim)
    return {"nv": len(vw), "worst": worst, "cv": cv,
            "clean": all(v == 0 for v in worst.values())}


def _cv_range(per_anim):
    lo = min((a["smoothness_cv_range"][0] for a in per_anim.values()), default=0)
    hi = max((a["smoothness_cv_range"][1] for a in per_anim.values()), default=0)
    return [round(lo, 3), round(hi, 3)]


def gen_metrics(sk, slot, spacing):
    g = generate_part(sk, slot, interior_spacing=spacing)
    vw = ss.decode_weighted(g["vertices"])
    tris = np.array(g["triangles"], dtype=np.int32).reshape(-1, 3)
    per_anim, worst, setup = eval_part(sk, slot, g["name"], vw, tris, DRIVING_ANIMS)
    return {"nv": g["gen_nv"], "tris": g["gen_tris"], "worst": worst,
            "cv": _cv_range(per_anim), "clean": all(v == 0 for v in worst.values()),
            "used_bones": g["used_bones"]}


def run():
    sk = ss.load("assets/Award.json")
    # 各件用不同內部密度(光暈為軟邊 fan,較疏;身體較密服務骨變形)
    spacing = {"機器人拆件/左手": 26.0, "機器人拆件/身體": 24.0, "機器人拆件/光暈": 40.0}
    report = {}
    all_pass = True
    for slot in PARTS:
        art = art_metrics(sk, slot)
        gen = gen_metrics(sk, slot, spacing[slot])
        cv_ok = gen["cv"][1] <= art["cv"][1] * 1.5 + 1e-6
        ac_w1 = gen["clean"]
        ac_w2 = cv_ok
        part_pass = ac_w1 and ac_w2
        all_pass = all_pass and part_pass
        report[slot] = {
            "art_nv": art["nv"], "gen_nv": gen["nv"], "gen_tris": gen["tris"],
            "used_bones": gen["used_bones"],
            "AC_W1_clean": ac_w1, "gen_worst": gen["worst"],
            "AC_W2_smoothness": ac_w2, "gen_cv": gen["cv"], "art_cv": art["cv"],
            "part_pass": part_pass,
        }
    report["_all_pass"] = all_pass
    return report


def density_sweep(slot="機器人拆件/身體"):
    """展示「內部取樣密度 ↔ 頂點數 ↔ 變形平滑度(CV)」的槓桿關係。"""
    sk = ss.load("assets/Award.json")
    rows = []
    for sp in [40.0, 30.0, 24.0, 18.0, 14.0]:
        g = gen_metrics(sk, slot, sp)
        rows.append({"spacing": sp, "nv": g["nv"], "clean": g["clean"], "cv": g["cv"]})
    return {"slot": slot, "sweep": rows}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "sweep":
        print(json.dumps(density_sweep(), ensure_ascii=False, indent=2))
    else:
        rep = run()
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        print("\n_all_pass:", rep["_all_pass"])
        sys.exit(0 if rep["_all_pass"] else 1)
