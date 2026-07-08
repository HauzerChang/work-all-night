#!/usr/bin/env python3
"""端到端「PSD→件→S3 mesh」對真實生產 mesh 驗收(Award 機器人拆件)。

背景(見 knowledge/s4-psd-to-spine-real.md):robot_parts.psd 的 5 圖層一對一對應
Award spine 的 slot `機器人拆件/<圖層名>`;其中 光暈/左手/身體 在 Award 中是 **mesh**
(右手/頭是 region)。這 3 個 mesh 在 Award 的 12 支動畫中 **皆無 deform timeline**
(靠骨骼剛體驅動,經本檔 assert_no_deform 確認),故此處驗收為 **靜態**:

  ① 覆蓋率 IoU:生成 mesh 對「PSD 切件 alpha」的覆蓋率,對比藝術家真實 mesh 對
     「Award atlas region alpha」的覆蓋率(兩者皆自相對,orientation/scale 不變)。
  ② 頂點預算:生成 nv 與真實 nv 的比較(evaluate_mesh 預算 <=64)。
  ③ 靜態良構:生成 mesh 的 setup 佈局 0 自交 / 0 退化三角(deform_eval.check)。

⚠️ 因真實標的無 deform,**耐變形(真實位移場轉移)無法對此標的驗收** —— 這是誠實的邊界,
   已在報告中標記;耐變形已在 main_draw 4 mesh 對藝術家真值驗過(見 s3-four-mesh-generalization)。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from evaluate_mesh import evaluate, load_mask
from atlas_crop import extract
from generate_mesh_v2 import generate as gen_v2
import deform_eval as de

# PSD 圖層名 → (Award slot/attachment 名, PSD 切件檔名前綴)
PIECES = {
    "光暈": "機器人拆件/光暈",
    "左手": "機器人拆件/左手",
    "身體": "機器人拆件/身體",
}


def get_attachment(sk, slot, name):
    skins = sk["skins"]
    skin = skins[0] if isinstance(skins, list) else skins
    att = skin.get("attachments", skin)
    return att[slot][name]


def assert_no_deform(sk, slots):
    """確認這些 slot 在所有動畫皆無 deform timeline(此驗收前提)。"""
    hits = []
    for an, data in sk.get("animations", {}).items():
        for skinname, sslots in data.get("deform", {}).items():
            for s in sslots:
                if s in slots:
                    hits.append((an, s))
    return hits


def real_mesh_iou(sk, slot, name, region_mask):
    """真實 mesh 對其 atlas region alpha 的覆蓋率(uvs region-local 0..1)。"""
    a = get_attachment(sk, slot, name)
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = region_mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, region_mask).sum()
    union = np.logical_or(recon, region_mask).sum()
    return float(inter / union) if union else 0.0, len(uvs), len(tris), a["hull"]


def static_wellformed(mesh, canvas=512):
    """以 uv 佈局(縮到 canvas 像素)檢查 setup mesh 幾何:0 自交 / 0 退化。"""
    uvs = np.array(mesh["uvs"]).reshape(-1, 2) * canvas
    tris = np.array(mesh["triangles"]).reshape(-1, 3).tolist()
    signs = [de.signed_area(uvs, t) > 0 for t in tris]
    return de.check(uvs, tris, signs)


def compare_one(psd_piece_png, sk, slot, region_mask, iou_margin, budget):
    # ① 生成 mesh(來源:PSD 切件 alpha)
    piece_mask = load_mask(psd_piece_png)
    mesh = gen_v2(psd_piece_png, mode="auto")
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    gen_nv = len(mesh["uvs"]) // 2
    ev = evaluate(mesh, piece_mask)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]
    wf = static_wellformed(mesh)

    # ② 藝術家真值(來源:Award atlas region alpha)
    base_iou, real_nv, real_tris, real_hull = real_mesh_iou(sk, slot, slot, region_mask)

    iou_pass = gen_iou >= base_iou - iou_margin
    budget_pass = gen_nv <= budget
    wf_pass = wf["self_intersections"] == 0 and wf["degenerate"] == 0
    return {
        "slot": slot,
        "generated": {"vertices": gen_nv, "hull": mesh["hull"],
                      "triangles": len(mesh["triangles"]) // 3, "mode": mesh.get("_mode")},
        "real_award": {"vertices": real_nv, "hull": real_hull, "triangles": real_tris},
        "AC_iou": {"generated": round(gen_iou, 4), "artist_baseline": round(base_iou, 4),
                   "margin": iou_margin, "pass": bool(iou_pass)},
        "AC_vertex_budget": {"generated": gen_nv, "real": real_nv, "budget": budget,
                             "pass": bool(budget_pass)},
        "AC_static_wellformed": {"self_intersections": wf["self_intersections"],
                                 "degenerate": wf["degenerate"], "pass": bool(wf_pass)},
        "overall_pass": bool(iou_pass and budget_pass and wf_pass),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--png2", default="assets/Award2.png")
    ap.add_argument("--parts", default="/tmp/robot_parts", help="psd_slice 輸出目錄")
    ap.add_argument("--iou_margin", type=float, default=0.03)
    ap.add_argument("--budget", type=int, default=64)
    a = ap.parse_args()

    sk = json.load(open(a.award))
    slots = [PIECES[k] for k in PIECES]
    deform_hits = assert_no_deform(sk, slots)

    # PSD 切件檔名前綴(來自 psd_slice 命名 NN_<name>.png)
    files = {f.split("_", 1)[1].rsplit(".", 1)[0]: os.path.join(a.parts, f)
             for f in os.listdir(a.parts) if f.endswith(".png")}

    reports = []
    for psd_name, slot in PIECES.items():
        piece_png = files[psd_name]
        # Award region 可能在第 2 頁;extract 會自行找頁(atlas_crop 多頁支援)
        try:
            sub = extract(a.atlas, a.png, slot, png2=a.png2)
        except TypeError:
            sub = extract(a.atlas, a.png, slot)
        region_crop = os.path.join(a.parts, f"_region_{psd_name}.png")
        cv2.imwrite(region_crop, sub)
        region_mask = load_mask(region_crop)
        reports.append(compare_one(piece_png, sk, slot, region_mask, a.iou_margin, a.budget))

    out = {
        "target": "Award 機器人拆件 (光暈/左手/身體)",
        "deform_gate_applicable": len(deform_hits) == 0 and "N/A: real meshes have no deform"
                                  or f"deform found: {deform_hits}",
        "pieces": reports,
        "overall_pass": all(r["overall_pass"] for r in reports),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["overall_pass"] else 1)


if __name__ == "__main__":
    main()
