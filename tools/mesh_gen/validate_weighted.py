#!/usr/bin/env python3
"""S3 weighted-mesh 骨骼變形評估器 — 標準驗收面板(對 Award 真實美術 weighted mesh)。

補上 STATE 標記的「唯一未驗維度」:weighted mesh 骨骼變形平滑度。
真值:Award.json 機器人 3 件(光暈/左手/身體),藝術家手綁權重 + 骨架 + 動畫。

三條 AC:
  AC1 蒙皮數值正確性:光暈 Award_Legend_In 末幀應回到獨立算出的 setup(area_ratio≈1、strain≈0)。
      → 證明整條 FK(root→…→4_LEG6)+ weighted 蒙皮數學正確(動畫把骨帶走再帶回,獨立 setup 完全吻合)。
  AC2 藝術家基線:4 件在真實 Loop 動作下 foldover-clean(0 自交/0 翻面/0 退化)。
      (In 動作另報:光暈 In 是真實「glow 爆入」→ 軟性加法貼圖容許重疊,非 bug,見 knowledge。)
  AC3 鑑別力(複合閘):對照硬綁(單骨剛體)負對照。
      (a) 應變平滑度:hard 的 max_strain 應顯著 > 藝術家(平滑權重變形均勻)。
      (b) foldover 韌性:放大動作,藝術家平滑權重的破裂 k 應 ≥ 硬綁;
          **例外(誠實界定)**:硬綁塌成單骨時退化為剛體 → 永不自交(break_k=None)卻也不關節化,
          故 foldover 單獨不足,必須與應變平滑度**複合**判定(此即本次方法論結論)。

用法:python3 tools/mesh_gen/validate_weighted.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import weighted_deform as W

ROBOT = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def main(path="assets/Award.json"):
    skel = W.load_skeleton(path)
    report = {"ac1": {}, "ac2": {}, "ac3": {}}

    # ---- AC1 蒙皮數值正確性 ----
    r = W.eval_mesh_anim(skel, "機器人拆件/光暈", "機器人拆件/光暈", "Award_Legend_In")
    last = r["frames"][-1]
    ac1_pass = abs(last["area_ratio"] - 1.0) < 1e-3 and last["max_strain"] < 1e-3
    report["ac1"] = {"end_time": last["time"], "area_ratio": last["area_ratio"],
                     "max_strain": last["max_strain"], "pass": bool(ac1_pass)}

    # ---- AC2 藝術家基線(Loop 乾淨;In 另報)----
    ac2_all = True
    for slot in ROBOT:
        row = {}
        for anim in ["Award_Legend_Loop", "Award_Legend_In"]:
            rr = W.eval_mesh_anim(skel, slot, slot, anim)
            row[anim] = {"clean": rr["clean"], "worst": rr["worst"], "nframes": rr["nframes"]}
        # 判定基線只看 Loop 乾淨(In 的 glow 爆入容許重疊)
        loop_clean = row["Award_Legend_Loop"]["clean"]
        ac2_all = ac2_all and loop_clean
        row["loop_baseline_pass"] = loop_clean
        report["ac2"][slot] = row

    # ---- AC3 鑑別力(複合:應變 + foldover 韌性)----
    # 只在「真正多骨」的 mesh 上要求鑑別:若所有頂點皆由同一骨主導(near single-bone),
    # 該件根本不測試多骨平滑度 → 標 N/A、排除於通過判定(誠實界定,非放水)。
    ac3_ok = True
    for slot in ROBOT:
        a = W.get_attachment(skel, slot, slot)
        vw = W.parse_weighted(a)[0]
        # 主導骨分布
        dom = {}
        for v in vw:
            bi = max(v, key=lambda e: e[3])[0]
            dom[bi] = dom.get(bi, 0) + 1
        n_dom_bones = len(dom)
        single_bone_dominant = n_dom_bones < 2
        hardvw = W.hardify(vw)
        art = W.eval_mesh_anim(skel, slot, slot, "Award_Legend_Loop")
        hard = W.eval_mesh_anim(skel, slot, slot, "Award_Legend_Loop", verts_w_override=hardvw)
        bp_art = W.stress_break_point(skel, slot, slot, "Award_Legend_Loop")
        bp_hard = W.stress_break_point(skel, slot, slot, "Award_Legend_Loop", verts_w_override=hardvw)
        strain_art = art["worst"]["max_strain"]
        strain_hard = hard["worst"]["max_strain"]
        rigid_degenerate = bp_hard["break_k"] is None  # 硬綁塌成單骨 → 剛體
        strain_discriminates = strain_hard > strain_art + 1e-6
        fold_discriminates = (not rigid_degenerate) and (
            (bp_art["break_k"] or 99) >= (bp_hard["break_k"] or 0))
        discriminates = strain_discriminates or fold_discriminates
        applicable = not single_bone_dominant
        if applicable:
            ac3_ok = ac3_ok and discriminates
        report["ac3"][slot] = {
            "n_dominant_bones": n_dom_bones,
            "single_bone_dominant": single_bone_dominant,
            "applicable": applicable,
            "strain_artist": strain_art, "strain_hard": strain_hard,
            "break_k_artist": bp_art["break_k"], "break_k_hard": bp_hard["break_k"],
            "hard_rigid_degenerate": rigid_degenerate,
            "strain_discriminates": strain_discriminates,
            "fold_discriminates": fold_discriminates,
            "discriminates": discriminates if applicable else "N/A (single-bone-dominant)"}

    overall = report["ac1"]["pass"] and ac2_all and ac3_ok
    report["summary"] = {"ac1_skin_correct": report["ac1"]["pass"],
                         "ac2_artist_baseline_clean": ac2_all,
                         "ac3_evaluator_discriminates": ac3_ok,
                         "overall_pass": overall}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return overall


if __name__ == "__main__":
    ok = main(*(sys.argv[1:2]))
    sys.exit(0 if ok else 1)
