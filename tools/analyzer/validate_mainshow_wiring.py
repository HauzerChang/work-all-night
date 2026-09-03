#!/usr/bin/env python3
"""candidate 0g 自我驗收閘 — 主秀 beat 已「併入 genre 先驗庫」端到端驗證(純 CPU,不靠肉眼)。

candidate 0f 造了主秀模板(hit/reveal),但只在 validate_beat_templates 用**手搭 storyboard**
(beat 名硬寫 "hit"/"reveal")驗過;真正的 `build_spine --animate` 走的是 genre 先驗庫的 beats,
其中 **slot_bigwin 只有 In/Loop/Out、缺主秀 payoff**。本次(0g)把主秀節拍**併進先驗庫**:
  - 先驗 beat 新增顯式 `cat`(運動類別),取代靠 beat 名關鍵字猜測(脆弱:'burst'∈reveal 關鍵字);
  - slot_bigwin 加 **Burst(cat=hit)** payoff(接在 In 後、Loop 前);slot_reveal 的 open/hit 顯式標 reveal/hit。
本閘走**與 build_spine --animate 相同的路徑**(analyze_target→gen_animations)驗證:

  M1 bigwin_payoff : slot_bigwin 端到端產出「宣告 cat==hit」的 beat(Burst),且具主秀 hit 結構簽章
                     (真峰 ≥1.12 + 反向預備 + (scale-1) 變號 ≥3)。→ 大獎演出現在有 payoff。
  M2 reveal_mainshow: slot_reveal 端到端產出 open(reveal 簽章:起 collapsed→峰→峰後穿越)+ hit(hit 簽章)。
                     兩者皆對應 main_draw 真值 anim(open/hit),屬**已驗證**主秀節拍。
  M3 cat_drives    : 顯式 cat 真的驅動分派——Burst 宣告 cat=hit 起於 identity;若改走 beat 名關鍵字
                     ('burst'→reveal)會起於 collapsed。兩路徑相異 → 證 cat 覆蓋了脆弱關鍵字匹配。
  M4 chainable     : payoff 介面正確——hit(Burst)首尾皆 identity(可插 Loop 間);reveal(open)首 collapsed 尾 identity。
  M5 discriminative: 一般節拍(intro/loop)**不具**主秀 hit 簽章(負對照);且「拔掉 cat 與 Burst」的
                     stripped 先驗使 slot_bigwin **無任何 hit/reveal 類別 beat** → 證 payoff 來自本次 wiring。
  M6 regression    : validate_priors(真值覆蓋)、validate_beat_templates(模板簽章)仍 overall_pass。

用法:
  python3 validate_mainshow_wiring.py           # 精簡 pass 表
  python3 validate_mainshow_wiring.py --json     # 完整 JSON
"""
import argparse, json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

from analyze_target import analyze
import gen_animations as GA
import spine_anim as SA
import validate_beat_templates as VB   # 復用簽章判定器(series/sign_changes/_hit_signature)

COLLAPSE = 0.10
PSD = "assets/robot_parts.psd"   # 供 role 來源;beats 來自 genre 先驗庫


def build(genre, storyboard=None):
    """走 build_spine --animate 相同路徑:analyze 取先驗 storyboard + 最小 skeleton → build_animations。"""
    sb = storyboard or analyze(PSD, genre)["3_motion_storyboard"]
    parts = sb["beats"][0]["parts"]
    bones = [{"name": "root"}] + [
        {"name": "b_" + GA.safe(p["part"]), "x": 100.0 + 30 * i, "y": 80.0}
        for i, p in enumerate(parts)]
    skel = {"skeleton": {"width": 713, "height": 693}, "bones": bones}
    return GA.build_animations(skel, sb), sb


def _declared_cat(sb, beat_key):
    for b in sb["beats"]:
        if b["beat"] == beat_key:
            return b.get("cat")
    return None


def _reveal_signature(anim):
    """reveal 主秀簽章:每 bone 起於 collapsed(scale≤COLLAPSE)、真峰 ≥1.12、峰後穿越 identity ≥2。"""
    for b in anim.get("bones", {}):
        v = VB.series(anim, b)
        if v[0] > COLLAPSE:
            return False
        pk = max(range(len(v)), key=lambda i: v[i])
        if max(v) < 1.12:
            return False
        if VB.sign_changes(v[pk:]) < 2:
            return False
    return True


def _starts_identity(anim, tol=1e-4):
    b0 = SA.sample(anim, 0.0)["bones"]
    return all(abs(b0[b]["scaleX"] - 1.0) <= tol for b in b0)


def _ends_identity(anim, tol=1e-4):
    d = SA.duration(anim)
    bE = SA.sample(anim, d)["bones"]
    sE = SA.sample(anim, d)["slots"]
    return (all(abs(bE[b]["scaleX"] - 1.0) <= tol for b in bE)
            and all(abs(s["alpha"] - 1.0) <= tol for s in sE.values()))


# ---------------- M1: slot_bigwin 端到端有 payoff ----------------
def check_m1():
    anims, sb = build("slot_bigwin")
    # 找宣告 cat==hit 的 beat
    hit_beats = [b["beat"] for b in sb["beats"] if b.get("cat") == "hit"]
    detail = {"hit_cat_beats": hit_beats}
    ok = len(hit_beats) >= 1
    for bk in hit_beats:
        sig = VB._hit_signature(anims[bk])
        detail[f"{bk}:hit_signature"] = sig
        ok = ok and sig
    return ok, detail


# ---------------- M2: slot_reveal open/hit 主秀(真值支撐) ----------------
def check_m2():
    anims, sb = build("slot_reveal")
    detail = {}
    open_ok = "open" in anims and _reveal_signature(anims["open"])
    hit_ok = "hit" in anims and VB._hit_signature(anims["hit"])
    detail["open:reveal_signature"] = open_ok
    detail["hit:hit_signature"] = hit_ok
    detail["open:declared_cat"] = _declared_cat(sb, "open")
    detail["hit:declared_cat"] = _declared_cat(sb, "hit")
    return open_ok and hit_ok, detail


# ---------------- M3: 顯式 cat 真的驅動分派(勝脆弱關鍵字) ----------------
def check_m3():
    """Burst 宣告 cat=hit → 起於 identity;把 cat 拔掉走 beat 名關鍵字('burst'→reveal)→ 起於 collapsed。
    兩路徑相異 ⇒ cat 覆蓋了關鍵字匹配(否則 payoff 會被誤判成 collapse-start reveal,破壞 Loop 間插入)。"""
    anims_cat, sb = build("slot_bigwin")
    burst = next((b["beat"] for b in sb["beats"] if b.get("cat") == "hit"), None)
    detail = {"burst_beat": burst, "beat_category_of_name": GA.beat_category(burst) if burst else None}
    if not burst:
        return False, detail
    # 走 cat 的實際結果:hit → 起於 identity
    with_cat_start_id = _starts_identity(anims_cat[burst])
    # 拔掉所有 cat → 同名 beat 改走關鍵字分派
    sb_strip = json.loads(json.dumps(sb))
    for b in sb_strip["beats"]:
        b.pop("cat", None)
    anims_kw, _ = build("slot_bigwin", sb_strip)
    kw_start_collapsed = SA.sample(anims_kw[burst], 0.0)["bones"]
    kw_collapsed = all(v["scaleX"] <= COLLAPSE for v in kw_start_collapsed.values())
    detail["with_cat_starts_identity"] = with_cat_start_id           # 期望 True(hit)
    detail["keyword_route_is_reveal"] = (GA.beat_category(burst) == "reveal")  # 'burst'∈reveal 關鍵字
    detail["keyword_route_starts_collapsed"] = kw_collapsed          # 期望 True(reveal)
    detail["routes_differ"] = with_cat_start_id and kw_collapsed
    ok = with_cat_start_id and detail["keyword_route_is_reveal"] and kw_collapsed
    return ok, detail


# ---------------- M4: 主秀節拍介面正確(可串接) ----------------
def check_m4():
    bw, _ = build("slot_bigwin")
    rv, _ = build("slot_reveal")
    detail = {}
    # hit(Burst):首尾 identity
    burst_start = _starts_identity(bw["Burst"]); burst_end = _ends_identity(bw["Burst"])
    detail["Burst:start_identity"] = burst_start
    detail["Burst:end_identity"] = burst_end
    # reveal(open):首 collapsed、尾 identity
    o = rv["open"]
    o0 = SA.sample(o, 0.0)
    open_start_collapsed = (all(v["scaleX"] <= COLLAPSE for v in o0["bones"].values())
                            or all(s["alpha"] <= COLLAPSE for s in o0["slots"].values()))
    open_end_id = _ends_identity(o)
    detail["open:start_collapsed"] = open_start_collapsed
    detail["open:end_identity"] = open_end_id
    ok = burst_start and burst_end and open_start_collapsed and open_end_id
    return ok, detail


# ---------------- M5: 鑑別力 + payoff 源自本次 wiring ----------------
def check_m5():
    anims, sb = build("slot_bigwin")
    detail = {}
    # (a) 一般節拍不具主秀 hit 簽章
    for bk in ("In", "Loop", "Out"):
        detail[f"{bk}:not_hit_signature"] = (VB._hit_signature(anims[bk]) is False)
    # (b) stripped(拔掉 cat 與 Burst beat)→ slot_bigwin 無任何 hit/reveal 類別 beat
    sb_strip = json.loads(json.dumps(sb))
    sb_strip["beats"] = [b for b in sb_strip["beats"] if b["beat"] != "Burst"]
    for b in sb_strip["beats"]:
        b.pop("cat", None)
    anims_strip, _ = build("slot_bigwin", sb_strip)
    cats = {GA.beat_category(nm) for nm in anims_strip}   # 走關鍵字
    detail["stripped_cats"] = sorted(cats)
    detail["stripped_has_no_mainshow"] = not (cats & {"hit", "reveal"})
    ok = all(v for k, v in detail.items() if k.endswith("not_hit_signature")) and detail["stripped_has_no_mainshow"]
    return ok, detail


# ---------------- M6: 回歸 ----------------
def check_m6():
    detail = {}
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    for name, argv in (("validate_priors", ["validate_priors.py", "--repo", "."]),
                       ("validate_beat_templates", ["validate_beat_templates.py"])):
        p = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), argv[0])] + argv[1:],
                           cwd=os.path.abspath(root), capture_output=True, text=True)
        detail[name] = {"returncode": p.returncode, "pass": p.returncode == 0}
    ok = all(v["pass"] for v in detail.values())
    return ok, detail


def run_all():
    res = {
        "M1_bigwin_payoff": check_m1(),
        "M2_reveal_mainshow": check_m2(),
        "M3_cat_drives_dispatch": check_m3(),
        "M4_chainable_interface": check_m4(),
        "M5_discriminative": check_m5(),
        "M6_regression": check_m6(),
    }
    overall = all(v[0] for v in res.values())
    return {"overall_pass": overall,
            "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    report = run_all()
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"overall_pass": report["overall_pass"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
