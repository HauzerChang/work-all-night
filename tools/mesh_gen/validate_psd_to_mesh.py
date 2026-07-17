#!/usr/bin/env python3
"""端到端「件 → S3 mesh → 對照真實生產 mesh」整合驗收(對 Award 機器人 mesh 件)。

背景(knowledge/s4-psd-to-spine-real.md):Award 的 5 個機器人件中,光暈/身體/左手為 **mesh**,
右手/頭為 region。這 3 個 mesh 件在 Award **無 deform timeline**(靠骨骼/權重變形),
因此 real-deform-field 閘不適用 → 本閘只做**靜態幾何**對照(覆蓋率 + 拓樸/預算),
並誠實標註「權重(BBW)是這類骨骼驅動件缺的 S3 子能力」。

兩個 alpha 來源(同一素材、不同解析度,texture 段已證 alpha-IoU 0.92~0.99):
  - atlas  : atlas region 切件(0.70 縮小打包;**同一 frame 內有藝術家 mesh 真值**,uvs 為 region-local 0..1)。
  - psd    : robot_parts.psd 切件(S4 契約的「件」,原始解析度)。

每件、每來源:
  1. 取 alpha 遮罩。
  2. generate_mesh_v2 產 mesh。
  3. 生成 IoU(vs 遮罩)、藝術家 baseline IoU(uvs×size vs 同遮罩)、格式/預算(evaluate_mesh)。
  4. pass = 生成 IoU ≥ 藝術家 baseline − margin  且  格式/預算全過。

用法:
  python3 tools/mesh_gen/validate_psd_to_mesh.py            # 兩來源全跑
  python3 tools/mesh_gen/validate_psd_to_mesh.py --source atlas
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract, parse_atlas
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_mesh, load_mask

# Award 機器人 mesh 件(slot==name);PSD 圖層名(切件檔前綴 index_名.png)
MESH_PIECES = [
    {"slot": "機器人拆件/光暈", "psd": "00_光暈.png"},
    {"slot": "機器人拆件/身體", "psd": "03_身體.png"},
    {"slot": "機器人拆件/左手", "psd": "04_左手.png"},
]


def artist_iou_on_mask(skel_att, slot, name, mask):
    """藝術家 mesh 在給定遮罩 frame 的覆蓋率(uvs 為 region-local 0..1 → ×size)。"""
    a = skel_att[slot][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    return (inter / union) if union else 0.0, len(uvs), len(tris)


def get_crop_png(source, slot, psd_file, tmp_dir):
    """回傳(寫到 tmp 的 PNG 路徑)。atlas: region 切件;psd: robot_parts 切件。"""
    os.makedirs(tmp_dir, exist_ok=True)
    out = os.path.join(tmp_dir, f"_{source}_{slot.split('/')[-1]}.png")
    if source == "atlas":
        sub = extract("assets/Award.atlas", "assets/Award.png", slot)
        cv2.imwrite(out, sub)
    else:
        src = os.path.join(tmp_dir, "..", "robot_parts", psd_file)
        src = os.path.normpath(src)
        img = cv2.imread(src, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise SystemExit(f"缺 PSD 切件: {src}(先跑 psd_slice.py -o {os.path.dirname(src)})")
        cv2.imwrite(out, img)
    return out


def validate_piece(source, slot, psd_file, skel_att, tmp_dir, margin=0.02, budget=96):
    png = get_crop_png(source, slot, psd_file, tmp_dir)
    mask = load_mask(png)  # evaluate_mesh.load_mask → 0/1
    # budget 為生產級(藝術家這 3 件用 78~98 頂點);target_vertices 驅動 v1 auto-epsilon
    mesh = gen_v2(png, mode="auto", target_vertices=budget)
    ev = eval_mesh(mesh, mask, vertex_budget=budget)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]
    base, art_nv, art_nt = artist_iou_on_mask(skel_att, slot, slot, mask)
    fmt_ok = (ev["criteria"]["AC4_format"]["pass"]
              and ev["criteria"]["AC2b_degenerate"]["pass"]
              and ev["criteria"]["AC2c_orphans"]["pass"]
              and ev["criteria"]["AC3_vertex_budget"]["pass"])
    iou_ok = gen_iou >= base - margin
    return {
        "slot": slot, "source": source,
        "frame": {"w": mask.shape[1], "h": mask.shape[0]},
        "gen": {"mode": mesh.get("_mode"), "vertices": len(mesh["uvs"]) // 2,
                "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3},
        "artist": {"vertices": art_nv, "triangles": art_nt, "weighted_bone_driven": True},
        "AC_coverage": {"gen_iou": round(gen_iou, 4), "artist_baseline": round(base, 4),
                        "margin": margin, "pass": bool(iou_ok)},
        "AC_topology": {"format_ok": bool(fmt_ok),
                        "budget": budget, "gen_vertices": len(mesh["uvs"]) // 2,
                        "centroid_in_mask": ev["criteria"]["AC2a_centroid_in_mask"]["value"]},
        "note_deform": "Award 無 deform timeline(骨骼/權重驅動)→ real-deform 閘不適用;S3 尚缺 BBW 權重。",
        "overall_pass": bool(iou_ok and fmt_ok),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["atlas", "psd", "both"], default="both")
    ap.add_argument("--tmp", default="/tmp/psd2mesh")
    ap.add_argument("--margin", type=float, default=0.02)
    ap.add_argument("--budget", type=int, default=96)
    a = ap.parse_args()

    aw = json.load(open("assets/Award.json"))
    sk = aw["skins"]; sk = sk[0] if isinstance(sk, list) else sk
    skel_att = sk.get("attachments", sk)

    sources = ["atlas", "psd"] if a.source == "both" else [a.source]
    reports = []
    for src in sources:
        for p in MESH_PIECES:
            reports.append(validate_piece(src, p["slot"], p["psd"], skel_att,
                                          a.tmp, a.margin, a.budget))
    overall = all(r["overall_pass"] for r in reports)
    print(json.dumps({"overall_pass": overall, "count": len(reports),
                      "reports": reports}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
