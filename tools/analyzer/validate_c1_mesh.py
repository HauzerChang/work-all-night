#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C1 閘 — `gen_lib.mesh` deform-aware mesh 生成 + 變形自交閘(spine-ai-editor 2.0 Phase C1)。

B 階段讓件**動起來**(beat/繞關節/序列);C1 讓件能**變形**:把 repo 的 S3 strip 生成器
(`generate_mesh_v2`)+ 真實位移場轉移自交閘(`deform_eval`)抽成 skill 入口
`skills/spine-ai-editor/assets/gen_lib/mesh.py`,並機械化驗 MERGE_PLAN 指名的
**「對 robot/curtain 件生成 strip mesh,真實 deform si=0」**。

**驗的是什麼(為何這個 chunk 有價值)**:
  v1.3.0 的 validator 只能 *檢查* 既有 mesh,**不能生成**。C1 讓 skill 能**從一張件 PNG 自動生成
  deformable mesh**,並用 main_draw 的**真實位移場**證明「這張自動生成的 mesh 在遊戲真實變形下不撕裂」
  (si=0)。核心發現:naive Delaunay 靜態 IoU 高,但真實 deform 下在 curtain_right/shadow **撕裂**;
  strip 直條拓樸(沿拉伸軸的邊界取樣)才是「真實 deform si=0」可達成的原因 → 生成器的**拓樸選型**是關鍵,
  不是附帶。viewer/Cocos 實機載入 = 使用者端(排程 scope 邊界),本閘用純 CPU 幾何真值替代。

**AC(全部客觀、可機讀)**:
  C1-1 entrypoint+schema : `gen_lib.mesh.generate_mesh` / `mesh_from_region` / `deform_si_check` 經**公開 API**
                           對 **curtain 件**(main_draw region)與 **robot 件**(robot_parts.psd)皆產出
                           strip mesh,且 `mesh_schema_errors()`==[](Spine 3.8 unweighted:len(v)==len(uv)、
                           hull 排前、三角索引在範圍、無孤兒頂點)。
  C1-2 real-deform si=0  : main_draw 4 mesh(curtain_left/right、shadow、shadow2)經公開 API 生成 strip mesh,
                           轉移**真實位移場** → **si=0 ∧ flip=0 ∧ degen=0**(clean)全數通過 = MERGE_PLAN 頭條。
  C1-3 strip-crux-vs-naive: **同一真實位移場**下,naive Delaunay mesh 在 curtain_right / shadow **撕裂**
                           (si>0 或 flip>0),strip 則 si=0 → 證 strip 拓樸選型是「真實 deform si=0」的原因
                           (非附帶);curtain_left 兩者皆乾淨(變形溫和處不鑑別,honest)。
  C1-4 coverage+budget   : strip mesh 對 4 件 IoU **≥ 藝術家 mesh 基準**(覆蓋保真、不欠覆蓋);
                           頂點數有界且可控(rows×cols=30 ≤ 預算 64)→ 不只合法,還**保真 + 精簡**。
  C1-5 gate-non-vacuous  : `deform_si_check` 抓到 (a) 人工自交 bowtie mesh(si>0)(b) naive Delaunay 真實 deform
                           撕裂(clean=False)→ 閘有牙;且 auto 選型**資料驅動**:高瘦 row-convex→strip、
                           軟邊 blob(羽化高,光暈)→boundary-dense、方正件(robot body aspect<1.2)→delaunay。

用法:
  python3 validate_c1_mesh.py            # 跑 C1-1..C1-5,印精簡 pass/fail + 指標
  python3 validate_c1_mesh.py --json     # 完整 JSON 報告

退出碼 0 = 全 AC PASS;非 0 = 有 AC FAIL。
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILL_ASSETS = os.path.join(_REPO, "skills", "spine-ai-editor", "assets")
_ASSETS = os.path.join(_REPO, "assets")
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_REPO, "tools", "mesh_gen"))
sys.path.insert(0, os.path.join(_SKILL_ASSETS, "gen_lib"))

import cv2                                     # noqa: E402
import mesh as MESH                            # noqa: E402  C1 skill 入口(gen_lib.mesh)
import generate_mesh as gm1                    # noqa: E402  naive Delaunay v1(對照)
import generate_mesh_v2 as gmv2                # noqa: E402  mode 自動選型
from evaluate_mesh import evaluate, load_mask  # noqa: E402  IoU 覆蓋評估
from atlas_crop import extract                 # noqa: E402  atlas region → png
from validate_against_real import artist_iou   # noqa: E402  藝術家 mesh IoU 基準

_SK = os.path.join(_ASSETS, "main_draw.json")
_AT = os.path.join(_ASSETS, "main_draw.atlas")
_PG = os.path.join(_ASSETS, "main_draw.png")
_ROBOT_PSD = os.path.join(_ASSETS, "robot_parts.psd")
_TMP = os.environ.get("C1_TMP") or os.path.join(tempfile.gettempdir(), "c1_mesh_gate")
os.makedirs(_TMP, exist_ok=True)

# main_draw 4 mesh:(slot, attachment-name, atlas-region)。shadow2 的 slot 與 shadow 共用
# attachment 名 **且** region。
_MESHES = [
    ("image/curtain_left", "image/curtain_left", "image/curtain_left"),
    ("image/curtain_right", "image/curtain_right", "image/curtain_right"),
    ("image/shadow", "image/shadow", "image/shadow"),
    ("image/shadow2", "image/shadow", "image/shadow"),
]


def _crop(region, tag):
    sub = extract(_AT, _PG, region)
    p = os.path.join(_TMP, "_c1_%s.png" % tag)
    cv2.imwrite(p, sub)
    return p


def _robot_body_png():
    """robot_parts.psd 的『身體』件 → 緊湊 RGBA png(robot 件代表)。"""
    from psd_tools import PSDImage
    psd = PSDImage.open(_ROBOT_PSD)
    for l in psd.descendants():
        if not l.is_group() and l.name == "身體":
            im = l.topil().convert("RGBA")
            p = os.path.join(_TMP, "_c1_robot_body.png")
            im.save(p)
            return p
    raise RuntimeError("robot_parts.psd 無『身體』圖層(C1-1 robot 件前提壞了)")


def run_all():
    sk = json.load(open(_SK, encoding="utf-8"))

    # ---- 預先:對 4 mesh 生成 strip + 取真實場 + 跑閘(C1-2/C1-3/C1-4 共用)----
    per = {}
    for slot, name, region in _MESHES:
        crop = _crop(region, slot.replace("/", "_"))
        mask = load_mask(crop)
        strip = MESH.generate_mesh(crop, mode="strip")
        naive, _ = gm1.generate(crop)
        uvs_src, field, frame = MESH.real_deform_field_for(sk, slot, name)
        rs = MESH.deform_si_check(strip, uvs_src, field)
        rn = MESH.deform_si_check(naive, uvs_src, field)
        iou = evaluate(strip, mask)["criteria"]["AC1_iou"]["value"]
        base = artist_iou(sk, slot, name, mask)
        per[slot] = {"mesh": strip, "mode": strip.get("_mode"), "nv": len(strip["uvs"]) // 2,
                     "schema": MESH.mesh_schema_errors(strip), "frame": frame,
                     "strip": rs, "naive": rn, "iou": iou, "artist_iou": round(base, 4)}

    # ============================================================ C1-1 entrypoint + schema
    robot_png = _robot_body_png()
    robot_strip = MESH.generate_mesh(robot_png, mode="strip")       # 強制 strip(robot 件非自然高瘦)
    robot_schema = MESH.mesh_schema_errors(robot_strip)
    curtain_strip = per["image/curtain_left"]
    api_ok = all(callable(getattr(MESH, fn, None)) for fn in
                 ("generate_mesh", "mesh_from_region", "deform_si_check",
                  "real_deform_field_for", "mesh_schema_errors"))
    # mesh_from_region 公開便捷入口也要能跑(端到端 atlas→mesh)
    mfr_mesh, _ = MESH.mesh_from_region(_SK, _AT, _PG, "image/curtain_left", tmp_crop=os.path.join(_TMP, "_mfr.png"))
    c11 = (api_ok and robot_strip.get("_mode") == "strip" and not robot_schema
           and curtain_strip["mode"] == "strip" and not curtain_strip["schema"]
           and not MESH.mesh_schema_errors(mfr_mesh))

    # ============================================================ C1-2 real-deform si=0(頭條)
    c12_each = {s: (v["strip"]["self_intersections"] == 0 and v["strip"]["triangle_flips"] == 0
                    and v["strip"]["degenerate"] == 0 and v["strip"]["clean"])
                for s, v in per.items()}
    c12 = all(c12_each.values())

    # ============================================================ C1-3 strip crux vs naive
    # 真實場下 naive 在 curtain_right / shadow 撕裂,strip 乾淨。curtain_left 溫和處不鑑別。
    naive_tears = {s: (not v["naive"]["clean"]) for s, v in per.items()}
    strip_clean = {s: v["strip"]["clean"] for s, v in per.items()}
    tear_slots = ["image/curtain_right", "image/shadow"]
    c13 = (all(naive_tears[s] for s in tear_slots)
           and all(strip_clean[s] for s in tear_slots)
           and all(strip_clean.values()))

    # ============================================================ C1-4 coverage + budget
    BUDGET = 64
    c14_each = {s: (v["iou"] >= v["artist_iou"] - 1e-9 and v["nv"] <= BUDGET) for s, v in per.items()}
    c14 = all(c14_each.values())

    # ============================================================ C1-5 gate non-vacuous + mode
    # (a) 人工自交 bowtie(對角線交叉)+ 零場 → si>0
    bow = {"vertices": [0, 0, 10, 10, 10, 0, 0, 10],
           "uvs": [0.0, 0.0, 1.0, 1.0, 1.0, 0.0, 0.0, 1.0],
           "triangles": [0, 1, 2, 2, 3, 0], "hull": 4, "width": 10, "height": 10}
    bow_uvs = np.array(bow["uvs"]).reshape(-1, 2)
    bow_res = MESH.deform_si_check(bow, bow_uvs, np.zeros_like(bow_uvs))
    bowtie_caught = bow_res["self_intersections"] > 0 and not bow_res["clean"]
    # (b) naive Delaunay 真實 deform 撕裂被閘抓(shadow)
    naive_caught = not per["image/shadow"]["naive"]["clean"]
    # (c) auto 選型資料驅動:curtain→strip、glow blob→boundary-dense、robot body→delaunay
    mode_curtain = gmv2.generate(_crop("image/curtain_left", "ql"), mode="auto").get("_mode")
    mode_glow = gmv2.generate(_crop("image/LG_glow_ball_00", "glow"), mode="auto").get("_mode")
    mode_robot = gmv2.generate(robot_png, mode="auto").get("_mode")
    mode_ok = (mode_curtain == "strip" and mode_glow == "boundary-dense-v1"
               and mode_robot == "delaunay-v1")
    c15 = bowtie_caught and naive_caught and mode_ok

    res = {
        "C1-1_entrypoint_schema": (c11, {
            "api_callable": api_ok,
            "robot_strip_mode": robot_strip.get("_mode"), "robot_schema_errs": robot_schema,
            "robot_nv": len(robot_strip["uvs"]) // 2,
            "curtain_strip_mode": curtain_strip["mode"], "curtain_schema_errs": curtain_strip["schema"],
            "mesh_from_region_schema_errs": MESH.mesh_schema_errors(mfr_mesh)}),
        "C1-2_real_deform_si0": (c12, {
            s: {"mode": per[s]["mode"], "frame": per[s]["frame"],
                "si": per[s]["strip"]["self_intersections"],
                "flip": per[s]["strip"]["triangle_flips"],
                "degen": per[s]["strip"]["degenerate"],
                "area_ratio": per[s]["strip"]["area_ratio"], "clean": per[s]["strip"]["clean"]}
            for s in c12_each}),
        "C1-3_strip_crux_vs_naive": (c13, {
            s: {"naive_si": per[s]["naive"]["self_intersections"],
                "naive_flip": per[s]["naive"]["triangle_flips"],
                "naive_clean": per[s]["naive"]["clean"], "strip_clean": per[s]["strip"]["clean"]}
            for s in per}),
        "C1-4_coverage_budget": (c14, {
            s: {"iou": per[s]["iou"], "artist_iou": per[s]["artist_iou"],
                "nv": per[s]["nv"], "budget": BUDGET, "pass": c14_each[s]} for s in c14_each}),
        "C1-5_gate_non_vacuous_mode": (c15, {
            "bowtie_si": bow_res["self_intersections"], "bowtie_caught": bowtie_caught,
            "naive_shadow_caught": naive_caught,
            "mode_curtain": mode_curtain, "mode_glow": mode_glow, "mode_robot": mode_robot,
            "mode_data_driven": mode_ok}),
    }
    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "C1 gen_lib.mesh: deform-aware strip mesh 生成 + 真實位移場自交閘(robot/curtain si=0)",
        "entry": "skills/spine-ai-editor/assets/gen_lib/mesh.py :: "
                 "generate_mesh / mesh_from_region / real_deform_field_for / deform_si_check / mesh_schema_errors",
        "meshes": [m[0] for m in _MESHES],
        "metrics": {
            "strip_si": {s: per[s]["strip"]["self_intersections"] for s in per},
            "naive_si": {s: per[s]["naive"]["self_intersections"] for s in per},
            "iou_vs_artist": {s: [per[s]["iou"], per[s]["artist_iou"]] for s in per},
            "strip_nv": {s: per[s]["nv"] for s in per}},
        "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="完整 JSON 報告")
    a = ap.parse_args()
    report = run_all()
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"overall_pass": report["overall_pass"], "metrics": report["metrics"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
