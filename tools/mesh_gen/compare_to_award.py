#!/usr/bin/env python3
"""端到端「PSD件 → S3 mesh → 對照 Award 真實 mesh」整合 AC(真實生產標的驗收）。

流程(純 CPU,對應 STATE.md 最高優先塊):
  robot_parts.psd  --psd_slice-->  各部位緊湊 PNG(alpha)
  三個 mesh 件(光暈/身體/左手)  --generate_mesh_v2-->  生成 mesh
  對照 Award.json 同名 slot 的**真實藝術家 mesh**:
    AC2 生成 mesh 格式/幾何(evaluate_mesh)
    AC3 覆蓋率 IoU >= 藝術家 mesh 在同一 alpha 上的覆蓋率 - margin  ← 真值閘
    AC4 頂點數 <= 藝術家頂點數(不比手做的更複雜)

⚠️ deform 閘 N/A:這 5 件在 Award **無 deform timeline**(weighted / 骨骼驅動,非逐頂點 deform,
   見 knowledge/s4-psd-to-spine-real.md)→ 真實位移場轉移閘不適用,不當失敗論。

藝術家 baseline 說明:Award mesh 的 uvs 為 region-local [0,1](與 main_draw 一致,已由
  validate_against_real 的 artist_iou 驗證可用)。此處把藝術家 uvs 光柵化到「PSD 切件 alpha」
  同一張遮罩上比 IoU → 與生成 mesh 公平同基準。殘差含 atlas +2px padding(~0.3%,可忽略)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_mesh


# Award 真實 mesh 件(PSD 圖層名 → slot/attachment 同名)
MESH_PARTS = ["光暈", "身體", "左手"]


def award_mesh(skeleton, slot_name):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    d = att[slot_name]
    name = next(iter(d))
    return d[name]


def artist_coverage_iou(mesh_att, mask):
    """把藝術家 mesh 的 region-local uvs 光柵化到 mask(同基準)算覆蓋 IoU。"""
    uvs = np.array(mesh_att["uvs"]).reshape(-1, 2)
    tris = np.array(mesh_att["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    return float(np.logical_and(recon, m).sum() / max(int(np.logical_or(recon, m).sum()), 1))


def load_alpha(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img.ndim == 3 and img.shape[2] == 4:
        return (img[:, :, 3] > 8).astype(np.uint8)
    g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return (g > 8).astype(np.uint8)


def run(psd_path, skeleton_path, out_dir, iou_margin=0.01):
    os.makedirs(out_dir, exist_ok=True)
    _, manifest, parts = slice_psd(psd_path, out_dir)
    sk = json.load(open(skeleton_path))
    by_name = {e["name"]: e for e in manifest["parts"]}

    report = {"psd": os.path.basename(psd_path), "skeleton": os.path.basename(skeleton_path),
              "parts": []}
    for part in MESH_PARTS:
        entry = by_name[part]
        png = os.path.join(out_dir, entry["file"])
        slot = f"機器人拆件/{part}"
        art = award_mesh(sk, slot)
        art_nv = len(art["uvs"]) // 2

        mesh = gen_v2(png, mode="auto")
        if isinstance(mesh, tuple):
            mesh = mesh[0]
        gen_nv = len(mesh["uvs"]) // 2

        mask = load_alpha(png)
        ev = eval_mesh(mesh, mask, vertex_budget=max(64, art_nv))
        gen_iou = ev["criteria"]["AC1_iou"]["value"]
        art_iou = round(artist_coverage_iou(art, mask), 4)

        ac2 = ev["criteria"]["AC4_format"]["pass"] and \
            ev["criteria"]["AC2b_degenerate"]["pass"] and \
            ev["criteria"]["AC2c_orphans"]["pass"] and \
            ev["criteria"]["AC2a_centroid_in_mask"]["pass"]
        ac3 = gen_iou >= art_iou - iou_margin
        ac4 = gen_nv <= art_nv

        report["parts"].append({
            "part": part, "slot": slot,
            "gen": {"mode": mesh.get("_mode"), "vertices": gen_nv, "hull": mesh["hull"],
                    "triangles": len(mesh["triangles"]) // 3},
            "artist": {"vertices": art_nv, "hull": art["hull"],
                       "triangles": len(art["triangles"]) // 3, "weighted": True},
            "AC2_mesh_valid": {"pass": bool(ac2),
                               "format": ev["criteria"]["AC4_format"]["pass"],
                               "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                               "orphans": ev["criteria"]["AC2c_orphans"]["value"],
                               "centroid_in_mask": ev["criteria"]["AC2a_centroid_in_mask"]["value"]},
            "AC3_coverage_vs_artist": {"pass": bool(ac3), "gen_iou": gen_iou,
                                       "artist_iou": art_iou, "margin": iou_margin},
            "AC4_vertex_budget": {"pass": bool(ac4), "gen": gen_nv, "artist": art_nv},
            "deform_gate": "N/A (無 deform timeline;weighted/骨骼驅動)",
            "overall_pass": bool(ac2 and ac3 and ac4),
        })
    report["overall_pass"] = all(p["overall_pass"] for p in report["parts"])
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--out", default="/tmp/robot_parts")
    ap.add_argument("--margin", type=float, default=0.01)
    a = ap.parse_args()
    rep = run(a.psd, a.skeleton, a.out, a.margin)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
