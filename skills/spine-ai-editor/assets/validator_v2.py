#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validator_v2 — spine-ai-editor 2.0 統一品質閘(MERGE_PLAN Phase D1)。

把本 research repo 的「閘紀律」＋ v1.3.0 的 `validator_v1` 合成**單一指令**,對一支
2.0 生成的(大獎)動畫一鍵輸出**全維度 pass/fail ＋ 量化指標**。這是 2.0 的 G2
(雙真值驗收)在**一條可重跑機讀閘**裡的落點:遊戲能播(runtime)**且** 編輯器能匯入
(editor)**且** 可循環(loop)**且** 手感可量(stiffness)**且** mesh 變形不撕裂(deform si)
**且** 自接點平滑(C1)。

維度(每項獨立 PASS / FAIL / NA / UNAVAILABLE):

  1. runtime_loadable  —— schema ＋ 引用完整性(validator_v0):spine-webgl 能否載入的純 CPU 代理。
  2. editor_importable —— 地雷 #12(末鍵 curve → Spine editor 匯入 AIOOBE)＋ cx(curve/c3)超 [0,1]
                          (runtime 解錯)。= v1.3.0 validator_v1 的編輯器真值檢查。
  3. loop_closure      —— 每條 timeline 首尾閉合 ＋ 首鍵在 0 / 末鍵在 dur ＋ key 時間單調
                          (curve_tools.loop_closure_report)。
  4. stiffness         —— key 處速度不連續量(curve_tools.stiffness_metric),越低越順。
                          永遠回報數值;給 --stiffness-max 才當硬閘。
  5. deform_si         —— mesh attachment 在**真實 deform 位移場**下是否自交 / 翻面 / 退化
                          (gen_lib.mesh.deform_si_gate,C1 的變形自交閘)。無 mesh+deform → NA。
  6. c1_continuity     —— 迴圈動畫自接點是否 C1-loopable(值 ＋ 速度皆連續,非只 C0)。
                          不傳 --loop-anims → NA(一次性大獎 beat 首尾 identity 但自接點速度突變)。

維度 1–4 **self-contained**(只依賴同資料夾的 validator_v0 / curve_tools);
維度 5–6 為 repo 生成引擎的延伸閘,過渡期 lazy import repo tools(E1 bundle 後 self-contained),
import 不到時標 **UNAVAILABLE**(不讓核心四維被拖垮)。

用法:
  python3 validator_v2.py Skel.json [Skel.atlas]
        [--loop-anims A,B] [--stiffness-max N] [--no-deform] [--no-c1] [--json]

退出碼 0 = 所有**可檢**維度(非 NA / 非 UNAVAILABLE)皆 PASS;非 0 = 至少一維 FAIL。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import validator_v0 as v0        # noqa: E402  schema + 引用完整性(runtime 載入代理)
import curve_tools as ct         # noqa: E402  loop 閉合 / stiffness / 末鍵 curve 工具

PASS, FAIL, NA, UNAVAIL = "PASS", "FAIL", "NA", "UNAVAILABLE"


# ===================================================================== 維度 2 editor
def _editor_import_problems(data: dict) -> list[str]:
    """v1.3.0 的編輯器真值檢查(不經 subprocess,直接讀 JSON):
      (a) 任何 timeline 的**最後一鍵**帶 curve/c2/c3/c4 → Spine editor 匯入 AIOOBE crash(地雷 #12)。
      (b) cx(curve / c3)超出 [0,1] → runtime 會解錯(cy=c2/c4 過衝為刻意穿透式切線,豁免)。
    """
    probs: list[str] = []
    for aname, anim in data.get("animations", {}).items():
        for sec in ("bones", "slots"):
            for tname, tls in anim.get(sec, {}).items():
                for prop, fr in tls.items():
                    if not (isinstance(fr, list) and fr):
                        continue
                    # (a) 末鍵 curve
                    last = fr[-1]
                    if isinstance(last, dict) and any(
                            k in last for k in ("curve", "c2", "c3", "c4")):
                        probs.append(
                            f"{aname} {tname}.{prop}: 最後一鍵帶 curve — "
                            f"Spine editor 匯入 AIOOBE crash(地雷 #12);"
                            f"用 curve_tools.strip_last_frame_curves() 清")
                    # (b) cx 超界
                    for k in fr:
                        if not isinstance(k, dict):
                            continue
                        for cxk in ("curve", "c3"):
                            v = k.get(cxk)
                            if isinstance(v, (int, float)) and not (0.0 <= v <= 1.0):
                                probs.append(
                                    f"{aname} {tname}.{prop}: {cxk}={v} 超出 [0,1] — "
                                    f"runtime 會解錯")
    return probs


# ===================================================================== 維度 5 deform si(延伸)
def _iter_mesh_attachments(data: dict):
    """yield (slot_name, att_name, mesh_dict)。只取 type=='mesh' 且帶 vertices/uvs/triangles 的件。"""
    skins = data.get("skins", {})
    if isinstance(skins, list):
        skins = {s["name"]: s.get("attachments", {}) for s in skins}
    for _skin_name, slot_map in skins.items():
        for slot_name, atts in slot_map.items():
            for att_key, att in atts.items():
                if not isinstance(att, dict) or att.get("type") != "mesh":
                    continue
                if not all(k in att for k in ("vertices", "uvs", "triangles")):
                    continue
                mesh = {"vertices": att["vertices"], "uvs": att["uvs"],
                        "triangles": att["triangles"], "hull": att.get("hull", 0)}
                # att.name 覆寫 fallback 到 att_key(deform timeline 用 skin 的 att_key)
                yield slot_name, att_key, mesh


def _deform_si_dimension(json_path: Path, data: dict) -> dict:
    """對每個帶**真實 deform timeline** 的 mesh attachment 跑 deform_si_gate。
    無 mesh / 無 deform → NA;repo 生成引擎 import 不到 → UNAVAILABLE。"""
    try:
        from gen_lib import mesh as mesh_mod   # noqa: E402
    except Exception as e:                      # pragma: no cover - 使用者端無 repo tools
        return {"status": UNAVAIL, "metrics": {"reason": f"gen_lib.mesh 不可用: {e}"},
                "problems": []}
    checked, probs, details = 0, [], []
    for slot, name, mesh in _iter_mesh_attachments(data):
        try:
            if not mesh_mod.has_real_deform(data, slot, name):
                continue
            gate = mesh_mod.deform_si_gate(mesh, data, slot, name)
        except Exception as e:
            probs.append(f"{slot}/{name}: deform_si_gate 例外 {e}")
            continue
        checked += 1
        d = {"slot": slot, "name": name, "clean": bool(gate["clean"]),
             "self_intersections": int(gate["self_intersections"]),
             "triangle_flips": int(gate["triangle_flips"]),
             "degenerate": int(gate["degenerate"]),
             "area_ratio": round(float(gate["area_ratio"]), 4), "frame": gate["frame"]}
        details.append(d)
        if not gate["clean"]:
            probs.append(f"{slot}/{name}: si={gate['self_intersections']} "
                         f"flips={gate['triangle_flips']} degen={gate['degenerate']}")
    if checked == 0:
        return {"status": NA, "metrics": {"meshes_with_deform": 0}, "problems": []}
    return {"status": PASS if not probs else FAIL,
            "metrics": {"meshes_checked": checked, "meshes": details},
            "problems": probs}


# ===================================================================== 維度 6 C1(延伸)
def _c1_dimension(data: dict, loop_anims) -> dict:
    """對指定 loop 動畫判 is_c1_loopable(值＋速度自接點皆連續)。
    不指定 loop_anims → NA(一次性大獎 beat 非 C1-loopable 屬正常,不該誤判 FAIL)。"""
    if not loop_anims:
        return {"status": NA, "metrics": {"reason": "未指定 --loop-anims"}, "problems": []}
    try:
        sys.path.insert(0, str((_HERE / ".." / ".." / ".." / "tools" / "analyzer").resolve()))
        import gen_animations as G   # noqa: E402
    except Exception as e:           # pragma: no cover - 使用者端無 repo tools
        return {"status": UNAVAIL, "metrics": {"reason": f"gen_animations 不可用: {e}"},
                "problems": []}
    anims = data.get("animations", {})
    probs, details = [], []
    checked = 0
    for a in loop_anims:
        if a not in anims:
            probs.append(f"{a}: 動畫不存在")
            continue
        try:
            ok = bool(G.is_c1_loopable(anims[a]))
        except Exception as e:
            probs.append(f"{a}: is_c1_loopable 例外 {e}")
            continue
        checked += 1
        details.append({"anim": a, "c1_loopable": ok})
        if not ok:
            probs.append(f"{a}: 非 C1-loopable(自接點速度不連續,平鋪會頓挫)")
    if checked == 0 and probs:
        return {"status": FAIL, "metrics": {"anims": details}, "problems": probs}
    return {"status": PASS if not probs else FAIL,
            "metrics": {"anims": details}, "problems": probs}


# ===================================================================== 主入口
def validate_v2(json_path, atlas_path=None, loop_anims=None, stiffness_max=None,
                check_deform=True, check_c1=True) -> dict:
    """對一份 skeleton JSON 跑六維統一品質閘,回傳結構化報告 dict。

    json_path     : skeleton .json 路徑。
    atlas_path    : 選配 .atlas(給維度 1 做 region 交叉檢查)。
    loop_anims    : 要做 loop 閉合 ＋ C1 的動畫名清單(None → loop 檢查全動畫、C1 標 NA)。
    stiffness_max : 給定時,任一動畫 stiffness 超過即維度 4 FAIL(否則只回報數值)。
    check_deform / check_c1 : 關掉延伸維度 5 / 6(標 NA)。

    回傳 {overall_pass, json, dimensions:{dim_name:{status,metrics,problems}}}。
    overall_pass = 所有非 NA / 非 UNAVAILABLE 維度皆 PASS。
    """
    json_path = Path(json_path)
    atlas_path = Path(atlas_path) if atlas_path else None
    data = json.loads(json_path.read_text(encoding="utf-8"))
    dims: dict = {}

    # --- 1. runtime loadable(v0 schema + 引用完整性) ---
    r0 = v0.validate(json_path, atlas_path)
    dims["runtime_loadable"] = {
        "status": PASS if r0.is_valid else FAIL,
        "metrics": {"errors": len(r0.errors), "warnings": len(r0.warnings)},
        "problems": list(r0.errors)}

    # --- 2. editor importable(地雷 #12 + cx) ---
    eprobs = _editor_import_problems(data)
    dims["editor_importable"] = {
        "status": PASS if not eprobs else FAIL,
        "metrics": {"problem_count": len(eprobs)},
        "problems": eprobs}

    # --- 3. loop closure ---
    lprobs = []
    anims = data.get("animations", {})
    for aname, anim in anims.items():
        if loop_anims is not None and aname not in loop_anims:
            continue
        dur = ct.anim_duration(anim)
        if dur <= 0:
            continue
        for p in ct.loop_closure_report(anim, dur):
            lprobs.append(f"{aname}: {p}")
    dims["loop_closure"] = {
        "status": PASS if not lprobs else FAIL,
        "metrics": {"problem_count": len(lprobs),
                    "scope": loop_anims or "all"},
        "problems": lprobs}

    # --- 4. stiffness ---
    metrics = {}
    for aname, anim in anims.items():
        dur = ct.anim_duration(anim)
        if dur <= 0:
            continue
        metrics[aname] = round(ct.stiffness_metric(anim, dur), 4)
    finite = all(v == v and v != float("inf") for v in metrics.values())
    sprobs = []
    if not finite:
        sprobs.append("stiffness 非有限數")
    if stiffness_max is not None:
        for a, v in metrics.items():
            if v > stiffness_max:
                sprobs.append(f"{a}: stiffness {v} > max {stiffness_max}")
    dims["stiffness"] = {
        "status": PASS if (finite and not sprobs) else FAIL,
        "metrics": {"per_anim": metrics, "max_threshold": stiffness_max},
        "problems": sprobs}

    # --- 5. deform si(延伸) ---
    if check_deform:
        dims["deform_si"] = _deform_si_dimension(json_path, data)
    else:
        dims["deform_si"] = {"status": NA, "metrics": {"reason": "--no-deform"}, "problems": []}

    # --- 6. c1 continuity(延伸) ---
    if check_c1:
        dims["c1_continuity"] = _c1_dimension(data, loop_anims)
    else:
        dims["c1_continuity"] = {"status": NA, "metrics": {"reason": "--no-c1"}, "problems": []}

    checkable = [d["status"] for d in dims.values() if d["status"] in (PASS, FAIL)]
    overall = all(s == PASS for s in checkable) and len(checkable) > 0
    return {"overall_pass": overall, "json": json_path.name, "dimensions": dims}


# ===================================================================== CLI
def _print_human(report: dict) -> None:
    print(f"=== validator_v2 on {report['json']} ===")
    label = {PASS: "✓ PASS", FAIL: "✗ FAIL", NA: "— NA  ", UNAVAIL: "? UNAVAIL"}
    for name, d in report["dimensions"].items():
        print(f"  [{label[d['status']]}] {name}")
        if d["status"] == FAIL:
            for p in d["problems"][:4]:
                print(f"          ↳ {p}")
            if len(d["problems"]) > 4:
                print(f"          ↳ …其餘 {len(d['problems'])-4} 條")
    st = report["dimensions"]["stiffness"]["metrics"]["per_anim"]
    if st:
        print("  --- stiffness(越低越順) ---")
        for k, v in sorted(st.items(), key=lambda x: -x[1]):
            print(f"      {k:28s} {v:8.2f}")
    print()
    print(f"RESULT: {'ALL PASS' if report['overall_pass'] else 'FAIL'}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="spine-ai-editor 2.0 統一品質閘 validator_v2")
    ap.add_argument("json", help="skeleton .json")
    ap.add_argument("atlas", nargs="?", default=None, help="選配 .atlas")
    ap.add_argument("--loop-anims", default=None,
                    help="逗號分隔的迴圈動畫名(做 loop 閉合 + C1);不給則 loop 檢查全動畫、C1 標 NA")
    ap.add_argument("--stiffness-max", type=float, default=None,
                    help="任一動畫 stiffness 超過即 FAIL(預設只回報不當閘)")
    ap.add_argument("--no-deform", action="store_true", help="跳過 deform si 維度")
    ap.add_argument("--no-c1", action="store_true", help="跳過 C1 維度")
    ap.add_argument("--json", action="store_true", dest="as_json", help="輸出完整 JSON 報告")
    a = ap.parse_args(argv)
    loop_anims = a.loop_anims.split(",") if a.loop_anims else None
    report = validate_v2(a.json, a.atlas, loop_anims=loop_anims,
                         stiffness_max=a.stiffness_max,
                         check_deform=not a.no_deform, check_c1=not a.no_c1)
    if a.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
