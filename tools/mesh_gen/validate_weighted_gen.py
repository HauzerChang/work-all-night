#!/usr/bin/env python3
"""驗證 weighted mesh 生成器(generate_weighted_mesh)對 Award 機器人真值的品質。

AC(對**不透明結構件**;軟性加成件另計):
  AC1 生成 mesh 重建 setup pose 乾淨(si=0 / degen=0)。
  AC2 真實 Legend 動畫下 si=0 / flip=0(過 weighted_deform_eval 同一道閘)。
  AC3 變形平滑度不劣於藝術家:edge-length CV 增幅 ≤ 藝術家 + 裕度、area_ratio_std ≈ 藝術家。
  AC4 頂點預算合理:≤ 1.4× 藝術家頂點數。

軟性加成件(光暈 halo):additive 混合下自我重疊視覺無害,且藝術家自身即 si>0 →
  **不列入 si=0 硬性 AC**,僅記錄生成 vs 藝術家的重疊幅度(誠實界定生成器對軟件尚未追平藝術家手工拓樸)。
"""
import json, sys
import generate_weighted_mesh as G
import weighted_deform_eval as W

# slot → (max_area, 類型)。opaque 走硬性 AC;soft 只記錄。
PARTS = {
    "機器人拆件/身體": (1500, "opaque"),
    "機器人拆件/左手": (1400, "opaque"),
    "機器人拆件/光暈": (1500, "soft"),
}
CV_MARGIN = 0.02      # AC3:CV 增幅可比藝術家多 0.02
AR_STD_MARGIN = 0.03  # AC3:area_ratio_std 可比藝術家多 0.03
NV_MULT = 1.4         # AC4


def eval_slot(slot, max_area):
    a = W.evaluate_weighted_mesh("assets/Award.json", slot)
    g = G.generate_for_slot("assets/Award.json", slot, max_area=max_area)
    r = W.eval_pv(g["sk"], g["bones"], g["byname"], g["order"], g["bidx_to_name"],
                  g["pv"], g["tris"], g["mesh_bone_names"])
    return a, r


def run():
    report = {"parts": {}, "overall_pass": True}
    for slot, (ma, kind) in PARTS.items():
        a, r = eval_slot(slot, ma)
        nm = slot.split("/")[-1]
        entry = {
            "kind": kind, "artist_nv": a["nv"], "gen_nv": r["nv"],
            "gen_worst": r["worst"], "gen_smooth": r["smoothness"],
            "artist_smooth": a["smoothness"],
        }
        if kind == "opaque":
            ac1 = r["setup"]["clean"]
            ac2 = (r["worst"]["self_intersections"] == 0 and r["worst"]["triangle_flips"] == 0)
            ac3 = (r["smoothness"]["edge_cv_increase_max"] <= a["smoothness"]["edge_cv_increase_max"] + CV_MARGIN
                   and r["smoothness"]["area_ratio_std"] <= a["smoothness"]["area_ratio_std"] + AR_STD_MARGIN)
            ac4 = r["nv"] <= a["nv"] * NV_MULT
            entry["AC"] = {"AC1_setup": ac1, "AC2_deform_clean": ac2, "AC3_smoothness": ac3, "AC4_budget": ac4}
            entry["pass"] = all([ac1, ac2, ac3, ac4])
            report["overall_pass"] &= entry["pass"]
        else:
            entry["note"] = ("軟性加成件:si 不列硬性 AC;生成 si=%d vs 藝術家 si=%d(生成器對軟件極端 reveal "
                             "尚未追平藝術家手工拓樸,屬已知限制)" %
                             (r["worst"]["self_intersections"], a["worst"]["self_intersections"]))
            entry["pass"] = None
        report["parts"][nm] = entry
    return report


if __name__ == "__main__":
    rep = run()
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print("\nOPAQUE 件 OVERALL:", "PASS ✅" if rep["overall_pass"] else "FAIL ❌")
    sys.exit(0 if rep["overall_pass"] else 1)
