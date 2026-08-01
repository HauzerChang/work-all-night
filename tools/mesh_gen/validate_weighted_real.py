#!/usr/bin/env python3
"""對「真實生產 weighted mesh」驗證生成的 mesh — 端到端 PSD→件→mesh vs 真實 mesh。

背景(2026-08-01 發現):Award 的機器人拆件 3 個 mesh(光暈/左手/身體)是
**weighted、由骨骼 skinning 驅動,無 deform timeline**。這與窗簾(unweighted、
deform 驅動)是**不同驗證體制**:
  - 窗簾:單軸大拉伸 → 關鍵閘是「deform 耐受(0 自交/翻面)」。
  - 機器人:剛性/skinned 跟著骨走,無逐頂點 deform → 耐變形非重點;
    重點是「覆蓋保真(能否像藝術家一樣把形狀包住)」+「頂點經濟」。

本工具對每個真實 mesh:
  ① atlas 切真實貼圖(derotate)→ mask。
  ② generate_mesh_v2 生成 mesh → 靜態 IoU vs mask。
  ③ artist baseline:真實 Award mesh 的 uvs/triangles 光柵化覆蓋 IoU vs 同 mask。
  ④ AC:生成 IoU ≥ 藝術家 baseline − margin(覆蓋不輸藝術家);頂點經濟比。
可選 --psd:同時對 PSD 切件 alpha 生成 mesh,確認 PSD 路徑與 atlas 路徑覆蓋一致
  (端到端 PSD→件→mesh == 對照真實 mesh)。
"""
import argparse, json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from evaluate_mesh import evaluate, load_mask
from atlas_crop import extract
from generate_mesh_v2 import generate as gen_v2


def artist_coverage(skeleton, slot, name, mask):
    """真實 mesh(uvs+triangles)光柵化覆蓋 IoU vs mask。weighted/unweighted 皆可
    (只用 uvs+triangles,與權重無關)。"""
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0, len(uvs), len(tris)


def gen_iou_from_mask(mask_path):
    mesh = gen_v2(mask_path, mode="auto")
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    mask = load_mask(mask_path)
    ev = evaluate(mesh, mask)
    return mesh, ev


def validate_one(sk, atlas, png, slot, name, tmp_dir, margin=0.03, budget_mult=1.6):
    sub = extract(atlas, png, name)
    crop = os.path.join(tmp_dir, "_wr_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    mesh, ev = gen_iou_from_mask(crop)
    gen_verts = len(mesh["uvs"]) // 2
    gen_iou = ev["criteria"]["AC1_iou"]["value"]

    base_iou, art_verts, art_tris = artist_coverage(sk, slot, name, mask)

    iou_pass = gen_iou >= base_iou - margin
    budget_pass = gen_verts <= art_verts * budget_mult
    # topology sanity from static evaluator (degenerate / centroid criteria)
    topo = all(c.get("pass", True) for k, c in ev["criteria"].items()
               if k != "AC1_iou")  # IoU judged vs artist baseline instead

    return {
        "slot": slot,
        "mode": mesh.get("_mode"),
        "gen": {"vertices": gen_verts, "hull": mesh["hull"],
                "triangles": len(mesh["triangles"]) // 3, "iou": round(gen_iou, 4)},
        "artist": {"vertices": art_verts, "triangles": art_tris // 3,
                   "coverage_iou": round(base_iou, 4)},
        "AC_coverage": {"pass": bool(iou_pass),
                        "delta_vs_artist": round(gen_iou - base_iou, 4)},
        "AC_vertex_economy": {"pass": bool(budget_pass),
                              "ratio": round(gen_verts / art_verts, 3)},
        "AC_topology": {"pass": bool(topo)},
        "deform_gate": "N/A (weighted, bone-driven, no deform timeline)",
        "overall_pass": bool(iou_pass and budget_pass and topo),
    }


def psd_cross_check(psd_path, layer, tmp_dir):
    """從 PSD 切該圖層 alpha → 生成 mesh → 回傳靜態 IoU(端到端 PSD 路徑)。"""
    from psd_tools import PSDImage
    psd = PSDImage.open(psd_path)
    for l in psd.descendants():
        if l.is_group() or l.name != layer:
            continue
        img = l.composite()
        arr = np.array(img.convert("RGBA"))
        p = os.path.join(tmp_dir, f"_wr_psd_{layer}.png")
        cv2.imwrite(p, cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA))
        mesh, ev = gen_iou_from_mask(p)
        return {"layer": layer, "gen_vertices": len(mesh["uvs"]) // 2,
                "gen_iou": round(ev["criteria"]["AC1_iou"]["value"], 4),
                "size": [arr.shape[1], arr.shape[0]]}
    return {"layer": layer, "error": "layer not found"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--psd", default=None, help="robot_parts.psd for PSD cross-check")
    ap.add_argument("--slots", nargs="*",
                    default=["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"])
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    # PSD layer names (drop the "機器人拆件/" prefix)
    psd_map = {"機器人拆件/光暈": "光暈", "機器人拆件/左手": "左手", "機器人拆件/身體": "身體"}

    reports = []
    for slot in a.slots:
        rep = validate_one(sk, a.atlas, a.png, slot, slot, a.tmp)
        if a.psd and slot in psd_map:
            rep["psd_route"] = psd_cross_check(a.psd, psd_map[slot], a.tmp)
        reports.append(rep)

    overall = all(r["overall_pass"] for r in reports)
    print(json.dumps({"reports": reports, "all_pass": overall},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
