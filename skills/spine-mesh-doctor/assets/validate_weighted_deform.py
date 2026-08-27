#!/usr/bin/env python3
"""驗證 weighted_deform_eval 這支閘本身可信(對照藝術家真值 + 負對照),並輸出 PASS/FAIL。

三道校驗(對照 unweighted deform_eval 的 _checker_validated 方法論):
  1. 自一致性(setup):由 weighted 綁定重建 setup pose → 每 mesh 0 自交/0 塌陷
     (證 bone world transform + skinning 數學正確,能重現藝術家靜態形狀)。
  2. 藝術家真值(真實動畫):**不透明結構件**(身體/左手)在其驅動動畫全幀乾淨(si=0/flip=0)
     → 證閘不會冤枉好 mesh(誤報)。**軟性加成件**(光暈)容許重疊(加成混合下不可見),
     故不列入 si=0 硬性要求,僅記錄其重疊幅度(誠實界定)。
  3. 鑑別力(負對照):破壞綁定(打亂權重)在放大動作下必產生自交/翻面
     → 證閘抓得到壞綁定(不會漏報),且能隨動作幅度分離『藝術家 vs 壞綁定』。

真值來源:assets/Award.json 的 3 個機器人 weighted mesh + 12 支真實動畫。
"""
import json, sys
import weighted_deform_eval as W

# 依 attachment 語意分類(來自 s3-robot-mesh-vs-award 的觀察:光暈是軟邊 additive halo)
OPAQUE = ["機器人拆件/身體", "機器人拆件/左手"]   # 不透明結構件:硬性 si=0
SOFT = ["機器人拆件/光暈"]                          # 軟性加成:容許重疊,僅記錄


def run(path="assets/Award.json"):
    results = {"checks": {}, "detail": {}}
    ok = True

    # ---- 1. 自一致性(setup 重建)----
    setup_ok = True
    for slot in OPAQUE + SOFT:
        r = W.evaluate_weighted_mesh(path, slot)
        results["detail"][slot] = {
            "nv": r["nv"], "tris": r["tris"], "bones": r["bones"],
            "setup_clean": r["setup"]["clean"],
            "worst_real": r["worst"],
        }
        if not r["setup"]["clean"]:
            setup_ok = False
    results["checks"]["1_setup_selfconsistent"] = setup_ok
    ok &= setup_ok

    # ---- 2. 藝術家真值:不透明件真實動畫全乾淨 ----
    opaque_ok = True
    for slot in OPAQUE:
        r = W.evaluate_weighted_mesh(path, slot)
        clean = (r["worst"]["self_intersections"] == 0 and r["worst"]["triangle_flips"] == 0
                 and r["worst"]["degenerate"] == 0)
        results["detail"][slot]["real_anim_clean"] = clean
        if not clean:
            opaque_ok = False
    results["checks"]["2_artist_opaque_clean_on_real_anims"] = opaque_ok
    ok &= opaque_ok
    # 軟件僅記錄(不影響 PASS)
    for slot in SOFT:
        r = W.evaluate_weighted_mesh(path, slot)
        overlap = {an: a["max_self_intersections"] for an, a in r["anims"].items()
                   if a["max_self_intersections"] > 0}
        results["detail"][slot]["soft_overlap_by_anim"] = overlap
        results["detail"][slot]["note"] = "軟性加成 halo,reveal 期自我重疊屬可見無害(additive)"

    # ---- 3. 鑑別力:負對照必破 ----
    # 3a. 直接負對照(動作足夠的件:左手)
    hand = W.evaluate_weighted_mesh(path, "機器人拆件/左手", mutate=W.mutate_scramble_weights)
    disc_direct = not (hand["worst"]["self_intersections"] == 0 and hand["worst"]["triangle_flips"] == 0)
    # 3b. 放大動作分離(近剛體件:身體),藝術家維持 si=0 而壞綁定 si>0
    amp = 4.0
    art = W.evaluate_weighted_mesh(path, "機器人拆件/身體", amplify=amp)
    bad = W.evaluate_weighted_mesh(path, "機器人拆件/身體", mutate=W.mutate_scramble_weights, amplify=amp)
    art_si = art["worst"]["self_intersections"]
    bad_si = bad["worst"]["self_intersections"]
    disc_amp = (art_si == 0 and bad_si > 0)
    results["detail"]["discrimination"] = {
        "hand_scramble_worst": hand["worst"],
        f"body_amp{amp:.0f}_artist_si": art_si,
        f"body_amp{amp:.0f}_scrambled_si": bad_si,
    }
    disc_ok = disc_direct and disc_amp
    results["checks"]["3_discriminative_negative_controls"] = disc_ok
    ok &= disc_ok

    results["overall_pass"] = bool(ok)
    return results


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    rep = run(path)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print("\nOVERALL:", "PASS ✅" if rep["overall_pass"] else "FAIL ❌")
    sys.exit(0 if rep["overall_pass"] else 1)
