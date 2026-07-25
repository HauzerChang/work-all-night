#!/usr/bin/env python3
"""端到端 S4→S3 驗證:PSD 件 → generate_mesh_v2 → 對照 Award 真實生產 mesh。

背景(STATE.md 最高優先 bounded chunk):`robot_parts.psd` 的 光暈/身體/左手 三件
在生產 spine `Award` 中都是 mesh attachment(有藝術家真值可比)。本工具把 S4(PSD 切圖)
與 S3(mesh 生成)串成端到端,並對「真實生產標的」驗收:

  Path A(PSD 出身/provenance):
    slice PSD → 該件緊湊 PNG → generate_mesh_v2 → evaluate(對自身 alpha 的靜態 IoU +
    格式/預算/0孤兒/0退化)。證明「PSD→件→mesh」這條路能自動產出結構合法、覆蓋自身輪廓的 mesh。

  Path B(藝術家真值/ground-truth):
    atlas 切出該 region → generate_mesh_v2 → evaluate 的 IoU 對照 **Award 藝術家 mesh
    自身覆蓋率**(artist_iou),並比對頂點/三角形預算。證明自動拓樸的覆蓋 ≥ 生產藝術家 mesh。

⚠️ 結構性發現(2026-07-25):Award 三件機器人 mesh 皆 **weighted(骨骼權重驅動)、且
   9/12 動畫皆無 deform timeline**。故 `validate_against_real` 的真實位移場轉移閘
   (針對 unweighted + deform 的窗簾)**結構上不適用**於這些骨驅動件——deform 穩健性
   需要 S3 尚未實作的「權重(BBW)」步驟才能對齊生產。本工具因此只跑靜態覆蓋 + 預算閘,
   並明確標注 deform 閘為 N/A(而非假性通過)。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from evaluate_mesh import evaluate, load_mask
from atlas_crop import extract
from generate_mesh_v2 import generate as gen_v2
from validate_against_real import artist_iou


# robot_parts.psd 圖層 -> Award slot/attachment(僅取 Award 中為 mesh 的三件)
PIECES = [
    {"psd_file": "00_光暈.png", "slot": "機器人拆件/光暈", "name": "機器人拆件/光暈"},
    {"psd_file": "03_身體.png", "slot": "機器人拆件/身體", "name": "機器人拆件/身體"},
    {"psd_file": "04_左手.png", "slot": "機器人拆件/左手", "name": "機器人拆件/左手"},
]


def artist_mesh_stats(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    nv = len(a["uvs"]) // 2
    weighted = len(a["vertices"]) != len(a["uvs"])
    return {"vertices": nv, "triangles": len(a["triangles"]) // 3,
            "hull": a["hull"], "weighted": weighted}


def has_deform(sk, slot, name):
    for an, ad in sk.get("animations", {}).items():
        for _, sd in (ad.get("deform") or {}).items():
            if slot in sd and name in sd[slot]:
                return an
    return None


def validate(psd_dir, skeleton_path, atlas_path, png_path, tmp_dir, epsilon_frac=0.002):
    # epsilon_frac=0.002:對真實生產 3 件校準的 hull 追蹤密度(預設 0.008 對 glow 覆蓋不足)。
    # 校準結論(見 knowledge/s3-psd-to-award-e2e.md):0.002 下 3 件皆 IoU ≥ 藝術家自身覆蓋、
    # 且頂點數 < 藝術家 → 用更少頂點達到 ≥ 生產藝術家覆蓋。
    sk = json.load(open(skeleton_path))
    os.makedirs(tmp_dir, exist_ok=True)
    out = []
    for p in PIECES:
        rec = {"piece": p["name"]}

        # ---- Path A:PSD 件 → mesh → 對自身 alpha ----
        psd_png = os.path.join(psd_dir, p["psd_file"])
        maskA = load_mask(psd_png)
        meshA = gen_v2(psd_png, mode="auto", epsilon_frac=epsilon_frac)
        if isinstance(meshA, tuple):
            meshA = meshA[0]
        evA = evaluate(meshA, maskA)
        rec["pathA_psd_provenance"] = {
            "source": p["psd_file"],
            "mesh": {"vertices": len(meshA["uvs"]) // 2, "hull": meshA["hull"],
                     "triangles": len(meshA["triangles"]) // 3, "mode": meshA.get("_mode")},
            "self_iou": evA["criteria"]["AC1_iou"]["value"],
            "format_ok": evA["criteria"]["AC4_format"]["pass"],
            "orphans": evA["criteria"]["AC2c_orphans"]["value"],
            "degenerate": evA["criteria"]["AC2b_degenerate"]["value"],
            "centroid_in_mask": evA["criteria"]["AC2a_centroid_in_mask"]["value"],
            # 端到端合法性:結構合法 + 覆蓋自身輪廓(用藝術家自身基準當門檻,見 Path B)
        }

        # ---- Path B:atlas region → mesh → 對照藝術家 mesh ----
        sub = extract(atlas_path, png_path, p["name"])
        crop = os.path.join(tmp_dir, "_awc.png")
        cv2.imwrite(crop, sub)
        maskB = load_mask(crop)
        meshB = gen_v2(crop, mode="auto", epsilon_frac=epsilon_frac)
        if isinstance(meshB, tuple):
            meshB = meshB[0]
        iouB = evaluate(meshB, maskB)["criteria"]["AC1_iou"]["value"]
        base = artist_iou(sk, p["slot"], p["name"], maskB)
        astat = artist_mesh_stats(sk, p["slot"], p["name"])
        rec["pathB_artist_groundtruth"] = {
            "gen_mesh": {"vertices": len(meshB["uvs"]) // 2, "hull": meshB["hull"],
                         "triangles": len(meshB["triangles"]) // 3},
            "artist_mesh": astat,
            "gen_iou": round(iouB, 4),
            "artist_iou_baseline": round(base, 4),
            "epsilon_frac": epsilon_frac,
            "coverage_pass": iouB >= base - 0.005,   # 自動覆蓋 ≥ 藝術家自身覆蓋(容差 0.005)
            "vertex_budget_pass": (len(meshB["uvs"]) // 2) <= astat["vertices"],
        }

        # ---- 結構性標注:deform 閘適用性 ----
        rec["deform_gate"] = {
            "applicable": False,
            "reason": "weighted mesh, no deform timeline (bone-driven)",
            "weighted": astat["weighted"],
            "deform_anim": has_deform(sk, p["slot"], p["name"]),
        }

        # Path A 合法性門檻:結構合法 + self_iou ≥ 該件藝術家基準(用 Path B 的 base)
        A = rec["pathA_psd_provenance"]
        rec["pathA_psd_provenance"]["valid_mesh_pass"] = bool(
            A["format_ok"] and A["orphans"] == 0 and A["degenerate"] == 0
            and A["self_iou"] >= base)

        rec["overall_pass"] = bool(
            rec["pathA_psd_provenance"]["valid_mesh_pass"]
            and rec["pathB_artist_groundtruth"]["coverage_pass"]
            and rec["pathB_artist_groundtruth"]["vertex_budget_pass"])
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd_dir", default="/tmp/robot_parts")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--tmp", default="/tmp/psd2award")
    a = ap.parse_args()
    rep = validate(a.psd_dir, a.skeleton, a.atlas, a.png, a.tmp)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all(r["overall_pass"] for r in rep) else 1)


if __name__ == "__main__":
    main()
