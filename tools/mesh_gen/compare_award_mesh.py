#!/usr/bin/env python3
"""端到端驗收:PSD件(用 Award atlas 真實 alpha)→ S3 generate_mesh_v2 → 對照 Award 藝術家 mesh。

機器人 3 個 mesh 件(光暈/身體/左手)在 Award 生產 spine 有藝術家手做 mesh = ground truth。
這 3 件**無 deform timeline**(靠骨骼/權重變形)→ 誠實地不用未校準合成壓力場;
閘 = 靜態 IoU ≥ 藝術家 baseline(margin 0.02) + 靜態拓樸乾淨(0 自交/0 退化/0 孤兒) + 頂點在預算內。

用法: python3 tools/mesh_gen/compare_award_mesh.py    (從 repo 根目錄跑)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from atlas_crop import extract
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask, mesh_pixel_coords
import deform_eval as de

SK = json.load(open("assets/Award.json"))
_s = SK["skins"]; _s = _s[0] if isinstance(_s, list) else _s
SKIN = _s.get("attachments", _s)
PARTS = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]
IOU_MARGIN = 0.02


def artist_ref(slot, name, mask):
    a = SKIN[slot][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2); tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    iou = float(np.logical_and(recon, mask).sum() / np.logical_or(recon, mask).sum())
    chk = de.check(rp.astype(np.float64), tris, None)
    return {"nv": len(uvs), "hull": int(a["hull"]), "tris": len(tris),
            "iou_over_region": round(iou, 4), "self_intersections": chk["self_intersections"]}


def run():
    report = {}
    for p in PARTS:
        sub = extract("assets/Award.atlas", "assets/Award.png", p)
        crop = f"/tmp/_award_{p.replace('/', '_')}.png"
        cv2.imwrite(crop, sub)
        mask = load_mask(crop)
        mesh = gen_v2(crop, mode="auto")
        ev = evaluate(mesh, mask, vertex_budget=200)
        gpix, _, _ = mesh_pixel_coords(mesh)
        gchk = de.check(gpix, np.array(mesh["triangles"]).reshape(-1, 3), None)
        art = artist_ref(p, p, mask)
        gen = {"mode": mesh.get("_mode"), "nv": len(mesh["uvs"]) // 2, "hull": mesh["hull"],
               "tris": len(mesh["triangles"]) // 3, "iou": ev["criteria"]["AC1_iou"]["value"],
               "self_intersections": gchk["self_intersections"],
               "degenerate": gchk["degenerate"], "orphans": ev["criteria"]["AC2c_orphans"]["value"],
               "format_ok": ev["criteria"]["AC4_format"]["pass"]}
        ac_iou = gen["iou"] >= art["iou_over_region"] - IOU_MARGIN
        ac_topo = (gen["self_intersections"] == 0 and gen["degenerate"] == 0
                   and gen["orphans"] == 0 and gen["format_ok"])
        report[p] = {"region_wh": [int(mask.shape[1]), int(mask.shape[0])], "gen": gen, "artist": art,
                     "AC2_iou_ge_artist": ac_iou, "AC3_topology_clean": ac_topo,
                     "overall_pass": ac_iou and ac_topo}
    return report


if __name__ == "__main__":
    rep = run()
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    ok = all(v["overall_pass"] for v in rep.values())
    print("\nALL_PASS =", ok)
    raise SystemExit(0 if ok else 1)
