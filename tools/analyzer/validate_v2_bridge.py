#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spine-ai-editor 2.0 — Phase B1 橋接閘(repo 生成 → v1.3.0 validator_v1)。

MERGE_PLAN_2.0 的第一個有界 chunk:證明「本 repo 的確定性生成引擎」產出的一支動畫
能無痛通過使用者既有 `spine-ai-editor v1.3.0` 的 `validator_v1`(= runtime 可載入 **且**
editor 可匯入 **且** loop 閉合 **且** stiffness 可量)。先把兩道硬性護欄機械化、可回歸:

  G1(末鍵 curve 必拔):任何要回 Spine editor 的輸出,`json.dump` 前須呼叫
     `curve_tools.strip_last_frame_curves()`;不拔則 editor 匯入 AIOOBE crash(地雷 #12)。
  G2(雙真值驗收):repo 閘只驗 runtime 可載入;2.0 的驗收 = validator_v1 全套(含 editor
     匯入的末鍵 curve 檢查 + loop 閉合 + stiffness)都要過。

**關鍵事實(本閘同時釘住)**:repo 的 `gen_animations._bez` 只對 `frames[:-1]` 下緊湊 bezier
(末鍵永不帶 curve),EASE=0.25 落在 [0,1] → repo 生成**天生就 G1-safe**。本閘用正對照證實這點,
再用**負對照**(人工把 curve 注進末鍵)證 validator_v1 的 editor 閘**有牙**(非恆真)、且
`strip_last_frame_curves()` 能機械化修掉 → G1/G2 皆可自動化。

主體 = 最單純的 cascade big-win beat(pop 波;每件依件序錯開放大再回 identity,首尾 identity
→ 可插 Loop 間)。fixture 用合成 5 件骨架(self-contained,不依賴 PSD;cascade 的跨件簽章真實性
已由 validate_cascade.py 覆蓋,本閘只驗「生成 → v1.3.0 閘」橋接)。

  V1 generate+wrap   : build_animations 產 cascade beat → 包成完整 Spine 3.8 skeleton JSON
                       (skeleton/bones/slots/skins.default/animations);JSON round-trip + 有限。
  V2 validator_v1 clean(G2): 把 wrap 後 JSON 跑過 validator_v1 → rc==0、0 個 [ERR ]
                       (含 schema/引用 + **末鍵 curve** editor 檢查)。
  V3 loop closure    : curve_tools.loop_closure_report(anim) == []
                       (每 bone 首尾值一致、首鍵在 0、末鍵在 dur → 可接 Loop)。
  V4 editor 閘有牙+G1(負對照): (a) 原生 anim 末鍵 0 curve(strip 回 0);
                       (b) 人工把 curve 注進某末鍵 → validator_v1 rc==1 且 [ERR ] 點名末鍵 curve;
                       (c) strip_last_frame_curves 後再跑 → rc==0(G1 機械化修復)。
  V5 stiffness 可量  : curve_tools.stiffness_metric(anim) 有限 ≥0 並回報(附帶指標)。
                       honest:不設 stiffness 閾值——手感主觀屬使用者/A 類;本閘只證「量得出」。

用法:
  python3 tools/analyzer/validate_v2_bridge.py            # 跑 V1–V5
  python3 tools/analyzer/validate_v2_bridge.py --json     # 完整 JSON
"""
from __future__ import annotations
import argparse, copy, io, json, math, os, sys, tempfile
from contextlib import redirect_stdout
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "mesh_gen"))
# v1.3.0 skill 的 validator_v1 + curve_tools(2.0 要併接的既有資產)
V13_ASSETS = os.path.join(ROOT, "skills", "spine-ai-editor", "assets")
sys.path.insert(0, V13_ASSETS)

import gen_animations as G          # noqa: E402  repo 確定性生成引擎
import spine_anim as SA             # noqa: E402  repo 取樣器
import curve_tools as ct            # noqa: E402  v1.3.0 曲線工具(loop/stiffness/strip)
import validator_v1 as V1           # noqa: E402  v1.3.0 雙真值閘

SPINE_VERSION = "3.8.99"


# ---------------- fixture:合成 5 件大獎骨架(self-contained,不依賴 PSD) ----------------
def build_fixture():
    """回傳 (skel, storyboard)。件序即 build_animations 的相位序(cascade 跨件波)。"""
    parts_meta = [("head", "head"), ("torso", "body"),
                  ("arm_l", "limb"), ("arm_r", "limb"), ("glow", "特效")]
    bones = [{"name": "root"}]
    for i, (p, role) in enumerate(parts_meta):
        bones.append({"name": "b_" + G.safe(p), "x": 100.0 + 30 * i, "y": 80.0})
    skel = {"skeleton": {"width": 713, "height": 693}, "bones": bones}
    parts = [{"part": p, "role": role, "action": "主秀"} for p, role in parts_meta]
    storyboard = {"beats": [{"beat": "cascade", "desc": "跨件錯開波主秀(pop)", "parts": parts}]}
    return skel, storyboard


def gen_cascade_beat():
    """repo 生成引擎 → 最單純 cascade big-win beat(pop 波)。"""
    skel, storyboard = build_fixture()
    anims = G.build_animations(skel, storyboard)
    return skel, anims["cascade"]


def _build_doc(skel, anim, anim_name="cascade"):
    """把生成的 beat 包成完整 Spine 3.8 skeleton JSON(validator_v1 吃得下),不做 strip。
    slots/skins 由骨架件自動導出:每個非 root 骨 `b_X` → slot `X`(綁 `b_X`)+ default skin
    一張 region attachment `X`(fx 件的 slot color/alpha timeline 才有合法 slot 可引用)。"""
    slots, atts = [], {}
    for b in skel["bones"]:
        if b["name"] == "root":
            continue
        part = b["name"].removeprefix("b_")
        slots.append({"name": part, "bone": b["name"]})
        atts[part] = {part: {"type": "region", "width": 32, "height": 32}}
    return {
        "skeleton": {"spine": SPINE_VERSION,
                     "width": skel["skeleton"]["width"],
                     "height": skel["skeleton"]["height"]},
        "bones": copy.deepcopy(skel["bones"]),
        "slots": slots,
        "skins": {"default": atts},
        "animations": {anim_name: copy.deepcopy(anim)},
    }


def wrap_skeleton_json(skel, anim, anim_name="cascade"):
    """_build_doc + G1:寫檔前一律過 strip_last_frame_curves(模擬 2.0 產線契約)。
    回傳 (doc, stripped_count)。此 beat 本就無末鍵 curve → stripped==0(正對照)。"""
    doc = _build_doc(skel, anim, anim_name)
    stripped = ct.strip_last_frame_curves(doc["animations"][anim_name])
    return doc, stripped


# ---------------- 跑 v1.3.0 validator_v1(真的過它一遍) ----------------
def run_validator_v1(doc):
    """把 doc 寫成暫存 JSON,跑 validator_v1.main(--metric),回 (rc, err_lines, stdout)。"""
    fd, path = tempfile.mkstemp(suffix=".json", prefix="v2bridge_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = V1.main(["validator_v1.py", path, "--metric"])
        out = buf.getvalue()
        err_lines = [ln.strip() for ln in out.splitlines() if "[ERR ]" in ln]
        return rc, err_lines, out
    finally:
        os.unlink(path)


# ---------------- AC ----------------
def check_v1(skel, anim):
    doc, _ = wrap_skeleton_json(skel, anim)
    finite = SA.all_finite(anim)
    try:
        roundtrip = json.loads(json.dumps(doc, ensure_ascii=False)) == doc
    except Exception:
        roundtrip = False
    top_ok = {"skeleton", "bones", "slots", "skins", "animations"} <= set(doc.keys())
    has_default_skin = "default" in doc["skins"]
    ok = finite and roundtrip and top_ok and has_default_skin
    return ok, {"finite": finite, "json_roundtrip": roundtrip,
                "top_level_keys_ok": top_ok, "has_default_skin": has_default_skin,
                "bones_in_anim": len(anim.get("bones", {})),
                "spine_version": SPINE_VERSION}


def check_v2(skel, anim):
    doc, _ = wrap_skeleton_json(skel, anim)
    rc, err_lines, _ = run_validator_v1(doc)
    ok = (rc == 0) and (len(err_lines) == 0)
    return ok, {"validator_v1_rc": rc, "n_errors": len(err_lines),
                "errors": err_lines[:5]}


def check_v3(skel, anim):
    dur = ct.anim_duration(anim)
    problems = ct.loop_closure_report(anim, dur)
    # 每 bone 都有 scale timeline 且首尾 identity → 可插 Loop
    ok = (dur > 0) and (len(problems) == 0)
    return ok, {"duration": round(dur, 4), "n_loop_problems": len(problems),
                "problems": problems[:5]}


def check_v4(skel, anim):
    out = {}
    # (a) 原生末鍵 0 curve(repo 生成天生 G1-safe)
    native = copy.deepcopy(anim)
    out["native_last_frame_curves"] = ct.strip_last_frame_curves(native)  # 期望 0
    native_clean = (out["native_last_frame_curves"] == 0)

    # (b) 負對照:人工把 curve 注進某 bone scale timeline 的**末鍵** → validator_v1 應 rc==1 報末鍵 curve
    injected = copy.deepcopy(anim)
    target_bone = next(iter(injected["bones"]))
    tl = injected["bones"][target_bone]
    prop = next(iter(tl))              # 任一 timeline(此 beat 為 scale)
    tl[prop][-1]["curve"] = 0.25       # 末鍵帶 curve = 地雷 #12
    doc_bad = _build_doc(skel, injected)
    rc_bad, err_bad, _ = run_validator_v1(doc_bad)
    caught = (rc_bad == 1) and any("末鍵" in e or "curve" in e for e in err_bad)
    out["injected_rc"] = rc_bad
    out["injected_errors"] = err_bad[:3]
    out["gate_catches_last_key_curve"] = caught

    # (c) G1 機械化修復:strip 後再跑 → rc==0
    n_stripped = ct.strip_last_frame_curves(injected)
    doc_fixed = _build_doc(skel, injected)
    rc_fixed, err_fixed, _ = run_validator_v1(doc_fixed)
    fixed = (n_stripped >= 1) and (rc_fixed == 0) and (len(err_fixed) == 0)
    out["stripped_count"] = n_stripped
    out["fixed_rc"] = rc_fixed
    out["g1_mechanized_fix"] = fixed

    ok = native_clean and caught and fixed
    return ok, out


def check_v5(skel, anim):
    dur = ct.anim_duration(anim)
    st = ct.stiffness_metric(anim, dur)
    ok = isinstance(st, float) and math.isfinite(st) and st >= 0.0
    return ok, {"stiffness": round(st, 4), "duration": round(dur, 4),
                "note": "advisory 指標;不設閾值(手感主觀=使用者/A類),本閘只證可量"}


def run_all():
    skel, anim = gen_cascade_beat()
    res = {}
    res["V1_generate_and_wrap"] = check_v1(skel, anim)
    res["V2_validator_v1_clean"] = check_v2(skel, anim)
    res["V3_loop_closure_chainable"] = check_v3(skel, anim)
    res["V4_editor_gate_teeth_and_g1"] = check_v4(skel, anim)
    res["V5_stiffness_measurable"] = check_v5(skel, anim)
    overall = all(v[0] for v in res.values())
    report = {
        "overall_pass": overall,
        "subject": {"beat": "cascade (pop wave)", "parts": len(anim.get("bones", {})),
                    "duration": round(SA.duration(anim), 3)},
        "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()},
    }
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    report = run_all()
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"overall_pass": report["overall_pass"],
                          "subject": report["subject"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
