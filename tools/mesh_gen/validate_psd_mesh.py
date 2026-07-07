#!/usr/bin/env python3
"""端到端整合 AC(S4→S3):分層 PSD 的件 → S3 生成 mesh → 對照生產 spine 真實 mesh。

流程:
  psd_slice.slice_psd(PSD) 切各件緊湊 PNG(S4 產物,alpha 即件輪廓)
  → 對「在生產 spine 中為 mesh」的件跑 S3 generate_mesh
  → ① 覆蓋率 IoU(生成 mesh vs 件 alpha)≥ 藝術家真實 mesh 對同一 alpha 的覆蓋率
     ② 基礎拓樸乾淨(setup 0 自交 / 0 退化)
     ③ 頂點數在藝術家預算內。

真值來源:生產 spine 的 mesh attachment。其 `uvs` 為 region-local [0,1](Spine JSON 慣例,
已於 knowledge/s3-psd-to-award-mesh.md 驗:as-is IoU 0.95~0.98、v-flip 0.43~0.60 → 確認不需翻 v),
故可直接 uvs×(件 W,H) 疊到件 alpha 上量藝術家覆蓋率當基準。

⚠️ 這些機器人件是 weighted mesh、生產中無 deform timeline(靠骨骼/權重變形,非逐頂點 deform),
   故本閘不套 transfer_deform_check(那需 deform timeline);deform-bearing 件(窗簾/陰影)
   仍走 validate_against_real.py。這裡量的是「靜態覆蓋率 + 基礎拓樸」。

slot 命名慣例:`<prefix>/<PSD圖層名>`(見 knowledge/s4-psd-to-spine-real.md)。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from psd_slice import slice_psd
from evaluate_mesh import evaluate, load_mask
import deform_eval as de


def skin_attachments(skeleton):
    skins = skeleton["skins"]
    if isinstance(skins, list):
        return skins[0]["attachments"]
    return skins.get("attachments", skins)


def artist_iou(uvs, tris, mask):
    """藝術家真實 mesh 對件 alpha 的覆蓋率(uvs region-local [0,1] × 件 W,H)。"""
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return float(np.logical_and(recon, mask).sum() / np.logical_or(recon, mask).sum())


def validate(psd_path, skeleton_path, prefix, out_dir,
             gen="v1", epsilon=0.003, iou_margin=0.0):
    sk = json.load(open(skeleton_path))
    att = skin_attachments(sk)
    _, _, parts = slice_psd(psd_path, out_dir)

    if gen == "v1":
        from generate_mesh import generate as g
        gen_fn = lambda p: g(p, epsilon_frac=epsilon)[0]
    else:
        from generate_mesh_v2 import generate as g
        gen_fn = lambda p: g(p, mode="auto")

    results = []
    for entry, _im in parts:
        layer = entry["name"]
        slot = f"{prefix}/{layer}"
        if slot not in att:
            continue
        a = att[slot].get(slot) or next(iter(att[slot].values()))
        if a.get("type") != "mesh":
            continue  # 只驗 mesh 件;region 件走 S4 切圖閘
        png = os.path.join(out_dir, entry["file"])
        mask = load_mask(png)
        uvs = np.array(a["uvs"]).reshape(-1, 2)
        tris = np.array(a["triangles"]).reshape(-1, 3)
        base = artist_iou(uvs, tris, mask)

        mesh = gen_fn(png)
        iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
        nv = len(mesh["uvs"]) // 2
        verts = np.array(mesh["vertices"]).reshape(-1, 2)
        mtris = np.array(mesh["triangles"]).reshape(-1, 3)
        topo = de.check(verts, mtris, None)

        iou_pass = iou >= base - iou_margin
        clean = topo["self_intersections"] == 0 and topo["degenerate"] == 0
        budget = nv <= len(uvs)
        results.append({
            "piece": layer, "slot": slot,
            "gen": {"vertices": nv, "hull": mesh["hull"],
                    "triangles": len(mtris), "mode": mesh.get("_mode", "delaunay-v1")},
            "artist": {"vertices": len(uvs), "hull": int(a["hull"]),
                       "triangles": len(tris)},
            "AC_iou": {"value": round(iou, 4), "artist_baseline": round(base, 4),
                       "pass": iou_pass},
            "AC_topology": {"self_intersections": topo["self_intersections"],
                            "degenerate": topo["degenerate"], "pass": clean},
            "AC_vertex_budget": {"gen": nv, "artist": len(uvs), "pass": budget},
            "piece_pass": iou_pass and clean and budget,
        })
    return {"source": os.path.basename(psd_path), "prefix": prefix,
            "gen": gen, "epsilon": epsilon,
            "pieces": results,
            "overall_pass": bool(results) and all(r["piece_pass"] for r in results)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--prefix", default="機器人拆件",
                    help="slot 前綴(slot = <prefix>/<圖層名>)")
    ap.add_argument("--gen", choices=["v1", "v2"], default="v1")
    ap.add_argument("--epsilon", type=float, default=0.003,
                    help="v1 hull 簡化係數;越小 hull 越貼、IoU 越高(大件用 0.003)")
    ap.add_argument("--out", default="/tmp/psd_mesh_parts")
    a = ap.parse_args()
    rep = validate(a.psd, a.skeleton, a.prefix, a.out, a.gen, a.epsilon)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
