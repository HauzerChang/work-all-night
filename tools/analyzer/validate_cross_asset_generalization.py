#!/usr/bin/env python3
"""candidate XA 自我驗收閘 — 主秀 beat 生成器**跨資產泛化**(純 CPU)。

**動機(攻擊重複 ~24 次的 honest boundary)**:S1 anim-forge 的每一條 cap(tier 幅度、
combo/wobble/squash/twist/charge/cascade 的 count-aware、…)結語都寫「**單一真值資產(robot)**,
與 anim-forge 同 HOLD」—— 整個生成能力一直只在 **一個** 資產(`robot_parts.psd`)上被驗過,
這是它遲遲無法離開 HOLD 的主因之一。但生成器本質是 **role-based**(`gen_loop(role,…)` 等依
`body/head/limb/特效` 路由,見 `gen_animations.py`),理應 **與資產無關**。本閘把「只在 robot
驗過」的結構簽章**實測**到**第二個獨立的真實資產** `Symbol_Ww.psd`(DJ 角色符號,18 件 vs
robot 6 件、180×180 畫布、全然不同的件集),證明泛化成立。

**關鍵分野(honest)**:主秀運動的「手感/美感」仍是 A 類(主觀,留使用者);本閘只驗**客觀、
與資產無關的結構簽章**是否在新資產上**仍成立**,以及**與資產相關的簽章**(cascade 跨件相位 threading)
是否**正確隨新資產幾何改變**。本閘 PASS **不**代表 anim-forge 可出貨(出貨是 C 類使用者拍板 +
美感 A 類);它**只**把「單一真值資產」這條 honest boundary 由「只在 robot 驗過」升級為
「在 2 個獨立真實資產驗過」—— 離開 HOLD 的**必要非充分**條件。

**為何可自主驗(不需藝術家真值)**:tier 幅度單調、介面 identity、count 段數遞增、cross-channel
守恆(squash det≡1 / twist φ)等都是**生成器自身數學的結構不變量**,對照的是生成器該產出什麼,
**不是**藝術家真值;故換一個骨架重跑即可自我驗收。唯一與資產相關的是 cascade 的 per-part 相位序
(讀件幾何/件序),本閘以「波序隨資產改變、threading 件數==資產件數」當 crux 鑑別子。

  XA1 pipeline on 2nd asset : 第二資產 `Symbol_Ww.psd` 端到端 build(slice→analyze→build→animate
                              →tier-variants)成功;8 個主秀 beat 家族(burst/hit/combo/charge/
                              cascade/wobble/squash/twist)× 4 檔位變體皆 present/finite/有 bone;
                              且**結構確實不同於 robot**(件數/畫布不同)→ 證是真·不同資產非 robot 複製。
  XA2 signatures (reuse)    : **復用 `validate_tier_variants.run()`**(與 per-cap 閘**同一度量**)在
                              第二資產上 → J2 介面 identity、J3 crux 幅度單調、J4 結構簽章、
                              J5 負對照(含平增益守衛)**全 PASS**。即:只在 robot 驗過的簽章,
                              在獨立資產上仍成立。
  XA3 count-aware (reuse)   : **復用 6 條 count 閘**(tier_combo / wobble / squash / twist / charge /
                              cascade_count)的 `run()` 在第二資產上 → 皆 `OVERALL_PASS`。即:count-aware
                              段數軸家族整體泛化到新資產。
  XA4 crux asset-dependent  : cascade 跨件相位 threading **隨資產幾何改變**:第二資產 per-part 峰時刻
                              依件序嚴格遞增且散佈 ≥ 門檻(仍一道有序跨件波),且 **threading 件數 ==
                              該資產件數**(symbol 18 ≠ robot 5),兩資產波序**成員/長度皆不同**
                              → 證波真讀資產幾何,非寫死 robot 樣式(寫死樣式在 18 件資產上會失敗/只穿 5 件)。
  XA5 anchor + neg-control  : (a) **ANCHOR**:同一 `validate_tier_variants.run()` 在 robot 上亦 PASS →
                              證本閘度量**重現既有 per-cap 結果**,故第二資產 PASS 是真泛化非放寬判準;
                              (b) **NEG**:第二資產上把增益階梯全設 1.0(平增益)→ 幅度單調性 FALSE
                              (本閘在新資產上仍保有鑑別力,非恆真)。此項直接取 XA2 回傳的
                              `J5_neg_control.c_flat_guard`(那本就在第二資產上跑平增益守衛)。

用法:
  python3 validate_cross_asset_generalization.py            # 摘要
  python3 validate_cross_asset_generalization.py --json     # 完整 JSON
"""
import argparse, importlib, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import gen_animations as G
from analyze_target import analyze
import build_spine
from validate_cascade import (series, peak_time, peak_times_in_order, cascade_spread,
                              is_strictly_increasing, SPREAD_THR)

GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
# 第二(新)資產 = 泛化目標;robot = anchor。皆在 repo。
SECOND = "assets/Symbol_Ww.psd"
ANCHOR = "assets/robot_parts.psd"
MAIN_SHOW_FAMILIES = {"burst", "hit", "combo", "charge", "cascade", "wobble", "squash", "twist"}
COUNT_GATES = ["validate_tier_combo_count", "validate_wobble_count", "validate_squash_count",
               "validate_twist_count", "validate_charge_count", "validate_cascade_count"]


def _resolve(psd):
    return psd if os.path.exists(psd) else os.path.join("..", "..", psd)


def _build(psd, out, **kw):
    build_spine.build(_resolve(psd), out, genre=GENRE, **kw)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _part_order(skel, sb):
    bn = {b["name"] for b in skel["bones"]}
    return ["b_" + G.safe(pe["part"]) for pe in sb["beats"][0]["parts"]
            if "b_" + G.safe(pe["part"]) in bn]


def _run_gate(modname, psd):
    """復用既有閘的 run():設其 PSD 後跑,回 (OVERALL_PASS, R)。與該閘度量逐條一致。"""
    m = importlib.import_module(modname)
    m.PSD = psd
    R = m.run()
    return bool(R.get("OVERALL_PASS")), R


def _cascade_threading(psd, out):
    """回傳 (ordered_ok, spread, bones_in_wave, n_parts)。"""
    skel = _build(psd, out, animate=False)
    sb = analyze(_resolve(psd), GENRE)["3_motion_storyboard"]
    order = _part_order(skel, sb)
    anims = G.build_animations(skel, sb)
    casc = anims["cascade"]
    bones_in_wave = [b for b in order if b in casc.get("bones", {})
                     and max(series(casc, b)) > 1.0001]
    pts = [peak_time(casc, b) for b in bones_in_wave]
    return (is_strictly_increasing(pts), round(cascade_spread(pts), 4),
            bones_in_wave, len([b for b in skel["bones"] if b["name"] != "root"]))


def run():
    R = {}

    # ---- XA1 pipeline on 2nd asset ----
    out2 = "/tmp/xa_second"
    skel2 = _build(SECOND, out2, animate=True, tier_variants=True)
    anims2 = skel2["animations"]
    present = {fam: all("{}__{}".format(fam, t) in anims2 for t in TIERS)
               for fam in MAIN_SHOW_FAMILIES}
    bad_finite, no_bones = [], []
    import spine_anim as SA
    for fam in MAIN_SHOW_FAMILIES:
        for t in TIERS:
            an = anims2.get("{}__{}".format(fam, t))
            if an is None:
                continue
            if not SA.all_finite(an):
                bad_finite.append("{}__{}".format(fam, t))
            if not an.get("bones"):
                no_bones.append("{}__{}".format(fam, t))
    skelA = _build(ANCHOR, "/tmp/xa_anchor_skel", animate=False)
    n2 = len([b for b in skel2["bones"] if b["name"] != "root"])
    nA = len([b for b in skelA["bones"] if b["name"] != "root"])
    structurally_different = (n2 != nA) and (skel2["skeleton"]["width"] != skelA["skeleton"]["width"]
                                             or skel2["skeleton"]["height"] != skelA["skeleton"]["height"])
    R["XA1_pipeline_2nd_asset"] = {
        "second_asset": SECOND, "n_parts_2nd": n2, "n_parts_anchor": nA,
        "canvas_2nd": [skel2["skeleton"]["width"], skel2["skeleton"]["height"]],
        "canvas_anchor": [skelA["skeleton"]["width"], skelA["skeleton"]["height"]],
        "families_present": present, "not_finite": bad_finite, "no_bones": no_bones,
        "structurally_different": structurally_different,
        "pass": all(present.values()) and not bad_finite and not no_bones and structurally_different}

    # ---- XA2 signatures on 2nd asset (reuse validate_tier_variants) ----
    tv_pass_2nd, tv_R_2nd = _run_gate("validate_tier_variants", SECOND)
    R["XA2_signatures_2nd"] = {
        "tier_variants_overall": tv_pass_2nd,
        "sub": {k: tv_R_2nd[k]["pass"] for k in tv_R_2nd if k != "OVERALL_PASS"},
        "pass": tv_pass_2nd}

    # ---- XA3 count-aware family on 2nd asset (reuse 6 count gates) ----
    count_res = {}
    for g in COUNT_GATES:
        ok, _ = _run_gate(g, SECOND)
        count_res[g] = ok
    R["XA3_count_aware_2nd"] = {"per_gate": count_res, "pass": all(count_res.values())}

    # ---- XA4 crux: asset-dependent cascade threading adapts ----
    ok2, spread2, wave2, parts2 = _cascade_threading(SECOND, "/tmp/xa_casc_2nd")
    okA, spreadA, waveA, partsA = _cascade_threading(ANCHOR, "/tmp/xa_casc_anchor")
    # 波真讀資產:threading 件數==資產件數(每件都入波);兩資產波序成員/長度不同。
    threads_all_2nd = (len(wave2) == parts2)
    threads_all_anchor = (len(waveA) == partsA)
    waves_differ = (len(wave2) != len(waveA)) or (set(wave2) != set(waveA))
    R["XA4_cascade_adapts"] = {
        "second": {"ordered": ok2, "spread": spread2, "n_in_wave": len(wave2), "n_parts": parts2},
        "anchor": {"ordered": okA, "spread": spreadA, "n_in_wave": len(waveA), "n_parts": partsA},
        "threads_all_parts_2nd": threads_all_2nd, "threads_all_parts_anchor": threads_all_anchor,
        "waves_differ_by_geometry": waves_differ,
        "pass": (ok2 and spread2 >= SPREAD_THR and threads_all_2nd
                 and okA and spreadA >= SPREAD_THR and threads_all_anchor
                 and waves_differ)}

    # ---- XA5 anchor (tier_variants on robot reproduces established result) + neg-control ----
    tv_pass_anchor, _ = _run_gate("validate_tier_variants", ANCHOR)
    # neg-control: 直接取 XA2 第二資產跑出的平增益守衛(那本就在第二資產上跑)
    flat_guard = tv_R_2nd["J5_neg_control"]["c_flat_guard"]
    flat_not_monotone = not flat_guard["flat_ladder_any_monotone"]
    R["XA5_anchor_neg_control"] = {
        "anchor_tier_variants_pass": tv_pass_anchor,
        "flat_gain_ladder_monotone_on_2nd": flat_guard["flat_ladder_any_monotone"],
        "flat_gain_correctly_not_monotone": flat_not_monotone,
        "pass": tv_pass_anchor and flat_not_monotone}

    R["OVERALL_PASS"] = all(R[k]["pass"] for k in R)
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    R = run()
    if a.json:
        print(json.dumps(R, ensure_ascii=False, indent=2))
    else:
        for k in ["XA1_pipeline_2nd_asset", "XA2_signatures_2nd", "XA3_count_aware_2nd",
                  "XA4_cascade_adapts", "XA5_anchor_neg_control"]:
            print("{:26s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        x1 = R["XA1_pipeline_2nd_asset"]
        print("  2nd asset: {} parts (anchor {}), canvas {} vs {}".format(
            x1["n_parts_2nd"], x1["n_parts_anchor"], x1["canvas_2nd"], x1["canvas_anchor"]))
        x4 = R["XA4_cascade_adapts"]
        print("  cascade threading: 2nd {} parts / anchor {} parts (波序隨幾何改變={})".format(
            x4["second"]["n_in_wave"], x4["anchor"]["n_in_wave"], x4["waves_differ_by_geometry"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
