#!/usr/bin/env python3
"""對「真實生產 spine(Award)」的 weighted mesh 件驗證 S3 生成器 — 端到端 PSD→件→mesh 驗收。

與 validate_against_real.py 的差異(為何需要另一支):
  - Award 的機器人 mesh 件(光暈/身體/左手)是 **weighted mesh**(骨骼權重驅動),
    且 **無 deform timeline**。real_deform_field 只能讀 unweighted 的攤平頂點格式,
    對 weighted 會 shape 不符而 crash(見 log 2026-08-09)。
  - 這些件靠骨骼/權重變形,不是逐頂點 deform → 「真實位移場轉移」閘在此不適用。

因此本閘只做**可誠實驗證**的兩件事:
  ① 靜態 IoU:生成 mesh 覆蓋率 vs 藝術家 mesh 覆蓋率(藝術家為 ground-truth 基準)。
  ② 拓樸/格式健全:格點在 mask 內、無退化/孤兒、頂點預算內;並列印藝術家 vs 生成的頂點/hull/三角數。
deform 閘標記為 N/A 並附原因(weighted + 無 deform timeline),不做假性通過。

alpha 來源:Award atlas 切出的 region(atlas_crop.extract,已 CW + 多頁修正,~0.70 縮放;
IoU 為正規化座標,縮放不影響)。artist uvs 正規化於同一 region → 對齊。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from evaluate_mesh import evaluate, load_mask
from atlas_crop import extract
from generate_mesh_v2 import generate as gen_v2


def artist_mesh(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    return a


def artist_iou(a, mask):
    """weighted-safe:只用 uvs + triangles(與權重無關)。"""
    uvs = np.array(a["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0


def is_weighted(a):
    v = a.get("vertices"); u = a.get("uvs")
    return v is not None and u is not None and len(v) != len(u)


def has_deform_timeline(skeleton, slot, name):
    for _an, body in skeleton.get("animations", {}).items():
        for _skin, slots in body.get("deform", {}).items():
            if slot in slots and name in slots[slot]:
                return True
    return False


def validate(skeleton_path, atlas_path, png_path, slot, name, tmp_dir, iou_margin=0.03):
    sk = json.load(open(skeleton_path))
    sub = extract(atlas_path, png_path, name)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    mesh = gen_v2(crop, mode="auto")
    nv = len(mesh["uvs"]) // 2

    # 靜態評估(不以 0.95 為門檻,改用藝術家基準;其餘格式/退化/孤兒仍要過)
    ev = evaluate(mesh, mask)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]

    a = artist_mesh(sk, slot, name)
    base = artist_iou(a, mask)
    a_nv = len(a["uvs"]) // 2
    a_tris = len(a["triangles"]) // 3
    a_hull = a.get("hull")

    iou_pass = gen_iou >= base - iou_margin
    # 拓樸健全:除 IoU 外的所有靜態 criteria
    topo_ok = all(c["pass"] for k, c in ev["criteria"].items() if k != "AC1_iou")

    deform_applicable = has_deform_timeline(sk, slot, name)

    return {
        "slot": slot,
        "region_px": [mask.shape[1], mask.shape[0]],
        "artist": {"vertices": a_nv, "hull": a_hull, "triangles": a_tris,
                   "weighted": is_weighted(a)},
        "generated": {"vertices": nv, "hull": mesh["hull"],
                      "triangles": len(mesh["triangles"]) // 3, "mode": mesh.get("_mode")},
        "AC_iou": {"generated": round(gen_iou, 4), "artist_baseline": round(base, 4),
                   "margin": iou_margin, "pass": iou_pass},
        "AC_topology": {"pass": topo_ok,
                        "detail": {k: v.get("value", v.get("pass"))
                                   for k, v in ev["criteria"].items() if k != "AC1_iou"}},
        "AC_deform": {"applicable": deform_applicable,
                      "note": "N/A — weighted mesh 靠骨骼權重變形,無 deform timeline"
                              if not deform_applicable else "有 deform timeline,應另跑 weighted-aware 閘"},
        "overall_pass": iou_pass and topo_ok,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--slots", nargs="+",
                    default=["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"])
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--margin", type=float, default=0.03)
    a = ap.parse_args()
    reps = []
    for s in a.slots:
        reps.append(validate(a.skeleton, a.atlas, a.png, s, s, a.tmp, a.margin))
    out = {"results": reps, "all_pass": all(r["overall_pass"] for r in reps)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["all_pass"] else 1)


if __name__ == "__main__":
    main()
