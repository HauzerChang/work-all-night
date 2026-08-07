#!/usr/bin/env python3
"""端到端驗收:PSD件 → S3 mesh → 對照 Award 真實生產 mesh(機器人拆件)。

STATE.md 最高優先 bounded chunk。用真實生產標的(Award spine 的機器人 mesh 件)當
ground truth,驗證 S3 generator 是否能對「非窗簾、blobby」的件產出與藝術家相當品質的 mesh,
並確認 v2 auto 模式選擇正確(這些件 aspect<1.2 → 應回退 v1 Delaunay,而非 strip)。

三件 Award mesh:機器人拆件/{光暈,左手,身體}(右手/頭為 region,不比)。
⚠️ 這三件在 Award **無 deform timeline**(靠骨骼 warp,非 baked FFD),故真實位移場閘 N/A;
   依 RULES「不用未校準 stress_field」,deform 軸誠實標 N/A,不捏造壓力測試。

比對軸:
  ① 靜態 IoU:生成 mesh 覆蓋率 vs 藝術家 mesh 自身覆蓋率(self-consistency baseline)。
  ② 頂點預算:生成頂點數 ≤ 藝術家頂點數(精簡度不輸)。
  ③ 拓樸模式:auto 選到的模式適當(blobby → v1 Delaunay)。
  ④ 端到端來源一致:另從 PSD 切件生成,確認模式/頂點數與 atlas 來源一致(S4→S3 串接)。

atlas 來源與藝術家 UV 對齊(同 validate_against_real 的校準路徑);PSD 件已於 S4 證實
與 atlas 件同素材(alpha-IoU 0.92~0.99)。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from atlas_crop import extract
from generate_mesh_v2 import generate as gen_v2, load_mask as load_mask_v2
from evaluate_mesh import evaluate as eval_mesh, load_mask as load_mask_eval
from validate_against_real import artist_iou

ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def has_deform(sk, slot, name):
    for an, data in sk.get("animations", {}).items():
        for skn, slots in data.get("deform", {}).items():
            if slot in slots and name in slots[slot]:
                return an
    return None


def artist_mesh(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    return a


def validate_piece(sk, atlas, png, slot, name, psd_parts_dir, tmp_dir):
    # --- atlas 來源(對齊藝術家 UV)---
    sub = extract(atlas, png, name)
    crop = os.path.join(tmp_dir, "_robot_region.png")
    cv2.imwrite(crop, sub)
    mask_eval = load_mask_eval(crop)
    mask_v2, W, H = load_mask_v2(crop)

    mesh = gen_v2(crop, mode="auto")
    nv = len(mesh["uvs"]) // 2
    ev = eval_mesh(mesh, mask_eval, vertex_budget=64)
    iou = ev["criteria"]["AC1_iou"]["value"]

    a = artist_mesh(sk, slot, name)
    art_nv = len(a["uvs"]) // 2
    base = artist_iou(sk, slot, name, mask_eval)

    df = has_deform(sk, slot, name)

    # --- PSD 來源(真端到端 S4→S3)---
    psd_entry = {"available": False}
    if psd_parts_dir and os.path.isdir(psd_parts_dir):
        layer = name.split("/")[-1]
        cand = [f for f in os.listdir(psd_parts_dir)
                if f.endswith(".png") and layer in f]
        if cand:
            ppath = os.path.join(psd_parts_dir, cand[0])
            pm = gen_v2(ppath, mode="auto")
            pmask = load_mask_eval(ppath)
            pev = eval_mesh(pm, pmask, vertex_budget=64)
            psd_entry = {"available": True, "file": cand[0],
                         "mode": pm.get("_mode"), "vertices": len(pm["uvs"]) // 2,
                         "self_iou": pev["criteria"]["AC1_iou"]["value"],
                         "mode_matches_atlas": pm.get("_mode") == mesh.get("_mode")}

    iou_pass = iou >= base - 0.02          # 覆蓋率不輸藝術家(2% 容差)
    budget_pass = nv <= art_nv             # 頂點數不多於藝術家
    fmt_pass = ev["criteria"]["AC4_format"]["pass"] and \
        ev["criteria"]["AC2b_degenerate"]["pass"] and ev["criteria"]["AC2c_orphans"]["pass"]

    return {
        "slot": slot,
        "region": [W, H],
        "gen": {"mode": mesh.get("_mode"), "vertices": nv, "hull": mesh["hull"],
                "triangles": len(mesh["triangles"]) // 3},
        "artist": {"vertices": art_nv, "hull": a.get("hull"),
                   "triangles": len(a["triangles"]) // 3},
        "AC_iou": {"value": iou, "artist_baseline": round(base, 4), "pass": bool(iou_pass)},
        "AC_vertex_budget": {"gen": nv, "artist": art_nv, "pass": bool(budget_pass)},
        "AC_format_clean": {"pass": bool(fmt_pass)},
        "AC_deform": {"applicable": df is not None,
                      "note": "N/A — no deform timeline (warps via bones)" if df is None
                      else f"has deform in {df}"},
        "psd_source": psd_entry,
        "overall_pass": bool(iou_pass and budget_pass and fmt_pass),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--psd-parts", default=None, help="psd_slice 切出的件目錄(端到端來源比對)")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reps = [validate_piece(sk, a.atlas, a.png, s, s, a.psd_parts, a.tmp) for s in ROBOT_MESHES]
    out = {"pieces": reps, "all_pass": all(r["overall_pass"] for r in reps)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["all_pass"] else 1)


if __name__ == "__main__":
    main()
